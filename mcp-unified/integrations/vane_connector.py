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
SEARXNG_URL  = os.environ.get("SEARXNG_URL",  "http://localhost:8091")
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
    Connector utama untuk riset dengan AI.
    Digunakan oleh ResearchAgent dan LegalAgent di MCP Unified.
    
    Mendukung 3-Tier LLM Synthesis Fallback:
      Tier 1: Groq Cloud API (Ultra-fast, ~1-3s)
      Tier 2: RunPod GPU vLLM Serverless (~2-5s)
      Tier 3: Local Ollama (~3-8s)
    """

    def __init__(
        self,
        searxng_url:        str = SEARXNG_URL,
        groq_key:           str = GROQ_API_KEY,
        model:              str = GROQ_MODEL,
        runpod_endpoint_id: Optional[str] = None,
        runpod_api_key:     Optional[str] = None,
        runpod_model:       Optional[str] = None,
        ollama_url:         Optional[str] = None,
        ollama_model:       Optional[str] = None,
    ):
        load_runtime_secrets()
        self.searxng_url      = searxng_url or os.getenv("SEARXNG_URL", "http://localhost:8091")
        self.groq_key         = groq_key or os.getenv("GROQ_API_KEY", "")
        self.model            = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        
        self.runpod_endpoint  = (runpod_endpoint_id or os.getenv("RUNPOD_VLLM_VISION_ENDPOINT_ID") or os.getenv("RUNPOD_ENDPOINT_ID") or RUNPOD_DEFAULT_ENDPOINT).strip()
        self.runpod_key       = (runpod_api_key or os.getenv("RUNPOD_VLLM_API_KEY") or os.getenv("RUNPOD_API_KEY", "")).strip()
        self.runpod_model     = (runpod_model or os.getenv("RUNPOD_VLLM_MODEL", RUNPOD_DEFAULT_MODEL)).strip()

        self.ollama_url       = (ollama_url or os.getenv("OLLAMA_URL", OLLAMA_DEFAULT_URL)).strip()
        self.ollama_model     = (ollama_model or os.getenv("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)).strip()

        self.session          = requests.Session()
        self.session.headers.update({
            "User-Agent": "MCP-Research-Agent/1.0"
        })

    def _is_blocked(self, url: str) -> bool:
        return any(d in url for d in BLOCKED_DOMAINS)

    def _strip_think_tags(self, text: str) -> str:
        """Strip <think>...</think> dari output reasoning model (Qwen, DeepSeek, dll)."""
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
    # SYNTHESIS PROVIDERS (Groq -> RunPod -> Ollama)
    # ----------------------------------------------------------
    def _synthesize_groq(
        self,
        messages: List[Dict],
        target_model: str,
        temperature: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        """Tier 1: Sintesis via Groq Cloud API."""
        if not self.groq_key:
            return None

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
                        "temperature": temperature,
                        "max_tokens":  2048,
                    },
                    timeout=25,
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

        return None

    def _synthesize_runpod(self, messages: List[Dict]) -> Optional[Dict[str, Any]]:
        """Tier 2: Sintesis fallback via RunPod vLLM GPU Serverless."""
        if not self.runpod_key or not self.runpod_endpoint:
            return None

        api_url = f"https://api.runpod.ai/v2/{self.runpod_endpoint}/openai/v1/chat/completions"
        try:
            resp = self.session.post(
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
                timeout=45,
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

        return None

    def _synthesize_ollama(self, messages: List[Dict]) -> Optional[Dict[str, Any]]:
        """Tier 3: Sintesis fallback via Ollama lokal."""
        try:
            resp = self.session.post(
                f"{self.ollama_url}/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "model":       self.ollama_model,
                    "messages":    messages,
                    "temperature": 0.2,
                    "max_tokens":  2048,
                },
                timeout=30,
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

        return None

    def synthesize(
        self,
        query:          str,
        search_results: List[Dict],
        system_prompt:  Optional[str] = None,
        model:          Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Kirim hasil pencarian ke engine AI untuk disintesis menjadi jawaban dengan sitasi.
        Secara otomatis mencoba Groq -> RunPod GPU -> Ollama Lokal.
        """
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

        # 1. Tier 1: Groq Cloud API
        res = self._synthesize_groq(messages, target_model)
        if res:
            return {
                "success":    True,
                "answer":     res["answer"],
                "model_used": res["model_used"],
                "sources":    search_results,
                "timestamp":  datetime.now().isoformat(),
            }

        # 2. Tier 2: RunPod GPU vLLM Serverless
        res = self._synthesize_runpod(messages)
        if res:
            return {
                "success":    True,
                "answer":     res["answer"],
                "model_used": res["model_used"],
                "sources":    search_results,
                "timestamp":  datetime.now().isoformat(),
            }

        # 3. Tier 3: Local Ollama
        res = self._synthesize_ollama(messages)
        if res:
            return {
                "success":    True,
                "answer":     res["answer"],
                "model_used": res["model_used"],
                "sources":    search_results,
                "timestamp":  datetime.now().isoformat(),
            }

        return {"success": False, "error": "Semua provider sintesis AI (Groq, RunPod, Ollama) gagal atau tidak dapat diakses."}

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

    def synthesize_6_dimensions(
        self,
        title: str,
        metadata: Optional[Dict[str, Any]] = None,
        extracted_text: Optional[str] = None,
        context_notes: Optional[str] = None,
        cross_references: Optional[List[Dict[str, str]]] = None,
        related_laws: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Sintesis Analisis Yuridis Komprehensif berbasis Standar Baku 6 Dimensi
        Evaluasi Peraturan Perundang-undangan (Pedoman BPHN No. PHN-HN.01.03-07).

        Versi 2.0 — menutup 4 gap dari bedah logika dokumen referensi BPHN 2024:
          Gap 1: Pre-Analysis Layer — peta isu krusial & politik hukum wajib
                 disusun SEBELUM masuk analisis per-dimensi.
          Gap 2: Tabel Persandingan — norma lama vs baru (wajib bila related_laws tersedia).
          Gap 3: Cross-Reference Pasal — setiap dimensi wajib menyebut min. 2-3 referensi
                 dari cross_references yang diberikan.
          Gap 4: Empirical Layer Dimensi 6 — analisis cost-benefit & data lapangan,
                 bukan sekadar deskripsi normatif.

        Args:
            title:            Judul/nama peraturan yang dianalisis.
            metadata:         Metadata regulasi (jenis, nomor, tahun, instansi, dll).
            extracted_text:   Kutipan teks dokumen asli (konsiderans & pasal pokok).
            context_notes:    Catatan kontekstual tambahan dari caller.
            cross_references: Dokumen/pasal referensi yang diberikan user untuk
                              cross-check. Format:
                              [{'title': 'UU No.32/2009 Pasal 22',
                                'content': 'teks pasal atau ringkasan...'}]
            related_laws:     Daftar UU/PP terkait untuk membangun tabel persandingan.
                              Contoh: ['UU No.11/2020 tentang Cipta Kerja',
                                       'PP No.22/2021 tentang Penyelenggaraan PPLH']

        Returns:
            Dict berisi:
              success (bool), title, analysis_6d (str hasil analisis),
              model_used, timestamp, cross_references_used (int),
              related_laws (list), analysis_version (str)

        Dimensi Analisis:
          0. Pra-Analisis: Politik Hukum & Isu Krusial  [GAP-1 BARU]
          1. Dimensi Pancasila
          2. Dimensi Ketepatan Jenis PUU
          3. Dimensi Potensi Disharmoni Pengaturan       [GAP-2 BARU: Tabel Persandingan]
          4. Dimensi Kejelasan Rumusan
          5. Dimensi Kesesuaian Asas Bidang Hukum
          6. Dimensi Efektivitas Pelaksanaan             [GAP-4 BARU: Empirical]
          7. Rekomendasi Yuridis Final                   [GAP-3 BARU: Cross-ref wajib]
        """
        meta     = metadata or {}
        meta_str = (
            "\n".join(f"- **{k}:** {v}" for k, v in meta.items() if v)
            or "- Tidak ada metadata spesifik"
        )
        # Batasi panjang teks agar tidak overflow context window
        text_snippet = (extracted_text or "")[:3000]

        # -------------------------------------------------------
        # SYSTEM PROMPT v2.0 — menutup 4 gap
        # -------------------------------------------------------
        system_prompt = (
            "Anda adalah Analis Hukum Senior di Pusat Analisis dan Evaluasi Hukum Nasional "
            "(BPHN, Kemenkumham RI) dan Perancang Peraturan Perundang-undangan berpengalaman. "
            "Anda WAJIB mengikuti metodologi resmi Pedoman Evaluasi Peraturan Perundang-undangan BPHN "
            "Nomor PHN-HN.01.03-07 Tahun 2020 (Standar 6 Dimensi) dengan presisi tinggi.\n\n"

            # ── INSTRUKSI UMUM KUALITAS ─────────────────────────────────
            "INSTRUKSI UMUM:\n"
            "1. Output HARUS mengikuti urutan seksi yang ditetapkan di bawah ini tanpa terkecuali.\n"
            "2. Setiap temuan WAJIB disertai dasar hukum atau referensi pasal yang konkret.\n"
            "   Format sitasi: (ref. Pasal X UU Y) atau ([REF-N] bila dari dokumen yang diberikan).\n"
            "3. Setiap dimensi WAJIB menyertakan minimum 2-3 cross-reference pasal dari \n"
            "   dokumen referensi yang diberikan di bawah (bila tersedia). [GAP-3]\n"
            "4. Gunakan pola penalaran berlapis: \n"
            "   Normatif-Hierarkis → Komparatif-Temporal → Teleologis → Empiris.\n"
            "5. Hindari generalisasi. Tajam, spesifik, dan berbasis data/norma.\n\n"

            # ── SEKSI 0: PRA-ANALISIS (GAP-1) ──────────────────────────
            "### 0. 🗺️ Pra-Analisis: Politik Hukum & Isu Krusial [WAJIB — sebelum 6 Dimensi]\n"
            "Uraikan:\n"
            "  a) Teleologi pembentukan: mengapa regulasi ini ada? Apa masalah yang ingin diselesaikan?\n"
            "  b) Konteks historis-politis: apakah ada perubahan UU yang mempengaruhi regulasi ini?\n"
            "  c) Identifikasi 3–6 ISU KRUSIAL yang paling signifikan sebagai frame of reference \n"
            "     untuk analisis 6 dimensi berikutnya.\n"
            "  d) Posisi regulasi ini dalam ekosistem regulasi terkait (sebagai payung, \n"
            "     pelaksana, atau peraturan sektoral).\n\n"

            # ── DIMENSI 1 ───────────────────────────────────────────────
            "### 1. 🏛️ Dimensi Pancasila\n"
            "Nilai-nilai Pancasila sebagai pisau analisis (5 variabel):\n"
            "  - Ketuhanan: apakah norma menghormati nilai keagamaan dan moralitas?\n"
            "  - Kemanusiaan: perlindungan HAM, non-diskriminasi, martabat manusia.\n"
            "  - Persatuan: tidak menimbulkan disintegrasi atau diskriminasi antar daerah/kelompok.\n"
            "  - Kerakyatan: apakah melibatkan partisipasi publik yang bermakna?\n"
            "  - Keadilan Sosial: distribusi hak & kewajiban yang adil, akses layanan merata.\n"
            "Wajib cross-reference ke Pasal 28A-J UUD 1945 bila relevan.\n\n"

            # ── DIMENSI 2 ───────────────────────────────────────────────
            "### 2. ⚖️ Dimensi Ketepatan Jenis Peraturan Perundang-undangan\n"
            "Gunakan pendekatan HELICOPTER VIEW secara berurutan:\n"
            "  1) Judul: apakah mencerminkan materi muatan dengan tepat?\n"
            "  2) Konsideran Menimbang: apakah teleologi pembentukan jelas dan valid?\n"
            "  3) Dasar Hukum Mengingat: apakah dasar atribusi/delegasi wewenang tepat?\n"
            "  4) Batang Tubuh: apakah materi muatan sesuai jenis & hierarki (UU/PP/Permen)?\n"
            "  5) Penjelasan Umum & Lampiran: apakah konsisten dengan batang tubuh?\n"
            "Acuan: UU No. 12/2011 jo UU No. 15/2019 jo UU No. 13/2022.\n\n"

            # ── DIMENSI 3 (GAP-2: Tabel Persandingan) ──────────────────
            "### 3. 🔍 Dimensi Potensi Disharmoni Pengaturan\n"
            "Evaluasi 6 objek disharmoni:\n"
            "  1) Kewenangan  2) Hak  3) Kewajiban  4) Perlindungan  "
            "5) Penegakan Hukum  6) Definisi/Konsep\n"
            "Pendekatan: normatif komparatif — konflik vertikal, horizontal, dan sektoral.\n\n"
            "[GAP-2] JIKA terdapat peraturan pembanding (UU/PP terkait) yang diberikan:\n"
            "Wajib sajikan TABEL PERSANDINGAN dengan format:\n"
            "| Aspek/Norma | Peraturan Lama / Norma Asli | Peraturan Baru / Perubahan | Implikasi Disharmoni |\n"
            "Identifikasi pergeseran paradigma (contoh: dari ex-ante ke ex-post compliance).\n\n"

            # ── DIMENSI 4 ───────────────────────────────────────────────
            "### 4. 📝 Dimensi Kejelasan Rumusan\n"
            "Acuan wajib: Lampiran II UU No. 12/2011 (Petunjuk Legistik No. 62–69).\n"
            "Periksa:\n"
            "  - Sistematika umum-khusus: apakah pasal berurutan logis?\n"
            "  - Pilihan kata: lugas, pasti, tidak multitafsir.\n"
            "  - Konsistensi istilah di seluruh batang tubuh.\n"
            "  - Kejelasan subjek-objek hukum dan sanksi.\n"
            "  - Definisi yang cermat (tidak tumpang tindih dengan UU lain).\n\n"

            # ── DIMENSI 5 ───────────────────────────────────────────────
            "### 5. 📚 Dimensi Kesesuaian Asas Bidang Hukum\n"
            "Berdasarkan Pasal 6 ayat (2) UU No. 12/2011: setiap PUU harus memenuhi asas \n"
            "materiil khusus sesuai bidang hukumnya.\n"
            "Identifikasi dan evaluasi asas-asas domain spesifik yang relevan, misal:\n"
            "  - Bidang Lingkungan Hidup: precautionary principle, polluter pays, "
            "intergenerational equity, public participation.\n"
            "  - Bidang Pemerintahan: AUPB (kepastian hukum, ketidakberpihakan, "
            "proporsionalitas, akuntabilitas).\n"
            "  - Bidang Keuangan: transparansi, efisiensi, akuntabilitas anggaran.\n\n"

            # ── DIMENSI 6 (GAP-4: Empirical Layer) ─────────────────────
            "### 6. 🌐 Dimensi Efektivitas Pelaksanaan & Implikasi Pemda\n"
            "[GAP-4] Analisis ini WAJIB melampaui deskripsi normatif. Gunakan pendekatan empiris:\n"
            "  a) Daya Laku Sosiologis:\n"
            "     - Apakah target subyek hukum mampu mematuhi (kapasitas, sumber daya)?\n"
            "     - Apakah sanksi dan mekanisme enforcement realistis?\n"
            "  b) Analisis Cost-Benefit (Rasio Biaya-Manfaat):\n"
            "     - Beban kepatuhan: biaya implementasi oleh pemerintah & masyarakat.\n"
            "     - Manfaat yang diharapkan: apakah proporsional dengan beban?\n"
            "     - Bila data kuantitatif tidak tersedia, estimasi berdasarkan:\n"
            "       kompleksitas mandatory vs optional, resource requirement, "
            "monitoring complexity.\n"
            "  c) Kesiapan Institusi Daerah:\n"
            "     - SDM, anggaran, infrastruktur daerah yang diperlukan.\n"
            "     - Implikasi terhadap tata kelola & APBD daerah.\n"
            "  d) Hambatan Implementasi yang Teridentifikasi:\n"
            "     - Struktural, kapasitas, budaya hukum, tumpang tindih kewenangan.\n\n"

            # ── REKOMENDASI FINAL ───────────────────────────────────────
            "### 💡 Rekomendasi Yuridis Final\n"
            "Format rekomendasi WAJIB mengikuti 3 pilihan BPHN:\n"
            "  ✅ PERTAHANKAN — bila sudah sesuai 6 dimensi, tidak ada permasalahan signifikan.\n"
            "  ✏️ UBAH — bila ditemukan disharmoni, kekaburan rumusan, atau lemah efektivitas.\n"
            "     Sertakan: pasal/bagian yang perlu diubah + substansi perubahan yang disarankan.\n"
            "  ❌ CABUT — bila tidak relevan, redundan, atau bertentangan dengan UU lebih baru.\n"
            "Sertakan prioritas: SEGERA / JANGKA MENENGAH / JANGKA PANJANG.\n"
            "Bila diperlukan peraturan pelaksana daerah, sebutkan secara eksplisit."
        )

        # -------------------------------------------------------
        # USER CONTENT BUILDER
        # -------------------------------------------------------
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

        # Inject cross-references dan related_laws (Gap 3 & Gap 2)
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

        # -------------------------------------------------------
        # EKSEKUSI 3-TIER FALLBACK
        # -------------------------------------------------------
        # Tingkatkan max_tokens untuk output yang lebih komprehensif
        original_model = self.model
        res = self._synthesize_groq(messages, original_model)
        if not res:
            res = self._synthesize_runpod(messages)
        if not res:
            res = self._synthesize_ollama(messages)

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
