# tools.py
"""
MCP Tools untuk PaddleOCR 3.x service.
Namespace: ocr/

Tools:
  - ocr/extract_text    : ekstraksi teks dari gambar (PP-OCRv5)
  - ocr/parse_document  : parsing struktur dokumen ke Markdown (PP-StructureV3)
                          mendukung gambar DAN PDF
"""
from execution.registry import registry
from .service import OCREngine
from .utils import (
    decode_base64_to_tempfile,
    validate_image_file,
    validate_doc_file,
    cleanup_tempfile,
)
from .active_learning import (
    export_samples_to_label,
    visualize_samples,
    convert_to_yolo,
    convert_to_coco,
    augment_dataset,
    visualize_augmentation_montage,
    split_dataset
)

def register_tools(server=None) -> None:
    """
    Register OCR tools to the registry.
    Args:
        server: Unused parameter, kept for backward compatibility.
                The actual registration uses the global registry.
    """
    engine = OCREngine.get_instance()

    @registry.register(name="ocr/extract_text")
    async def extract_text(
        image_path: str = None,
        image_base64: str = None,
        mode: str = "standard"
    ) -> dict:
        """
        Ekstraksi teks dari gambar dokumen dengan pilihan mode pemrosesan.
        
        Pilihan Mode (Dialog):
          - fast      : Fokus kecepatan & hemat token. Tanpa pre-processing, tanpa LLM.
          - standard  : Standar pipeline. Pre-processing + Google Vision + Auto LLM (jika perlu).
          - deep      : Fokus akurasi. Pre-processing + Google Vision + LLM Refinement Wajib.
          - structured: Fokus data. Deep + Ekstraksi JSON terstruktur (khusus dokumen keuangan).

        Args:
            image_path  : Path absolut ke file gambar lokal.
            image_base64: Gambar dalam format base64.
            mode        : Pilihan strategi (fast | standard | deep | structured). Default: standard.

        Returns:
            { "full_text": str, "mode_requested": str, "refined_data": dict, ... }
        """
        tmp = None
        try:
            if image_base64:
                tmp = decode_base64_to_tempfile(image_base64)
                path = tmp
            elif image_path:
                path = image_path
            else:
                raise ValueError("Harus menyertakan image_path atau image_base64")

            validate_image_file(path)
            return engine.run_ocr(path, mode=mode)
        finally:
            if tmp:
                cleanup_tempfile(tmp)

    @registry.register(name="ocr/parse_document")
    async def parse_document(
        file_path: str = None,
        image_base64: str = None,
    ) -> str:
        """
        Parse struktur dokumen ke format Markdown menggunakan PP-StructureV3.
        Mendukung gambar (jpg/png/bmp/tiff/webp) DAN PDF langsung.
        Mengenali: judul, paragraf, tabel, heading, cap/stempel, formula.

        Args:
            file_path   : Path absolut ke file gambar atau PDF lokal
            image_base64: Gambar dalam format base64 (hanya gambar, bukan PDF)

        Returns:
            str Markdown dengan struktur dokumen terpelihara
        """
        tmp = None
        try:
            if image_base64:
                tmp = decode_base64_to_tempfile(image_base64)
                path = tmp
            elif file_path:
                path = file_path
            else:
                raise ValueError("Harus menyertakan file_path atau image_base64")

            validate_doc_file(path)
            return engine.run_structure(path)
        finally:
            if tmp:
                cleanup_tempfile(tmp)

    @registry.register(name="ocr/prepare_training_data")
    async def prepare_training_data(dataset_dir: str = None) -> dict:
        """
        Menyiapkan data yang memiliki tingkat kepercayaan (confidence) rendah 
        untuk dianotasi secara manual menggunakan PPOCRLabel.
        Setelah diekspor, daftar sampel di server akan dikosongkan.

        Args:
            dataset_dir: Folder tujuan ekspor file gambar.
                         Defaut: mcp-unified/services/ocr/training_data/to_label

        Returns:
            { "status", "count", "target_directory", "command_hint" }
        """
        return export_samples_to_label(dataset_dir)

    @registry.register(name="ocr/visualize_dataset")
    async def visualize_dataset(dataset_dir: str, limit: int = 5) -> dict:
        """
        Menghasilkan gambar visualisasi (bbox + teks) dari Label.txt 
        untuk verifikasi kualitas anotasi.

        Args:
            dataset_dir: Folder dataset yang berisi Label.txt
            limit: Jumlah maksimal gambar yang divisualisasi

        Returns:
            { "status", "visualized_files" }
        """
        files = visualize_samples(dataset_dir, limit)
        return {
            "status": "success" if files else "no_labels_found",
            "visualized_files": files
        }

    @registry.register(name="ocr/export_yolo")
    async def export_yolo(dataset_dir: str) -> dict:
        """
        Mengonversi dataset PaddleOCR ke format YOLO (.txt per gambar).
        """
        path = convert_to_yolo(dataset_dir)
        return {"status": "success", "yolo_label_dir": path}

    @registry.register(name="ocr/export_coco")
    async def export_coco(dataset_dir: str) -> dict:
        """
        Mengonversi dataset PaddleOCR ke format COCO JSON tunggal.
        """
        path = convert_to_coco(dataset_dir)
        return {"status": "success", "coco_json_path": path}

    @registry.register(name="ocr/augment_data")
    async def augment_data(dataset_dir: str, factor: int = 3) -> dict:
        """
        Melakukan augmentasi dataset (Image + Labels) secara masal.
        Mendukung rotasi, noise, blur, dll tanpa merusak koordinat label.

        Args:
            dataset_dir: Folder dataset berisi Label.txt
            factor: Jumlah variasi per gambar (default: 3)

        Returns:
            { "status", "new_images_count", "label_file" }
        """
        return augment_dataset(dataset_dir, factor)

    @registry.register(name="ocr/preview_augmentation")
    async def preview_augmentation(image_path: str, factor: int = 4) -> dict:
        """
        Menghasilkan gambar pratinjau montage untuk melihat efek augmentasi.
        Berguna untuk verifikasi sebelum melakukan augmentasi masal.

        Args:
            image_path: Path absolut ke satu file gambar lokal
            factor: Jumlah variasi augmentasi yang ditampilkan (default: 4)

        Returns:
            { "status", "montage_path" }
        """
        path = visualize_augmentation_montage(image_path, factor)
        return {"status": "success", "montage_path": path}

    @registry.register(name="ocr/split_dataset")
    async def split_data(dataset_dir: str, train: float = 0.7, 
                         val: float = 0.15, test: float = 0.15) -> dict:
        """
        Membagi dataset menjadi 3 bagian: TRAIN, VAL, TEST.
        Sinkronisasi otomatis untuk format PaddleOCR dan YOLO.

        Args:
            dataset_dir: Folder dataset berisi Label.txt
            train: Ratio training (default: 0.7)
            val: Ratio validation (default: 0.15)
            test: Ratio test (default: 0.15)

        Returns:
            { "status", "output_path", "summary", "percentages" }
        """
        return split_dataset(dataset_dir, train, val, test)