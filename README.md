# IF3141-Implementasi-K01-G02

**Sistem Informasi Operasional Terintegrasi berbasis Odoo Community** untuk **Unlimited Billiard & Cafe**.
IF3141 Sistem Informasi · Kelas K01 · Kelompok G02.

> **Draf teknis (Samson).** Bagian bertanda *[Ega]* dilengkapi Ega sesuai Panduan: identitas anggota, deskripsi, screenshot per langkah, kesimpulan dan saran.

## Identitas Kelompok *[Ega]*

| Nama | NIM |
|---|---|
| Samuelson Dharmawan Tanuraharja | 13524001 |
| Nicholas Wise Saragih Sumbayak | 13524037 |
| Michael James Liman | 13524106 |
| *[Ega]* | |
| *[Rasyad]* | |
| *[Syaqina]* | |

## Deskripsi *[Ega]*

Satu modul kustom, `custom_addons/unlimited_billiard`, di atas Odoo 17.0 Community (`point_of_sale`, `pos_restaurant`, `pos_loyalty`, `pos_mrp`, `purchase_stock`, `contacts`, `l10n_id`). Modul ini berisi:

| Fitur | Model / komponen | FR |
|---|---|---|
| Sesi meja: tombol *Mulai Sesi / Selesai Sesi* di POS, biaya per menit, tarif Early Time / member dipilih otomatis dan dipecah per segmen jam | `ub.sesi.meja`, `static/src/sesi_meja_button.*` | FR-08, FR-13 |
| *Stock opname* Kitchen: draf → ajukan → validasi/kembalikan oleh Manajer, % selisih dalam rupiah | `ub.stock.opname`, `ub.stock.opname.line` | FR-04 |
| Serah terima *shift* Kitchen untuk bahan kritis | `ub.serah.terima.shift`, `ub.detail.serah.terima` | FR-05 |
| Keanggotaan 1 bulan (otomatis saat dibayar di POS), *cron* kedaluwarsa, persetujuan data, anonimisasi | `ub.keanggotaan`, ekstensi `res.partner` | FR-12 |
| No. faktur pemasok wajib sebelum *Receipt* divalidasi | ekstensi `stock.picking` | FR-07 |
| Tiket Kitchen disimpan sebagai gambar (printer disimulasikan) | `controllers/kitchen_ticket.py` | FR-02 |
| Konfigurasi: semua PO butuh persetujuan, stok POS dipotong saat pesanan lunas, ubah harga/diskon POS hanya untuk manajer, data demo | `data/`, `views/settings_views.xml` | FR-03, FR-07, FR-13 |

## Cara Menjalankan *[Ega: tambahkan screenshot hasil tiap langkah]*

Prasyarat: Docker Desktop dan Git.

1. Clone repo, lalu buat `.env`:
   ```bash
   git clone https://github.com/samuelsondhrm/IF3141-Implementasi-K01-G02.git
   cd IF3141-Implementasi-K01-G02
   cp .env.example .env        # Windows: copy .env.example .env
   ```
   Ubah `POSTGRES_PASSWORD` di `.env`.
2. Jalankan container:
   ```bash
   docker compose up -d
   ```
3. Pasang modul (sekali, ±2 menit):
   ```bash
   docker compose run --rm web odoo -d odoo_app -i unlimited_billiard --stop-after-init
   docker compose restart web
   ```
4. Buka http://localhost:8069 dan masuk dengan salah satu akun di bawah.

Untuk mengulang dari awal dengan data demo yang bersih: `docker compose down -v`, lalu ulangi langkah 2–3.

## Akun Demo

Semua akun memakai kata sandi **`unlimited123`** (hanya untuk lingkungan demo).

| Aktor | Login | Nama | Akses utama |
|---|---|---|---|
| A-01 Admin (siang) | `rina.admin` | Rina Kartika | POS, pelanggan, *Receipt*, draf PO |
| A-01 Admin (malam) | `dimas.admin` | Dimas Pratama | sama dengan Rina |
| A-02 Kitchen (siang) | `ujang.kitchen` | Ujang Suherman | *stock opname*, serah terima, *Replenishment* |
| A-02 Kitchen (malam) | `fajar.kitchen` | Fajar Nugraha | sama dengan Ujang |
| A-03 Manajer Operasional | `bayu.manajer` | Bayu Santoso | validasi *stock opname*, *Approve Order*, ubah harga POS, anonimkan pelanggan, hak akses |
| A-04 Owner | `hendra.owner` | Hendra Wijaya | laporan POS, Inventory, Purchase |
| Akun nonaktif (uji FR-14) | `lina.admin` | Lina Marlina | tidak bisa login |
| Administrator teknis | `admin` | — | kata sandi `admin`, hanya untuk pemeliharaan |

Pelanggan demo: Andi Saputra (member aktif), Sinta Maharani (member kedaluwarsa), Rizky Ramadhan (bukan member), Pelanggan Umum.

## Perintah Lain

| Keperluan | Perintah |
|---|---|
| Lihat log | `docker compose logs -f web` |
| Berhenti (data tetap) | `docker compose down` |
| Berhenti dan **menghapus data** | `docker compose down -v` |
| Upgrade modul setelah `git pull` | `docker compose run --rm web odoo -d odoo_app -u unlimited_billiard --stop-after-init` lalu `docker compose restart web` |
| Jalankan test modul | `docker compose run --rm web odoo -d odoo_test -i unlimited_billiard --test-enable --test-tags /unlimited_billiard --stop-after-init --without-demo=all` |
| Backup / restore database | `scripts/export_db.sh`, `scripts/import_db.sh` (Windows: `.cmd`) |

Catatan:

- Gunakan `docker compose run --rm web odoo ...`, bukan `exec`, karena hanya `run` yang memakai koneksi database dari `.env`.
- Untuk menjalankan test kedua kalinya pada `odoo_test` yang sama, ganti `-i` dengan `-u`. Di Git Bash Windows, awali dengan `MSYS_NO_PATHCONV=1` agar `/unlimited_billiard` tidak diubah menjadi path Windows.

## Batasan Implementasi

- Berjalan lokal di Docker. Rancangan produksi (VPS, M3 TW-05/AR-02) belum di-*deploy*, jadi QR-03 (POS luring) dan QR-04 (kinerja cetak) belum diuji.
- Printer Kitchen disimulasikan: tiket disimpan sebagai gambar di menu **Point of Sale › Orders › Tiket Kitchen**. Alamat printer diset ke `localhost:8069`; bila `ODOO_PORT` diubah, ubah juga *Proxy IP* Printer Kitchen.
- Odoo Community tidak punya peran baca-saja, jadi Owner memakai hak manajer Inventory/Purchase dan dimitigasi lewat SOP + jejak *chatter*.

## Kesimpulan dan Saran *[Ega]*

## Troubleshooting

- **Port 8069 terpakai**: ubah `ODOO_PORT` di `.env`, lalu `docker compose up -d`.
- **`variable is missing a value`**: `.env` belum dibuat atau belum diisi.
- **Modul tidak muncul**: pastikan langkah 3 dijalankan, atau aktifkan Developer Mode lalu **Apps › Update Apps List**.
- **Skrip `.sh` error `\r`**: pastikan file memakai LF (`.gitattributes` sudah mengaturnya; clone ulang bila perlu).
