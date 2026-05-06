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

class OCRProcessor:
    """
    Centralized OCR and Visual Analysis Engine for legal documents.
    """
    
    def __init__(self):
        pass

    def analyze_visuals(self, img_data: bytes) -> Dict[str, bool]:
        """
        Detect signatures (blue) and stamps (purple/red) in an image.
        """
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"has_signature": False, "has_stamp": False}

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Blue mask for signatures
        blue_mask = cv2.inRange(hsv, np.array([100, 50, 50]), np.array([130, 255, 255]))
        
        # Purple/Red mask for stamps
        purple_mask = cv2.inRange(hsv, np.array([130, 50, 50]), np.array([160, 255, 255]))
        
        def check_presence(mask, min_area=1000):
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            return any(cv2.contourArea(c) > min_area for c in contours)

        return {
            "has_signature": check_presence(blue_mask, 1500),
            "has_stamp": check_presence(purple_mask, 500)
        }

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
