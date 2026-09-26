"""
Srikandi Authentication & Multi-Account Profile Manager
Mengelola kredensial multi-akun, state sesi (storageState cookies/localStorage),
serta alur login otomatis (headless) dan interactive seeding (headed) untuk SRIKANDI.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, Any, List, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger("srikandi_auth_manager")

# Base URLs
SRIKANDI_BASE_URL = os.getenv("SRIKANDI_BASE_URL", "https://srikandi.arsip.go.id")
SRIKANDI_LOGIN_URL = f"{SRIKANDI_BASE_URL}/auth/login"
SRIKANDI_DASHBOARD_URL = f"{SRIKANDI_BASE_URL}/dashboard"

# Paths
REPO_ROOT = Path(__file__).resolve().parents[5]
SESSIONS_DIR = REPO_ROOT / "storage" / "admin_data" / "srikandi_sessions"
ACCOUNTS_CONFIG_FILE = REPO_ROOT / "storage" / "admin_data" / "srikandi_accounts.json"


@dataclass
class SrikandiAccountProfile:
    profile_id: str
    label: str
    username: str
    password: str
    unit_kerja: str = ""
    is_active: bool = True
    session_file: str = ""
    last_verified: Optional[str] = None
    is_session_valid: bool = False

    def to_dict(self, mask_secret: bool = True) -> Dict[str, Any]:
        d = asdict(self)
        if mask_secret and d.get("password"):
            d["password"] = "******"
        return d


class SrikandiAuthManager:
    """Manages multi-account profiles and persistent browser session storage states for SRIKANDI."""

    def __init__(self):
        self.sessions_dir = SESSIONS_DIR
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.accounts_file = ACCOUNTS_CONFIG_FILE
        self._ensure_env_loaded()

    def _ensure_env_loaded(self):
        """Loads secrets from environment files if available."""
        try:
            from core.secrets import load_runtime_secrets
            load_runtime_secrets()
        except Exception:
            try:
                from scripts.load_env import load_env
                load_env()
            except Exception:
                pass

    def list_profiles(self, mask_secret: bool = True) -> List[Dict[str, Any]]:
        """Mengembalikan daftar semua profil akun SRIKANDI yang terdaftar."""
        profiles = self.get_all_profiles()
        return [p.to_dict(mask_secret=mask_secret) for p in profiles.values()]

    def get_all_profiles(self) -> Dict[str, SrikandiAccountProfile]:
        """Load all profiles from config file and environment variables."""
        profiles: Dict[str, SrikandiAccountProfile] = {}

        # 1. Load from JSON config file in storage/admin_data/ if exists
        if self.accounts_file.exists():
            try:
                with open(self.accounts_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("profiles", []):
                        pid = item.get("profile_id", "").strip()
                        if pid:
                            sess_file = str(self.sessions_dir / f"session_{pid}.json")
                            profiles[pid] = SrikandiAccountProfile(
                                profile_id=pid,
                                label=item.get("label", pid),
                                username=item.get("username", ""),
                                password=item.get("password", ""),
                                unit_kerja=item.get("unit_kerja", ""),
                                is_active=item.get("is_active", True),
                                session_file=sess_file,
                                last_verified=item.get("last_verified"),
                                is_session_valid=Path(sess_file).exists(),
                            )
            except Exception as e:
                logger.error(f"Gagal membaca srikandi_accounts.json: {e}")

        # 2. Check SRIKANDI_ACCOUNTS_JSON env var
        env_accounts_json = os.getenv("SRIKANDI_ACCOUNTS_JSON")
        if env_accounts_json:
            try:
                parsed = json.loads(env_accounts_json)
                items = parsed if isinstance(parsed, list) else parsed.get("profiles", [])
                for item in items:
                    pid = item.get("profile_id", "").strip()
                    if pid:
                        sess_file = str(self.sessions_dir / f"session_{pid}.json")
                        profiles[pid] = SrikandiAccountProfile(
                            profile_id=pid,
                            label=item.get("label", pid),
                            username=item.get("username", ""),
                            password=item.get("password", ""),
                            unit_kerja=item.get("unit_kerja", ""),
                            is_active=item.get("is_active", True),
                            session_file=sess_file,
                            last_verified=item.get("last_verified"),
                            is_session_valid=Path(sess_file).exists(),
                        )
            except Exception as e:
                logger.error(f"Gagal mem-parse SRIKANDI_ACCOUNTS_JSON: {e}")

        # 3. Default single account fallback from SRIKANDI_USER / SRIKANDI_PASS
        default_user = os.getenv("SRIKANDI_USER")
        default_pass = os.getenv("SRIKANDI_PASS")
        if default_user and "default" not in profiles:
            sess_file = str(self.sessions_dir / "session_default.json")
            profiles["default"] = SrikandiAccountProfile(
                profile_id="default",
                label="Akun Utama (Default)",
                username=default_user,
                password=default_pass or "",
                unit_kerja=os.getenv("SRIKANDI_UNIT_KERJA", "Ditjen Bina Bangda"),
                is_active=True,
                session_file=sess_file,
                is_session_valid=Path(sess_file).exists(),
            )

        return profiles

    def get_profile(self, profile_id: str = "default") -> Optional[SrikandiAccountProfile]:
        """Mendapatkan detail profil berdasarkan profile_id."""
        profiles = self.get_all_profiles()
        if profile_id in profiles:
            return profiles[profile_id]
        if profiles and profile_id == "default":
            # return first available profile
            return next(iter(profiles.values()))
        return None

    def save_profile(self, profile: SrikandiAccountProfile) -> bool:
        """Menyimpan atau memperbarui profil akun ke storage/admin_data/srikandi_accounts.json."""
        try:
            profiles = self.get_all_profiles()
            profiles[profile.profile_id] = profile

            serialized = []
            for p in profiles.values():
                serialized.append({
                    "profile_id": p.profile_id,
                    "label": p.label,
                    "username": p.username,
                    "password": p.password,
                    "unit_kerja": p.unit_kerja,
                    "is_active": p.is_active,
                    "last_verified": p.last_verified,
                })

            self.accounts_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.accounts_file, "w", encoding="utf-8") as f:
                json.dump({"profiles": serialized}, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Gagal menyimpan profil akun Srikandi: {e}")
            return False

    def get_session_file(self, profile_id: str) -> Path:
        """Path session state storage untuk profile_id."""
        return self.sessions_dir / f"session_{profile_id}.json"

    async def create_browser_context(
        self,
        playwright_instance,
        profile_id: str = "default",
        headless: bool = True
    ) -> tuple[Browser, BrowserContext]:
        """
        Membuat Browser & BrowserContext yang diinisialisasi dengan storage_state tersimpan jika ada.
        """
        session_file = self.get_session_file(profile_id)
        storage_state = str(session_file) if session_file.exists() else None

        browser = await playwright_instance.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--disable-dev-shm-usage",
            ],
            ignore_default_args=["--enable-automation"]
        )

        context_kwargs: Dict[str, Any] = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "viewport": {"width": 1440, "height": 900},
            "accept_downloads": True,
        }
        if storage_state:
            context_kwargs["storage_state"] = storage_state

        context = await browser.new_context(**context_kwargs)

        # Injeksi stealth scripts & localStorage / sessionStorage
        await context.add_init_script("""() => {
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
        }""")

        # Injeksi eksplisit localStorage dan sessionStorage via init_script untuk memastikan SPA React segera terhidrasi
        if storage_state and Path(storage_state).exists():
            try:
                with open(storage_state, "r", encoding="utf-8") as f:
                    sess_data = json.load(f)

                # 1. Injeksi sessionStorage jika tersimpan
                sess_storage = sess_data.get("sessionStorage", {})
                if sess_storage:
                    sess_stmts = [
                        f"try {{ sessionStorage.setItem({json.dumps(k)}, {json.dumps(v)}); }} catch(e) {{}}"
                        for k, v in sess_storage.items()
                    ]
                    await context.add_init_script(";\n".join(sess_stmts))

                # 2. Injeksi localStorage
                raw_ls = sess_data.get("raw_localStorage", {})
                if raw_ls:
                    ls_stmts = [
                        f"try {{ localStorage.setItem({json.dumps(k)}, {json.dumps(v)}); }} catch(e) {{}}"
                        for k, v in raw_ls.items()
                    ]
                    await context.add_init_script(";\n".join(ls_stmts))
                else:
                    for origin_data in sess_data.get("origins", []):
                        ls_items = origin_data.get("localStorage", [])
                        if ls_items:
                            init_statements = [
                                f"try {{ localStorage.setItem({json.dumps(item['name'])}, {json.dumps(item['value'])}); }} catch(e) {{}}"
                                for item in ls_items
                            ]
                            await context.add_init_script(";\n".join(init_statements))
            except Exception as e:
                logger.debug(f"Gagal injeksi init_script storage: {e}")

        return browser, context

    async def check_session_validity(self, profile_id: str = "default") -> Dict[str, Any]:
        """
        Mengecek apakah session storage aktif masih valid dengan mengakses dashboard Srikandi.
        """
        session_file = self.get_session_file(profile_id)
        if not session_file.exists():
            return {
                "profile_id": profile_id,
                "is_valid": False,
                "reason": f"File session belum ada ({session_file.name}). Butuh login terlebih dahulu."
            }

        async with async_playwright() as p:
            browser, context = await self.create_browser_context(p, profile_id=profile_id, headless=True)
            page = await context.new_page()
            try:
                await page.goto(f"{SRIKANDI_BASE_URL}/dashboard", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2.5)
                current_url = page.url

                is_login_page = "/auth/login" in current_url or "/login" in current_url
                is_valid = not is_login_page and (
                    "/dashboard" in current_url or 
                    "/beranda" in current_url or 
                    "/surat" in current_url or
                    "/pembuatan-naskah" in current_url or
                    SRIKANDI_BASE_URL in current_url
                )

                title = await page.title()
                return {
                    "profile_id": profile_id,
                    "is_valid": is_valid,
                    "current_url": current_url,
                    "title": title,
                    "session_file": str(session_file),
                }
            except Exception as e:
                return {
                    "profile_id": profile_id,
                    "is_valid": False,
                    "error": str(e)
                }
            finally:
                await context.close()
                await browser.close()

    async def login_headless(self, profile_id: str = "default") -> Dict[str, Any]:
        """
        Melakukan login otomatis headless menggunakan username & password profil.
        Menyimpan session state ke JSON jika berhasil.
        """
        profile = self.get_profile(profile_id)
        if not profile:
            return {"success": False, "error": f"Profil '{profile_id}' tidak ditemukan."}

        if not profile.username or not profile.password:
            return {
                "success": False,
                "error": f"Username atau Password untuk profil '{profile_id}' kosong. Harap isi di .env atau konfigurasi."
            }

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 900}
            )
            page = await context.new_page()

            try:
                logger.info(f"Membuka halaman login SRIKANDI: {SRIKANDI_LOGIN_URL}")
                await page.goto(SRIKANDI_LOGIN_URL, wait_until="networkidle", timeout=35000)
                await asyncio.sleep(2)

                # Target input username / email / NIK (MUI & standard inputs)
                user_selectors = [
                    'input[name="username"]',
                    'input[name="email"]',
                    'input[name="nik"]',
                    'input[id="username"]',
                    'input[type="text"]',
                    'input[placeholder*="Username" i]',
                    'input[placeholder*="NIK" i]'
                ]
                user_filled = False
                for sel in user_selectors:
                    if await page.locator(sel).first.is_visible(timeout=1500):
                        await page.locator(sel).first.fill(profile.username)
                        user_filled = True
                        break

                if not user_filled:
                    # Fallback evaluation
                    await page.evaluate(f"""() => {{
                        const inputs = Array.from(document.querySelectorAll('input'));
                        const userInp = inputs.find(i => i.type === 'text' || i.name.includes('user') || i.id.includes('user'));
                        if (userInp) {{ userInp.value = "{profile.username}"; userInp.dispatchEvent(new Event('input', {{ bubbles: true }})); }}
                    }}""")

                # Target input password
                pass_selectors = [
                    'input[name="password"]',
                    'input[id="password"]',
                    'input[type="password"]',
                    'input[placeholder*="Password" i]',
                    'input[placeholder*="Kata Sandi" i]'
                ]
                pass_filled = False
                for sel in pass_selectors:
                    if await page.locator(sel).first.is_visible(timeout=1500):
                        await page.locator(sel).first.fill(profile.password)
                        pass_filled = True
                        break

                if not pass_filled:
                    await page.evaluate(f"""() => {{
                        const passInp = document.querySelector('input[type="password"]');
                        if (passInp) {{ passInp.value = "{profile.password}"; passInp.dispatchEvent(new Event('input', {{ bubbles: true }})); }}
                    }}""")

                # Submit button
                submit_selectors = [
                    'button[type="submit"]',
                    'button:has-text("Masuk")',
                    'button:has-text("Login")',
                    '.btn-primary',
                    '.MuiButton-containedPrimary'
                ]
                btn_clicked = False
                for sel in submit_selectors:
                    if await page.locator(sel).first.is_visible(timeout=1500):
                        await page.locator(sel).first.click()
                        btn_clicked = True
                        break

                if not btn_clicked:
                    await page.keyboard.press("Enter")

                # Wait for navigation after submit
                await asyncio.sleep(4)
                await page.wait_for_load_state("domcontentloaded", timeout=15000)

                current_url = page.url
                if "/auth/login" not in current_url:
                    # Berhasil login! Simpan storage state
                    session_file = self.get_session_file(profile_id)
                    await context.storage_state(path=str(session_file))
                    logger.info(f"Login berhasil. Sesi tersimpan di: {session_file}")
                    return {
                        "success": True,
                        "profile_id": profile_id,
                        "current_url": current_url,
                        "session_file": str(session_file),
                        "message": f"Login berhasil untuk profil '{profile_id}'."
                    }
                else:
                    # Cek pesan error di halaman
                    error_msg = await page.evaluate("""() => {
                        const alertEl = document.querySelector('.MuiAlert-message, .alert, .error-message, .toast-error');
                        return alertEl ? alertEl.innerText : 'Gagal login (masih di halaman login). Mungkin butuh CAPTCHA atau kredensial salah.';
                    }""")
                    return {
                        "success": False,
                        "profile_id": profile_id,
                        "current_url": current_url,
                        "error": error_msg
                    }
            except Exception as e:
                logger.error(f"Error login headless: {e}")
                return {"success": False, "profile_id": profile_id, "error": str(e)}
            finally:
                await context.close()
                await browser.close()

    async def seed_interactive_session(self, profile_id: str = "default", timeout_seconds: int = 180) -> Dict[str, Any]:
        """
        Membuka browser tampilan visual (headed) agar pengguna dapat login manual
        (misal untuk memasukkan CAPTCHA / 2FA). Begitu login selesai dan masuk dashboard,
        sesi otomatis disimpan ke storageState.json.
        """
        profile = self.get_profile(profile_id)
        pid = profile.profile_id if profile else profile_id

        async with async_playwright() as p:
            # Note: headed requires display environment. If headless only, standard launch.
            try:
                browser = await p.chromium.launch(
                    headless=False,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
            except Exception:
                # Fallback to headless if no display server is attached
                logger.warning("Display server tidak tersedia. Menggunakan headless mode.")
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"]
                )

            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 900}
            )
            page = await context.new_page()

            try:
                await page.goto(SRIKANDI_LOGIN_URL, wait_until="domcontentloaded")
                logger.info(f"Menunggu login interaktif profil '{pid}' (Timeout: {timeout_seconds}s)...")

                # Pre-fill username if available
                if profile and profile.username:
                    try:
                        await page.locator('input[type="text"]').first.fill(profile.username)
                    except Exception:
                        pass

                start_time = asyncio.get_event_loop().time()
                logged_in = False

                while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
                    await asyncio.sleep(2)
                    cur_url = page.url

                    # Verifikasi apakah token otentikasi sudah tersimpan di localStorage
                    has_auth_token = await page.evaluate("""() => {
                        const token = localStorage.getItem('@secure.s.access_token') || localStorage.getItem('token') || localStorage.getItem('access_token');
                        const user = localStorage.getItem('@secure.s.users');
                        return Boolean((token && token.length > 20) || (user && user.length > 20));
                    }""")

                    # Harus sudah berada di dashboard/beranda/modul naskah (dan sama sekali BUKAN halaman /auth/ apapun termasuk OTP)
                    is_in_dashboard = (
                        "/auth/" not in cur_url and
                        ("/beranda" in cur_url or "/dashboard" in cur_url or "/pembuatan-naskah" in cur_url or "/surat" in cur_url)
                    )

                    if has_auth_token and is_in_dashboard:
                        logger.info(f"Sesi login & OTP terdeteksi valid di {cur_url}! Menunggu 4 detik untuk stabilisasi cookie...")
                        await asyncio.sleep(4)
                        logged_in = True
                        break

                if logged_in:
                    session_file = self.get_session_file(pid)
                    await context.storage_state(path=str(session_file))

                    # Tangkap juga sessionStorage dan raw localStorage untuk SPAs
                    try:
                        extra_storage = await page.evaluate("""() => {
                            const ss = {};
                            for (let i = 0; i < sessionStorage.length; i++) {
                                const k = sessionStorage.key(i);
                                if (k) ss[k] = sessionStorage.getItem(k);
                            }
                            const ls = {};
                            for (let i = 0; i < localStorage.length; i++) {
                                const k = localStorage.key(i);
                                if (k) ls[k] = localStorage.getItem(k);
                            }
                            return { sessionStorage: ss, raw_localStorage: ls };
                        }""")

                        with open(session_file, "r+", encoding="utf-8") as f:
                            sess_json = json.load(f)
                            sess_json["sessionStorage"] = extra_storage.get("sessionStorage", {})
                            sess_json["raw_localStorage"] = extra_storage.get("raw_localStorage", {})
                            f.seek(0)
                            json.dump(sess_json, f, indent=2)
                            f.truncate()
                    except Exception as e:
                        logger.debug(f"Gagal capture extra storage: {e}")

                    logger.info(f"Session seeding berhasil disimpan di {session_file}")
                    return {
                        "success": True,
                        "profile_id": pid,
                        "session_file": str(session_file),
                        "current_url": page.url,
                        "message": "Sesi interaktif berhasil disimpan."
                    }
                else:
                    return {
                        "success": False,
                        "profile_id": pid,
                        "error": f"Timeout {timeout_seconds} detik terlampaui sebelum login selesai (belum mendeteksi token/dashboard)."
                    }
            finally:
                await context.close()
                await browser.close()


srikandi_auth_manager = SrikandiAuthManager()
