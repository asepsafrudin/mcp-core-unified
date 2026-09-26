"""
Srikandi SPA Crawler & Table Extractor Engine
Mengekstrak data surat masuk, surat keluar, disposisi, dan naskah dinas dari portal SRIKANDI
dengan dukungan penanganan komponen dinamis React & Material-UI.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page

from .auth_manager import srikandi_auth_manager, SRIKANDI_BASE_URL

logger = logging.getLogger("srikandi_scraper")

# URL mapping modul-modul persuratan di Srikandi
MODULE_ROUTES = {
    "verifikasi_naskah": "/pembuatan-naskah-keluar/verifikasi-naskah",
    "pembuatan_naskah_keluar": "/pembuatan-naskah-keluar/verifikasi-naskah",
    "surat_masuk": "/surat-masuk",
    "naskah_masuk": "/registrasi-naskah-masuk",
    "surat_keluar": "/surat-keluar",
    "naskah_keluar": "/naskah-keluar",
    "disposisi": "/disposisi",
    "disposisi_masuk": "/kotak-masuk-disposisi",
    "naskah_dinas": "/naskah-dinas",
    "arsip_aktif": "/arsip-aktif",
}


class SrikandiScraper:
    """Crawler & Extractor untuk halaman data SRIKANDI."""

    def __init__(self):
        self.auth_manager = srikandi_auth_manager

    def _resolve_module_url(self, module: str) -> str:
        route = MODULE_ROUTES.get(module, f"/{module.replace('_', '-')}")
        return f"{SRIKANDI_BASE_URL}{route}"

    async def fetch_documents(
        self,
        module: str = "verifikasi_naskah",
        profile_id: str = "default",
        max_pages: int = 1,
        search_query: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fetch_details: bool = True,
    ) -> Dict[str, Any]:
        """
        Mengekstrak daftar dokumen/surat dari modul tertentu dengan profil akun yang ditentukan.
        """
        # Cek ketersediaan file sesi tersimpan
        session_file = self.auth_manager.get_session_file(profile_id)
        if not session_file.exists():
            logger.info(f"File sesi profil '{profile_id}' belum ada. Mencoba login otomatis...")
            login_res = await self.auth_manager.login_headless(profile_id=profile_id)
            if not login_res.get("success"):
                return {
                    "success": False,
                    "profile_id": profile_id,
                    "error": f"Autentikasi gagal untuk profil '{profile_id}': {login_res.get('error')}. Jalankan --interactive-seed terlebih dahulu."
                }

        target_url = self._resolve_module_url(module)
        extracted_rows: List[Dict[str, Any]] = []

        async with async_playwright() as p:
            browser, context = await self.auth_manager.create_browser_context(
                p, profile_id=profile_id, headless=False
            )
            page = await context.new_page()

            try:
                # 1. Buka /beranda terlebih dahulu untuk inisialisasi state sesi React SPA
                beranda_url = f"{SRIKANDI_BASE_URL}/beranda"
                logger.info(f"Membuka {beranda_url} untuk inisialisasi sesi profil '{profile_id}'...")
                await page.goto(beranda_url, wait_until="domcontentloaded", timeout=35000)
                await asyncio.sleep(2.5)

                # 2. Navigasi ke modul target
                logger.info(f"Navigasi ke {target_url}...")
                if page.url != target_url:
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=40000)
                    await asyncio.sleep(3)

                # Jika dialihkan kembali ke login, sesi kedaluwarsa
                if "/auth/login" in page.url:
                    return {
                        "success": False,
                        "profile_id": profile_id,
                        "error": "Sesi kedaluwarsa setelah redirect. Perlu re-login/interactive seeding."
                    }

                # 1. Coba klik tombol "HITUNG TOTAL" jika tersedia untuk estimasi volume data
                total_records_est = await self._try_click_hitung_total(page)

                # 2. Atur dropdown "Menampilkan : [ 10/25/50/100 ]" jika diminta
                await self._adjust_page_size(page, target_size=50)

                # 3. Terapkan kata kunci pencarian jika ada
                if search_query:
                    search_selectors = [
                        'input[placeholder*="Cari" i]',
                        'input[placeholder*="Search" i]',
                        'input[type="search"]',
                        'input.MuiInputBase-input'
                    ]
                    for sel in search_selectors:
                        if await page.locator(sel).first.is_visible(timeout=2000):
                            await page.locator(sel).first.fill(search_query)
                            await page.keyboard.press("Enter")
                            await asyncio.sleep(3)
                            break

                # 4. Deteksi dan lakukan Infinite Scrolling otomatis jika tabel menggunakan mekanisme gulir terus menerus
                logger.info("Memeriksa dan mengeksekusi infinite scroll otomatis jika tersedia...")
                await self._scroll_infinite_table(page, max_scroll_turns=60)

                current_page_idx = 1
                while current_page_idx <= max_pages:
                    # Ekstraksi baris tabel halaman aktif
                    rows = await self._extract_table_rows(page, module, profile_id)

                    # Jika deep detail diaktifkan, telusuri link di kolom Aksi
                    if fetch_details:
                        for r in rows:
                            if r.get("detail_url") and r["detail_url"].startswith("http"):
                                logger.info(f"Mengambil detail naskah: {r.get('nomor_naskah', 'doc')}...")
                                detail_data = await self._fetch_single_detail(context, r["detail_url"])
                                if detail_data:
                                    r["detail_data"] = detail_data
                                    if detail_data.get("lampiran_urls"):
                                        r["lampiran_urls"].extend(detail_data["lampiran_urls"])
                                        r["lampiran_urls"] = list(set(r["lampiran_urls"]))

                    extracted_rows.extend(rows)

                    if current_page_idx >= max_pages:
                        break

                    # Pindah ke halaman berikutnya jika bukan infinite scroll
                    has_next = await self._navigate_next_page(page)
                    if not has_next:
                        logger.info("Tidak ada halaman berikutnya atau paginasi berbasis infinite scroll selesai.")
                        break

                    current_page_idx += 1
                    await asyncio.sleep(2)

                return {
                    "success": True,
                    "profile_id": profile_id,
                    "module": module,
                    "total_extracted": len(extracted_rows),
                    "total_records_est": total_records_est,
                    "pages_scraped": current_page_idx,
                    "timestamp": datetime.now().isoformat(),
                    "data": extracted_rows,
                }
            except Exception as e:
                logger.error(f"Error ekstraksi data Srikandi: {e}")
                return {
                    "success": False,
                    "profile_id": profile_id,
                    "module": module,
                    "error": str(e),
                    "partial_data": extracted_rows,
                }
            finally:
                await context.close()
                await browser.close()

    async def _extract_table_rows(self, page: Page, module: str, profile_id: str) -> List[Dict[str, Any]]:
        """Mengekstrak baris-baris data dari tabel MUI / SPA."""
        raw_rows = await page.evaluate("""() => {
            const results = [];
            // Deteksi tabel standar atau MUI DataGrid
            const table = document.querySelector('table, .MuiTable-root, .MuiDataGrid-root, [role="grid"]');
            if (!table) {
                // Alternatif: List item cards
                const cards = document.querySelectorAll('.card-surat, .MuiCard-root, .list-item');
                cards.forEach((card, idx) => {
                    results.push({
                        idx: idx + 1,
                        text: card.innerText,
                        html: card.innerHTML,
                        links: Array.from(card.querySelectorAll('a')).map(a => ({ href: a.href, text: a.innerText }))
                    });
                });
                return results;
            }

            // Ambil headers
            const headerEls = table.querySelectorAll('th, .MuiTableCell-head, [role="columnheader"]');
            const headers = Array.from(headerEls).map(th => th.innerText.trim().toLowerCase());

            // Ambil rows
            const rowEls = table.querySelectorAll('tbody tr, .MuiTableBody-root tr, [role="row"]:not([role="columnheader"])');
            rowEls.forEach((tr, rIdx) => {
                const cellEls = tr.querySelectorAll('td, .MuiTableCell-body, [role="cell"], [role="gridcell"]');
                if (cellEls.length === 0) return;

                const cells = Array.from(cellEls).map(c => c.innerText.trim());
                const links = Array.from(tr.querySelectorAll('a, button[data-url]')).map(a => ({
                    text: a.innerText.trim() || a.getAttribute('title') || a.getAttribute('aria-label') || '',
                    href: a.href || a.getAttribute('data-url') || '',
                    action: a.getAttribute('data-action') || ''
                }));

                const buttons = Array.from(tr.querySelectorAll('button')).map(b => ({
                    text: b.innerText.trim() || b.getAttribute('aria-label') || b.getAttribute('title') || '',
                    aria_label: b.getAttribute('aria-label') || '',
                    classes: b.className || ''
                }));

                results.push({
                    row_index: rIdx + 1,
                    cells: cells,
                    headers: headers,
                    links: links,
                    buttons: buttons,
                    raw_text: tr.innerText.trim()
                });
            });

            return results;
        }""")

        structured_results: List[Dict[str, Any]] = []
        for r in raw_rows:
            parsed = self._normalize_row(r, module=module, profile_id=profile_id)
            if parsed:
                structured_results.append(parsed)

        return structured_results

    def _normalize_row(self, raw_row: Dict[str, Any], module: str, profile_id: str) -> Optional[Dict[str, Any]]:
        """Menyelaraskan struktur kolom tabel menjadi format standar korespondensi."""
        cells = raw_row.get("cells", [])
        raw_text = raw_row.get("raw_text", "").strip()
        
        # Abaikan baris placeholder, filter header, atau scroll helper
        if not cells and not raw_text:
            return None
        if raw_text in ["Cari Status", "Gulir ke bawah untuk memuat lebih banyak", "Tidak ada data"]:
            return None
        if len(cells) <= 2 and "cari" in raw_text.lower():
            return None

        # Template format terstruktur
        item: Dict[str, Any] = {
            "nomor_naskah": "",
            "tanggal_naskah": "",
            "tanggal_diterima": "",
            "pengirim": "",
            "penerima": "",
            "perihal": "",
            "sifat_naskah": "Biasa",
            "status_disposisi": "",
            "lampiran_urls": [],
            "detail_url": "",
            "scraped_by_profile": profile_id,
            "module_source": module,
            "raw_text": raw_text,
            "extracted_at": datetime.now().isoformat(),
        }

        # Parsing links for attachments or detail
        for l in raw_row.get("links", []):
            href = l.get("href", "")
            text = (l.get("text", "") or "").lower()
            if "pdf" in href.lower() or "download" in href.lower() or "unduh" in text or "lampiran" in text:
                item["lampiran_urls"].append(href)
            elif "/detail" in href.lower() or "/view" in href.lower() or "lihat" in text or "verifikasi" in text:
                item["detail_url"] = href

        headers = [h.lower() for h in raw_row.get("headers", [])]
        
        # 1. Header-Aware Mapping jika header terdeteksi
        if headers and len(cells) == len(headers):
            for h, c in zip(headers, cells):
                c_clean = c.strip()
                if "tgl" in h or "tanggal" in h:
                    item["tanggal_naskah"] = c_clean
                elif "nomor" in h or "no naskah" in h:
                    item["nomor_naskah"] = c_clean
                elif "hal" in h or "perihal" in h or "ringkasan" in h:
                    item["perihal"] = c_clean
                elif "asal" in h or "pengirim" in h:
                    item["pengirim"] = c_clean
                elif "tujuan" in h or "penerima" in h:
                    item["penerima"] = c_clean
                elif "status" in h:
                    item["status_disposisi"] = c_clean
                elif "sifat" in h:
                    item["sifat_naskah"] = c_clean
        elif len(cells) >= 6:
            # Standar Verifikasi Naskah / Naskah Keluar (7 Kolom):
            # [0: No, 1: Tanggal Naskah, 2: Nomor Naskah, 3: Hal, 4: Asal Naskah, 5: Status, 6: Aksi]
            if len(cells) >= 7:
                item["tanggal_naskah"] = cells[1].strip()
                item["nomor_naskah"] = cells[2].strip()
                item["perihal"] = cells[3].strip()
                item["pengirim"] = cells[4].strip()
                item["status_disposisi"] = cells[5].strip()
            else:
                # 6 Kolom: [No, Tanggal, Nomor, Hal, Asal, Status]
                item["tanggal_naskah"] = cells[1].strip()
                item["nomor_naskah"] = cells[2].strip()
                item["perihal"] = cells[3].strip()
                item["pengirim"] = cells[4].strip()
                item["status_disposisi"] = cells[5].strip()
        elif len(cells) >= 3:
            # Srikandi fallback format
            for idx, c in enumerate(cells):
                c_clean = c.strip()
                if not c_clean:
                    continue
                if idx == 1:
                    item["nomor_naskah"] = c_clean
                elif idx == 2:
                    item["perihal"] = c_clean
                elif idx == 3:
                    item["pengirim"] = c_clean
                elif idx == 4 and not item["status_disposisi"]:
                    item["status_disposisi"] = c_clean
        else:
            full_text = raw_row.get("raw_text", "")
            lines = [line.strip() for line in full_text.split("\n") if line.strip()]
            if len(lines) >= 1:
                item["nomor_naskah"] = lines[0]
            if len(lines) >= 2:
                item["perihal"] = lines[1]
            if len(lines) >= 3:
                item["pengirim"] = lines[2]

        return item

    async def _navigate_next_page(self, page: Page) -> bool:
        """Mengecek dan mengeklik tombol pagination halaman berikutnya."""
        next_selectors = [
            'button[aria-label="Go to next page"]',
            'button[aria-label="Next page"]',
            'button.MuiPaginationItem-next',
            'li.next a',
            'button:has-text("Selanjutnya")',
            'button:has-text("Berikutnya")',
        ]

        for sel in next_selectors:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=1500):
                is_disabled = await loc.is_disabled()
                if not is_disabled:
                    await loc.click()
                    return True
        return False

    async def _scroll_infinite_table(self, page: Page, max_scroll_turns: int = 100) -> int:
        """
        Mendeteksi dan melakukan scroll dinamis berkelanjutan (infinite scroll) pada tabel Srikandi,
        dengan pertahanan berlapis (resilient retry) terhadap kegagalan server dan tombol 'COBA LAGI'.
        """
        try:
            last_count = 0
            stagnant_turns = 0
            retry_attempts = 0
            
            for turn in range(1, max_scroll_turns + 1):
                # 1. Cek tombol retry 'COBA LAGI' jika server SRIKANDI mengalami kegagalan/timeout
                retry_locators = page.locator('button:has-text("COBA LAGI"), button:has-text("Coba Lagi"), [role="button"]:has-text("COBA LAGI")')
                if await retry_locators.count() > 0 and await retry_locators.first.is_visible(timeout=500):
                    retry_attempts += 1
                    logger.warning(f"⚠️ Server SRIKANDI gagal memuat batch (percobaan retry #{retry_attempts}). Menekan tombol 'COBA LAGI'...")
                    try:
                        await retry_locators.first.click()
                        # Beri jeda lebih sabar (5 detik) untuk server merespons ulang
                        await asyncio.sleep(5)
                        stagnant_turns = 0  # Reset agar tidak berhenti prematur
                        continue
                    except Exception as e:
                        logger.debug(f"Gagal klik tombol COBA LAGI: {e}")

                # 2. Hitung jumlah baris data valid saat ini
                rows_info = await page.evaluate('''() => {
                    const rows = Array.from(document.querySelectorAll('table tr, .MuiTable-root tr, [role="row"]'));
                    const validRows = [];
                    let hasTrigger = false;
                    let hasError = false;
                    
                    rows.forEach(r => {
                        const txt = r.innerText.trim();
                        if (txt.includes('Gulir ke bawah untuk memuat lebih banyak')) {
                            hasTrigger = true;
                        }
                        if (txt.includes('Gagal memuat data') || txt.includes('COBA LAGI')) {
                            hasError = true;
                        }
                        if (txt.length > 10 && !txt.includes('Cari Status') && !txt.includes('Gulir') && !txt.includes('Gagal') && !txt.startsWith('NO')) {
                            validRows.push(txt);
                        }
                    });
                    
                    return {
                        totalValid: validRows.length,
                        hasTrigger: hasTrigger,
                        hasError: hasError
                    };
                }''')

                curr_count = rows_info.get("totalValid", 0)
                has_trigger = rows_info.get("hasTrigger", False)
                has_error = rows_info.get("hasError", False)

                if has_error:
                    # Jika terdeteksi teks gagal memuat data tapi tombol belum diklik
                    retry_btn = page.locator('button:has-text("COBA LAGI"), [role="button"]:has-text("COBA LAGI")').first
                    if await retry_btn.is_visible(timeout=800):
                        logger.warning("Menekan tombol COBA LAGI dari deteksi error...")
                        await retry_btn.click()
                        await asyncio.sleep(5)
                        stagnant_turns = 0
                        continue

                if curr_count > last_count:
                    stagnant_turns = 0
                    retry_attempts = 0
                    last_count = curr_count
                    logger.info(f"[Infinite Scroll] Turn {turn}: {curr_count} dokumen termuat...")
                else:
                    stagnant_turns += 1
                    if not has_trigger and not has_error and stagnant_turns >= 4:
                        logger.info(f"[Infinite Scroll] Trigger selesai dan tidak ada error, total naskah termuat: {curr_count}")
                        break
                    elif stagnant_turns >= 8:
                        logger.info(f"[Infinite Scroll] Jumlah baris stabil pada {curr_count} setelah beberapa percobaan. Selesai.")
                        break

                # 3. Gulir elemen trigger atau container tabel
                trigger_loc = page.locator('text="Gulir ke bawah untuk memuat lebih banyak"').last
                if await trigger_loc.is_visible(timeout=500):
                    try:
                        await trigger_loc.scroll_into_view_if_needed(timeout=1500)
                    except Exception:
                        pass

                await page.evaluate('''() => {
                    window.scrollTo(0, document.body.scrollHeight);
                    const tableContainers = document.querySelectorAll('.MuiTableContainer-root, [class*="TableContainer"], [class*="table"], .overflow-auto, .overflow-y-auto');
                    tableContainers.forEach(c => {
                        c.scrollTop = c.scrollHeight;
                    });
                }''')

                # Kirim mouse wheel event
                await page.mouse.wheel(0, 2500)
                await asyncio.sleep(3.5)

            return last_count
        except Exception as e:
            logger.debug(f"Infinite scroll error/fallback: {e}")
            return 0

    async def _try_click_hitung_total(self, page: Page) -> Optional[int]:
        """Mengeklik tombol 'HITUNG TOTAL' jika tersedia dan membaca total data naskah."""
        try:
            btn_selectors = [
                'button:has-text("HITUNG TOTAL")',
                'button:has-text("Hitung Total")',
                '.btn-hitung-total',
                'button.MuiButton-root:has-text("TOTAL")'
            ]
            for sel in btn_selectors:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=1500):
                    await loc.click()
                    await asyncio.sleep(2)
                    
                    # Cek teks hasil hitung total
                    total_text = await page.evaluate("""() => {
                        const el = document.querySelector('.total-count, .badge-total, .MuiChip-label, span.font-weight-bold');
                        return el ? el.innerText.trim() : null;
                    }""")
                    if total_text:
                        import re
                        digits = re.findall(r'\d+', total_text)
                        if digits:
                            return int("".join(digits))
                    break
        except Exception as e:
            logger.debug(f"Info hitung total not available: {e}")
        return None

    async def _adjust_page_size(self, page: Page, target_size: int = 50):
        """Menyesuaikan dropdown 'Menampilkan : [ 10/25/50/100 ]'."""
        try:
            # Cari elemen select di sekitar teks 'Menampilkan'
            select_loc = page.locator('select').first
            if await select_loc.is_visible(timeout=1500):
                options = await select_loc.locator('option').all_inner_texts()
                # Pilih nilai terbesar yang cocok (misal 50 atau 100)
                matched_val = None
                for opt in [str(target_size), "100", "50", "25"]:
                    if any(opt in o for o in options):
                        matched_val = opt
                        break
                if matched_val:
                    await select_loc.select_option(label=matched_val)
                    await asyncio.sleep(2)
                    logger.info(f"Page size disesuaikan menjadi: {matched_val}")
        except Exception as e:
            logger.debug(f"Gagal menyesuaikan page size: {e}")

    async def _fetch_single_detail(self, context, detail_url: str) -> Optional[Dict[str, Any]]:
        """
        Membuka halaman detail data index naskah dan mengekstrak informasi mendalam.
        Mendukung penangkapan respons API backend (JSON) secara otomatis dan fallback DOM.
        """
        detail_page = None
        intercepted_api_data: Dict[str, Any] = {}

        try:
            detail_page = await context.new_page()

            # Listener untuk menangkap payload JSON API Srikandi secara langsung (High Fidelity)
            async def handle_response(response):
                try:
                    url = response.url
                    if any(k in url for k in ["/api/", "/naskah", "/verifikasi", "/detail"]) and "json" in response.headers.get("content-type", ""):
                        data = await response.json()
                        if isinstance(data, dict):
                            intercepted_api_data.update(data)
                except Exception:
                    pass

            detail_page.on("response", handle_response)

            await detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=35000)
            await asyncio.sleep(4)

            # 1. Expand seluruh Accordion (Verifikator, Penandatangan, Riwayat Metadata, Linimasa)
            try:
                acc_headers = await detail_page.locator('div:has-text("Daftar Verifikator"), div:has-text("Daftar Penandatangan"), div:has-text("Linimasa"), div:has-text("Daftar Riwayat")').all()
                for h in acc_headers:
                    txt = await h.inner_text()
                    if any(k in txt for k in ["Daftar", "Linimasa", "Riwayat"]):
                        try:
                            await h.click(timeout=1000)
                            await asyncio.sleep(0.5)
                        except Exception:
                            pass
            except Exception:
                pass

            # Ekstrak dari struktur DOM (Material-UI Form Controls, Tables, Tabs, Timeline, File Cards)
            dom_detail = await detail_page.evaluate("""() => {
                const res = {
                    title: document.title,
                    fields: {},
                    verifikator_list: [],
                    penandatangan_list: [],
                    history_logs: [],
                    lampiran_files: [],
                    lampiran_urls: [],
                    raw_sections: []
                };

                // 1. Ekstrak key-value dari label & input/value/typography MUI
                const allLabels = Array.from(document.querySelectorAll('label, .MuiFormLabel-root, dt, th, strong, .font-medium, .text-xs'));
                allLabels.forEach(lbl => {
                    const key = lbl.innerText.trim().replace(/:$/, '');
                    if (!key || key.length > 50) return;

                    const container = lbl.closest('.MuiFormControl-root, .row, .col, .form-group, tr, div');
                    if (container) {
                        const valEl = container.querySelector('input, textarea, select, .MuiTypography-root:not(.MuiFormLabel-root), dd, td, .form-control-plaintext, p');
                        if (valEl && valEl !== lbl) {
                            const val = valEl.value || valEl.innerText || '';
                            if (val.trim()) res.fields[key] = val.trim();
                        }
                    }
                });

                // 2. Ekstrak file lampiran kartu (DOCX / PDF / XLS)
                document.querySelectorAll('.card, .MuiCard-root, [class*="lampiran" i], div:has(> svg)').forEach(card => {
                    const txt = card.innerText ? card.innerText.trim() : '';
                    if (txt.includes('.docx') || txt.includes('.pdf') || txt.includes('.doc') || txt.includes('.xlsx') || txt.includes('Lampiran')) {
                        const lines = txt.split('\\n').map(l => l.trim()).filter(Boolean);
                        const fileName = lines.find(l => l.includes('.') && (l.endsWith('.docx') || l.endsWith('.pdf') || l.endsWith('.doc') || l.endsWith('.xlsx'))) || lines[0] || 'Lampiran';
                        const linkEl = card.querySelector('a, div.cursor-pointer, button');
                        const href = (linkEl && linkEl.href) ? linkEl.href : '';
                        res.lampiran_files.push({
                            filename: fileName,
                            raw_text: txt,
                            download_url: href
                        });
                    }
                });

                // 3. Ekstrak tabel verifikator & penandatangan
                const allTables = Array.from(document.querySelectorAll('table, .MuiTable-root'));
                allTables.forEach(tbl => {
                    const tblText = tbl.innerText || '';
                    if (tblText.includes('Verifikator') || tblText.includes('Paraf') || tblText.includes('URUTAN')) {
                        const rows = tbl.querySelectorAll('tbody tr, tr');
                        rows.forEach(tr => {
                            const cells = Array.from(tr.querySelectorAll('td, th')).map(c => c.innerText.trim());
                            if (cells.length >= 2) {
                                res.verifikator_list.push(cells);
                            }
                        });
                    } else if (tblText.includes('Penandatangan') || tblText.includes('TTE')) {
                        const rows = tbl.querySelectorAll('tbody tr, tr');
                        rows.forEach(tr => {
                            const cells = Array.from(tr.querySelectorAll('td, th')).map(c => c.innerText.trim());
                            if (cells.length >= 2) {
                                res.penandatangan_list.push(cells);
                            }
                        });
                    }
                });

                // 4. Ekstrak riwayat log / timeline verifikasi
                const logEls = document.querySelectorAll('.timeline-item, .history-log, .log-item, .activity-item, [class*="timeline" i]');
                logEls.forEach(l => {
                    if (l.innerText.trim()) res.history_logs.push(l.innerText.trim());
                });

                // 5. Ekstrak link download langsung
                const links = document.querySelectorAll('a[href*="download"], a[href*="pdf"], a[href*="docx"], a.btn-download, embed[src], iframe[src]');
                links.forEach(el => {
                    const src = el.href || el.src;
                    if (src && !src.startsWith('javascript:')) {
                        res.lampiran_urls.push(src);
                    }
                });

                return res;
            }""")

            # Ekstrak ID dari parameter query URL (?id=U2FsdGVk...)
            import urllib.parse as up
            parsed_u = up.urlparse(detail_url)
            query_params = up.parse_qs(parsed_u.query)
            srikandi_id = query_params.get("id", [""])[0]

            combined_result = {
                "srikandi_id": srikandi_id,
                "detail_url": detail_url,
                "api_payload": intercepted_api_data.get("data") or intercepted_api_data,
                "dom_fields": dom_detail.get("fields", {}),
                "verifikator_list": dom_detail.get("verifikator_list", []),
                "history_logs": dom_detail.get("history_logs", []),
                "lampiran_urls": list(set(dom_detail.get("lampiran_urls", []))),
            }

            return combined_result
        except Exception as e:
            logger.error(f"Gagal mengambil detail dari {detail_url}: {e}")
            return None
        finally:
            if detail_page:
                try:
                    await detail_page.close()
                except Exception:
                    pass


srikandi_scraper = SrikandiScraper()
