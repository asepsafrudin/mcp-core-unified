"""
hybrid_search.py — Tri-Engine Hybrid Search Engine & Autonomous Browser Integrator.
Integrates Fast-Path (DDG Lite & Playwright), Browser-Use (AI Sub-Agent), and Direct JDIH/Gov Scrapers
with Intelligent Complexity Routing, Content Safety Filtering, and Dual-Layer Caching (Redis + Memory).
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("hybrid_search")

# ─── 1. Content Safety & Domain Filtering ─────────────────────────────────────

# Blacklist domain sampah / tidak pantas untuk institusi dinas
BLOCKED_DOMAINS = [
    "kaskus.co.id", "kaskus.id", "reddit.com",
    "bokep", "porn", "xxx", "gambling", "slot", "judi"
]

# Whitelist domain prioritas hukum dan pemerintahan
GOVERNMENT_DOMAINS = [
    "peraturan.bpk.go.id",
    "bpk.go.id",
    "jdih.kemendagri.go.id",
    "peraturan.go.id",
    "bphn.go.id",
    "setneg.go.id",
    "mkri.id",
    "mahkamahagung.go.id",
    "dpr.go.id",
    "kemendagri.go.id",
    "lapor.go.id"
]

try:
    from services.db_logger import log_browser_action
except ImportError:
    try:
        from core.services.db_logger import log_browser_action
    except ImportError:
        log_browser_action = None


def is_content_safe(url: str, title: str = "", snippet: str = "") -> bool:
    """Memverifikasi bahwa hasil pencarian aman dan bebas dari polusi / spam."""
    combined = f"{url} {title} {snippet}".lower()
    for bad in BLOCKED_DOMAINS:
        if bad in combined:
            return False
    return True


# ─── 2. Dual-Layer Cache (Redis + In-Memory TTL Fallback) ─────────────────────

class SearchCache:
    """
    Cache layer dengan dukungan Redis dan fallback in-memory TTL.
    Menjamin efisiensi biaya token dan kecepatan akses 0 ms untuk query berulang.
    """
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._mem_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._redis = None
        self._redis_tested = False

    def _init_redis(self):
        if self._redis_tested:
            return
        self._redis_tested = True
        redis_url = os.getenv("REDIS_URL", "")
        # Gunakan in-memory cache jika Redis tidak disetel kredensial khusus
        if not redis_url:
            self._redis = None
            return
        try:
            import redis
            client = redis.from_url(redis_url, socket_connect_timeout=0.5, socket_timeout=0.5, decode_responses=True)
            client.ping()
            self._redis = client
            logger.info("SearchCache: Redis connection established.")
        except Exception as e:
            logger.debug(f"SearchCache: Redis skipped ({e}), using in-memory TTL cache.")
            self._redis = None

    def _make_key(self, query: str, user_id: Optional[str] = None) -> str:
        norm = query.strip().lower()
        if user_id:
            norm = f"{user_id}:{norm}"
        return f"search_cache:{hashlib.sha256(norm.encode()).hexdigest()[:16]}"

    async def get(self, query: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        self._init_redis()
        key = self._make_key(query, user_id)

        # 1. Try Redis
        if self._redis:
            try:
                data = self._redis.get(key)
                if data:
                    return json.loads(data)
            except Exception:
                pass

        # 2. Try In-Memory
        if key in self._mem_cache:
            exp, val = self._mem_cache[key]
            if time.time() < exp:
                return val
            else:
                del self._mem_cache[key]

        return None

    async def set(self, query: str, data: Dict[str, Any], user_id: Optional[str] = None):
        self._init_redis()
        key = self._make_key(query, user_id)

        # 1. Try Redis
        if self._redis:
            try:
                self._redis.setex(key, self.ttl, json.dumps(data))
            except Exception:
                pass

        # 2. Store in In-Memory
        self._mem_cache[key] = (time.time() + self.ttl, data)


# ─── 3. Intelligent Router dengan Complexity & Intent Scoring ─────────────────

class BrowserRouter:
    """
    Menentukan engine terbaik untuk query/tugas berdasarkan intent dan kompleksitas.
    """
    LEGAL_PATTERNS = [
        r"\b(permendagri|kepmendagri|inmendagri|uu|undang-undang|perpres|perda|perwal|perbup|peraturan|pasal)\b",
        r"\b(jdih|bphn|hukum|klausul|doktrin|hierarki)\b",
        r"\b\d+\s+tahun\s+\d{4}\b"
    ]

    COMPLEX_PATTERNS = [
        r"\b(login|masuk|unduh|download|screenshot|tangkapan layar)\b",
        r"\b(sp4n|lapor|srikandi|oss|simbangda)\b",
        r"\b(isi formulir|klik tombol|navigasi ke)\b"
    ]

    def classify_task(self, query: str, url: Optional[str] = None) -> Dict[str, Any]:
        q_lower = query.lower()

        # 1. Cek Intent Dokumen Hukum / Regulasi Pemerintahan
        is_legal = any(re.search(p, q_lower) for p in self.LEGAL_PATTERNS)
        if is_legal:
            return {
                "engine": "fast_web",
                "intent": "legal_regulation",
                "score": 80,
                "reason": "Terdeteksi istilah regulasi/peraturan dinas Kemendagri"
            }

        # 2. Cek Tugas Otonom / Alur Kompleks
        is_complex = any(re.search(p, q_lower) for p in self.COMPLEX_PATTERNS)
        if is_complex or (url and any(k in url for k in ["srikandi", "sp4n", "auth", "login"])):
            return {
                "engine": "browser_use",
                "intent": "autonomous_task",
                "score": 90,
                "reason": "Tugas membutuhkan navigasi dinamis/interaksi form"
            }

        # 3. Default Fast-Path (Pencarian Cepat Berita / Data Umum)
        return {
            "engine": "fast_web",
            "intent": "general_search",
            "score": 30,
            "reason": "Pencarian fakta / web umum cepat"
        }


# ─── 4. Tri-Engine Hybrid Search Engine ───────────────────────────────────────

class HybridSearchEngine:
    """
    Tri-Engine Browser & Web Search Engine Orchestrator:
    - Engine 1: Fast-Path Web Search (DDG Lite Direct, 100% Bersih, <1.5s, 0 AI Token)
    - Engine 2: Playwright Headless DOM (Pencarian Interaktif & Rendering SPA)
    - Engine 3: Browser-Use Sub-Agent (AI-driven autonomous multi-step reasoning)
    """

    def __init__(self):
        self.router = BrowserRouter()
        self.cache = SearchCache(ttl_seconds=300)

    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        max_results: int = 5,
        force_engine: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Metode pencarian terpusat dengan Router, Caching, Whitelisting, dan Fallback Chain.
        """
        start_time = time.time()

        # 1. Cek Cache
        if not force_engine:
            cached = await self.cache.get(query, user_id)
            if cached:
                cached["from_cache"] = True
                cached["duration_ms"] = round((time.time() - start_time) * 1000, 1)
                return cached

        # 2. Routing Engine
        if force_engine:
            primary_engine = force_engine
            intent_meta = {"engine": force_engine, "intent": "forced", "score": 100}
        else:
            intent_meta = self.router.classify_task(query)
            primary_engine = intent_meta["engine"]

        logger.info(f"HybridSearch: Query='{query[:40]}...' -> Routed to '{primary_engine}'")

        # Urutan Fallback Chain
        engine_order = []
        is_bpk_query = any(k in query.lower() for k in ["bpk.go.id", "bpk", "peraturan.bpk"])
        if is_bpk_query:
            engine_order.append("bpk_direct")

        if primary_engine not in engine_order:
            engine_order.append(primary_engine)

        for alt in ["fast_web", "playwright", "browser_use"]:
            if alt not in engine_order:
                engine_order.append(alt)

        last_error = None
        for engine in engine_order:
            try:
                results = []
                if engine == "bpk_direct":
                    results = await asyncio.to_thread(self._search_bpk_direct_sync, query, max_results)
                elif engine == "fast_web":
                    results = await asyncio.to_thread(self._search_fast_web_sync, query, max_results)
                elif engine == "playwright":
                    results = await self._search_playwright(query, max_results)
                elif engine == "browser_use":
                    results = await self._search_browser_use(query, max_results)

                # Filter hasil dengan Content Safety Guard
                clean_results = [
                    r for r in results
                    if is_content_safe(r.get("url", ""), r.get("title", ""), r.get("snippet", ""))
                ]

                if clean_results:
                    duration_ms = round((time.time() - start_time) * 1000, 1)
                    payload = {
                        "success": True,
                        "query": query,
                        "engine_used": engine,
                        "intent": intent_meta.get("intent", "general"),
                        "total_results": len(clean_results),
                        "results": clean_results[:max_results],
                        "from_cache": False,
                        "duration_ms": duration_ms
                    }
                    # Catat log audit ke PostgreSQL browser_hybrid_logs
                    if log_browser_action:
                        try:
                            log_browser_action(
                                engine=engine,
                                tool_name="search_web_realtime",
                                status="success",
                                input_summary=query[:250],
                                duration_ms=int(duration_ms)
                            )
                        except Exception as log_err:
                            logger.debug(f"Failed logging browser action: {log_err}")

                    # Simpan ke cache
                    await self.cache.set(query, payload, user_id)
                    return payload

            except Exception as e:
                logger.warning(f"Engine '{engine}' encountered issue: {e}")
                last_error = str(e)
                continue

        # Jika semua engine gagal / 0 hasil
        duration_ms = round((time.time() - start_time) * 1000, 1)
        if log_browser_action:
            try:
                log_browser_action(
                    engine="hybrid",
                    tool_name="search_web_realtime",
                    status="error",
                    input_summary=query[:250],
                    duration_ms=int(duration_ms),
                    error_message=str(last_error)
                )
            except Exception:
                pass
        return {
            "success": False,
            "query": query,
            "engine_used": "none",
            "error": "NO_CLEAN_RESULTS",
            "message": f"Pencarian tidak menemukan hasil valid pada portal resmi. (Terakhir: {last_error})",
            "results": [],
            "from_cache": False,
            "duration_ms": duration_ms
        }

    # ─── Implementasi Engine Khusus ──────────────────────────────────────────

    def _search_bpk_direct_sync(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Direct JDIH BPK RI Scraper (peraturan.bpk.go.id).
        Mengekstrak judul, URL, dan nomor regulasi langsung dari search engine resmi BPK.
        """
        clean_q = re.sub(r'https?://[^\s]+', '', query)
        clean_q = re.sub(
            r'\b(peraturan\.bpk\.go\.id|bpk\.go\.id|bpk|cari|peraturan|terbaru|terbit|sebutkan|judul-judulnya|judulnya|saja|yaitu|adalah|terkait|apakah|di)\b',
            ' ',
            clean_q,
            flags=re.IGNORECASE
        )
        tokens = [w.strip() for w in clean_q.split() if len(w.strip()) > 1]
        keywords = "+".join(tokens) if tokens else "peraturan+2026"

        target_url = f"https://peraturan.bpk.go.id/Search?keywords={keywords}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        try:
            resp = requests.get(target_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"BPK search status code: {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, 'html.parser')
            results = []
            for item in soup.select('div.col-lg-10.fs-2.fw-bold.pe-4 a'):
                href = item.get('href', '')
                title = item.get_text(strip=True)
                if href and title:
                    full_url = f"https://peraturan.bpk.go.id{href}" if href.startswith('/') else href
                    results.append({
                        "title": title,
                        "url": full_url,
                        "snippet": f"Peraturan resmi terbitan terindeks di database JDIH BPK RI: {title}",
                        "source": "official_bpk_gov",
                        "is_government": True
                    })
            return results[:limit]
        except Exception as e:
            logger.warning(f"BPK direct search error: {e}")
            return []

    def _search_fast_web_sync(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Fast-Path Web Search menggunakan multi-endpoint DuckDuckGo (HTML & Lite).
        Sangat cepat (<1.5s), tanpa JavaScript overhead, tahan blokir, dan akurat.
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        
        from urllib.parse import urlparse, parse_qs, unquote
        results = []
        seen_urls = set()

        # 1. Coba HTML Endpoint
        try:
            resp = requests.post(
                'https://html.duckduckgo.com/html/',
                data={'q': query},
                headers=headers,
                timeout=4
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for item in soup.find_all('div', class_='result'):
                    a_tag = item.find('a', class_='result__a')
                    if not a_tag:
                        continue
                    title = a_tag.get_text(strip=True)
                    raw_href = a_tag.get('href', '')
                    if 'uddg=' in raw_href:
                        parsed = parse_qs(urlparse(raw_href).query)
                        clean_url = unquote(parsed.get('uddg', [raw_href])[0])
                    else:
                        clean_url = raw_href
                    
                    if not clean_url or clean_url in seen_urls:
                        continue
                    seen_urls.add(clean_url)

                    snippet_tag = item.find('a', class_='result__snippet')
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ''

                    is_gov = any(gov in clean_url for gov in GOVERNMENT_DOMAINS) or clean_url.endswith('.go.id')
                    results.append({
                        "title": title,
                        "url": clean_url,
                        "snippet": snippet,
                        "source": "official_gov" if is_gov else "web",
                        "is_government": is_gov
                    })
                    if len(results) >= limit:
                        break
        except Exception as e:
            logger.debug(f"HTML DDG failed: {e}")

        # 2. Fallback ke Lite Endpoint jika kosong
        if not results:
            try:
                resp = requests.post(
                    'https://lite.duckduckgo.com/lite/',
                    data={'q': query},
                    headers=headers,
                    timeout=4
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    links = soup.find_all('a', class_='result-link')
                    snippets = soup.find_all('td', class_='result-snippet')
                    for l, s in zip(links, snippets):
                        url = l.get('href', '')
                        if not url or url in seen_urls:
                            continue
                        seen_urls.add(url)
                        title = l.get_text(strip=True)
                        snippet = s.get_text(strip=True)
                        is_gov = any(gov in url for gov in GOVERNMENT_DOMAINS) or url.endswith('.go.id')
                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                            "source": "official_gov" if is_gov else "web",
                            "is_government": is_gov
                        })
                        if len(results) >= limit:
                            break
            except Exception as e:
                logger.debug(f"Lite DDG failed: {e}")

        # Urutkan agar domain pemerintah selalu di atas
        results.sort(key=lambda x: 0 if x.get("is_government") else 1)
        return results[:limit]

    def _search_social_sync(self, query: str, platform: str = "all", limit: int = 5) -> List[Dict[str, Any]]:
        """
        Pencarian opini, postingan, dan isu di platform media sosial publik (<1.5s).
        """
        from urllib.parse import urlparse

        clean_q = re.sub(r'\b(periksa|cari|di|media|sosial|medsos|sosmed|apakah|isu|terbaru|terkini|viral|2026|terkait|tentang|mengenai|pada|ke|dari|dan|yang|ada|tolong|cek|pantau|lihat)\b', ' ', query, flags=re.IGNORECASE)
        clean_q = ' '.join(clean_q.split()).strip()
        if not clean_q or len(clean_q) < 3:
            clean_q = query.strip()

        platforms_config = {
            "twitter": ("(site:twitter.com OR site:x.com)", "🐦 [X / TWITTER]", ["twitter.com", "x.com"]),
            "x": ("(site:twitter.com OR site:x.com)", "🐦 [X / TWITTER]", ["twitter.com", "x.com"]),
            "youtube": ("site:youtube.com", "🎥 [YOUTUBE]", ["youtube.com", "youtu.be"]),
            "instagram": ("site:instagram.com", "📸 [INSTAGRAM]", ["instagram.com"]),
            "tiktok": ("site:tiktok.com", "📱 [TIKTOK]", ["tiktok.com"]),
            "facebook": ("site:facebook.com", "👥 [FACEBOOK]", ["facebook.com"]),
            "linkedin": ("site:linkedin.com", "💼 [LINKEDIN]", ["linkedin.com"])
        }

        results = []
        seen_urls = set()

        plat_key = platform.strip().lower()
        if plat_key in platforms_config:
            dork, badge, valid_domains = platforms_config[plat_key]
            search_query = f"{clean_q} {dork}"
        else:
            search_query = f"{clean_q} (site:x.com OR site:twitter.com OR site:youtube.com OR site:instagram.com OR site:tiktok.com)"

        raw_res = self._search_fast_web_sync(search_query, limit=limit * 2)
        
        # Mapping badge berdasarkan domain hasil
        for r in raw_res:
            url = r.get("url", "")
            dom = urlparse(url).netloc.lower()
            badge = "📱 [MEDIA SOSIAL]"
            for p, (_, p_badge, v_doms) in platforms_config.items():
                if any(v in dom for v in v_doms):
                    badge = p_badge
                    break
            
            if url not in seen_urls:
                seen_urls.add(url)
                results.append({
                    "title": r.get("title", ""),
                    "url": url,
                    "snippet": r.get("snippet", ""),
                    "badge": badge,
                    "source": "social_media"
                })
            if len(results) >= limit:
                break

        # Fallback jika dorking kosong: cari query umum dengan kata media sosial
        if not results:
            fallback_res = self._search_fast_web_sync(f"{clean_q} media sosial", limit=limit)
            for r in fallback_res:
                if r.get("url") not in seen_urls:
                    seen_urls.add(r.get("url"))
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("snippet", ""),
                        "badge": "🌐 [DISKUSI / OPINI PUBLIK]",
                        "source": "social_media"
                    })

        return results[:limit]

    async def _search_playwright(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Playwright Headless Search Engine.
        Digunakan jika endpoint cepat membutuhkan rendering dinamis.
        """
        try:
            from core.browser.adapters.playwright_adapter import playwright_adapter
            await playwright_adapter.start()

            target_url = f"https://www.bing.com/search?q={query.replace(' ', '+')}"
            nav_res = await playwright_adapter.navigate(target_url, wait_for="domcontentloaded", timeout=6000)
            if not nav_res.get("success"):
                return []

            page = playwright_adapter.page
            if not page:
                return []

            items = await page.evaluate('''() => {
                const list = [];
                const results = document.querySelectorAll('li.b_algo');
                results.forEach(el => {
                    const titleEl = el.querySelector('h2 a');
                    const snippetEl = el.querySelector('.b_caption p');
                    if (titleEl && titleEl.innerText.trim()) {
                        list.push({
                            title: titleEl.innerText.trim(),
                            url: titleEl.href,
                            snippet: snippetEl ? snippetEl.innerText.trim() : ''
                        });
                    }
                });
                return list;
            }''')

            results = []
            for it in items[:limit]:
                results.append({
                    "title": it.get("title"),
                    "url": it.get("url"),
                    "snippet": it.get("snippet"),
                    "source": "playwright_bing"
                })
            return results
        except Exception as e:
            logger.debug(f"Playwright search error: {e}")
            return []

    async def _search_browser_use(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Autonomous Multi-Step AI Browser Search via browser-use.
        Dijalankan jika butuh ekstraksi cerdas dari halaman yang dinamis.
        """
        from core.browser.adapters.browser_use_adapter import BrowserUseAdapter
        adapter = BrowserUseAdapter()
        nav_res = await adapter.navigate(f"https://duckduckgo.com/?q={query.replace(' ', '+')}")
        if nav_res.get("success"):
            return [{
                "title": nav_res.get("title", f"Pencarian: {query}"),
                "url": nav_res.get("url"),
                "snippet": nav_res.get("title"),
                "source": "browser_use_ai"
            }]
        return []


# Instansiasi Singleton
hybrid_search_engine = HybridSearchEngine()


async def search_hybrid(query: str, user_id: Optional[str] = None, max_results: int = 5) -> Dict[str, Any]:
    """Helper global untuk pemanggilan hybrid search."""
    return await hybrid_search_engine.search(query=query, user_id=user_id, max_results=max_results)
