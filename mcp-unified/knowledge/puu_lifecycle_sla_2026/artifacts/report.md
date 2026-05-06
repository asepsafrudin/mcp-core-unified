# Report: PUU Correspondence Lifecycle, Timeline & SLA Implementation

Dokumen ini mencatat transformasi sistem korespondensi PUU (Substansi Perundang-undangan) dari sistem pelaporan statis menjadi sistem manajemen siklus hidup yang cerdas dan terukur.

## 1. Database-Driven Status (Refined Mapping)
Sistem telah beralih dari status *hardcoded* menjadi status dinamis yang dipetakan dari kolom `POSISI` di database.
- **Mapping Logic**:
    - `TTD` $\rightarrow$ **Selesai / Siap Dikirim**
    - `DONE` / `SELESAI` / `DJ` $\rightarrow$ **Arsip Final**
    - `PARAFA` / `KOREKSI` / `REVISI` $\rightarrow$ **Proses Koreksi / Paraf**
    - `PUU` $\rightarrow$ **Proses di Substansi PUU**
- **Implementasi**: Fungsi `determine_refined_status` di `mcp-unified/integrations/korespondensi/utils.py`.

## 2. Pelacakan Posisi (Timeline) Terpadu
Fitur "Lacak Posisi" yang sebelumnya hanya ada di Surat Masuk kini tersedia penuh di **Proses PUU** (Vault).
- **Infrastruktur**: Tabel `vault_events` dan kolom `posisi` pada `surat_keluar_puu`.
- **Automasi**: ETL script secara otomatis mencatat setiap perubahan posisi sebagai event historis.
- **Visualisasi**: Modal timeline interaktif dengan interpretasi unit kerja (unit meaning).

## 3. Indikator SLA & Durasi Proses
Sistem pemantauan beban kerja kini memiliki indikator waktu yang cerdas.
- **Perhitungan**: Selisih hari antara `tanggal_surat` dan hari ini.
- **SLA Freeze**: Jika status mencapai `TTD` atau `Arsip Final`, perhitungan durasi dihentikan dan badge berubah menjadi **✅ Selesai**.
- **Color Coding**:
    - **Hijau (0-3 Hari)**: Cepat
    - **Kuning (4-7 Hari)**: Normal
    - **Merah (>7 Hari)**: Perlu Atensi

## 4. Sistem Catatan & Tagging Internal
Kemampuan anotasi manual untuk kolaborasi tim.
- **Fitur**: Modal input komentar pada setiap baris dokumen.
- **Visibilitas**: Catatan muncul dengan ikon 📌 langsung di bawah perihal surat untuk peringatan atau instruksi cepat.
- **Penyimpanan**: Kolom `catatan` dan `tags` (JSONB) pada tabel utama.

## 5. Pembaruan Terminologi (UX)
Mengubah istilah **"Vault Substansi PUU"** menjadi **"Proses PUU"** di seluruh antarmuka (Sidebar, Header, Titles) untuk mencerminkan alur kerja yang aktif.

## Lampiran Teknis
- **Web App**: `src/web_app.py` diperbarui dengan API tagging dan perhitungan SLA.
- **Sync Service**: `src/services/sync_service.py` diperbarui dengan `get_vault_timeline`.
- **ETL**: `scripts/etl_korespondensi_db_centric.py` diperbarui untuk tracking posisi vault.
- **Database**:
    - Kolom baru di `surat_keluar_puu`: `status_pengiriman`, `posisi`, `catatan`, `tags`.
    - Tabel baru: `vault_events`.

---
*Status LTM: Diperbarui pada 17 April 2026*
