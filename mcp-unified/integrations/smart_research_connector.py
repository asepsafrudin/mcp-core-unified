"""
Smart Research Connector - Bypass Vane's slow URL scraping
Alur: SearxNG (snippet) → Groq API (synthesis) → Result with citations

Karena Vane terlalu lambat (scrape penuh tiap URL),
kita gunakan SearxNG+Groq secara langsung.
"""
import re
import requests
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

from core.secrets import load_runtime_secrets

# Domain yang diblokir (konten China tidak relevan untuk riset hukum Indonesia)
BLOCKED_DOMAINS = [
    "baidu.com", "zhidao.baidu.com", "zhihu.com", "weibo.com",
    "qq.com", "163.com", "sohu.com", "taobao.com", "jd.com"
]

# ================================
# CONFIG
# ================================
SEARXNG_URL = "http://localhost:8090"   # SearxNG dari dalam Vane (port 8090 di-expose)
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = os.environ.get("GROQ_MODEL", "qwen/qwen3-32b")  # model default

# Fallback model — qwen/qwen3-32b bisa diakses (error 400 bukan 403)
# Note: kita TIDAK pakai response_format jadi qwen support!
GROQ_FALLBACK_MODELS = [
    "qwen/qwen3-32b",
    "moonshotai/kimi-k2-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "groq/compound-mini",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]


class SmartResearchConnector:
    """
    Research connector untuk MCP Agent.
    Menggunakan SearxNG untuk pencarian web + Groq untuk sintesis.
    """

    def __init__(self, searxng_url: str = SEARXNG_URL, groq_key: str = GROQ_API_KEY):
        load_runtime_secrets()
        self.searxng_url = searxng_url
        self.groq_key = groq_key or os.environ.get("GROQ_API_KEY", "")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (MCP Research Agent)"
        })

    def _is_blocked_domain(self, url: str) -> bool:
        """Cek apakah URL berasal dari domain yang diblokir."""
        return any(domain in url for domain in BLOCKED_DOMAINS)

    def search_web(self, query: str, num_results: int = 8) -> List[Dict]:
        """Cari menggunakan SearxNG, kembalikan snippet (bukan full page content)."""
        try:
            resp = self.session.get(
                f"{self.searxng_url}/search",
                params={
                    "q": query,
                    "format": "json",
                    # Gunakan Google + Bing: lebih relevan untuk Indonesia
                    # Hindari Baidu (China) yang tidak relevan
                    "engines": "google,bing,duckduckgo,wikipedia",
                    "language": "id-ID",
                    "locale": "id",
                    "categories": "general",
                    "pageno": 1
                },
                timeout=20
            )
            data = resp.json()
            results = []
            for r in data.get("results", []):
                url = r.get("url", "")
                # Filter domain China
                if self._is_blocked_domain(url):
                    continue
                results.append({
                    "title": r.get("title", ""),
                    "url": url,
                    "snippet": r.get("content", ""),
                    "engine": r.get("engine", "")
                })
                if len(results) >= num_results:
                    break
            return results
        except Exception as e:
            print(f"SearxNG error: {e}")
            return []

    def synthesize(self, query: str, search_results: List[Dict],
                   model: str = None, system_prompt: str = None) -> Dict[str, Any]:
        """Kirim hasil pencarian ke Groq untuk disintesis."""
        if not model:
            model = GROQ_MODEL

        # Buat konteks dari snippets
        context_parts = []
        for i, r in enumerate(search_results, 1):
            context_parts.append(
                f"[{i}] {r['title']}\nURL: {r['url']}\nSnippet: {r['snippet']}"
            )
        context = "\n\n".join(context_parts)

        sys_prompt = system_prompt or (
            "Anda adalah asisten riset hukum yang ahli dalam regulasi Indonesia. "
            "Berikan jawaban komprehensif dan akurat berdasarkan sumber yang diberikan. "
            "Selalu sertakan nomor sitasi [1], [2], dst pada klaim penting. "
            "Gunakan Bahasa Indonesia yang formal dan mudah dipahami."
        )

        messages = [
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": (
                    f"Pertanyaan: {query}\n\n"
                    f"Sumber informasi:\n{context}\n\n"
                    f"Berikan jawaban berdasarkan sumber di atas dengan sitasi yang jelas."
                )
            }
        ]

        # Coba beberapa model sebagai fallback
        models_to_try = [model] + [m for m in GROQ_FALLBACK_MODELS if m != model]

        for m in models_to_try:
            try:
                resp = self.session.post(
                    GROQ_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": m,
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 2048
                    },
                    timeout=60
                )
                if resp.status_code == 200:
                    data = resp.json()
                    raw_answer = data["choices"][0]["message"]["content"]
                    # Strip <think>...</think> tags dari Qwen3/reasoning models
                    answer = re.sub(r'<think>.*?</think>', '', raw_answer,
                                    flags=re.DOTALL).strip()
                    return {
                        "success": True,
                        "answer": answer,
                        "model_used": m,
                        "sources": search_results,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    err = resp.json()
                    code = err.get("error", {}).get("code", "")
                    print(f"  [{m}] Error {resp.status_code}: {code}")
                    if code in ("model_permission_blocked_project", "model_not_found"):
                        continue  # coba model berikutnya
                    # error lain, stop
                    return {"success": False, "error": f"{resp.status_code}: {resp.text[:200]}"}
            except requests.Timeout:
                print(f"  [{m}] Timeout, mencoba model berikutnya...")
                continue
            except Exception as e:
                print(f"  [{m}] Exception: {e}")
                continue

        return {"success": False, "error": "Semua model gagal"}

    def research(self, query: str, num_results: int = 8,
                 system_prompt: str = None) -> Dict[str, Any]:
        """Full research pipeline: search → synthesize → return with citations."""
        print(f"🔍 Mencari: {query}")
        results = self.search_web(query, num_results)

        if not results:
            return {"success": False, "error": "SearxNG tidak mengembalikan hasil"}

        print(f"📄 {len(results)} hasil ditemukan, mensintesis dengan Groq...")
        return self.synthesize(query, results, system_prompt=system_prompt)


# ================================
# TEST LANGSUNG
# ================================
def test():
    conn = SmartResearchConnector()

    print("="*60)
    print("SMART RESEARCH CONNECTOR TEST")
    print("="*60)

    # Test 1: SearxNG
    print("\n[1] Test SearxNG...")
    results = conn.search_web("UU 23 tahun 2014 pemerintahan daerah", 5)
    if results:
        print(f"  ✅ {len(results)} hasil dari SearxNG")
        for r in results[:3]:
            print(f"  • {r['title'][:60]} ({r['url'][:50]})")
    else:
        print("  ❌ SearxNG gagal")
        return

    # Test 2: Full research
    print("\n[2] Full Research (SearxNG + Groq)...")
    result = conn.research(
        query="6 urusan pemerintahan wajib berkaitan pelayanan dasar menurut UU 23 tahun 2014"
    )

    if result.get("success"):
        print(f"\n✅ BERHASIL! Model: {result['model_used']}")
        print(f"\n📝 JAWABAN ({len(result['answer'])} karakter):")
        print(result['answer'][:1000])
        print(f"\n🔗 SUMBER ({len(result['sources'])}):")
        for i, s in enumerate(result['sources'][:5], 1):
            print(f"  [{i}] {s['title'][:60]}")
            print(f"       {s['url']}")
    else:
        print(f"❌ Gagal: {result.get('error')}")


if __name__ == "__main__":
    test()
