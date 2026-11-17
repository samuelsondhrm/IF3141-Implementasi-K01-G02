from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


def wib(jam, menit=0):
    """Waktu WIB 17 Nov 2026 sebagai datetime UTC naif (WIB = UTC+7)."""
    return datetime(2026, 11, 17, jam, menit) - timedelta(hours=7)


class TestSesiMeja(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Sesi = cls.env["ub.sesi.meja"]
        cls.meja = cls.env.ref("unlimited_billiard.meja_03")
        cls.andi = cls.env.ref("unlimited_billiard.pelanggan_andi")  # member aktif
        cls.rizky = cls.env.ref("unlimited_billiard.pelanggan_rizky")  # bukan member

    def _sesi(self, mulai, selesai, partner=None, **vals):
        rec = self.Sesi.create({"meja_id": self.meja.id, "jam_mulai": mulai,
                                "partner_id": (partner or self.rizky).id, **vals})
        rec.write({"jam_selesai": selesai, "status": "selesai"})
        return rec

    def test_tolak_meja_terpakai(self):
        self.Sesi.create({"meja_id": self.meja.id})
        with self.assertRaises(ValidationError):
            self.Sesi.create({"meja_id": self.meja.id})

    def test_open_table_95_menit(self):
        rec = self._sesi(wib(15), wib(16, 35))
        self.assertEqual(rec.durasi_menit, 95)
        self.assertEqual(rec.pricelist_id, self.env.ref("unlimited_billiard.pricelist_reguler"))
        self.assertEqual(rec.biaya_sewa, round(95 * 37000 / 60))

    def test_durasi_tetap_lewat_10_menit(self):
        rec = self._sesi(wib(15), wib(17, 10), jenis_tarif="durasi_tetap", durasi_dipesan=2)
        self.assertEqual(rec.biaya_sewa, round(130 * 37000 / 60))
        pulang_cepat = self._sesi(wib(20), wib(21), jenis_tarif="durasi_tetap", durasi_dipesan=2)
        self.assertEqual(pulang_cepat.biaya_sewa, 74000)

    def test_early_time(self):
        rec = self._sesi(wib(11), wib(12))
        self.assertEqual(rec.pricelist_id, self.env.ref("unlimited_billiard.pricelist_early_time"))
        self.assertEqual(rec.biaya_sewa, 22000)

    def test_lintas_batas_dipecah_per_segmen(self):
        # 13.00–14.30 Early Time (90 menit) + 14.30–15.00 Reguler (30 menit)
        rec = self._sesi(wib(13), wib(15))
        self.assertEqual(rec.biaya_sewa, 33000 + 18500)

    def test_member_sebelum_dan_sesudah_19(self):
        self.assertEqual(self._sesi(wib(17), wib(18), self.andi).biaya_sewa, 0)
        # 18.00–19.00 gratis + 19.00–20.00 Member Malam (Reguler − 20%)
        rec = self._sesi(wib(18), wib(20), self.andi)
        self.assertTrue(rec.is_member)
        self.assertEqual(rec.biaya_sewa, 29600)

    def test_cron_melewati_batas(self):
        rec = self.Sesi.create({"meja_id": self.meja.id, "jenis_tarif": "durasi_tetap", "durasi_dipesan": 1,
                                "jam_mulai": fields.Datetime.now() - timedelta(hours=2)})
        self.Sesi._cron_melewati_batas()
        self.assertEqual(rec.status, "melewati_batas")
        rec.action_selesai()
        self.assertEqual(rec.status, "selesai")
        self.assertEqual(rec.ditutup_oleh, self.env.user)
