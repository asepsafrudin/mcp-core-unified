import asyncio
import os
import sys
import json
from pathlib import Path

project_root = Path('/home/aseps/MCP/mcp-unified')
sys.path.insert(0, str(project_root))
from core.secrets import load_runtime_secrets

load_runtime_secrets()

from memory import longterm

async def setup_puu_knowledge_and_profiles():
    await longterm.initialize_db()
    
    group_id = "6281343733332-1606811696@g.us"
    
    # 1. Update Group Profile & Bot Identity
    group_prompt = """Identitas Bot: Anda adalah 'Asisten Substansi PUU', seorang supporting staff yang melayani grup 'Substansi Perundang-undangan'.
Profil Grup: Grup ini mewakili Bagian Perundang-undangan, Sekretariat Ditjen Bina Pembangunan Daerah, Kemendagri RI.
Tugas Bot: 
1. Melayani substansi perundang-undangan (pencarian aturan, analisis sederhana).
2. Manajemen dokumen grup (arsip file/link).
3. Administrasi grup.
Etika Umum: Gunakan bahasa yang sangat sopan, formal, dan hormat kepada pimpinan dan ketua tim. Hindari jawaban yang terlalu santai kecuali berbicara dengan pencipta bot (Mas Asep)."""

    await longterm.upsert_group_config(
        group_id=group_id,
        name="🌹Bagian PUU 🌹",
        system_prompt=group_prompt,
        settings={"is_official": True}
    )
    print("✅ Group config updated.")

    # 2. Register Members
    members = [
        {"id": "6281284631983@c.us", "name": "Ibu Lady Diana", "role": "Pimpinan Tertinggi", "ethics": "Sangat formal, gunakan gelar Pimpinan, respon cepat dan prioritas tinggi."},
        {"id": "6281343733332@c.us", "name": "Pak Faisal Baharuddin", "role": "Ketua Tim Penyusunan Produk Hukum", "ethics": "Formal dan profesional, fokus pada substansi produk hukum."},
        {"id": "6281584354128@c.us", "name": "Pak Sukma Adi Nugroho", "role": "Ketua Tim Dokumentasi dan Informasi Produk Hukum", "ethics": "Formal, fokus pada keakuratan data dokumen dan informasi."},
        {"id": "628111581083@c.us", "name": "Mbak Lucia Hapsari A.", "role": "Ketua Tim Advokasi Hukum", "ethics": "Sopan dan formal, fokus pada bantuan advokasi."},
        {"id": "6281574191868@c.us", "name": "Mas Romi Nugraha", "role": "Anggota Tim & Bendahara", "ethics": "Profesional, komunikatif mengenai administrasi keuangan."},
        {"id": "6285717066459@c.us", "name": "Mba Vania", "role": "Anggota Tim & Administrasi", "ethics": "Sopan, fokus pada ketertiban administrasi peraturan."},
        {"id": "6281288130530@c.us", "name": "Mas Amir Salim", "role": "Anggota Tim Advokasi", "ethics": "Sopan, bantu monitor pelaporan tanda terima dokumen/surat."},
        {"id": "6285717223889@c.us", "name": "Mas Asep Safrudin", "role": "Pencipta Bot & Anggota Tim Dokumentasi", "ethics": "Bisa sedikit lebih santai tapi tetap sopan, anda adalah pencipta saya."}
    ]

    for m in members:
        res = await longterm.upsert_member_profile(
            whatsapp_id=m["id"],
            name=m["name"],
            role=m["role"],
            ethics_notes=m["ethics"]
        )
        print(f"✅ Profile saved for {m['name']}: {res}")

if __name__ == "__main__":
    asyncio.run(setup_puu_knowledge_and_profiles())
