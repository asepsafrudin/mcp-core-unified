"""
Vane Connector - MCP Unified Integration
=========================================
Menghubungkan MCP Agent dengan kemampuan AI search:
  SearxNG (dari Vane Docker) → Groq API → Jawaban ter-sitasi

Arsitektur:
  Query → SearxNG (snippet only, ~5s) → Groq qwen3-32b (~5-10s) → Result+Citations

BUKAN menggunakan Vane's built-in /api/search (terlalu lambat karena full URL scraping).
Sebaliknya, kita bypass langsung ke komponen SearxNG + Groq secara terpisah.

Port yang digunakan:
  - SearxNG: localhost:8090 (exposed dari Vane container port 8080)
  - Groq API: https://api.groq.com (cloud)
  - Vane UI:  localhost:3000 (untuk config management)
"""

import re
import os
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime

from core.secrets import load_runtime_secrets

logger = logging.getLogger(__name__)

# ============================================================
# KONFIGURASI DEFAULT
# ============================================================
SEARXNG_URL  = os.environ.get("SEARXNG_URL",  "http://localhost:8090")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = os.environ.get("GROQ_MODEL",   "qwen/qwen3-32b")

# Model fallback urutan prioritas (qwen3 paling reliable di akun ini)
GROQ_FALLBACK_MODELS = [
    "qwen/qwen3-32b",
    "moonshotai/kimi-k2-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "groq/compound-mini",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

# Domain yang diblokir (sumber China tidak relevan untuk riset hukum Indonesia)
BLOCKED_DOMAINS = [
    "baidu.com", "zhidao.baidu.com", "zhihu.com", "weibo.com",
    "qq.com", "163.com", "sohu.com", "taobao.com", "jd.com",
]


class VaneConnector:
    """
    Connector utama untuk riset dengan AI.
    Digunakan oleh ResearchAgent dan LegalAgent di MCP Unified.
    
    Contoh penggunaan:
        connector = VaneConnector()
        result = connector.research("dasar hukum SPM bidang kesehatan")
        if result["success"]:
            print(result["answer"])
            for s in result["sources"]:
                print(s["url"])
    """

    def __init__(
        self,
        searxng_url: str = SEARXNG_URL,
        groq_key:    str = GROQ_API_KEY,
        model:       str = GROQ_MODEL,
    ):
        load_runtime_secrets()
        self.searxng_url = searxng_url
        self.groq_key    = groq_key or os.getenv("GROQ_API_KEY", "")
        self.model       = model
        self.session     = requests.Session()
        self.session.headers.update({
            "User-Agent": "MCP-Research-Agent/1.0"
        })

    def _is_blocked(self, url: str) -> bool:
        return any(d in url for d in BLOCKED_DOMAINS)

    def _strip_think_tags(self, text: str) -> str:
        """Strip <think>...</think> dari output reasoning model (Qwen3, dll)."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # ----------------------------------------------------------
    # SEARCH
    # ----------------------------------------------------------
    def search_web(
        self,
        query:       str,
        num_results: int = 8,
        engines:     str = "google,bing,duckduckgo,wikipedia",
    ) -> List[Dict[str, str]]:
        """
        Cari web menggunakan SearxNG dan kembalikan daftar snippet.
        Tidak melakukan full-page scraping (cepat).
        """
        try:
            resp = self.session.get(
                f"{self.searxng_url}/search",
                params={
                    "q":          query,
                    "format":     "json",
                    "engines":    engines,
                    "language":   "id-ID",
                    "locale":     "id",
                    "categories": "general",
                    "pageno":     1,
                },
                timeout=20,
            )
            resp.raise_for_status()
            raw = resp.json().get("results", [])
            results = []
            for r in raw:
                url = r.get("url", "")
                if self._is_blocked(url):
                    continue
                results.append({
                    "title":   r.get("title",   ""),
                    "url":     url,
                    "snippet": r.get("content", ""),
                    "engine":  r.get("engine",  ""),
                })
                if len(results) >= num_results:
                    break
            logger.info(f"SearxNG: {len(results)} hasil untuk '{query}'")
            return results
        except Exception as e:
            logger.error(f"SearxNG error: {e}")
            return []

    # ----------------------------------------------------------
    # SYNTHESIS via Groq
    # ----------------------------------------------------------
    def synthesize(
        self,
        query:          str,
        search_results: List[Dict],
        system_prompt:  Optional[str] = None,
        model:          Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Kirim hasil pencarian ke Groq untuk disintesis menjadi jawaban
        dengan sitasi. Tidak menggunakan response_format sehingga
        kompatibel dengan qwen/qwen3-32b.
        """
        if not self.groq_key:
            return {"success": False, "error": "GROQ_API_KEY tidak dikonfigurasi"}

        # Bangun konteks dari snippets
        context = "\n\n".join(
            f"[{i}] {r['title']}\nURL: {r['url']}\nSnippet: {r['snippet']}"
            for i, r in enumerate(search_results, 1)
        )

        sys_prompt = system_prompt or (
            "Anda adalah asisten riset hukum yang ahli dalam regulasi Indonesia. "
            "Berikan jawaban komprehensif dan akurat berdasarkan sumber yang diberikan. "
            "Selalu sertakan nomor sitasi [1], [2], dst pada klaim penting. "
            "Gunakan Bahasa Indonesia yang formal dan mudah dipahami. "
            "Jika sumber tidak mencukupi, nyatakan secara eksplisit."
        )

        messages = [
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": (
                    f"Pertanyaan: {query}\n\n"
                    f"Sumber informasi:\n{context}\n\n"
                    f"Berikan jawaban terstruktur dengan sitasi yang jelas."
                ),
            },
        ]

        target_model = model or self.model
        models_to_try = [target_model] + [
            m for m in GROQ_FALLBACK_MODELS if m != target_model
        ]

        for m in models_to_try:
            try:
                resp = self.session.post(
                    GROQ_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.groq_key}",
                        "Content-Type":  "application/json",
                    },
                    json={
                        "model":       m,
                        "messages":    messages,
                        "temperature": 0.2,
                        "max_tokens":  2048,
                    },
                    timeout=60,
                )
                if resp.status_code == 200:
                    raw = resp.json()["choices"][0]["message"]["content"]
                    answer = self._strip_think_tags(raw)
                    logger.info(f"Sintesis berhasil dengan model: {m}")
                    return {
                        "success":    True,
                        "answer":     answer,
                        "model_used": m,
                        "sources":    search_results,
                        "timestamp":  datetime.now().isoformat(),
                    }
                else:
                    err  = resp.json()
                    code = err.get("error", {}).get("code", "")
                    logger.warning(f"[{m}] {resp.status_code}: {code}")
                    if code in ("model_permission_blocked_project", "model_not_found"):
                        continue
                    return {"success": False, "error": f"{resp.status_code}: {resp.text[:200]}"}
            except requests.Timeout:
                logger.warning(f"[{m}] Timeout, mencoba model berikutnya")
                continue
            except Exception as e:
                logger.error(f"[{m}] Exception: {e}")
                continue

        return {"success": False, "error": "Semua model Groq gagal"}

    # ----------------------------------------------------------
    # FULL RESEARCH PIPELINE
    # ----------------------------------------------------------
    def research(
        self,
        query:          str,
        num_results:    int            = 8,
        system_prompt:  Optional[str]  = None,
        model:          Optional[str]  = None,
    ) -> Dict[str, Any]:
        """
        Pipeline riset lengkap: SearxNG → Groq synthesis → hasil dengan sitasi.
        
        Args:
            query:         Pertanyaan riset
            num_results:   Jumlah hasil SearxNG yang diambil (default: 8)
            system_prompt: Custom prompt untuk Groq (optional)
            model:         Override model Groq (optional)
            
        Returns:
            {
                "success": bool,
                "answer":  str,           # Jawaban tersintesis
                "model_used": str,        # Model yang berhasil digunakan
                "sources": [              # Sumber-sumber yang digunakan
                    {"title": ..., "url": ..., "snippet": ...}
                ],
                "timestamp": str
            }
        """
        logger.info(f"Research query: {query}")
        results = self.search_web(query, num_results)
        if not results:
            return {"success": False, "error": "SearxNG tidak mengembalikan hasil"}
        return self.synthesize(query, results, system_prompt=system_prompt, model=model)

    def format_for_knowledge_base(self, result: Dict[str, Any], namespace: str = "legal_research_deep") -> Dict:
        """Format hasil riset untuk disimpan ke MCP Knowledge Base."""
        return {
            "title":     f"Research: {result.get('query', 'Untitled')}",
            "content":   result.get("answer", ""),
            "namespace": namespace,
            "metadata": {
                "source":       "vane_smart_connector",
                "model":        result.get("model_used", ""),
                "sources_urls": [s["url"] for s in result.get("sources", [])],
                "timestamp":    result.get("timestamp", datetime.now().isoformat()),
            },
        }


# ============================================================
# QUICK TEST (jalankan langsung: python3 vane_connector.py)
# ============================================================
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    query = " ".join(sys.argv[1:]) or "6 urusan pemerintahan wajib pelayanan dasar UU 23 2014"
    print(f"\n{'='*60}")
    print(f"VaneConnector Quick Test")
    print(f"Query: {query}")
    print(f"{'='*60}\n")

    conn   = VaneConnector()
    result = conn.research(query)

    if result["success"]:
        print(f"✅ Model: {result['model_used']}")
        print(f"\n📝 JAWABAN:\n{result['answer']}")
        print(f"\n🔗 SUMBER ({len(result['sources'])}):")
        for i, s in enumerate(result["sources"][:5], 1):
            print(f"  [{i}] {s['title'][:60]}\n       {s['url']}")
    else:
        print(f"❌ Error: {result['error']}")
