from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestStockOpname(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ujang = cls.env.ref("unlimited_billiard.user_ujang")
        cls.bayu = cls.env.ref("unlimited_billiard.user_bayu")
        cls.ayam = cls.env.ref("unlimited_billiard.b04")
        cls.Opname = cls.env["ub.stock.opname"]

    def _ajukan(self, kurang=1.0):
        rec = self.Opname.with_user(self.ujang).create({})
        line = rec.line_ids.filtered(lambda l: l.bahan_id == self.ayam)
        line.jumlah_fisik = line.stok_sistem - kurang
        rec.action_ajukan()
        return rec, line

    def test_hitung_persen_selisih(self):
        rec, line = self._ajukan()
        self.assertTrue(rec.line_ids)
        self.assertEqual(line.selisih_rupiah, -self.ayam.standard_price)
        nilai_sistem = sum(l.stok_sistem * l.harga_pokok for l in rec.line_ids)
        self.assertAlmostEqual(rec.persen_selisih, self.ayam.standard_price / nilai_sistem * 100, places=2)
        self.assertEqual(rec.status, "menunggu_validasi")

    def test_kitchen_tidak_bisa_validasi(self):
        rec, _line = self._ajukan()
        with self.assertRaises(UserError):
            rec.with_user(self.ujang).action_validasi()
        with self.assertRaises(UserError):
            rec.with_user(self.ujang).action_kembalikan()

    def test_kembalikan_wajib_catatan(self):
        rec, _line = self._ajukan()
        rec = rec.with_user(self.bayu)
        with self.assertRaises(UserError):
            rec.action_kembalikan()
        rec.catatan_pengembalian = "Hitung ulang ayam fillet"
        rec.action_kembalikan()
        self.assertEqual(rec.status, "dikembalikan")
        rec.with_user(self.ujang).action_ke_draf()
        self.assertEqual(rec.status, "draf")

    def test_validasi_mengubah_stok(self):
        awal = self.ayam.qty_available
        rec, _line = self._ajukan(kurang=0.5)
        rec.with_user(self.bayu).action_validasi()
        self.assertEqual(rec.status, "tervalidasi")
        self.assertEqual(rec.validator_id, self.bayu)
        self.ayam.invalidate_recordset(["qty_available"])
        self.assertAlmostEqual(self.ayam.qty_available, awal - 0.5)
        move = self.env["stock.move"].search([("product_id", "=", self.ayam.id), ("is_inventory", "=", True)],
                                             order="id desc", limit=1)
        self.assertIn("Stock Opname", move.reference)
