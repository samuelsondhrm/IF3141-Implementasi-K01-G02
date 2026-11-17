from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import buat_pesanan_pos


class TestKonfigurasi(TransactionCase):
    def test_v1_stok_dipotong_saat_lunas(self):
        """V-1 / D-04: pesanan draf tidak memotong stok; pesanan lunas memotong bahan resep."""
        es_teh = self.env.ref("unlimited_billiard.m09")
        gula = self.env.ref("unlimited_billiard.b15")
        awal = gula.qty_available
        draf = buat_pesanan_pos(self.env, [(es_teh, 2)], draft=True)
        self.assertFalse(draf.picking_ids)
        self.assertEqual(gula.with_context(prefetch_fields=False).qty_available, awal)
        lunas = buat_pesanan_pos(self.env, [(es_teh, 2)])
        self.assertEqual(lunas.state, "paid")
        self.assertEqual(lunas.picking_ids.state, "done")
        gula.invalidate_recordset(["qty_available"])
        self.assertAlmostEqual(gula.qty_available, awal - 0.04)

    def test_semua_po_butuh_persetujuan(self):
        rina = self.env.ref("unlimited_billiard.user_rina")
        po = self.env["purchase.order"].with_user(rina).create({
            "partner_id": self.env.ref("unlimited_billiard.s01").id,
            "order_line": [Command.create({"product_id": self.env.ref("unlimited_billiard.b15").id,
                                           "product_qty": 1, "price_unit": 1000})],
        })
        po.button_confirm()
        self.assertEqual(po.state, "to approve")

    def test_receipt_wajib_no_faktur(self):
        po = self.env["purchase.order"].create({
            "partner_id": self.env.ref("unlimited_billiard.s01").id,
            "order_line": [Command.create({"product_id": self.env.ref("unlimited_billiard.b15").id,
                                           "product_qty": 2, "price_unit": 1000})],
        })
        po.button_confirm()
        po.button_approve()
        receipt = po.picking_ids
        receipt.move_ids.quantity = 2
        with self.assertRaises(UserError):
            receipt.button_validate()
        receipt.ub_no_faktur = "INV/BJ/2026/001"
        receipt.button_validate()
        self.assertEqual(receipt.state, "done")
