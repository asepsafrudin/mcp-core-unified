"""
srikandi_rag_connector.py — SRIKANDI Vector & RAG Knowledge Connector for SATRIA WhatsApp Co-Pilot.

Menghubungkan 1.288 Vektor Chunks Naskah & Lampiran SRIKANDI (Model nomic-embed-text 768-Dimensi)
langsung ke ekosistem Asisten Ahli Madya SATRIA di WhatsApp.
"""

import os
import sys
import json
import sqlite3
import urllib.request
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("satria_srikandi_rag")

DB_PATH = Path('/home/aseps/MCP/storage/admin_data/srikandi_korespondensi.db')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'nomic-embed-text')
NAMESPACE = 'srikandi_korespondensi'


def get_embedding(text: str) -> List[float]:
    """Menghasilkan embedding 768 dimensi via Ollama nomic-embed-text."""
    try:
        clean_text = " ".join(text.split())[:2000]
        payload = json.dumps({
            "model": EMBEDDING_MODEL,
            "prompt": clean_text
        }).encode("utf-8")
        
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return res.get("embedding", [])
    except Exception as e:
        logger.error(f"Error generating embedding in srikandi_rag_connector: {e}")
        return []


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Menghitung kemiripan kosinus antara 2 vektor."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = sum(a * a for a in v1) ** 0.5
    norm2 = sum(b * b for b in v2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def search_srikandi_rag(query: str, top_k: int = 3, threshold: float = 0.55) -> List[Dict[str, Any]]:
    """
    Melakukan pencarian semantik terhadap 1.288 vektor chunks SRIKANDI.
    """
    if not DB_PATH.exists():
        logger.warning(f"Database SRIKANDI {DB_PATH} tidak ditemukan.")
        return []

    q_emb = get_embedding(query)
    if not q_emb:
        return []

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        cur = conn.cursor()
        
        cur.execute('''
            SELECT id, nomor_naskah, perihal, tanggal_naskah, pengirim, filename, local_path, chunk_text, embedding_json
            FROM srikandi_vector_index
            WHERE namespace = ?
        ''', (NAMESPACE,))
        
        rows = cur.fetchall()
        scored = []
        
        for r in rows:
            chunk_id, nomor, perihal, tgl, pengirim, fname, lpath, ctext, emb_json = r
            try:
                emb = json.loads(emb_json)
                sim = cosine_similarity(q_emb, emb)
                if sim >= threshold:
                    scored.append((sim, {
                        "id": chunk_id,
                        "nomor_naskah": nomor,
                        "perihal": perihal,
                        "tanggal_naskah": tgl,
                        "pengirim": pengirim,
                        "filename": fname,
                        "local_path": lpath,
                        "text": ctext,
                        "similarity": round(sim, 4)
                    }))
            except Exception:
                pass

        scored.sort(key=lambda x: x[0], reverse=True)
        conn.close()
        
        return [item[1] for item in scored[:top_k]]
    except Exception as e:
        logger.error(f"Error querying srikandi_vector_index: {e}")
        return []


def format_srikandi_for_whatsapp(results: List[Dict[str, Any]], query: str) -> str:
    """
    Memformat hasil temuan semantik SRIKANDI ke dalam gaya khas eksekutif SATRIA WhatsApp.
    """
    if not results:
        return f"⚠️ *SATRIA SRIKANDI Knowledge*: Tidak ditemukan naskah dinas atau regulasi yang cocok dengan kueri _{query}_ pada repositori SRIKANDI."

    output = [
        f"🏛️ *HASIL PENELUSURAN NASKAH DINAS SRIKANDI — SATRIA*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🔍 *Kueri Pencarian*: _{query}_",
        f"📚 *Basis Pengetahuan*: 265 Naskah Induk & 395 Berkas Lampiran (1.288 Vektor Chunks)",
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]

    for idx, doc in enumerate(results, 1):
        stars = "⭐⭐⭐⭐⭐" if doc["similarity"] >= 0.70 else "⭐⭐⭐⭐" if doc["similarity"] >= 0.62 else "⭐⭐⭐"
        output.append(f"📌 *Dokumen #{idx}* (Skor Relevansi: `{doc['similarity']}` {stars})")
        output.append(f"   • *Nomor Naskah* : `{doc['nomor_naskah'] or '-'}`")
        output.append(f"   • *Perihal*      : *{doc['perihal'] or '-'}*")
        output.append(f"   • *Tanggal*      : {doc['tanggal_naskah'] or '-'}")
        output.append(f"   • *Asal/Pengirim*: {doc['pengirim'] or 'Ditjen Bina Pembangunan Daerah'}")
        if doc.get('filename') and doc['filename'] != 'METADATA_INDUK':
            output.append(f"   • *Berkas Lampiran*: `{doc['filename']}`")

        # Format snippet isi teks
        raw_text = doc.get("text", "")
        clean_lines = [
            l.strip() for l in raw_text.split("\n") 
            if l.strip() and not l.startswith("[") and not l.startswith("Nomor") 
            and not l.startswith("Perihal") and not l.startswith("Tanggal") 
            and not l.startswith("Pengirim") and not l.startswith("Isi Ringkas")
            and not l.startswith("Nama Berkas") and not l.startswith("Bagian Chunk")
            and not l.startswith("Isi Teks") and not l.startswith("Isi Dokumen")
        ]
        snippet = " ".join(clean_lines)[:260]
        if snippet:
            output.append(f"   • *Kutipan Naskah*:\n     _{snippet}..._")
        
        output.append(f"────────────────────────")

    output.append(f"\n💡 _Dihubungkan secara otomatis melalui SATRIA AI Orchestrator & MCP Universal Hub._")
    return "\n".join(output)
