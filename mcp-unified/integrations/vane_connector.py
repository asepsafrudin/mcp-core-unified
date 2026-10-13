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
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import httpx

from core.secrets import load_runtime_secrets

logger = logging.getLogger(__name__)

# ============================================================
# KONFIGURASI DEFAULT & UPSTREAM ENDPOINTS
# ============================================================
VANE_API_URL = os.environ.get("VANE_API_URL", "http://localhost:3002")
SEARXNG_URL  = os.environ.get("SEARXNG_URL",  "http://localhost:8091")
EXA_API_URL  = "https://api.exa.ai/search"
EXA_API_KEY  = os.environ.get("EXA_API_KEY", "")
TAVILY_API_URL = "https://api.tavily.com/search"
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = os.environ.get("GROQ_MODEL",   "openai/gpt-oss-120b")

# Model fallback urutan prioritas pada Groq API
GROQ_FALLBACK_MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b",
    "groq/compound-mini",
    "openai/gpt-oss-20b",
    "groq/compound",
]

# RunPod vLLM Fallback
RUNPOD_DEFAULT_ENDPOINT = os.environ.get("RUNPOD_VLLM_VISION_ENDPOINT_ID") or os.environ.get("RUNPOD_ENDPOINT_ID") or "qi2tml56v6cf1p"
RUNPOD_DEFAULT_MODEL    = os.environ.get("RUNPOD_VLLM_MODEL", "qwen/qwen2.5-vl-7b-instruct")

# Ollama Fallback
OLLAMA_DEFAULT_URL   = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

# Domain yang diblokir (sumber China tidak relevan untuk riset hukum Indonesia)
BLOCKED_DOMAINS = [
    "baidu.com", "zhidao.baidu.com", "zhihu.com", "weibo.com",
    "qq.com", "163.com", "sohu.com", "taobao.com", "jd.com",
]


class VaneConnector:
    """
    Connector utama untuk riset dengan AI (Asinkron & Upstream Aligned).
    Digunakan oleh ResearchAgent dan LegalAgent di MCP Unified.
    
    Fitur Utama:
      - Upstream Vane Adapter: Mode 'speed', 'balanced', 'quality' via /api/search
      - Search Providers: Exa Neural Search / Tavily / SearxNG lokal
      - 3-Tier LLM Synthesis Fallback:
          Tier 1: Groq Cloud API (Ultra-fast, ~1-3s)
          Tier 2: RunPod GPU vLLM Serverless (~2-5s)
          Tier 3: Local Ollama (~3-8s)
      - Dual Support: Full Async native + Synchronous wrappers
    """

    def __init__(
        self,
        vane_api_url:       Optional[str] = None,
        searxng_url:        Optional[str] = None,
        groq_key:           Optional[str] = None,
        model:              Optional[str] = None,
        runpod_endpoint_id: Optional[str] = None,
        runpod_api_key:     Optional[str] = None,
        runpod_model:       Optional[str] = None,
        ollama_url:         Optional[str] = None,
        ollama_model:       Optional[str] = None,
        exa_key:            Optional[str] = None,
        tavily_key:         Optional[str] = None,
    ):
        load_runtime_secrets()
        self.vane_api_url     = (vane_api_url or os.getenv("VANE_API_URL", VANE_API_URL)).strip()
        self.searxng_url      = (searxng_url or os.getenv("SEARXNG_URL", SEARXNG_URL)).strip()
        self.groq_key         = (groq_key or os.getenv("GROQ_API_KEY", GROQ_API_KEY)).strip()
        self.model            = (model or os.getenv("GROQ_MODEL", GROQ_MODEL)).strip()
        
        self.runpod_endpoint  = (runpod_endpoint_id or os.getenv("RUNPOD_VLLM_VISION_ENDPOINT_ID") or os.getenv("RUNPOD_ENDPOINT_ID") or RUNPOD_DEFAULT_ENDPOINT).strip()
        self.runpod_key       = (runpod_api_key or os.getenv("RUNPOD_VLLM_API_KEY") or os.getenv("RUNPOD_API_KEY", "")).strip()
        self.runpod_model     = (runpod_model or os.getenv("RUNPOD_VLLM_MODEL", RUNPOD_DEFAULT_MODEL)).strip()

        self.ollama_url       = (ollama_url or os.getenv("OLLAMA_URL", OLLAMA_DEFAULT_URL)).strip()
        self.ollama_model     = (ollama_model or os.getenv("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)).strip()

        self.exa_key          = (exa_key or os.getenv("EXA_API_KEY", EXA_API_KEY)).strip()
        self.tavily_key       = (tavily_key or os.getenv("TAVILY_API_KEY", TAVILY_API_KEY)).strip()

    def _run_sync(self, coro):
        """Helper untuk menjalankan async coroutine dengan aman dari fungsi sinkron."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()

    def _is_blocked(self, url: str) -> bool:
        return any(d in url for d in BLOCKED_DOMAINS)

    def _strip_think_tags(self, text: str) -> str:
        """Strip <think>...</think> dari output reasoning model (Qwen, DeepSeek, dll)."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # ----------------------------------------------------------
    # UPSTREAM VANE NATIVE ADAPTER (/api/search)
    # ----------------------------------------------------------
    async def search_vane_native_async(
        self,
        query: str,
        mode: str = "speed",
        num_results: int = 8,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Panggil langsung Vane Next.js API (/api/search) dengan optimizationMode.
        Upstream Vane alignment (speed / balanced / quality).
        """
        if not self.vane_api_url:
            return None

        url = f"{self.vane_api_url.rstrip('/')}/api/search"
        payload = {
            "query": query,
            "optimizationMode": mode,
            "stream": False,
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MCP-Research-Agent/2.0"
        }

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=25.0)
            should_close = True

        try:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("message") or data.get("answer") or ""
                sources = data.get("sources") or []
                if answer:
                    return {
                        "success": True,
                        "answer": self._strip_think_tags(answer),
                        "model_used": f"vane-native:{mode}",
                        "sources": sources[:num_results],
                        "timestamp": datetime.now().isoformat(),
                    }
            else:
                logger.debug(f"Vane native API HTTP {resp.status_code}: {resp.text[:120]}")
        except Exception as e:
            logger.debug(f"Vane native API tidak merespons ({e}), fallback ke provider lain.")
        finally:
            if should_close:
                await client.aclose()

        return None

    # ----------------------------------------------------------
    # SEARCH PROVIDERS (SearxNG, Exa, Tavily)
    # ----------------------------------------------------------
    async def search_web_async(
        self,
        query: str,
        num_results: int = 8,
        engines: str = "google,bing,duckduckgo,wikipedia",
        client: Optional[httpx.AsyncClient] = None,
    ) -> List[Dict[str, str]]:
        """
        Cari web menggunakan SearxNG secara asinkron.
        Tidak melakukan full-page scraping (cepat).
        """
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=20.0)
            should_close = True

        try:
            resp = await client.get(
                f"{self.searxng_url.rstrip('/')}/search",
                params={
                    "q":          query,
                    "format":     "json",
                    "engines":    engines,
                    "language":   "id-ID",
                    "locale":     "id",
                    "categories": "general",
                    "pageno":     1,
                },
                headers={"User-Agent": "MCP-Research-Agent/2.0"},
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
        finally:
            if should_close:
                await client.aclose()

    def search_web(
        self,
        query: str,
        num_results: int = 8,
        engines: str = "google,bing,duckduckgo,wikipedia",
    ) -> List[Dict[str, str]]:
        """Wrapper sinkron untuk search_web_async."""
        return self._run_sync(self.search_web_async(
            query=query,
            num_results=num_results,
            engines=engines,
        ))

    async def search_exa_async(
        self,
        query: str,
        num_results: int = 8,
        client: Optional[httpx.AsyncClient] = None,
    ) -> List[Dict[str, str]]:
        """Neural Search via Exa API jika EXA_API_KEY dikonfigurasi."""
        if not self.exa_key:
            return []

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=20.0)
            should_close = True

        try:
            resp = await client.post(
                EXA_API_URL,
                headers={
                    "x-api-key": self.exa_key,
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "numResults": num_results,
                    "useAutoprompt": True,
                },
            )
            if resp.status_code == 200:
                raw_results = resp.json().get("results", [])
                results = []
                for r in raw_results:
                    url = r.get("url", "")
                    if self._is_blocked(url):
                        continue
                    results.append({
                        "title": r.get("title", ""),
                        "url": url,
                        "snippet": r.get("text", "")[:300],
                        "engine": "exa",
                    })
                return results
        except Exception as e:
            logger.warning(f"Exa search error: {e}")
        finally:
            if should_close:
                await client.aclose()

        return []

    async def search_tavily_async(
        self,
        query: str,
        num_results: int = 8,
        client: Optional[httpx.AsyncClient] = None,
    ) -> List[Dict[str, str]]:
        """Web search via Tavily API jika TAVILY_API_KEY dikonfigurasi."""
        if not self.tavily_key:
            return []

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=20.0)
            should_close = True

        try:
            resp = await client.post(
                TAVILY_API_URL,
                headers={"Content-Type": "application/json"},
                json={
                    "api_key": self.tavily_key,
                    "query": query,
                    "max_results": num_results,
                },
            )
            if resp.status_code == 200:
                raw_results = resp.json().get("results", [])
                results = []
                for r in raw_results:
                    url = r.get("url", "")
                    if self._is_blocked(url):
                        continue
                    results.append({
                        "title": r.get("title", ""),
                        "url": url,
                        "snippet": r.get("content", ""),
                        "engine": "tavily",
                    })
                return results
        except Exception as e:
            logger.warning(f"Tavily search error: {e}")
        finally:
            if should_close:
                await client.aclose()

        return []

    # ----------------------------------------------------------
    # SYNTHESIS PROVIDERS ASYNC (Groq -> RunPod -> Ollama)
    # ----------------------------------------------------------
    async def _synthesize_groq_async(
        self,
        messages: List[Dict],
        target_model: str,
        temperature: float = 0.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[Dict[str, Any]]:
        """Tier 1: Sintesis asinkron via Groq Cloud API."""
        if not self.groq_key:
            return None

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=25.0)
            should_close = True

        models_to_try = [target_model] + [
            m for m in GROQ_FALLBACK_MODELS if m != target_model
        ]

        try:
            for m in models_to_try:
                try:
                    resp = await client.post(
                        GROQ_API_URL,
                        headers={
                            "Authorization": f"Bearer {self.groq_key}",
                            "Content-Type":  "application/json",
                        },
                        json={
                            "model":       m,
                            "messages":    messages,
                            "temperature": temperature,
                            "max_tokens":  2048,
                        },
                    )
                    if resp.status_code == 200:
                        raw = resp.json()["choices"][0]["message"]["content"]
                        answer = self._strip_think_tags(raw)
                        logger.info(f"Sintesis Groq berhasil dengan model: {m}")
                        return {
                            "answer": answer,
                            "model_used": f"groq:{m}",
                        }
                    else:
                        err = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                        code = err.get("error", {}).get("code", "")
                        logger.warning(f"Groq [{m}] HTTP {resp.status_code}: {code}")
                        if resp.status_code == 401 or code == "invalid_api_key":
                            break
                        if code in ("model_permission_blocked_project", "model_not_found", "rate_limit_exceeded"):
                            continue
                except Exception as e:
                    logger.warning(f"Groq [{m}] Exception: {e}")
                    continue
        finally:
            if should_close:
                await client.aclose()

        return None

    def _synthesize_groq(
        self,
        messages: List[Dict],
        target_model: str,
        temperature: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        return self._run_sync(self._synthesize_groq_async(messages, target_model, temperature))

    async def _synthesize_runpod_async(
        self,
        messages: List[Dict],
        client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[Dict[str, Any]]:
        """Tier 2: Sintesis asinkron fallback via RunPod vLLM GPU Serverless."""
        if not self.runpod_key or not self.runpod_endpoint:
            return None

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=45.0)
            should_close = True

        api_url = f"https://api.runpod.ai/v2/{self.runpod_endpoint}/openai/v1/chat/completions"
        try:
            resp = await client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {self.runpod_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":       self.runpod_model,
                    "messages":    messages,
                    "temperature": 0.2,
                    "max_tokens":  2048,
                },
            )
            if resp.status_code == 200:
                raw = resp.json()["choices"][0]["message"]["content"]
                answer = self._strip_think_tags(raw)
                logger.info(f"Sintesis RunPod GPU berhasil: {self.runpod_model} @ {self.runpod_endpoint}")
                return {
                    "answer": answer,
                    "model_used": f"runpod:{self.runpod_model}@{self.runpod_endpoint}",
                }
            else:
                logger.warning(f"RunPod vLLM HTTP {resp.status_code}: {resp.text[:150]}")
        except Exception as e:
            logger.warning(f"RunPod vLLM exception: {e}")
        finally:
            if should_close:
                await client.aclose()

        return None

    def _synthesize_runpod(self, messages: List[Dict]) -> Optional[Dict[str, Any]]:
        return self._run_sync(self._synthesize_runpod_async(messages))

    async def _synthesize_ollama_async(
        self,
        messages: List[Dict],
        client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[Dict[str, Any]]:
        """Tier 3: Sintesis asinkron fallback via Ollama lokal."""
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=30.0)
            should_close = True

        try:
            resp = await client.post(
                f"{self.ollama_url.rstrip('/')}/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "model":       self.ollama_model,
                    "messages":    messages,
                    "temperature": 0.2,
                    "max_tokens":  2048,
                },
            )
            if resp.status_code == 200:
                raw = resp.json()["choices"][0]["message"]["content"]
                answer = self._strip_think_tags(raw)
                logger.info(f"Sintesis Ollama berhasil dengan model: {self.ollama_model}")
                return {
                    "answer": answer,
                    "model_used": f"ollama:{self.ollama_model}",
                }
        except Exception as e:
            logger.warning(f"Ollama fallback exception: {e}")
        finally:
            if should_close:
                await client.aclose()

        return None

    def _synthesize_ollama(self, messages: List[Dict]) -> Optional[Dict[str, Any]]:
        return self._run_sync(self._synthesize_ollama_async(messages))

    async def synthesize_async(
        self,
        query: str,
        search_results: List[Dict],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """
        Sintesis asinkron jawaban dengan sitasi dari hasil pencarian.
        Secara otomatis mencoba Groq -> RunPod GPU -> Ollama Lokal.
        """
        context = "\n\n".join(
            f"[{i}] {r.get('title', '')}\nURL: {r.get('url', '')}\nSnippet: {r.get('snippet', '')}"
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

        # 1. Tier 1: Groq Cloud API
        res = await self._synthesize_groq_async(messages, target_model, client=client)
        if res:
            return {
                "success":    True,
                "answer":     res["answer"],
                "model_used": res["model_used"],
                "sources":    search_results,
                "timestamp":  datetime.now().isoformat(),
            }

        # 2. Tier 2: RunPod GPU vLLM Serverless
        res = await self._synthesize_runpod_async(messages, client=client)
        if res:
            return {
                "success":    True,
                "answer":     res["answer"],
                "model_used": res["model_used"],
                "sources":    search_results,
                "timestamp":  datetime.now().isoformat(),
            }

        # 3. Tier 3: Local Ollama
        res = await self._synthesize_ollama_async(messages, client=client)
        if res:
            return {
                "success":    True,
                "answer":     res["answer"],
                "model_used": res["model_used"],
                "sources":    search_results,
                "timestamp":  datetime.now().isoformat(),
            }

        return {"success": False, "error": "Semua provider sintesis AI (Groq, RunPod, Ollama) gagal atau tidak dapat diakses."}

    def synthesize(
        self,
        query: str,
        search_results: List[Dict],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Wrapper sinkron untuk synthesize_async."""
        return self._run_sync(self.synthesize_async(
            query=query,
            search_results=search_results,
            system_prompt=system_prompt,
            model=model,
        ))

    # ----------------------------------------------------------
    # FULL RESEARCH PIPELINE (ASYNC & SYNC)
    # ----------------------------------------------------------
    async def research_async(
        self,
        query: str,
        num_results: int = 8,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        mode: str = "speed",
        client: Optional[httpx.AsyncClient] = None,
        use_vane_native: bool = True,
    ) -> Dict[str, Any]:
        """
        Pipeline riset asinkron lengkap:
          1. Coba Vane Native API jika aktif (/api/search dengan optimizationMode).
          2. Jika tidak aktif / gagal: Ambil data via Exa/Tavily/SearxNG -> 3-Tier Synthesis LLM.
        """
        logger.info(f"Research query async: {query!r} (mode={mode})")

        if use_vane_native and self.vane_api_url:
            native_res = await self.search_vane_native_async(
                query=query,
                mode=mode,
                num_results=num_results,
                client=client,
            )
            if native_res and native_res.get("success"):
                return native_res

        # Fallback / Direct search: Coba Exa -> Tavily -> SearxNG
        results = []
        if self.exa_key:
            results = await self.search_exa_async(query, num_results=num_results, client=client)
        if not results and self.tavily_key:
            results = await self.search_tavily_async(query, num_results=num_results, client=client)
        if not results:
            results = await self.search_web_async(query, num_results=num_results, client=client)

        if not results:
            return {"success": False, "error": "Mesin pencari tidak mengembalikan hasil"}

        return await self.synthesize_async(
            query=query,
            search_results=results,
            system_prompt=system_prompt,
            model=model,
            client=client,
        )

    def research(
        self,
        query: str,
        num_results: int = 8,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        mode: str = "speed",
        use_vane_native: bool = True,
    ) -> Dict[str, Any]:
        """Wrapper sinkron untuk research_async."""
        return self._run_sync(self.research_async(
            query=query,
            num_results=num_results,
            system_prompt=system_prompt,
            model=model,
            mode=mode,
            use_vane_native=use_vane_native,
        ))

    # ----------------------------------------------------------
    # 6 DIMENSI ANALISIS PRODUK HUKUM (STANDAR BPHN PHN-HN.01.03-07)
    # Versi 2.0 — Hasil Bedah Logika Dokumen Referensi BPHN 2024
    # Gap yang ditutup:
    #   Gap 1: Pre-Analysis Layer (isu krusial & politik hukum)
    #   Gap 2: Tabel Persandingan (norma lama vs baru)
    #   Gap 3: Cross-Reference Pasal (min 2-3 ref per dimensi)
    #   Gap 4: Empirical Layer Dimensi 6 (cost-benefit & data lapangan)
    # ----------------------------------------------------------

    def _build_persandingan_context(
        self,
        cross_references: List[Dict[str, str]],
        related_laws: List[str],
    ) -> str:
        """
        Bangun blok konteks cross-reference dan tabel persandingan
        dari dokumen referensi yang diberikan oleh user/caller.

        Args:
            cross_references: List dokumen referensi, masing-masing dict berisi
                              'title' (wajib) dan 'content' (isi/kutipan pasal, opsional).
            related_laws:     List nama UU/PP terkait untuk tabel persandingan.

        Returns:
            String blok konteks siap-inject ke user_content.
        """
        blocks: List[str] = []

        if cross_references:
            ref_lines = []
            for i, ref in enumerate(cross_references, 1):
                ref_title   = ref.get("title", f"Referensi-{i}")
                ref_content = ref.get("content", "").strip()
                # Potong panjang isi agar tidak membanjiri context window
                if len(ref_content) > 800:
                    ref_content = ref_content[:800] + "...[dipotong]"
                entry = f"[REF-{i}] {ref_title}"
                if ref_content:
                    entry += f":\n{ref_content}"
                ref_lines.append(entry)
            blocks.append(
                f"📎 DOKUMEN REFERENSI CROSS-CHECK ({len(cross_references)} dokumen):\n"
                + "\n\n".join(ref_lines)
            )

        if related_laws:
            laws_list = "\n".join(f"  • {law}" for law in related_laws)
            blocks.append(
                f"⚖️ PERATURAN TERKAIT UNTUK TABEL PERSANDINGAN:\n{laws_list}"
            )

        return "\n\n".join(blocks)

    async def synthesize_6_dimensions_async(
        self,
        title: str,
        metadata: Optional[Dict[str, Any]] = None,
        extracted_text: Optional[str] = None,
        context_notes: Optional[str] = None,
        cross_references: Optional[List[Dict[str, str]]] = None,
        related_laws: Optional[List[str]] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """
        Sintesis Analisis Yuridis Komprehensif berbasis Standar Baku 6 Dimensi (Async).
        Evaluasi Peraturan Perundang-undangan (Pedoman BPHN No. PHN-HN.01.03-07).
        """
        meta     = metadata or {}
        meta_str = (
            "\n".join(f"- **{k}:** {v}" for k, v in meta.items() if v)
            or "- Tidak ada metadata spesifik"
        )
        text_snippet = (extracted_text or "")[:3000]

        system_prompt = (
            "Anda adalah Analis Hukum Senior di Pusat Analisis dan Evaluasi Hukum Nasional "
            "(BPHN, Kemenkumham RI) dan Perancang Peraturan Perundang-undangan berpengalaman. "
            "Anda WAJIB mengikuti metodologi resmi Pedoman Evaluasi Peraturan Perundang-undangan BPHN "
            "Nomor PHN-HN.01.03-07 Tahun 2020 (Standar 6 Dimensi) dengan presisi tinggi.\n\n"
            "INSTRUKSI UMUM:\n"
            "1. Output HARUS mengikuti urutan seksi yang ditetapkan di bawah ini tanpa terkecuali.\n"
            "2. Setiap temuan WAJIB disertai dasar hukum atau referensi pasal yang konkret.\n"
            "   Format sitasi: (ref. Pasal X UU Y) atau ([REF-N] bila dari dokumen yang diberikan).\n"
            "3. Setiap dimensi WAJIB menyertakan minimum 2-3 cross-reference pasal dari \n"
            "   dokumen referensi yang diberikan di bawah (bila tersedia). [GAP-3]\n"
            "4. Gunakan pola penalaran berlapis: \n"
            "   Normatif-Hierarkis → Komparatif-Temporal → Teleologis → Empiris.\n"
            "5. Hindari generalisasi. Tajam, spesifik, dan berbasis data/norma.\n\n"
            "### 0. 🗺️ Pra-Analisis: Politik Hukum & Isu Krusial [WAJIB — sebelum 6 Dimensi]\n"
            "Uraikan:\n"
            "  a) Teleologi pembentukan: mengapa regulasi ini ada? Apa masalah yang ingin diselesaikan?\n"
            "  b) Konteks historis-politis: apakah ada perubahan UU yang mempengaruhi regulasi ini?\n"
            "  c) Identifikasi 3–6 ISU KRUSIAL yang paling signifikan sebagai frame of reference \n"
            "     untuk analisis 6 dimensi berikutnya.\n"
            "  d) Posisi regulasi ini dalam ekosistem regulasi terkait (sebagai payung, \n"
            "     pelaksana, atau peraturan sektoral).\n\n"
            "### 1. 🏛️ Dimensi Pancasila\n"
            "Nilai-nilai Pancasila sebagai pisau analisis (5 variabel):\n"
            "  - Ketuhanan: apakah norma menghormati nilai keagamaan dan moralitas?\n"
            "  - Kemanusiaan: perlindungan HAM, non-diskriminasi, martabat manusia.\n"
            "  - Persatuan: tidak menimbulkan disintegrasi atau diskriminasi antar daerah/kelompok.\n"
            "  - Kerakyatan: apakah melibatkan partisipasi publik yang bermakna?\n"
            "  - Keadilan Sosial: distribusi hak & kewajiban yang adil, akses layanan merata.\n"
            "Wajib cross-reference ke Pasal 28A-J UUD 1945 bila relevan.\n\n"
            "### 2. ⚖️ Dimensi Ketepatan Jenis Peraturan Perundang-undangan\n"
            "Gunakan pendekatan HELICOPTER VIEW secara berurutan:\n"
            "  1) Judul: apakah mencerminkan materi muatan dengan tepat?\n"
            "  2) Konsideran Menimbang: apakah teleologi pembentukan jelas dan valid?\n"
            "  3) Dasar Hukum Mengingat: apakah dasar atribusi/delegasi wewenang tepat?\n"
            "  4) Batang Tubuh: apakah materi muatan sesuai jenis & hierarki (UU/PP/Permen)?\n"
            "  5) Penjelasan Umum & Lampiran: apakah konsisten dengan batang tubuh?\n"
            "Acuan: UU No. 12/2011 jo UU No. 15/2019 jo UU No. 13/2022.\n\n"
            "### 3. 🔍 Dimensi Potensi Disharmoni Pengaturan\n"
            "Evaluasi 6 objek disharmoni:\n"
            "  1) Kewenangan  2) Hak  3) Kewajiban  4) Perlindungan  "
            "5) Penegakan Hukum  6) Definisi/Konsep\n"
            "Pendekatan: normatif komparatif — konflik vertikal, horizontal, dan sektoral.\n\n"
            "[GAP-2] JIKA terdapat peraturan pembanding (UU/PP terkait) yang diberikan:\n"
            "Wajib sajikan TABEL PERSANDINGAN dengan format:\n"
            "| Aspek/Norma | Peraturan Lama / Norma Asli | Peraturan Baru / Perubahan | Implikasi Disharmoni |\n"
            "Identifikasi pergeseran paradigma (contoh: dari ex-ante ke ex-post compliance).\n\n"
            "### 4. 📝 Dimensi Kejelasan Rumusan\n"
            "Acuan wajib: Lampiran II UU No. 12/2011 (Petunjuk Legistik No. 62–69).\n"
            "Periksa:\n"
            "  - Sistematika umum-khusus: apakah pasal berurutan logis?\n"
            "  - Pilihan kata: lugas, pasti, tidak multitafsir.\n"
            "  - Konsistensi istilah di seluruh batang tubuh.\n"
            "  - Kejelasan subjek-objek hukum dan sanksi.\n"
            "  - Definisi yang cermat (tidak tumpang tindih dengan UU lain).\n\n"
            "### 5. 📚 Dimensi Kesesuaian Asas Bidang Hukum\n"
            "Berdasarkan Pasal 6 ayat (2) UU No. 12/2011: setiap PUU harus memenuhi asas \n"
            "materiil khusus sesuai bidang hukumnya.\n"
            "Identifikasi dan evaluasi asas-asas domain spesifik yang relevan.\n\n"
            "### 6. 🌐 Dimensi Efektivitas Pelaksanaan & Implikasi Pemda\n"
            "[GAP-4] Analisis ini WAJIB melampaui deskripsi normatif. Gunakan pendekatan empiris:\n"
            "  a) Daya Laku Sosiologis: kemampuan subjek mematuhi dan efektivitas penegakan.\n"
            "  b) Analisis Cost-Benefit: rasio beban kepatuhan dengan manfaat publik.\n"
            "  c) Kesiapan Institusi Daerah: SDM, anggaran APBD, kelembagaan.\n"
            "  d) Hambatan Implementasi: struktural, koordinasi, tumpang tindih.\n\n"
            "### 💡 Rekomendasi Yuridis Final\n"
            "Format rekomendasi WAJIB mengikuti 3 pilihan BPHN:\n"
            "  ✅ PERTAHANKAN — bila sudah sesuai 6 dimensi, tidak ada permasalahan signifikan.\n"
            "  ✏️ UBAH — bila ditemukan disharmoni, kekaburan rumusan, atau lemah efektivitas.\n"
            "     Sertakan: pasal/bagian yang perlu diubah + substansi perubahan yang disarankan.\n"
            "  ❌ CABUT — bila tidak relevan, redundan, atau bertentangan dengan UU lebih baru.\n"
            "Sertakan prioritas: SEGERA / JANGKA MENENGAH / JANGKA PANJANG.\n"
            "Bila diperlukan peraturan pelaksana daerah, sebutkan secara eksplisit."
        )

        user_content = (
            f"PERATURAN YANG DIANALISIS:\n"
            f"Judul: **{title}**\n"
            f"Metadata Regulasi:\n{meta_str}\n"
        )

        if text_snippet:
            user_content += (
                f"\n📄 Kutipan Dokumen Asli (Konsiderans & Pasal Pokok — {len(text_snippet)} karakter):\n"
                f"{text_snippet}\n"
            )

        if context_notes:
            user_content += f"\n📌 Catatan Kontekstual:\n{context_notes}\n"

        xref_block = self._build_persandingan_context(
            cross_references or [],
            related_laws or [],
        )
        if xref_block:
            user_content += f"\n\n{xref_block}\n"

        user_content += (
            "\n---\n"
            "Susunlah analisis lengkap mulai dari Seksi 0 (Pra-Analisis) hingga "
            "Rekomendasi Yuridis Final. "
            "Pastikan setiap dimensi memuat cross-reference pasal yang konkret. "
            "Gunakan bahasa hukum yang formal, tajam, dan padat."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ]

        original_model = self.model
        res = await self._synthesize_groq_async(messages, original_model, client=client)
        if not res:
            res = await self._synthesize_runpod_async(messages, client=client)
        if not res:
            res = await self._synthesize_ollama_async(messages, client=client)

        if res and res.get("answer"):
            return {
                "success":               True,
                "title":                 title,
                "analysis_6d":           res["answer"],
                "model_used":            res["model_used"],
                "timestamp":             datetime.now().isoformat(),
                "cross_references_used": len(cross_references or []),
                "related_laws":          related_laws or [],
                "analysis_version":      "6D-v2.0-BPHN-PHN.01.03-07",
            }

        return {
            "success":           False,
            "error":            "Gagal melakukan sintesis 6 dimensi dengan seluruh tier model AI",
            "title":             title,
            "analysis_version": "6D-v2.0-BPHN-PHN.01.03-07",
        }

    def synthesize_6_dimensions(
        self,
        title: str,
        metadata: Optional[Dict[str, Any]] = None,
        extracted_text: Optional[str] = None,
        context_notes: Optional[str] = None,
        cross_references: Optional[List[Dict[str, str]]] = None,
        related_laws: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Wrapper sinkron untuk synthesize_6_dimensions_async."""
        return self._run_sync(self.synthesize_6_dimensions_async(
            title=title,
            metadata=metadata,
            extracted_text=extracted_text,
            context_notes=context_notes,
            cross_references=cross_references,
            related_laws=related_laws,
        ))

    # ----------------------------------------------------------
    # 7 PILAR DIM v2.0 SINTESIS ANALISIS REGULASI (TRACK A DITJEN PP & BANGDA)
    # ----------------------------------------------------------
    async def synthesize_7_pillars_async(
        self,
        title: str,
        draft_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context_notes: Optional[str] = None,
        cross_references: Optional[List[Dict[str, str]]] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """
        Sintesis Analisis Legislatif Berbasis Taksonomi 7 Pilar DIM v2.0 (Async).
        Standar Ditjen Pembangunan Daerah & Ditjen Peraturan Perundang-undangan (Ditjen PP).

        Pilar:
          1. Kewenangan & Yurisdiksi (Urusan Konkuren UU 23/2014 & Ultra Vires Check)
          2. Kelembagaan & Tata Kelola (OPD & Struktur Pelaksana)
          3. Hierarki Peraturan & Landasan Hukum (UU 12/2011 jo UU 13/2022)
          4. Personil & SDM Aparatur (PPNS & Pejabat Fungsional Perancang/Pengawas)
          5. Finansial, Beban Fiskal & APBD (Kepatuhan UU HKPD 1/2022 & Standar Biaya)
          6. Sarana Prasarana & Fasilitas Standar (SPBE & Infrastruktur Layanan Publik)
          7. Prosedur, Standar SPM & Penegakan (SOP & Sanksi Bertahap)
        Output dilengkapi MATRIKS DISPOSISI DIM (APPROVED, PARKING_LOT, ENCLAVE,
        ALTERNATIVE_VEHICLE, OUT_OF_SCOPE, FUTURE_AGENDA).
        """
        meta = metadata or {}
        meta_str = (
            "\n".join(f"- **{k}:** {v}" for k, v in meta.items() if v)
            or "- Tidak ada metadata spesifik"
        )
        text_snippet = (draft_text or "")[:3500]

        system_prompt = (
            "Anda adalah Tenaga Ahli Perancang Peraturan Perundang-undangan Senior (Ditjen PP, Kemenkumham RI) "
            "dan Analis Kebijakan Otonomi Daerah (Ditjen Bina Pembangunan Daerah, Kemendagri RI).\n"
            "Tugas Anda: Melakukan evaluasi rancangan regulasi / instrumen hukum berdasarkan "
            "TAKSONOMI 7 PILAR DAFTAR INVENTARISASI MASALAH (DIM) v2.0 secara tajam, berbobot, dan normatif.\n\n"
            "URUTAN OUTPUT WAJIB:\n"
            "### 1. 🏛️ Pilar 1: Kewenangan & Yurisdiksi (Ultra Vires Check)\n"
            "  - Pemetaan jenis urusan pemerintahan (Absolut / Konkuren Wajib Pelayanan Dasar / Wajib Non-Dasar / Pilihan / Umum) berdasarkan UU 23/2014.\n"
            "  - Verifikasi batas kewenangan pusat vs provinsi vs kabupaten/kota. Pastikan tidak ada norma yang ultra vires.\n\n"
            "### 2. 🏢 Pilar 2: Kelembagaan & Tata Kelola Perangkat Daerah\n"
            "  - Ketepatan penunjukan dinas/badan/satuan kerja perangkat daerah pelaksana.\n"
            "  - Hubungan kerja lintas sektor dan koordinasi vertikal/horizontal.\n\n"
            "### 3. ⚖️ Pilar 3: Hierarki Peraturan & Landasan Hukum\n"
            "  - Validasi asas hierarki UU No. 12/2011 jo UU No. 13/2022 (Pasal 7 & 8).\n"
            "  - Ketepatan atribusi/delegasi wewenang; hindari perbenturan dengan peraturan perundang-undangan yang lebih tinggi.\n\n"
            "### 4. 👥 Pilar 4: Personil & SDM Aparatur Pelaksana\n"
            "  - Ketersediaan formasi jabatan fungsional, PPNS, inspektur, atau aparat pengawas.\n"
            "  - Standar kompetensi dan integritas aparatur daerah yang diwajibkan.\n\n"
            "### 5. 💰 Pilar 5: Finansial, Beban Fiskal & Implikasi APBD\n"
            "  - Analisis beban anggaran dan sumber pembiayaan (APBD / DAK / DAU / DBH).\n"
            "  - Kesesuaian dengan UU No. 1/2022 tentang Hubungan Keuangan antara Pemerintah Pusat dan Pemerintahan Daerah (HKPD).\n\n"
            "### 6. 🏗️ Pilar 6: Sarana Prasarana & Fasilitas Standar (SPBE & Aset)\n"
            "  - Kebutuhan sistem informasi pemerintahan daerah (SIPD / SPBE nasional).\n"
            "  - Standar kelayakan sarana prasarana fisik/teknis minimal.\n\n"
            "### 7. 📋 Pilar 7: Prosedur, Standar SPM & Mekanisme Penegakan\n"
            "  - Kejelasan tahapan SOP, jangka waktu penerbitan izin/rekomendasi, transparansi pelayanan.\n"
            "  - Kepatuhan Standar Pelayanan Minimal (PP 2/2018) dan gradasi sanksi (teguran -> pembatasan -> pembekuan/pencabutan).\n\n"
            "### 📊 MATRIKS DISPOSISI DIM (Daftar Inventarisasi Masalah)\n"
            "Sajikan tabel DIM terstruktur dengan klasifikasi disposisi resmi:\n"
            "| No | Pasal / Frasa Kritis | Isu Yuridis & Catatan Kritis | Disposisi | Rekomendasi Rumusan Alternatif |\n"
            "Pilihan Disposisi Wajib:\n"
            "- APPROVED (Disetujui)\n"
            "- PARKING_LOT (Ditunda / Perlu Kajian Lanjutan)\n"
            "- ENCLAVE (Pindahkan ke Juknis/SOP Daerah)\n"
            "- ALTERNATIVE_VEHICLE (Atur di instrumen hukum lain yang lebih tepat)\n"
            "- OUT_OF_SCOPE (Keluarkan dari materi muatan / Di luar kewenangan)\n"
            "- FUTURE_AGENDA (Simpan untuk revisi Prolegda mendatang)"
        )

        user_content = (
            f"RANCANGAN PERATURAN YANG DIEVALUASI:\n"
            f"Judul: **{title}**\n"
            f"Metadata Regulasi:\n{meta_str}\n"
        )

        if text_snippet:
            user_content += (
                f"\n📄 Teks Rancangan Regulasi ({len(text_snippet)} karakter):\n"
                f"{text_snippet}\n"
            )

        if context_notes:
            user_content += f"\n📌 Catatan Pembahasan / Latar Belakang:\n{context_notes}\n"

        if cross_references:
            ref_lines = []
            for i, ref in enumerate(cross_references, 1):
                ref_title = ref.get("title", f"Referensi-{i}")
                ref_content = ref.get("content", "").strip()[:600]
                ref_lines.append(f"[REF-{i}] {ref_title}:\n{ref_content}")
            user_content += f"\n\n📎 Ketentuan Pembanding / Rujukan:\n" + "\n\n".join(ref_lines) + "\n"

        user_content += (
            "\n---\n"
            "Susun analisis komprehensif 7 Pilar DIM v2.0 secara lengkap dan diakhiri dengan "
            "Matriks Disposisi DIM yang memuat telaah per pasal/isu kritis."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ]

        original_model = self.model
        res = await self._synthesize_groq_async(messages, original_model, client=client)
        if not res:
            res = await self._synthesize_runpod_async(messages, client=client)
        if not res:
            res = await self._synthesize_ollama_async(messages, client=client)

        if res and res.get("answer"):
            return {
                "success":           True,
                "title":             title,
                "analysis_7pillars": res["answer"],
                "model_used":        res["model_used"],
                "timestamp":         datetime.now().isoformat(),
                "analysis_version":  "7Pillars-v2.0-DitjenPP-Bangda",
                "pillars_evaluated": 7,
            }

        return {
            "success":           False,
            "error":            "Gagal melakukan sintesis 7 pilar DIM dengan seluruh tier model AI",
            "title":             title,
            "analysis_version": "7Pillars-v2.0-DitjenPP-Bangda",
            "pillars_evaluated": 7,
        }

    def synthesize_7_pillars(
        self,
        title: str,
        draft_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context_notes: Optional[str] = None,
        cross_references: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Wrapper sinkron untuk synthesize_7_pillars_async."""
        return self._run_sync(self.synthesize_7_pillars_async(
            title=title,
            draft_text=draft_text,
            metadata=metadata,
            context_notes=context_notes,
            cross_references=cross_references,
        ))

    def format_for_knowledge_base(
        self,
        result: Dict[str, Any],
        namespace: str = "puu:regulasi:pencari"
    ) -> Dict[str, Any]:
        """
        Format hasil riset untuk disimpan ke MemForge / MCP Knowledge Base.
        Mengikuti taksonomi Zero-Leakage (AGENTS.md §5).
        """
        target_ns = normalize_research_namespace(namespace)
        sources_urls = [s["url"] for s in result.get("sources", []) if isinstance(s, dict) and s.get("url")]
        return {
            "title":     f"Research: {result.get('query', 'Untitled')}",
            "content":   result.get("answer", ""),
            "namespace": target_ns,
            "metadata": {
                "source":       "vane_smart_connector",
                "model":        result.get("model_used", ""),
                "sources_urls": sources_urls,
                "timestamp":    result.get("timestamp", datetime.now().isoformat()),
            },
        }

    async def save_to_memforge_async(
        self,
        result: Dict[str, Any],
        namespace: str = "puu:regulasi:pencari",
        importance: float = 0.8,
        agent_id: str = "puu:regulasi:pencari",
        memory_type: str = "observation",
    ) -> Dict[str, Any]:
        """
        Simpan hasil riset Vane ke MemForge Native (PostgreSQL pgvector / SQLite-vec).
        Secara otomatis memvalidasi taksonomi Zero-Leakage dan melakukan kuantisasi semantik.
        """
        target_ns = normalize_research_namespace(namespace)
        content = result.get("answer", "")
        if not content:
            return {"success": False, "error": "Tidak ada konten answer untuk disimpan"}

        query = result.get("query", "")
        if query and not content.startswith("Kueri"):
            content_to_save = f"Kueri Riset: {query}\n\nTemuan & Sintesis:\n{content}"
        else:
            content_to_save = content

        try:
            try:
                from tools.agent_memory_tools import agent_remember
            except ImportError:
                from mcp_unified.tools.agent_memory_tools import agent_remember

            remember_res = await agent_remember(
                namespace=target_ns,
                content=content_to_save,
                importance=importance,
                agent_id=agent_id,
                memory_type=memory_type,
            )

            status = remember_res.get("status")
            return {
                "success": status in ("stored", "updated") or remember_res.get("memory_id") is not None,
                "memory_id": remember_res.get("memory_id"),
                "namespace": target_ns,
                "importance": remember_res.get("importance", importance),
                "quantized_content": remember_res.get("quantized_content"),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Gagal menyimpan ke MemForge: {e}")
            return {
                "success": False,
                "error": str(e),
                "namespace": target_ns,
            }

    def save_to_memforge(
        self,
        result: Dict[str, Any],
        namespace: str = "puu:regulasi:pencari",
        importance: float = 0.8,
        agent_id: str = "puu:regulasi:pencari",
        memory_type: str = "observation",
    ) -> Dict[str, Any]:
        """Wrapper sinkron untuk save_to_memforge_async."""
        return self._run_sync(self.save_to_memforge_async(
            result=result,
            namespace=namespace,
            importance=importance,
            agent_id=agent_id,
            memory_type=memory_type,
        ))


def normalize_research_namespace(namespace: Optional[str]) -> str:
    """
    Normalisasi namespace riset hukum sesuai taksonomi resmi Ditjen PUU/Bangda (TASK-116 & AGENTS.md §5).
    Menjamin Zero-Leakage Policy:
      - 'legal_research_deep', 'default', None -> 'puu:regulasi:pencari'
      - 'puu:{domain}:{agent}' -> dipertahankan
      - 'shared_{domain}' -> dipertahankan
      - Lainnya -> 'shared_legal'
    """
    if not namespace or namespace.strip().lower() in ("legal_research_deep", "default", "legal"):
        return "puu:regulasi:pencari"

    ns = namespace.strip().lower()
    if ns.startswith("puu:") or ns.startswith("shared_"):
        return ns

    return "shared_legal"



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
