"""
Document AI Engine — Modul komunikasi dengan Google Document AI API.

Fitur:
  - Inisialisasi DocumentProcessorServiceClient
  - Kirim PDF ke Document AI API
  - Generic table parser (baca page.tables secara dinamis)
  - Multi-page table merge (gabungkan baris jika struktur kolom sama)

Dual-runtime: murni Python, tanpa dependensi Colab.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DocumentAIConfig, load_config, ConfigError
from .pdf_handler import slice_pdf, cleanup_temp_file, PDFProcessingError
from .text_cleaner import clean_table_dict


class DocumentAIError(Exception):
    """Raised when Document AI API call fails."""


class DocumentAIEngine:
    """
    Engine untuk komunikasi dengan Google Cloud Document AI.

    Usage:
        engine = DocumentAIEngine(project_id, location, processor_id)
        tables = engine.extract_tables("data/sample.pdf", pages="4-7")
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        processor_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
    ):
        """
        Initialize Document AI engine.

        Args:
            project_id: GCP Project ID. Jika None, baca dari env.
            location: GCP location ("us", "eu"). Default "us".
            processor_id: Document AI Processor ID.
            credentials_path: Path ke service account JSON (opsional).
        """
        if project_id or processor_id:
            self.config = DocumentAIConfig(
                project_id=project_id or "",
                location=location or "us",
                processor_id=processor_id or "",
                credentials_path=credentials_path,
            )
        else:
            self.config = load_config()

        self.config.validate()
        self._client = None

    def _get_client(self):
        """
        Lazy-initialize DocumentProcessorServiceClient.

        Returns:
            DocumentProcessorServiceClient instance.
        """
        if self._client is not None:
            return self._client

        try:
            from google.cloud import documentai
        except ImportError:
            raise DocumentAIError(
                "google-cloud-documentai not installed. "
                "Install with: pip install google-cloud-documentai"
            )

        try:
            from google.api_core.client_options import ClientOptions

            client_options = ClientOptions(api_endpoint=self.config.api_endpoint)

            if self.config.credentials_path:
                self._client = documentai.DocumentProcessorServiceClient.from_service_account_file(
                    self.config.credentials_path,
                    client_options=client_options,
                )
            else:
                self._client = documentai.DocumentProcessorServiceClient(
                    client_options=client_options,
                )
        except Exception as e:
            raise DocumentAIError(f"Failed to initialize Document AI client: {e}")

        return self._client

    def _build_process_options(self) -> Any:
        """
        Build ProcessOptions yang dioptimalkan untuk dokumen OCR rumit.

        Dua mode:
          - Mode dasar (default): compatible dengan semua processor (FORM_PARSER, OCR 1.0)
            * Native PDF parsing (jika PDF digital)
            * Language hints (Indonesia + English)
          - Mode premium: diaktifkan via env DOCAI_PREMIUM_FEATURES=1
            * Image quality scores
            * Symbol detection
            * Style info (deteksi header bold)
            * Selection mark detection
            * Table annotation (bounding boxes)

        Returns:
            ProcessOptions object atau None jika tidak didukung.
        """
        import os
        from google.cloud import documentai

        try:
            process_options = documentai.ProcessOptions()

            # === OcrConfig (fitur dasar - aman untuk semua processor) ===
            ocr_config = process_options.ocr_config
            ocr_config.enable_native_pdf_parsing = True

            # Language hints: dukung dokumen Indonesia (id) + English (en)
            language_hints = self.config.language_hints or ["id", "en"]
            ocr_config.hints.language_hints.extend(language_hints)

            # === Fitur premium (hanya jika diaktifkan eksplisit) ===
            # Catatan: fitur ini hanya didukung oleh OCR 2.0+ processors.
            # FORM_PARSER & OCR 1.0 akan error jika fitur ini diaktifkan.
            premium = os.getenv("DOCAI_PREMIUM_FEATURES", "0") == "1"
            if premium:
                ocr_config.enable_image_quality_scores = True
                ocr_config.enable_symbol = True
                ocr_config.compute_style_info = True

                # Premium features: deteksi selection marks & math OCR
                try:
                    ocr_config.premium_features.enable_selection_mark_detection = True
                except Exception:
                    pass

                # === LayoutConfig ===
                # Anotasi tabel + bounding boxes untuk deteksi tabel lebih baik
                layout_config = process_options.layout_config
                layout_config.enable_table_annotation = True
                layout_config.return_bounding_boxes = True

            return process_options

        except Exception:
            # Fallback: kembalikan None jika ProcessOptions tidak didukung
            return None

    def process_pdf(
        self,
        file_path: str,
        page_range: Optional[str] = None,
    ) -> Any:
        """
        Kirim PDF ke Document AI API dan kembalikan response.

        Args:
            file_path: Path ke file PDF.
            page_range: Page range ("all", "4-7", "1,3,5"). Default "all".

        Returns:
            Document AI Document response object.

        Raises:
            DocumentAIError: Jika API call gagal.
            PDFProcessingError: Jika PDF tidak valid.
        """
        from google.cloud import documentai

        path = Path(file_path)
        if not path.exists():
            raise PDFProcessingError(f"File not found: {file_path}")

        client = self._get_client()

        # Slice PDF if page range specified
        sliced_path = None
        try:
            if page_range and page_range.strip().lower() != "all":
                sliced_path = slice_pdf(file_path, page_range)
                process_path = sliced_path
            else:
                process_path = file_path

            # Read PDF bytes
            with open(process_path, "rb") as f:
                pdf_bytes = f.read()

            # Build request
            raw_document = documentai.RawDocument(
                content=pdf_bytes,
                mime_type="application/pdf",
            )

            # Build ProcessOptions (robust OCR config)
            process_options = self._build_process_options()

            request = documentai.ProcessRequest(
                name=self.config.processor_name,
                raw_document=raw_document,
                process_options=process_options,
            )

            # Process document
            result = client.process_document(request=request)
            return result.document

        except DocumentAIError:
            raise
        except PDFProcessingError:
            raise
        except Exception as e:
            raise DocumentAIError(f"Document AI processing failed: {e}")
        finally:
            if sliced_path:
                cleanup_temp_file(sliced_path)

    def extract_tables(
        self,
        file_path: str,
        page_range: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Ekstrak tabel dari PDF secara generik.

        Membaca page.tables dari Document AI response secara dinamis.
        Header baris pertama → column headers, sisa → data rows.
        Multi-page table digabung jika struktur kolom sama.

        Dilengkapi post-processing untuk dokumen kompleks:
          - Deteksi header cerdas (skip baris yang sebenarnya adalah data lanjutan)
          - Infer kolom kosong dengan nama generik (Kolom 1, Kolom 2, ...)

        Args:
            file_path: Path ke file PDF.
            page_range: Page range ("all", "4-7", "1,3,5"). Default "all".

        Returns:
            List of dict: [{"table_index", "headers", "rows", "page_numbers"}]

        Raises:
            DocumentAIError: Jika API call gagal.
            PDFProcessingError: Jika PDF tidak valid.
        """
        document = self.process_pdf(file_path, page_range)
        document_text = document.text or ""

        tables: List[Dict[str, Any]] = []
        table_index = 0

        for page_num, page in enumerate(document.pages, start=1):
            for table in page.tables:
                # Parse table body rows
                body_rows = []
                for row in table.body_rows:
                    cells = []
                    for cell in row.cells:
                        cells.append(self._extract_cell_text(cell, document_text))
                    body_rows.append(cells)

                if not body_rows:
                    continue

                # Post-processing cerdas untuk dokumen kompleks
                headers, data_rows = self._smart_split_header(body_rows)

                # Clean data
                table_data = {
                    "table_index": table_index,
                    "headers": self._infer_empty_headers(headers),
                    "rows": data_rows,
                    "page_numbers": [page_num],
                }
                table_data = clean_table_dict(table_data)

                # Try to merge with previous table if same structure
                if tables and self._can_merge(tables[-1], table_data):
                    tables[-1]["rows"].extend(table_data["rows"])
                    tables[-1]["page_numbers"].extend(table_data["page_numbers"])
                else:
                    tables.append(table_data)
                    table_index += 1

        return tables

    def _smart_split_header(self, body_rows: List[List[str]]) -> tuple:
        """
        Pisahkan header dari data rows secara cerdas untuk dokumen kompleks.

        Masalah yang ditangani:
          - Baris pertama berisi data (bukan header sebenarnya) jika kolom
            terakhir berisi angka/blank (bukan nama kolom)
          - Header mungkin berkisar 1-2 baris (multi-row header)

        Strategi:
          - Cek apakah baris pertama "terlihat seperti header":
            * Header biasanya: teks pendek, bukan angka murni, tidak dominan kosong
            * Data: baris pertama sering berisi nomor urut, nama, atau angka

        Args:
            body_rows: List of rows dari Document AI table.

        Returns:
            (headers, data_rows): Baris header terpilih dan sisa data.
        """
        if not body_rows:
            return ([], [])

        first = body_rows[0]
        num_cols = len(first)

        # Helper: apakah baris terlihat seperti header (bukan data)?
        def _looks_like_header(row: List[str]) -> bool:
            if not row:
                return False
            # Hitung sel non-empty
            non_empty = [c for c in row if c.strip()]
            if not non_empty:
                return False
            # Header biasanya: banyak sel non-empty
            if len(non_empty) < max(2, num_cols * 0.4):
                return False
            # Header tidak dominan angka. Hitung sel angka
            import re
            numeric_count = 0
            for cell in row:
                if re.match(r'^[\d.,\s()\-:;]+$', cell):
                    numeric_count += 1
            # Jika >70% sel adalah angka, ini lebih mirip data baris
            if numeric_count > len(non_empty) * 0.7:
                return False
            return True

        # Jika baris 1 terlihat header → pakai
        if _looks_like_header(first):
            return first, body_rows[1:]

        # Jika baris 1 bukan header (baris data), cek baris 2-3 apakah header
        # ini terjadi pada tabel yang berpindah halaman (header diulang di data)
        for i in range(1, min(3, len(body_rows))):
            if _looks_like_header(body_rows[i]):
                return body_rows[i], body_rows[i+1:]

        # Fallback: header = baris pertama (anggap benar)
        return first, body_rows[1:]

    def _infer_empty_headers(self, headers: List[str]) -> List[str]:
        """
        Infer nama kolom untuk kolom yang kosong.

        Jika header sel kosong, beri nama generik "Kolom N" agar
        data tetap terstruktur saat export.

        Args:
            headers: List of header strings (bisa kosong).

        Returns:
            List of header dengan kolom kosong sudah diisi.
        """
        result = []
        for i, h in enumerate(headers):
            if not h or not h.strip():
                result.append(f"Kolom {i+1}")
            else:
                result.append(h)
        return result

    def _extract_cell_text(self, cell, document_text: str) -> str:
        """
        Extract text dari Document AI table cell.

        Args:
            cell: Document AI TableCell object.
            document_text: Full text dari document (untuk segment extraction).

        Returns:
            String teks dari cell.
        """
        if not cell.layout or not cell.layout.text_anchor:
            return ""

        text_segments = cell.layout.text_anchor.text_segments
        if not text_segments:
            return ""

        # Use the first segment's start and last segment's end
        start = text_segments[0].start_index
        end = text_segments[-1].end_index

        # Extract text from document using segment indices
        if document_text and start is not None and end is not None:
            return document_text[start:end]

        return ""

    def _can_merge(self, table_a: Dict, table_b: Dict) -> bool:
        """
        Check apakah dua tabel bisa digabung (multi-page table).

        Dua tabel bisa digabung jika headers-nya sama.

        Args:
            table_a: Tabel pertama.
            table_b: Tabel kedua.

        Returns:
            True jika headers sama, False jika tidak.
        """
        return table_a["headers"] == table_b["headers"]


def extract_tables_from_pdf(
    file_path: str,
    page_range: Optional[str] = None,
    project_id: Optional[str] = None,
    location: Optional[str] = None,
    processor_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Convenience function untuk ekstraksi tabel dari PDF.

    Args:
        file_path: Path ke file PDF.
        page_range: Page range ("all", "4-7", "1,3,5").
        project_id: GCP Project ID (opsional, default dari env).
        location: GCP location (opsional, default "us").
        processor_id: Document AI Processor ID (opsional, default dari env).

    Returns:
        List of dict tabel yang diekstrak.

    Raises:
        DocumentAIError, PDFProcessingError, ConfigError.
    """
    engine = DocumentAIEngine(
        project_id=project_id,
        location=location,
        processor_id=processor_id,
    )
    return engine.extract_tables(file_path, page_range)