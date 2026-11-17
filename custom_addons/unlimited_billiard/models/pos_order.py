from odoo import fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        produk = self.env.ref("unlimited_billiard.keanggotaan")
        for order in self.filtered(lambda o: o.partner_id and produk in o.lines.product_id):
            # shortcut: satu pembelian = satu bulan meski qty > 1; tambah loop qty bila ada paket multi-bulan.
            self.env["ub.keanggotaan"].create({
                "partner_id": order.partner_id.id,
                "tgl_mulai": fields.Date.context_today(order),
                "pos_order_id": order.id,
            })
        return res
