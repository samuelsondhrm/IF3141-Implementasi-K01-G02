from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    """D-23 PenerimaanBarang: nomor faktur pemasok wajib sebelum Receipt divalidasi (FR-07, UC-22)."""

    _inherit = "stock.picking"

    ub_no_faktur = fields.Char(string="No. Faktur Pemasok", tracking=True, copy=False)

    def button_validate(self):
        tanpa_faktur = self.filtered(lambda p: p.picking_type_code == "incoming" and not p.ub_no_faktur)
        if tanpa_faktur:
            raise UserError(_("Isi No. Faktur Pemasok sebelum memvalidasi penerimaan: %s",
                              ", ".join(tanpa_faktur.mapped("name"))))
        return super().button_validate()
