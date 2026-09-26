"""
execution/contracts.py — Schema Kontrak Deterministik (Pydantic)
Mendefinisikan input & output baku untuk Autonomous Coder & Output Engine (MAF-Based).
Memastikan batas token < 500 token untuk response yang dikembalikan ke Agent IDE.
"""

from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field


class CodeExecutionRequest(BaseModel):
    """Permintaan eksekusi atau penulisan kode tervalidasi."""
    task_description: str = Field(..., description="Deskripsi tugas koding yang harus diselesaikan")
    target_file: str = Field(..., description="Path berkas sasaran (harus di bawah scripts/, storage/, atau scratch/)")
    language: str = Field(default="python", description="Bahasa pemrograman (default: python)")
    context_payload: Optional[Dict[str, Any]] = Field(default=None, description="Konteks data atau dependensi tambahan")
    max_healing_attempts: int = Field(default=3, description="Maksimum iterasi perbaikan mandiri di sandbox")


class CodeExecutionResponse(BaseModel):
    """Hasil eksekusi penulisan kode terstruktur untuk Agent IDE."""
    status: str = Field(..., description="Status hasil: success | partial_success_draft | failed")
    target_file: str = Field(..., description="Path berkas final yang dihasilkan atau draft tersisa")
    summary: str = Field(..., description="Ringkasan eksekutif hasil eksekusi (maks 500 token)")
    trace_id: str = Field(..., description="Trace ID unik untuk audit trail")
    healing_attempts_used: int = Field(default=0, description="Jumlah siklus perbaikan mandiri yang dijalankan")
    ast_valid: bool = Field(default=False, description="Apakah kode lolos validasi pohon sintaks abstrak (AST)")
    execution_time_ms: float = Field(default=0.0, description="Total durasi eksekusi dalam milidetik")


class ReportRenderRequest(BaseModel):
    """Permintaan perenderan laporan formal berstandar SATRIA."""
    template_name: str = Field(default="satria_formal_html", description="Nama template (e.g. satria_formal_html)")
    title: str = Field(..., description="Judul resmi dokumen laporan")
    data_payload: Union[List[Dict[str, Any]], Dict[str, Any]] = Field(..., description="Data JSON yang akan diinjeksi ke template")
    output_filename: str = Field(..., description="Nama berkas keluaran di storage/reports/ (e.g. laporan_indeks.html)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata pendukung (nomor surat, tanggal, institusi)")
    generate_canvas_artifact: bool = Field(default=True, description="Apakah menghasilkan artefak markdown secara simultan")


class ReportRenderResponse(BaseModel):
    """Hasil perenderan laporan formal untuk Agent IDE."""
    status: str = Field(..., description="Status hasil: success | failed")
    report_path: str = Field(..., description="Path berkas HTML/PDF yang dihasilkan di storage/reports/")
    canvas_artifact_path: Optional[str] = Field(default=None, description="Path artefak markdown di brain/ (jika aktif)")
    summary: str = Field(..., description="Ringkasan metrik dan status dokumen yang dirender")
    trace_id: str = Field(..., description="Trace ID unik untuk audit trail")
    total_items_rendered: int = Field(default=0, description="Jumlah baris data yang berhasil dirender")


class ScriptPipelineRequest(BaseModel):
    """Permintaan eksekusi skrip pipeline/ETL di sandbox lokal."""
    pipeline_name: str = Field(..., description="Nama identifikasi pipeline")
    script_path: str = Field(..., description="Path skrip yang akan dieksekusi (harus dalam allowlist)")
    args: List[str] = Field(default_factory=list, description="Argumen CLI tambahan untuk skrip")
    timeout_seconds: int = Field(default=120, description="Batas waktu eksekusi dalam detik")


class ScriptPipelineResponse(BaseModel):
    """Hasil eksekusi pipeline terstruktur untuk Agent IDE."""
    status: str = Field(..., description="Status hasil: success | failed | timeout")
    exit_code: int = Field(..., description="Exit code proses subprocess")
    summary: str = Field(..., description="Ringkasan eksekutif hasil proses (maks 500 token)")
    trace_id: str = Field(..., description="Trace ID unik untuk audit trail")
    execution_time_ms: float = Field(default=0.0, description="Durasi eksekusi dalam milidetik")
