# preprocessor.py
import cv2
import numpy as np
import os
import tempfile
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)

class ImagePreProcessor:
    """
    Menangani pembersihan gambar sebelum OCR untuk meningkatkan akurasi.
    Implementasi menggunakan OpenCV 4.x.
    """
    
    def __init__(self, debug: bool = False):
        self.debug = debug

    def process(self, image_path: str) -> str:
        """
        Melakukan rangkaian pembersihan gambar.
        Returns: Path ke file gambar hasil pembersihan (temporary).
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Gagal membaca gambar di {image_path}")

        # 1. Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2. Rescaling (DPI check/fix jika perlu - opsional)
        # scale_factor = 2 # misal jika gambar terlalu kecil
        # gray = cv2.resize(gray, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)

        # 3. Denoising (Bilateral filtering lebih baik mempertahankan edge/teks daripada Gaussian)
        denoised = cv2.bilateralFilter(gray, 9, 75, 75)

        # 4. Adaptive Thresholding (Penting untuk dokumen yang pencahayaannya tidak rata)
        # Berfungsi mengubah ke hitam-putih murni
        thresh = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )

        # 5. Deskewing (Luruskan gambar miring) - Implementasi sederhana
        # (Bisa ditambahkan kemudian jika banyak dokumen yang miring)

        # Simpan hasil ke temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
            temp_path = f.name
        
        cv2.imwrite(temp_path, thresh)
        
        if self.debug:
            logger.info("image_preprocessing_complete", original=image_path, processed=temp_path)
            
        return temp_path

    def deskew(self, img):
        """
        Meluruskan kemiringan teks.
        """
        coords = np.column_stack(np.where(img > 0))
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        (h, w) = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated
