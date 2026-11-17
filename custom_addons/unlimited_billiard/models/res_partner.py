from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

STATUS_MEMBER = [("bukan_member", "Bukan Member"), ("aktif", "Aktif"), ("kedaluwarsa", "Kedaluwarsa")]


class ResPartner(models.Model):
    """D-13 Pelanggan (FR-12): persetujuan data, anonimisasi, dan status member."""

    _inherit = "res.partner"

    ub_persetujuan_data = fields.Boolean(string="Persetujuan Data Pribadi", tracking=True)
    ub_tgl_persetujuan = fields.Datetime(string="Tanggal Persetujuan", readonly=True)
    ub_persetujuan_promosi = fields.Boolean(string="Bersedia Menerima Promosi", tracking=True)
    ub_is_anonim = fields.Boolean(string="Dianonimkan", readonly=True)
    ub_keanggotaan_ids = fields.One2many("ub.keanggotaan", "partner_id", string="Riwayat Keanggotaan")
    ub_status_member = fields.Selection(STATUS_MEMBER, string="Status Member", compute="_compute_ub_status_member",
                                        store=True)

    @api.depends("ub_keanggotaan_ids.status", "ub_keanggotaan_ids.tgl_mulai")
    def _compute_ub_status_member(self):
        for partner in self:
            terakhir = partner.ub_keanggotaan_ids.sorted(lambda k: (k.tgl_mulai, k.id))[-1:]
            partner.ub_status_member = terakhir.status or "bukan_member"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Pelanggan baru dari menu Pelanggan / POS (UC-13) wajib menyetujui pemrosesan data.
            if self.env.context.get("ub_pelanggan") and not vals.get("ub_persetujuan_data"):
                raise ValidationError(_("Pelanggan harus menyetujui pemrosesan data pribadi sebelum disimpan."))
            if vals.get("ub_persetujuan_data"):
                vals.setdefault("ub_tgl_persetujuan", fields.Datetime.now())
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("ub_persetujuan_data"):
            vals.setdefault("ub_tgl_persetujuan", fields.Datetime.now())
        return super().write(vals)

    def action_anonimkan(self):
        """FR-12 op. (8): hapus data identitas tanpa menghapus riwayat transaksi."""
        if not self.env.user.has_group("point_of_sale.group_pos_manager"):
            raise UserError(_("Hanya Manajer Operasional yang boleh menganonimkan pelanggan."))
        for partner in self:
            partner.write({
                "name": _("Pelanggan Anonim #%s", partner.id),
                "phone": False, "mobile": False, "email": False, "street": False, "street2": False,
                "city": False, "comment": False, "image_1920": False, "vat": False,
                "ub_persetujuan_promosi": False, "ub_is_anonim": True,
            })
            partner.message_post(body=_("Data pribadi pelanggan dianonimkan."))
