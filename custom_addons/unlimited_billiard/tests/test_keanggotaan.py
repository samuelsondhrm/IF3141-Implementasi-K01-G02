from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

from .common import buat_pesanan_pos


class TestKeanggotaan(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.andi = cls.env.ref("unlimited_billiard.pelanggan_andi")
        cls.sinta = cls.env.ref("unlimited_billiard.pelanggan_sinta")
        cls.rizky = cls.env.ref("unlimited_billiard.pelanggan_rizky")
        cls.rina = cls.env.ref("unlimited_billiard.user_rina")

    def test_status_data_demo(self):
        self.assertEqual(self.andi.ub_status_member, "aktif")
        self.assertEqual(self.sinta.ub_status_member, "kedaluwarsa")
        self.assertEqual(self.rizky.ub_status_member, "bukan_member")

    def test_kedaluwarsa_otomatis(self):
        k = self.env["ub.keanggotaan"].create({"partner_id": self.rizky.id})
        self.assertEqual(k.tgl_berakhir, k.tgl_mulai + relativedelta(months=1))
        self.assertEqual(self.rizky.ub_status_member, "aktif")
        k.tgl_mulai = fields.Date.today() - timedelta(days=40)
        self.env["ub.keanggotaan"]._cron_kedaluwarsa()
        self.assertEqual(k.status, "kedaluwarsa")
        self.assertEqual(self.rizky.ub_status_member, "kedaluwarsa")

    def test_pelanggan_baru_wajib_persetujuan(self):
        Partner = self.env["res.partner"].with_user(self.rina).with_context(ub_pelanggan=True)
        with self.assertRaises(ValidationError):
            Partner.create({"name": "Budi Tanpa Persetujuan"})
        budi = Partner.create({"name": "Budi Setuju", "ub_persetujuan_data": True})
        self.assertTrue(budi.ub_tgl_persetujuan)
        # Pemasok / kontak lain di luar menu Pelanggan tidak terkena aturan ini.
        self.env["res.partner"].create({"name": "CV Pemasok Baru", "is_company": True})

    def test_beli_keanggotaan_di_pos(self):
        produk = self.env.ref("unlimited_billiard.keanggotaan")
        order = buat_pesanan_pos(self.env, [(produk, 1)], partner=self.rizky)
        k = self.rizky.ub_keanggotaan_ids
        self.assertEqual(len(k), 1)
        self.assertEqual(k.pos_order_id, order)
        self.assertEqual(self.rizky.ub_status_member, "aktif")

    def test_anonimkan_mempertahankan_pesanan(self):
        order = buat_pesanan_pos(self.env, [(self.env.ref("unlimited_billiard.m09"), 1)], partner=self.andi)
        with self.assertRaises(UserError):
            self.andi.with_user(self.rina).action_anonimkan()
        self.andi.with_user(self.env.ref("unlimited_billiard.user_bayu")).action_anonimkan()
        self.assertTrue(self.andi.ub_is_anonim)
        self.assertFalse(self.andi.phone)
        self.assertNotIn("Andi", self.andi.name)
        self.assertEqual(order.partner_id, self.andi)
        self.assertTrue(order.exists())
