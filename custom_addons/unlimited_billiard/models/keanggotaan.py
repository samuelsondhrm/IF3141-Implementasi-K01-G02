from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

# Nilai status mengikuti STD Keanggotaan M4 (Gambar 1.1.a).
STATUS = [("aktif", "Aktif"), ("kedaluwarsa", "Kedaluwarsa")]


class Keanggotaan(models.Model):
    """D-14 Keanggotaan (FR-12): masa member 1 bulan sejak pembayaran Rp375.000."""

    _name = "ub.keanggotaan"
    _description = "Keanggotaan Pelanggan"
    _inherit = ["mail.thread"]
    _order = "tgl_mulai desc, id desc"

    partner_id = fields.Many2one("res.partner", string="Pelanggan", required=True, ondelete="restrict",
                                 tracking=True, domain=[("is_company", "=", False)])
    tgl_mulai = fields.Date(string="Tanggal Mulai", required=True, default=fields.Date.context_today, tracking=True)
    tgl_berakhir = fields.Date(string="Tanggal Berakhir", compute="_compute_tgl_berakhir", store=True)
    status = fields.Selection(STATUS, default="aktif", required=True, readonly=True, tracking=True)
    pos_order_id = fields.Many2one("pos.order", string="Bukti Bayar", readonly=True, ondelete="set null")

    @api.depends("tgl_mulai")
    def _compute_tgl_berakhir(self):
        for rec in self:
            rec.tgl_berakhir = rec.tgl_mulai and rec.tgl_mulai + relativedelta(months=1)

    @api.depends("partner_id", "tgl_mulai", "tgl_berakhir")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _("%(nama)s (%(mulai)s – %(akhir)s)", nama=rec.partner_id.name or "",
                                 mulai=rec.tgl_mulai or "", akhir=rec.tgl_berakhir or "")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._tandai_kedaluwarsa()  # data lama yang masa berlakunya sudah lewat langsung kedaluwarsa
        return records

    def _tandai_kedaluwarsa(self):
        lewat = self.filtered(lambda r: r.status == "aktif" and r.tgl_berakhir < fields.Date.context_today(r))
        lewat.status = "kedaluwarsa"

    @api.model
    def _cron_kedaluwarsa(self):
        """Cron harian: aktif → kedaluwarsa setelah tanggal berakhir lewat."""
        self.search([("status", "=", "aktif"), ("tgl_berakhir", "<", fields.Date.context_today(self))])._tandai_kedaluwarsa()
