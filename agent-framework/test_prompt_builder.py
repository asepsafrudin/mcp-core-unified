import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.agent_framework.prompt_builder import (
    DynamicPromptBuilder,
    UserRbacProfile,
    RbacRole
)


class TestDynamicPromptBuilder(unittest.TestCase):

    def test_super_admin_prompt(self):
        admin_user = UserRbacProfile(
            user_id="asep_safrudin",
            full_name="Asep Safrudin, S.Kom",
            nip="198501012010011001",
            jabatan="Penata Layanan Operasional / Administrator",
            unit_kerja="Sekretariat Ditjen Bina Bangda",
            tim_kerja="Tata Usaha & Sistem Informasi",
            role=RbacRole.SUPER_ADMIN.value,
            permissions=["admin_manage", "full_audit"]
        )

        prompt = DynamicPromptBuilder.build_prompt(admin_user)
        self.assertIn("Asep Safrudin, S.Kom", prompt)
        self.assertIn("SUPER_ADMIN", prompt)
        self.assertIn("MICROSOFT AGENT FRAMEWORK", prompt)
        self.assertIn("WEWENANG SUPER ADMINISTRATOR", prompt)
        # Token efficiency check: should be under 4000 characters (~700 tokens)
        self.assertLess(len(prompt), 3500)

    def test_legal_analyst_prompt(self):
        legal_user = UserRbacProfile(
            user_id="lady_diana",
            full_name="Lady Diana, S.H., M.H.",
            nip="198303062008122001",
            jabatan="Analis Hukum Ahli Madya",
            unit_kerja="Sekretariat Ditjen Bina Bangda",
            tim_kerja="Subbag Peraturan Perundang-undangan",
            role=RbacRole.LEGAL_ANALYST.value,
            permissions=["legal_review", "drafting"]
        )

        prompt = DynamicPromptBuilder.build_prompt(
            user=legal_user,
            intent_type="evaluate_bphn_doctrine"
        )
        self.assertIn("Lady Diana, S.H., M.H.", prompt)
        self.assertIn("LEGAL_ANALYST", prompt)
        self.assertIn("WEWENANG ANALIS HUKUM & PUU", prompt)
        self.assertIn("FOKUS TUGAS: Telaah Yuridis Doktrin 6 Dimensi BPHN", prompt)

    def test_regional_support_prompt(self):
        supd_user = UserRbacProfile(
            user_id="ahmad_supd",
            full_name="Ahmad Fauzi, S.STP",
            nip="199002152012011002",
            jabatan="Analis Kebijakan Ahli Muda",
            unit_kerja="Direktorat Sinkronisasi Urusan Pemerintahan Daerah II",
            tim_kerja="Urusan Sosial & PMD",
            role=RbacRole.REGIONAL_SUPPORT.value,
            permissions=["regional_review"]
        )

        prompt = DynamicPromptBuilder.build_prompt(supd_user)
        self.assertIn("Ahmad Fauzi, S.STP", prompt)
        self.assertIn("REGIONAL_SUPPORT", prompt)
        self.assertIn("WEWENANG SINKRONISASI URUSAN DAERAH", prompt)
        self.assertIn("UU 23/2014", prompt)

    def test_office_staff_prompt(self):
        staff_user = UserRbacProfile(
            user_id="staff_persuratan",
            full_name="Siti Rahma",
            jabatan="Pengadministrasi Umum",
            unit_kerja="Bagian Umum / ULA",
            role=RbacRole.OFFICE_STAFF.value,
            permissions=["read_correspondence"]
        )

        prompt = DynamicPromptBuilder.build_prompt(
            user=staff_user,
            intent_type="cari_surat_korespondensi"
        )
        self.assertIn("Siti Rahma", prompt)
        self.assertIn("OFFICE_STAFF", prompt)
        self.assertIn("WEWENANG ADMINISTRASI PERSURATAN", prompt)
        self.assertIn("FOKUS TUGAS: Penelusuran Surat & Disposisi", prompt)

    def test_media_context_injection(self):
        user = UserRbacProfile(user_id="u1", full_name="User Test")
        prompt = DynamicPromptBuilder.build_prompt(
            user=user,
            attached_media_context="BERKAS: Ranperda RTRW Kab. Morowali 2026.pdf"
        )
        self.assertIn("KONTEKS DOKUMEN / LAMPIRAN AKTIF", prompt)
        self.assertIn("Ranperda RTRW Kab. Morowali 2026.pdf", prompt)

    def test_perancang_puu_persona(self):
        # Ahli Muda Track A (Ditjen PP)
        prompt_muda = DynamicPromptBuilder.build_legal_persona_prompt(
            persona_key="PERANCANG_PUU_AHLI_MUDA",
            intent_type="draft_peraturan_perda"
        )
        self.assertIn("Perancang PUU Ahli Muda (Substantive Drafter)", prompt_muda)
        self.assertIn("Ditjen PP Kemenkum", prompt_muda)
        self.assertIn("KAIDAH FORMULASI NORMA DEONTIK", prompt_muda)
        self.assertIn("SURUHAN: Gunakan kata 'wajib'", prompt_muda)
        self.assertIn("236 Kaidah Lampiran II UU 12/2011", prompt_muda)

        # Ahli Madya Track A (Harmonization Gatekeeper)
        prompt_madya = DynamicPromptBuilder.build_legal_persona_prompt(
            persona_key="PERANCANG_PUU_AHLI_MADYA",
            intent_type="harmonisasi_raperda_ditjen_pp"
        )
        self.assertIn("Perancang PUU Ahli Madya (Harmonization Gatekeeper)", prompt_madya)
        self.assertIn("Harmonisasi, Pembulatan, & Pemantapan Konsepsi", prompt_madya)
        self.assertIn("Pasal 58 UU 13/2022", prompt_madya)
        self.assertIn("Matriks Hasil Pengharmonisasian 5 Kolom", prompt_madya)

    def test_analis_hukum_persona(self):
        # Ahli Muda Track B (Legal Opinion IRAC & Contract Vetting)
        prompt_analis = DynamicPromptBuilder.build_legal_persona_prompt(
            persona_key="ANALIS_HUKUM_AHLI_MUDA",
            intent_type="legal_opinion_irac"
        )
        self.assertIn("Analis Hukum Ahli Muda (Legal Opinion & Contract Vetting)", prompt_analis)
        self.assertIn("BPHN Kemenkumham", prompt_analis)
        self.assertIn("METODOLOGI PENALARAN DEDUKTIF IRAC", prompt_analis)
        self.assertIn("ISSUE (Isu Hukum)", prompt_analis)
        self.assertIn("UJI AUPB & KEUANGAN NEGARA", prompt_analis)

        # Ahli Utama Track B (Executive Counsel & Mandatory HITL)
        prompt_utama = DynamicPromptBuilder.build_legal_persona_prompt(
            persona_key="ANALIS_HUKUM_AHLI_UTAMA",
            intent_type="judicial_review_mkri"
        )
        self.assertIn("Analis Hukum Ahli Utama (Executive Counsel & Judicial Review)", prompt_utama)
        self.assertIn("YA (Memerlukan Paraf/Pengesahan Pejabat)", prompt_utama)
        self.assertIn("Judicial Review MKRI & MA", prompt_utama)

    def test_legal_intent_classification(self):
        from core.agent_framework.channel_router import classify_legal_intent

        # Track A: Perancangan Raperda
        res_a1 = classify_legal_intent("Tolong buatkan draf pasal sanksi untuk Raperda Penyelenggaraan Jalan")
        self.assertEqual(res_a1["track"], "TRACK_A_PERANCANG")
        self.assertEqual(res_a1["intent"], "draft_peraturan_perda")
        self.assertEqual(res_a1["recommended_persona"], "PERANCANG_PUU_AHLI_MUDA")

        # Track A: Harmonisasi Ditjen PP
        res_a2 = classify_legal_intent("Bagaimana tata cara dan matriks harmonisasi raperda berdasarkan Pasal 58 UU 13/2022?")
        self.assertEqual(res_a2["track"], "TRACK_A_PERANCANG")
        self.assertEqual(res_a2["intent"], "harmonisasi_raperda_ditjen_pp")
        self.assertEqual(res_a2["recommended_persona"], "PERANCANG_PUU_AHLI_MADYA")

        # Track B: Legal Opinion & Kontrak PBJ
        res_b1 = classify_legal_intent("Mohon disusunkan legal opinion terkait wanprestasi dan klausul denda kontrak pengadaan barang jasa")
        self.assertEqual(res_b1["track"], "TRACK_B_ANALIS")
        self.assertEqual(res_b1["intent"], "contract_vetting_pbj_pks")

        # Track B: Litigasi PTUN
        res_b2 = classify_legal_intent("Siapkan eksepsi dan kronologi fakta untuk gugatan sengketa KTUN di PTUN Jakarta")
        self.assertEqual(res_b2["track"], "TRACK_B_ANALIS")
        self.assertEqual(res_b2["intent"], "litigasi_ptun_advokasi")
        self.assertEqual(res_b2["recommended_persona"], "ANALIS_HUKUM_AHLI_MADYA")

        # Track B: Judicial Review MKRI
        res_b3 = classify_legal_intent("Susun keterangan presiden untuk permohonan uji materiil UU di Mahkamah Konstitusi")
        self.assertEqual(res_b3["track"], "TRACK_B_ANALIS")
        self.assertEqual(res_b3["intent"], "judicial_review_mkri")
        self.assertEqual(res_b3["recommended_persona"], "ANALIS_HUKUM_AHLI_UTAMA")

    def test_executive_summary_formatting(self):
        from core.agent_framework.channel_router import generate_executive_summary

        raw_analysis = (
            "DUDUK PERKARA:\n"
            "Terdapat potensi sengketa batas wilayah antara Pemkab Morowali dan Pemkab Kolaka.\n"
            "Berdasarkan Permendagri No. 141 Tahun 2017, batas daerah harus mengacu pada titik koordinat kartometrik.\n"
            "KESIMPULAN: Perlu dilakukan verifikasi lapangan bersama tim Badan Informasi Geospasial."
        )

        summary = generate_executive_summary(raw_analysis, track="TRACK_B_ANALIS", intent="legal_opinion_irac")
        self.assertIn("RINGKASAN EKSEKUTIF PIMPINAN (1-PAGE EXECUTIVE BRIEF)", summary)
        self.assertIn("3 POIN AKSI KUNCI", summary)
        self.assertIn("TINGKAT RISIKO HUKUM", summary)
        self.assertIn("Analisis & Opini Hukum (BPHN)", summary)


if __name__ == "__main__":
    unittest.main()

