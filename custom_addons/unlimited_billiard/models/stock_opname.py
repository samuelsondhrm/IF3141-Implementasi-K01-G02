from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Nilai status mengikuti STD StockOpname M4 (Gambar 1.1.b).
STATUS = [
    ("draf", "Draf"),
    ("menunggu_validasi", "Menunggu Validasi"),
    ("tervalidasi", "Tervalidasi"),
    ("dikembalikan", "Dikembalikan"),
]


class StockOpname(models.Model):
    """D-17 StockOpname (FR-04): hitung fisik Kitchen, selisih dalam rupiah, validasi Manajer."""

    _name = "ub.stock.opname"
    _description = "Stock Opname Kitchen"
    _inherit = ["mail.thread"]
    _order = "tanggal desc, id desc"

    tanggal = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    petugas_id = fields.Many2one("res.users", string="Petugas", required=True, default=lambda self: self.env.user,
                                 readonly=True)
    validator_id = fields.Many2one("res.users", string="Validator", readonly=True, tracking=True)
    status = fields.Selection(STATUS, default="draf", required=True, readonly=True, tracking=True)
    catatan_pengembalian = fields.Text(string="Catatan Pengembalian", tracking=True)
    line_ids = fields.One2many("ub.stock.opname.line", "opname_id", string="Bahan")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id, readonly=True)
    nilai_sistem = fields.Monetary(string="Nilai Stok Sistem", compute="_compute_selisih", store=True)
    nilai_selisih_absolut = fields.Monetary(string="Nilai Selisih Absolut", compute="_compute_selisih", store=True)
    persen_selisih = fields.Float(string="% Selisih", compute="_compute_selisih", store=True, digits=(16, 2),
                                 group_operator="avg")

    @api.depends("line_ids.selisih_rupiah", "line_ids.stok_sistem", "line_ids.harga_pokok")
    def _compute_selisih(self):
        # QR-05: % selisih = Σ|selisih rupiah| ÷ Σ(stok sistem × harga pokok) × 100%
        for rec in self:
            rec.nilai_sistem = sum(line.stok_sistem * line.harga_pokok for line in rec.line_ids)
            rec.nilai_selisih_absolut = sum(abs(line.selisih_rupiah) for line in rec.line_ids)
            rec.persen_selisih = rec.nilai_sistem and rec.nilai_selisih_absolut / rec.nilai_sistem * 100

    @api.depends("tanggal")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _("Stock Opname %s", rec.tanggal.strftime("%d/%m/%Y") if rec.tanggal else "")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered(lambda r: not r.line_ids).action_segarkan()
        return records

    def _lokasi_kitchen(self):
        return self.env.ref("stock.stock_location_stock")

    def _cek_status(self, *status):
        for rec in self:
            if rec.status not in status:
                raise UserError(_("Aksi ini tidak tersedia untuk stock opname berstatus %s.",
                                  dict(STATUS)[rec.status]))

    def _cek_manajer(self):
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise UserError(_("Hanya Manajer Operasional yang boleh memvalidasi atau mengembalikan stock opname."))

    def action_segarkan(self):
        """Muat semua bahan storable beserta stok sistem dan harga pokok saat ini (aturan 1)."""
        self._cek_status("draf")
        lokasi = self._lokasi_kitchen()
        bahan = self.env["product.product"].search([("type", "=", "product")], order="name")
        for rec in self:
            existing = {line.bahan_id: line for line in rec.line_ids}
            for product in bahan:
                stok = product.with_context(location=lokasi.id).qty_available
                if product in existing:
                    existing[product].write({"stok_sistem": stok, "harga_pokok": product.standard_price})
                else:
                    # Jumlah fisik diisi awal = stok sistem; petugas cukup mengubah yang berbeda.
                    rec.line_ids = [fields.Command.create({
                        "bahan_id": product.id, "stok_sistem": stok, "jumlah_fisik": stok,
                        "harga_pokok": product.standard_price,
                    })]

    def action_ajukan(self):
        self._cek_status("draf")
        self.status = "menunggu_validasi"

    def action_kembalikan(self):
        self._cek_manajer()
        self._cek_status("menunggu_validasi")
        if any(not rec.catatan_pengembalian for rec in self):
            raise UserError(_("Isi Catatan Pengembalian sebelum mengembalikan stock opname."))
        self.write({"status": "dikembalikan", "validator_id": self.env.user.id})

    def action_ke_draf(self):
        self._cek_status("dikembalikan")
        self.status = "draf"

    def action_validasi(self):
        """Tulis jumlah fisik ke stock.quant lalu terapkan sebagai stock move (aturan 4)."""
        self._cek_manajer()
        self._cek_status("menunggu_validasi")
        lokasi = self._lokasi_kitchen()
        Quant = self.env["stock.quant"].with_context(inventory_mode=True)
        for rec in self:
            quants = Quant.browse()
            for line in rec.line_ids.filtered("is_berbeda"):
                quants |= Quant.create({"product_id": line.bahan_id.id, "location_id": lokasi.id,
                                        "inventory_quantity": line.jumlah_fisik})
            quants.with_context(inventory_name=rec.display_name).action_apply_inventory()
            rec.write({"status": "tervalidasi", "validator_id": self.env.user.id})


class StockOpnameLine(models.Model):
    """D-18 DetailStockOpname."""

    _name = "ub.stock.opname.line"
    _description = "Detail Stock Opname"
    _order = "bahan_id"

    opname_id = fields.Many2one("ub.stock.opname", required=True, ondelete="cascade")
    bahan_id = fields.Many2one("product.product", string="Bahan", required=True)
    uom_id = fields.Many2one(related="bahan_id.uom_id")
    stok_sistem = fields.Float(digits="Product Unit of Measure", readonly=True)
    jumlah_fisik = fields.Float(digits="Product Unit of Measure")
    selisih_satuan = fields.Float(digits="Product Unit of Measure", compute="_compute_selisih", store=True)
    currency_id = fields.Many2one(related="opname_id.currency_id")
    harga_pokok = fields.Monetary(readonly=True)
    selisih_rupiah = fields.Monetary(compute="_compute_selisih", store=True)
    is_berbeda = fields.Boolean(string="Berbeda", compute="_compute_selisih", store=True)

    _sql_constraints = [
        ("bahan_unik", "unique(opname_id, bahan_id)", "Bahan sudah ada di stock opname ini."),
    ]

    @api.depends("jumlah_fisik", "stok_sistem", "harga_pokok", "bahan_id.uom_id.rounding")
    def _compute_selisih(self):
        for line in self:
            rounding = line.bahan_id.uom_id.rounding or 0.01
            line.selisih_satuan = line.jumlah_fisik - line.stok_sistem
            line.selisih_rupiah = line.selisih_satuan * line.harga_pokok
            line.is_berbeda = not fields.Float.is_zero(line.selisih_satuan, precision_rounding=rounding)
