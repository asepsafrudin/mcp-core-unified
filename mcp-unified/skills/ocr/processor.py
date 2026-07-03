import os
import cv2
import numpy as np
import io
import tempfile
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, Tuple

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from docx import Document
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

# Default model path — can be overridden via constructor
DEFAULT_YOLO_MODEL_PATH = "/home/aseps/MCP/storage/models/yolo11/best.pt"


class OCRProcessor:
    """
    Centralized OCR and Visual Analysis Engine for legal documents.
    
    Supports hybrid detection:
    - Primary: YOLO11 AI model (confidence-scored, trained on PUU documents)
    - Fallback: OpenCV heuristic (color masking, spatial analysis)
    """
    
    def __init__(self, yolo_model_path: str = None):
        self._yolo_model = None
        self._yolo_model_path = yolo_model_path or DEFAULT_YOLO_MODEL_PATH
        self._load_yolo_model()

    def _load_yolo_model(self):
        """Load YOLO model if available."""
        if not YOLO_AVAILABLE:
            return
        model_path = self._yolo_model_path
        if os.path.exists(model_path):
            try:
                self._yolo_model = YOLO(model_path)
                # Warm up with a dummy inference
                dummy = np.zeros((64, 64, 3), dtype=np.uint8)
                self._yolo_model.predict(dummy, verbose=False)
            except Exception as e:
                print(f"⚠️ YOLO model load failed: {e}")
                self._yolo_model = None

    def _detect_with_yolo(self, img: np.ndarray, conf: float = 0.25) -> list:
        """
        Run YOLO inference on a document image.
        Returns list of bboxes in the same format as heuristic detection.
        """
        if self._yolo_model is None:
            return []
        
        try:
            results = self._yolo_model.predict(img, conf=conf, verbose=False)
            bboxes = []
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls)
                    cls_name = r.names[cls_id]
                    confidence = float(box.conf)
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    bboxes.append({
                        "label": cls_name,
                        "box": [int(x1), int(y1), int(x2 - x1), int(y2 - y1)],
                        "area": int((x2 - x1) * (y2 - y1)),
                        "confidence": confidence,
                        "source": "yolo"
                    })
            return bboxes
        except Exception as e:
            print(f"⚠️ YOLO inference failed: {e}")
            return []

    def analyze_visuals(self, img_data: bytes, conf: float = 0.25) -> Dict[str, Any]:
        """
        Detect and locate signatures, stamps, and logos.
        
        Hybrid strategy:
        1. YOLO11 AI detection (primary, confidence-scored)
        2. OpenCV heuristic (fallback for classes YOLO missed)
        
        Args:
            img_data: Raw image bytes (PNG/JPG)
            conf: YOLO confidence threshold (default 0.25)
        """
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"has_wet_signature": False, "has_stamp": False, "has_logo": False, "bboxes": []}

        # === PRIMARY: YOLO AI Detection ===
        yolo_bboxes = self._detect_with_yolo(img, conf=conf)
        if yolo_bboxes:
            # YOLO found objects — use as primary, augment with heuristic for missed classes
            yolo_classes = {b["label"] for b in yolo_bboxes}
            heuristic_bboxes = self._detect_heuristic(img)
            
            # Add heuristic detections for classes YOLO didn't find
            for hb in heuristic_bboxes:
                hb_class_key = hb["label"].split("_")[0]  # e.g., "wet" from "wet_signature"
                if not any(hb_class_key in yc for yc in yolo_classes):
                    hb["source"] = "heuristic_supplement"
                    hb["confidence"] = 0.3  # Lower confidence for heuristic
                    yolo_bboxes.append(hb)
            
            bboxes = yolo_bboxes
            detection_method = "yolo_hybrid"
        else:
            # YOLO unavailable or found nothing — full heuristic fallback
            bboxes = self._detect_heuristic(img)
            for b in bboxes:
                b["source"] = "heuristic"
                b["confidence"] = 0.5
            detection_method = "heuristic"

        return {
            "has_wet_signature": any("signature" in b["label"] for b in bboxes),
            "has_stamp": any("stamp" in b["label"] for b in bboxes),
            "has_paraf": any("paraf" in b["label"] for b in bboxes),
            "has_notes": any("notes" in b["label"] for b in bboxes),
            "has_logo": any("logo" in b["label"] for b in bboxes),
            "has_qr_code": any("qr" in b["label"] for b in bboxes),
            "detection_method": detection_method,
            "bboxes": bboxes
        }

    def _detect_heuristic(self, img: np.ndarray) -> list:
        """
        Original OpenCV heuristic detection (color masking + spatial analysis).
        Kept as fallback when YOLO is unavailable.
        """

        h_img, w_img = img.shape[:2]
        header_limit = int(h_img * 0.25) # Top 25% for logos
        footer_limit = int(h_img * 0.65) # Bottom 35% for signatures
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        bboxes = []
        
        # 1. Color-Based Detection
        blue_mask = cv2.inRange(hsv, np.array([100, 50, 50]), np.array([130, 255, 255]))
        purple_mask = cv2.inRange(hsv, np.array([130, 50, 50]), np.array([160, 255, 255]))
        red_mask1 = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([10, 255, 255]))
        red_mask2 = cv2.inRange(hsv, np.array([170, 70, 50]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)
        gold_mask = cv2.inRange(hsv, np.array([20, 100, 100]), np.array([30, 255, 255]))
        
        stamp_logo_mask = cv2.bitwise_or(purple_mask, cv2.bitwise_or(red_mask, gold_mask))
        
        def get_bboxes(mask, default_label, min_area=1000):
            found_bboxes = []
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                area = cv2.contourArea(c)
                if area > 100: # Capture even small marks (checkboxes)
                    x, y, w, h = cv2.boundingRect(c)
                    label = default_label
                    
                    # 1. Spatial & Size Logic for Color Marks
                    if y < header_limit and area > 1500:
                        label = "logo_instansi"
                    elif area < 400:
                        label = "checkbox_mark"
                    elif area < 1500:
                        label = "paraf_koordinasi"
                    else:
                        # Large objects in the middle are notes, in the bottom are signatures/stamps
                        if y > footer_limit:
                            label = "stamp_utama" if "stamp" in default_label else "wet_signature"
                        elif y > header_limit:
                            label = "handwritten_notes"
                    
                    found_bboxes.append({"label": label, "box": [x, y, w, h], "area": area})
            return found_bboxes

        bboxes.extend(get_bboxes(blue_mask, "wet_signature", 400))
        bboxes.extend(get_bboxes(stamp_logo_mask, "stamp", 400))

        # 2. B&W Fallback Logic
        if len(bboxes) < 2: # Trigger if very few marks found (likely B&W)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
            
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                area = cv2.contourArea(c)
                if area > 1000: # Threshold for B&W
                    x, y, w, h = cv2.boundingRect(c)
                    aspect_ratio = w / float(h)
                    
                    if y < header_limit and 0.5 < aspect_ratio < 2.0:
                        bboxes.append({"label": "logo_instansi_bw", "box": [x, y, w, h], "area": area})
                    elif y > footer_limit and area > 4500:
                        bboxes.append({"label": "signature_candidate_bw", "box": [x, y, w, h], "area": area})
                    elif header_limit < y < footer_limit and area > 5000:
                        bboxes.append({"label": "handwritten_notes_bw", "box": [x, y, w, h], "area": area})

        # 3. QR Code Detection
        qr_detector = cv2.QRCodeDetector()
        has_qr, points, _ = qr_detector.detectAndDecode(img)
        if has_qr and points is not None:
            p = points[0].astype(int)
            x, y = np.min(p, axis=0)
            x2, y2 = np.max(p, axis=0)
            bboxes.append({"label": "qr_code", "box": [int(x), int(y), int(x2-x), int(y2-y)], "area": int((x2-x)*(y2-y))})



        # Sort by area descending to process larger containers first
        bboxes = sorted(bboxes, key=lambda x: x["area"], reverse=True)
        refined_bboxes = []
        
        for i, current in enumerate(bboxes):
            is_contained = False
            for parent in refined_bboxes:
                # Check if current is inside parent (with some margin)
                px, py, pw, ph = parent["box"]
                cx, cy, cw, ch = current["box"]
                if cx >= px-10 and cy >= py-10 and (cx+cw) <= (px+pw+10) and (cy+ch) <= (py+ph+10):
                    is_contained = True
                    break
            
            if not is_contained:
                refined_bboxes.append(current)

        # Final Merger for nearby objects (Cross-Label Merger for Header)
        final_bboxes = []
        while refined_bboxes:
            curr = refined_bboxes.pop(0)
            merged = False
            for i, other in enumerate(final_bboxes):
                c1 = curr["box"]
                c2 = other["box"]
                
                # Distance check
                dist_x = max(0, max(c1[0], c2[0]) - min(c1[0]+c1[2], c2[0]+c2[2]))
                dist_y = max(0, max(c1[1], c2[1]) - min(c1[1]+c1[3], c2[1]+c2[3]))
                
                # Allow cross-label merging in Header (y < header_limit)
                is_header_merger = (c1[1] < header_limit and c2[1] < header_limit)
                
                if dist_x < 60 and dist_y < 60 and (curr["label"] == other["label"] or is_header_merger):
                    # Merge boxes
                    nx = min(c1[0], c2[0])
                    ny = min(c1[1], c2[1])
                    nx2 = max(c1[0]+c1[2], c2[0]+c2[2])
                    ny2 = max(c1[1]+c1[3], c2[1]+c2[3])
                    
                    # Update other box
                    final_bboxes[i]["box"] = [nx, ny, nx2-nx, ny2-ny]
                    final_bboxes[i]["area"] = (nx2-nx) * (ny2-ny)
                    
                    # Inheritance: If any part is a logo, the whole thing is a logo
                    if "logo" in curr["label"] or "logo" in other["label"]:
                        final_bboxes[i]["label"] = "logo_instansi"
                    
                    merged = True
                    break
            if not merged:
                final_bboxes.append(curr)

        # Final Cleaning: Reject objects that don't make visual sense (e.g. extremely wide text blocks as logos)
        verified_bboxes = []
        for b in final_bboxes:
            x, y, w, h = b["box"]
            aspect_ratio = w / float(h)
            
            if "logo" in b["label"]:
                # Logos should be somewhat balanced (shield-like), not a thin line of text
                if 0.4 < aspect_ratio < 3.0: 
                    verified_bboxes.append(b)
            else:
                verified_bboxes.append(b)

        bboxes = verified_bboxes

        return bboxes

    async def extract_text_vision(self, content: bytes) -> Dict[str, Any]:
        """
        Extract text using Google Cloud Vision API.
        """
        try:
            from google.cloud import vision
            client = vision.ImageAnnotatorClient()
            
            # PDF Handling: Convert first page to image for spatial Vision
            image_content = content
            if content.startswith(b"%PDF"):
                import fitz
                doc = fitz.open(stream=content, filetype="pdf")
                page = doc.load_page(0)
                pix = page.get_pixmap()
                image_content = pix.tobytes("png")
                doc.close()
            
            image = vision.Image(content=image_content)
            response = client.document_text_detection(image=image)
            
            from google.protobuf.json_format import MessageToDict
            resp_dict = MessageToDict(response._pb)
            
            return {
                "text": response.full_text_annotation.text or "",
                "raw_response": resp_dict
            }
        except Exception as e:
            raise RuntimeError(f"Vision API extraction failed: {str(e)}")

    async def extract_text(self, file_content: bytes, mime_type: str, file_name: str) -> Tuple[str, int]:
        """
        Extract text from PDF or DOCX with fallback to OCR for scanned PDFs.
        """
        text = ""
        page_count = 0
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_name).suffix) as tmp:
            tmp.write(file_content)
            tmp_path = Path(tmp.name)
        
        try:
            if mime_type == 'application/pdf' and PYMUPDF_AVAILABLE:
                doc = fitz.open(tmp_path)
                text = "\n\n".join([str(page.get_text()) for page in doc])
                page_count = len(doc)
                doc.close()
                
                # Fallback to OCR if text is too short (likely scanned)
                if len(text.strip()) < 100 and OCR_AVAILABLE:
                    images = convert_from_path(tmp_path, first_page=1, last_page=3)
                    ocr_text = []
                    for i, image in enumerate(images):
                        page_text = pytesseract.image_to_string(image)
                        ocr_text.append(f"--- OCR Page {i+1} ---\n{page_text}")
                    text = "\n\n".join(ocr_text)
            
            elif 'word' in mime_type and PYTHON_DOCX_AVAILABLE:
                doc = Document(str(tmp_path))
                text = "\n".join([p.text for p in doc.paragraphs])
                page_count = 1
                
            return text, page_count
        except Exception as e:
            raise RuntimeError(f"Text extraction failed: {str(e)}")
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def get_file_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    async def process_file(self, file_path: Path) -> Tuple[str, int, str]:
        """
        Process a local file and return text, page count, and hash.
        """
        with open(file_path, 'rb') as f:
            content = f.read()
        
        file_hash = self.get_file_hash(content)
        
        # Determine mime type from extension if possible
        ext = file_path.suffix.lower()
        if ext == '.pdf':
            mime_type = 'application/pdf'
        elif ext == '.docx':
            mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        else:
            mime_type = 'application/octet-stream'
            
        text, pages = await self.extract_text(content, mime_type, file_path.name)
        return text, pages, file_hash

    def extract_metadata_spatially(self, response_dict: Any, page_idx: int = 0, rel_y_limit: float = 0.4) -> Dict[str, Any]:
        """
        Extracts structured metadata using spatial coordinates from Google Vision response.
        Handles both dict and Google SDK Message objects.
        """
        if not response_dict: return {}
        
        # Defensive: Handle nested raw_response
        if isinstance(response_dict, dict) and "raw_response" in response_dict:
            response_dict = response_dict["raw_response"]
        
        import re
        from google.protobuf.json_format import MessageToDict
        
        # 0. Convert to dict if it's a Proto Message
        if not isinstance(response_dict, dict):
            try:
                # Try to use MessageToDict for older objects or direct attribute access
                if hasattr(response_dict, 'full_text_annotation'):
                    # Custom conversion for common Vision Response objects
                    data = {
                        'fullTextAnnotation': {
                            'pages': []
                        }
                    }
                    for page in response_dict.full_text_annotation.pages:
                        page_data = {
                            'width': page.width,
                            'height': page.height,
                            'blocks': []
                        }
                        for block in page.blocks:
                            block_data = {'paragraphs': []}
                            for para in block.paragraphs:
                                para_data = {'words': []}
                                for word in para.words:
                                    word_text = "".join([s.text for s in word.symbols])
                                    vertices = [{"x": v.x, "y": v.y} for v in word.bounding_box.vertices]
                                    para_data['words'].append({
                                        'text': word_text,
                                        'symbols': [{'text': s.text} for s in word.symbols],
                                        'boundingBox': {'vertices': vertices}
                                    })
                                block_data['paragraphs'].append(para_data)
                            page_data['blocks'].append(block_data)
                        data['fullTextAnnotation']['pages'].append(page_data)
                    response_dict = data
                else:
                    response_dict = MessageToDict(response_dict)
            except Exception as e:
                # Fallback: if conversion fails, return empty
                print(f"   ⚠️ Spatial conversion failed: {str(e)}")
                return {}

        # 1. Flatten word data
        words_data = []
        try:
            pages = response_dict.get('fullTextAnnotation', {}).get('pages', [])
            if not pages: return {}
            page = pages[page_idx]
            width = int(page.get('width', 0))
            height = int(page.get('height', 0))
            
            for block in page.get('blocks', []):
                for paragraph in block.get('paragraphs', []):
                    for word in paragraph.get('words', []):
                        word_text = "".join([s.get('text', '') for s in word.get('symbols', [])])
                        vertices = word.get('boundingBox', {}).get('vertices', [])
                        if not vertices: continue
                        
                        min_x = min([v.get('x', 0) for v in vertices])
                        max_x = max([v.get('x', 0) for v in vertices])
                        min_y = min([v.get('y', 0) for v in vertices])
                        max_y = max([v.get('y', 0) for v in vertices])
                        
                        words_data.append({
                            "text": word_text,
                            "min_x": min_x,
                            "max_x": max_x,
                            "min_y": min_y,
                            "max_y": max_y,
                            "center_x": (min_x + max_x) / 2,
                            "center_y": (min_y + max_y) / 2,
                            "height": max_y - min_y
                        })
        except (IndexError, KeyError):
            return {}

        if not words_data:
            return {}

        # 2. Group into visual lines (filtered by rel_y_limit)
        words_filtered = [w for w in words_data if w['center_y'] / height <= rel_y_limit]
        if not words_filtered:
            return {}
            
        words_sorted = sorted(words_filtered, key=lambda x: x['center_y'])
        visual_lines = []
        current_line = []
        last_y = words_sorted[0]['center_y']
        y_tolerance = words_sorted[0]['height'] * 0.5
        
        for w in words_sorted:
            if abs(w['center_y'] - last_y) > y_tolerance:
                visual_lines.append(sorted(current_line, key=lambda x: x['center_x']))
                current_line = [w]
                last_y = w['center_y']
            else:
                current_line.append(w)
        if current_line:
            visual_lines.append(sorted(current_line, key=lambda x: x['center_x']))

        # 3. Detect Document Type (Nota Dinas vs Surat Dinas)
        is_nota_dinas = False
        for line in visual_lines[:10]:
            line_text = " ".join([w['text'] for w in line])
            if "NOTA DINAS" in line_text.upper():
                # Check if it's centered (approx middle of page)
                nota_w = next((w for w in line if "NOTA" in w['text'].upper()), None)
                if nota_w and width * 0.3 < nota_w['center_x'] < width * 0.7:
                    is_nota_dinas = True
                    break
        
        doc_type = "NOTA DINAS" if is_nota_dinas else "SURAT DINAS"

        # 4. Spatial Anchor Logic
        metadata = {
            "nomor": "", 
            "tanggal": "", 
            "hal": "", 
            "yth": "", 
            "dari": "", 
            "sifat": "", 
            "lampiran": "",
            "jenis_naskah": doc_type
        }
        
        # Detected global column X boundary as fallback
        global_column_x = width * 0.20 
        for line in visual_lines[:25]:
            for w in line:
                if ":" in w['text'] and width * 0.1 < w['center_x'] < width * 0.4:
                    global_column_x = max(global_column_x, w['max_x'])

        def get_row_metadata(line_idx, anchor_text):
            line = visual_lines[line_idx]
            
            # Find the anchor word and any colon near it
            anchor_w = next((w for w in line if anchor_text.lower() in w['text'].lower()), None)
            if not anchor_w: return ""
            
            # Boundary is either the colon's max_x or anchor's max_x
            row_boundary = anchor_w['max_x']
            colon_w = next((w for w in line if ":" in w['text'] and w['min_x'] >= anchor_w['min_x']), None)
            if colon_w:
                row_boundary = max(row_boundary, colon_w['max_x'])
            
            # Use the further of row_boundary or a minimum offset to avoid catching the label itself
            # Use a very small offset to avoid cutting off anything
            effective_boundary = max(row_boundary, anchor_w['min_x'] + 10)
            
            # Use max_x of the word to see if it even partially crosses the boundary
            right_words = [w['text'] for w in line if w['max_x'] > effective_boundary]
            
            # Clean leading colons/dots/spaces
            filtered = []
            seen_content = False
            for rw in right_words:
                clean = re.sub(r'[:\.\s]', '', rw)
                if not seen_content and not clean:
                    continue
                filtered.append(rw)
                seen_content = True
            
            return " ".join(filtered).strip()

        # Semantic Stop Phrases (VLM-style context)
        stop_phrases = [
            "Demikian", "Sekretaris", "Direktur", "Kepala", "NIP", 
            "Pembina Utama", "ditandatangani secara elektronik", 
            "BSrE", "BSSN", "Yth.", "Dari:", "Dalam rangka", 
            "Sehubungan", "Bersama ini", "Menindaklanjuti"
        ]

        def get_multiline_row_metadata(start_line_idx, anchor_text):
            first_line_val = get_row_metadata(start_line_idx, anchor_text)
            if not first_line_val: return ""
            
            results = [first_line_val]
            
            # Find the X-start of the first line's content to use as a vertical column guide
            anchor_w = next((w for w in visual_lines[start_line_idx] if anchor_text.lower() in w['text'].lower()), None)
            first_val_word = next((w for w in visual_lines[start_line_idx] if w['text'] in first_line_val), None)
            content_x_guide = first_val_word['min_x'] if first_val_word else global_column_x
            
            last_y = visual_lines[start_line_idx][0]['center_y']
            
            for i in range(start_line_idx + 1, min(start_line_idx + 10, len(visual_lines))):
                line = visual_lines[i]
                line_text = " ".join([w['text'] for w in line])
                current_y = line[0]['center_y']
                
                # Gap Detection: Stop if there is a blank line (significant Y jump)
                # Usually a line height is 15-25px, a double space is > 40px
                line_height = line[0]['height'] if line else 20
                if abs(current_y - last_y) > line_height * 2.5:
                    break
                
                # Logical Stop: known labels at start of line
                if any(kw in line_text[:25] for kw in ["Nomor", "Sifat", "Lampiran", "Hal", "Yth", "Dari", "Sehubungan", "Menindaklanjuti", "Tembusan", "Tujuan"]):
                    break
                
                # Semantic Stop: signature blocks or opening phrases
                if any(sp.lower() in line_text.lower() for sp in stop_phrases):
                    # For Yth, we might want to capture "Kepala..." but stop at "Dalam rangka"
                    # If the stop phrase is at the very beginning of the line, it's a paragraph
                    if any(line_text.strip().startswith(sp) for sp in ["Dalam rangka", "Sehubungan", "Bersama ini", "Menindaklanjuti"]):
                        break
                
                # In multiline, we take words that are aligned with the content_x_guide
                line_content = [w['text'] for w in line if w['max_x'] > content_x_guide - 50]
                if line_content:
                    results.append(" ".join(line_content))
                    last_y = current_y
                else:
                    break 
            return " ".join(results).strip()

        # Set anchors based on profile (extended with regex support)
        anchor_patterns = {
            "nomor": r"\b(nomor|no\.|nomer)\b",
            "tanggal": r"\b(tanggal|tgl)\b",
            "yth": r"\b(yth|kepada)\b",
            "dari": r"\b(dari)\b",
            "hal": r"\b(hal|perihal)\b",
            "sifat": r"\b(sifat)\b",
            "lampiran": r"\b(lampiran)\b"
        }

        for i, line in enumerate(visual_lines):
            if len(line) == 0: continue
            # Only search for anchors in the left-hand side of the page
            if True: # Search all horizontal positions
                line_text = " ".join([w['text'] for w in line])
                for key, pattern in anchor_patterns.items():
                    if re.search(pattern, line_text, re.IGNORECASE):
                        # Special handling for already filled keys (take the highest one)
                        if metadata.get(key): continue
                        
                        anchor_text = re.search(pattern, line_text, re.IGNORECASE).group(0)
                        if key in ["hal", "yth"]:
                            metadata[key] = get_multiline_row_metadata(i, anchor_text)
                        else:
                            metadata[key] = get_row_metadata(i, anchor_text)

        # 5. Logical Date & Number Refinement (VLM Approach)
        
        # Fallback for Nomor: If not found via label, look for typical pattern in header area
        if not metadata["nomor"]:
            for line in visual_lines:
                line_text = " ".join([w['text'] for w in line])
                # Typical pattern: 123.4.5/6789/Letter (handle common OCR slash noise % or &)
                num_pattern = re.search(r'\b\d{1,3}[\.\/]\d{1,3}[\.\/]\d{1,4}[\.\/\%\&]\w+\b', line_text)
                if num_pattern:
                    val = num_pattern.group(0).replace('%', '/').replace('&', '/')
                    metadata["nomor"] = val
                    break
        
        # Refinement for Nomor (prevent date bleeding and fix OCR slash-digit confusion)
        if metadata["nomor"]:
            # Fix slash confusion: common OCR mistake '23011' for '2301/'
            # If nomor ends with a digit that was likely a slash (often '1' or '7' at the end of a block)
            metadata["nomor"] = re.sub(r'(\d)/(\d)1$', r'\1/\2/', metadata["nomor"])
            metadata["nomor"] = re.sub(r'(\d)1$', r'\1/', metadata["nomor"]) if metadata["nomor"].count('/') < 2 else metadata["nomor"]

            for month in ["januari", "februari", "maret", "april", "mei", "juni", "juli", "agustus", "september", "oktober", "november", "desember"]:
                if month in metadata["nomor"].lower():
                    parts = re.split(rf"\s*{month}", metadata["nomor"], flags=re.IGNORECASE)
                    metadata["nomor"] = parts[0].strip()
                    if not metadata["tanggal"]:
                        date_part = re.search(rf"(\d{{1,2}})?\s*{month}\s+\d{{4}}", metadata["nomor"] + " " + month, flags=re.IGNORECASE)
                        if date_part: metadata["tanggal"] = date_part.group(0)
                    break

        # Fallback Date Logic
        if not metadata["tanggal"]:
            for line in visual_lines[:20]:
                line_text = " ".join([w['text'] for w in line])
                if any(m in line_text.lower() for m in ["januari", "februari", "maret", "april", "mei", "juni", "juli", "agustus", "september", "oktober", "november", "desember"]):
                    # If it's a Nota Dinas and we found a date in the middle-left, take it
                    if is_nota_dinas and line[0]['center_x'] < width * 0.5:
                         metadata["tanggal"] = line_text.strip()
                         break
                    # For Surat Dinas or top-right dates
                    date_words = [w for w in line if w['min_x'] > width * 0.25]
                    if date_words:
                        sorted_date_words = sorted(date_words, key=lambda x: x['min_x'])
                        metadata["tanggal"] = " ".join([w['text'] for w in sorted_date_words]).strip()
                        break

        # 6. Extract Substansi (Main Body)
        # Body starts after the last metadata field and ends before signature
        body_lines = []
        in_body = False
        
        # Determine the last line index of metadata
        last_meta_idx = 0
        for i, line in enumerate(visual_lines[:40]):
            line_text = " ".join([w['text'] for w in line])
            if any(kw in line_text[:25] for kw in ["Hal", "Yth", "Tujuan"]):
                # Give it some room to finish multiline Hal/Yth
                last_meta_idx = i + 3 

        for i, line in enumerate(visual_lines[last_meta_idx:]):
            line_text = " ".join([w['text'] for w in line])
            
            # Start body when we see common opening phrases or after meta
            if not in_body:
                if any(op.lower() in line_text.lower() for op in ["Menindaklanjuti", "Sehubungan", "Bersama ini", "Dalam rangka", "Dengan hormat"]):
                    in_body = True
            
            # End body if we hit signature stop phrases
            if in_body:
                if any(sp.lower() in line_text.lower() for sp in stop_phrases[:8]): # Use primary stop phrases
                    # If the stop phrase is the only thing or start of line, it's the signature block
                    if any(line_text.strip().startswith(sp) for sp in ["Demikian", "Sekretaris", "Direktur", "Kepala"]):
                        break
                body_lines.append(line_text)

        metadata["substansi"] = "\n".join(body_lines).strip()

        # Final Cleaning
        for k in metadata:
            if isinstance(metadata[k], str):
                # Remove trailing dots/colons often picked up by OCR
                metadata[k] = re.sub(r"[:\.,]$", "", metadata[k]).strip()

        return metadata
