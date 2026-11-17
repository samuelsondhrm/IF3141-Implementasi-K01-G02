from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Nilai status mengikuti STD SesiMeja M4 (Gambar 1.1.g).
STATUS = [("berjalan", "Berjalan"), ("melewati_batas", "Melewati Batas"), ("selesai", "Selesai")]
JENIS_TARIF = [("open_table", "Open Table"), ("durasi_tetap", "Durasi Tetap")]

TZ = pytz.timezone("Asia/Jakarta")
# Batas jam tarif (IW-12, FR-13): Early Time 10.30–14.30 untuk non-member; member gratis sampai 19.00.
EARLY_MULAI, EARLY_SELESAI, MEMBER_MALAM = time(10, 30), time(14, 30), time(19, 0)
BATAS_TARIF = (time(0, 0), EARLY_MULAI, EARLY_SELESAI, MEMBER_MALAM)


class SesiMeja(models.Model):
    """D-09 SesiMeja (FR-08, FR-13). Biaya dipecah per segmen jam tarif (keputusan D-02)."""

    _name = "ub.sesi.meja"
    _description = "Sesi Meja Biliar"
    _inherit = ["mail.thread"]
    _order = "jam_mulai desc, id desc"

    meja_id = fields.Many2one("restaurant.table", string="Meja", required=True, tracking=True,
                              domain=[("name", "!=", "Kasir")])
    pos_order_id = fields.Many2one("pos.order", string="Pesanan", readonly=True, ondelete="set null")
    pos_reference = fields.Char(string="Referensi Pesanan POS", readonly=True, copy=False)
    partner_id = fields.Many2one("res.partner", string="Pelanggan", tracking=True)
    is_member = fields.Boolean(string="Tarif Member", compute="_compute_is_member", store=True, readonly=True)
    jam_mulai = fields.Datetime(string="Jam Mulai", required=True, default=fields.Datetime.now, readonly=True)
    jam_selesai = fields.Datetime(string="Jam Selesai", readonly=True)
    jenis_tarif = fields.Selection(JENIS_TARIF, string="Jenis Tarif", required=True, default="open_table")
    durasi_dipesan = fields.Float(string="Durasi Dipesan (jam)")
    jam_batas = fields.Datetime(string="Batas Waktu", compute="_compute_jam_batas", store=True)
    durasi_menit = fields.Integer(string="Durasi (menit)", compute="_compute_biaya")
    pricelist_id = fields.Many2one("product.pricelist", string="Tarif Saat Mulai", compute="_compute_biaya")
    biaya_sewa = fields.Monetary(string="Biaya Sewa", compute="_compute_biaya")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id, readonly=True)
    status = fields.Selection(STATUS, default="berjalan", required=True, readonly=True, tracking=True)
    dibuka_oleh = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    ditutup_oleh = fields.Many2one("res.users", readonly=True)

    @api.depends("partner_id")
    def _compute_is_member(self):
        # Status member dibekukan saat pelanggan dikaitkan, supaya kedaluwarsa di tengah sesi tidak mengubah tarif.
        for rec in self:
            rec.is_member = rec.partner_id.ub_status_member == "aktif"

    @api.depends("jam_mulai", "jenis_tarif", "durasi_dipesan")
    def _compute_jam_batas(self):
        for rec in self:
            tetap = rec.jenis_tarif == "durasi_tetap" and rec.jam_mulai
            rec.jam_batas = tetap and rec.jam_mulai + timedelta(hours=rec.durasi_dipesan)

    @api.depends("jam_mulai", "jam_selesai", "jenis_tarif", "durasi_dipesan", "is_member")
    def _compute_biaya(self):
        sewa = self.env.ref("unlimited_billiard.sewa_meja")
        for rec in self:
            mulai = _menit(rec.jam_mulai)
            selesai = _menit(rec.jam_selesai or fields.Datetime.now())
            rec.durasi_menit = max(0, int((selesai - mulai).total_seconds() // 60))
            rec.pricelist_id = rec._pricelist_pada(mulai)
            menit_ditagih = rec.durasi_menit
            if rec.jenis_tarif == "durasi_tetap":
                menit_ditagih = max(menit_ditagih, round(rec.durasi_dipesan * 60))
            rec.biaya_sewa = rec._hitung_biaya(mulai, mulai + timedelta(minutes=menit_ditagih), sewa)

    def _pricelist_pada(self, waktu_utc):
        jam = pytz.utc.localize(waktu_utc).astimezone(TZ).time()
        if self.is_member:
            return self.env.ref("unlimited_billiard.pricelist_member_malam" if jam >= MEMBER_MALAM
                                else "unlimited_billiard.pricelist_member")
        if EARLY_MULAI <= jam < EARLY_SELESAI:
            return self.env.ref("unlimited_billiard.pricelist_early_time")
        return self.env.ref("unlimited_billiard.pricelist_reguler")

    def _hitung_biaya(self, mulai, selesai, sewa):
        """Σ menit tiap segmen × tarif per jam segmen ÷ 60 (D-02: tarif dipecah per segmen jam)."""
        total, t = 0.0, mulai
        while t < selesai:
            batas = min(selesai, _batas_berikut(t))
            tarif = self._pricelist_pada(t)._get_product_price(sewa, 1.0)
            total += (batas - t).total_seconds() / 60 * tarif / 60
            t = batas
        return round(total)

    @api.depends("meja_id", "jam_mulai")
    def _compute_display_name(self):
        for rec in self:
            mulai = fields.Datetime.context_timestamp(rec, rec.jam_mulai).strftime("%d/%m %H:%M") if rec.jam_mulai else ""
            rec.display_name = "%s · %s" % (rec.meja_id.name or "", mulai)

    @api.constrains("meja_id", "status")
    def _check_meja_kosong(self):
        for rec in self.filtered(lambda r: r.status != "selesai"):
            if self.search_count([("meja_id", "=", rec.meja_id.id), ("status", "!=", "selesai"), ("id", "!=", rec.id)]):
                raise ValidationError(_("%s masih memiliki sesi yang berjalan.", rec.meja_id.name))

    @api.constrains("jenis_tarif", "durasi_dipesan")
    def _check_durasi(self):
        if any(rec.jenis_tarif == "durasi_tetap" and rec.durasi_dipesan <= 0 for rec in self):
            raise ValidationError(_("Isi durasi yang dipesan untuk tarif durasi tetap."))

    def action_selesai(self):
        """Tutup sesi; biaya akhir dibekukan oleh jam_selesai."""
        for rec in self:
            if rec.status == "selesai":
                raise UserError(_("Sesi %s sudah selesai.", rec.display_name))
        self.write({"jam_selesai": fields.Datetime.now(), "ditutup_oleh": self.env.user.id, "status": "selesai"})
        return True

    # --- RPC dari tombol Sesi Meja di layar POS (static/src/sesi_meja_button.js) ---

    @api.model
    def _pos_cari(self, pos_reference, meja_id):
        # Cari lewat referensi pesanan dulu, supaya sesi tetap ditemukan setelah pesanan di-Transfer ke meja lain.
        domain = [("status", "!=", "selesai")]
        return (self.search(domain + [("pos_reference", "=", pos_reference)], limit=1)
                or self.search(domain + [("meja_id", "=", meja_id)], limit=1))

    def _pos_data(self):
        self.ensure_one()
        return {
            "id": self.id, "status": self.status, "jenis_tarif": self.jenis_tarif,
            "jam_mulai": fields.Datetime.to_string(self.jam_mulai), "durasi_menit": self.durasi_menit,
            "biaya_sewa": self.biaya_sewa, "tarif": self.pricelist_id.name, "is_member": self.is_member,
        }

    @api.model
    def pos_status(self, pos_reference, meja_id):
        sesi = self._pos_cari(pos_reference, meja_id)
        return sesi._pos_data() if sesi else False

    @api.model
    def pos_mulai(self, meja_id, pos_reference, partner_id=False, jenis_tarif="open_table", durasi_dipesan=0):
        sesi = self.create({
            "meja_id": meja_id, "pos_reference": pos_reference, "partner_id": partner_id,
            "jenis_tarif": jenis_tarif, "durasi_dipesan": durasi_dipesan,
            "pos_order_id": self.env["pos.order"].search([("pos_reference", "=", pos_reference)], limit=1).id,
        })
        return sesi._pos_data()

    def pos_selesai(self, meja_id, pos_reference, partner_id=False):
        """Tutup sesi dan kembalikan baris Sewa Meja yang ditambahkan POS ke pesanan (aturan 5)."""
        self.ensure_one()
        vals = {"meja_id": meja_id, "pos_reference": pos_reference}
        if partner_id and not self.partner_id:
            vals["partner_id"] = partner_id
        self.write(vals)
        self.action_selesai()
        mulai = fields.Datetime.context_timestamp(self, self.jam_mulai).strftime("%H:%M")
        selesai = fields.Datetime.context_timestamp(self, self.jam_selesai).strftime("%H:%M")
        return dict(self._pos_data(), product_id=self.env.ref("unlimited_billiard.sewa_meja").id,
                    keterangan=_("%(meja)s · %(mulai)s–%(selesai)s (%(menit)s menit, %(tarif)s)", meja=self.meja_id.name,
                                 mulai=mulai, selesai=selesai, menit=self.durasi_menit, tarif=self.pricelist_id.name))

    @api.model
    def _cron_melewati_batas(self):
        self.search([("status", "=", "berjalan"), ("jenis_tarif", "=", "durasi_tetap"),
                     ("jam_batas", "<", fields.Datetime.now())]).status = "melewati_batas"


def _menit(dt):
    return dt.replace(second=0, microsecond=0)


def _batas_berikut(waktu_utc):
    """Batas tarif lokal berikutnya (00.00, 10.30, 14.30, 19.00) setelah waktu_utc, dalam UTC naif."""
    lokal = pytz.utc.localize(waktu_utc).astimezone(TZ)
    for hari in (0, 1):
        tanggal = lokal.date() + timedelta(days=hari)
        for jam in BATAS_TARIF:
            kandidat = TZ.localize(datetime.combine(tanggal, jam))
            if kandidat > lokal:
                return kandidat.astimezone(pytz.utc).replace(tzinfo=None)
    raise AssertionError("unreachable")
