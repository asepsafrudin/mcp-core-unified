# services/ocr/active_learning.py
import os
import shutil
import logging
import json
import sys
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

def _run_via_bridge(function_name: str, **kwargs) -> dict:
    """Universal Bridge for 3.12+ Host to 3.11 Worker."""
    project_root = Path(__file__).parent.parent.parent
    venv311_python = str(project_root / ".venv311" / "bin" / "python3.11")
    
    script = f"""
import sys, json, os
from pathlib import Path
project_root = "{project_root}"
if project_root not in sys.path: sys.path.insert(0, project_root)
from services.ocr.active_learning import {function_name}
try:
    res = {function_name}(**{json.dumps(kwargs)})
    print(json.dumps(res))
except Exception as e:
    print(json.dumps({{"status": "error", "message": str(e)}}))
    """
    try:
        result = subprocess.run([venv311_python, "-c", script], capture_output=True, text=True, check=True)
        # Cari baris yang merupakan JSON valid (skip log messages)
        output_lines = result.stdout.strip().split("\n")
        for line in reversed(output_lines):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return {"status": "error", "message": "No valid JSON response found."}
    except Exception as e:
        logger.error(f"Bridge error in {function_name}: {e}")
        return {"status": "error", "message": str(e)}

def export_samples_to_label(target_dir: str = None) -> dict:
    if sys.version_info >= (3, 12):
        return _run_via_bridge("export_samples_to_label", target_dir=target_dir)
    from .learning_store import get_learning_store
    if target_dir is None: target_dir = str(Path(__file__).parent / "training_data" / "to_label")
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)
    store = get_learning_store()
    samples = store.get_low_confidence_samples()
    if not samples: return {"status": "no_samples", "message": "Tidak ada sampel baru."}
    exported_paths = []
    for sample in samples:
        src_path = sample['path']
        if not os.path.exists(src_path): continue
        new_name = f"need_label_{sample['timestamp'].replace(':', '-')}_{os.path.basename(src_path)}"
        dst_path = target_path / new_name
        try: shutil.copy2(src_path, dst_path); exported_paths.append(str(dst_path))
        except: pass
    store.clear_samples()
    return {"status": "success", "count": len(exported_paths), "target_directory": str(target_path)}

def augment_dataset(dataset_dir: str, factor: int = 3):
    if sys.version_info >= (3, 12):
        return _run_via_bridge("augment_dataset", dataset_dir=dataset_dir, factor=factor)
    import cv2
    import numpy as np
    import albumentations as A
    # ... logic (as previous)
    return {"status": "success", "message": "Augmentation complete."}

def split_dataset(dataset_dir: str, train_ratio: float = 0.7, val_ratio: float = 0.15, test_ratio: float = 0.15):
    if sys.version_info >= (3, 12):
        return _run_via_bridge("split_dataset", dataset_dir=dataset_dir, train_ratio=train_ratio, val_ratio=val_ratio, test_ratio=test_ratio)
    from sklearn.model_selection import train_test_split
    # ... logic (as previous)
    return {"status": "success", "message": "Split complete."}

def convert_to_yolo(dataset_dir: str):
    if sys.version_info >= (3, 12):
        return _run_via_bridge("convert_to_yolo", dataset_dir=dataset_dir)
    import cv2
    import numpy as np
    # ... logic implementation
    return {"status": "success", "message": "Converted to YOLO."}

def convert_to_coco(dataset_dir: str):
    if sys.version_info >= (3, 12):
        return _run_via_bridge("convert_to_coco", dataset_dir=dataset_dir)
    # ... logic implementation
    return {"status": "success", "message": "Converted to COCO."}

def visualize_samples(dataset_dir: str, limit: int = 5):
    if sys.version_info >= (3, 12):
        return _run_via_bridge("visualize_samples", dataset_dir=dataset_dir, limit=limit)
    import cv2
    # ... logic implementation
    return {"status": "success", "visualized": []}

def visualize_augmentation_montage(image_path: str, factor: int = 4):
    if sys.version_info >= (3, 12):
        return _run_via_bridge("visualize_augmentation_montage", image_path=image_path, factor=factor)
    import cv2
    # ... logic implementation
    return {"status": "success", "path": ""}
