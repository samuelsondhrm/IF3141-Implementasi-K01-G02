from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        # Sesi meja dibuka sebelum pesanan tersimpan di server; kaitkan lewat referensi pesanan POS.
        for order in orders.filtered("pos_reference"):
            self.env["ub.sesi.meja"].search([("pos_reference", "=", order.pos_reference),
                                             ("pos_order_id", "=", False)]).pos_order_id = order
        return orders

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
