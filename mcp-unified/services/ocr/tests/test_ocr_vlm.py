import pytest
import os
from pathlib import Path
from services.ocr.service import OCREngine
from services.ocr.config import VISION_VLM_MODEL, get_ollama_base_url
from execution.registry import registry
from services.ocr.tools import register_tools

SAMPLE_IMG = "/home/aseps/MCP/workspace/korespondensi-server/training_data_v1/images/PUU03022026_0001_p1.png"

def test_ocr_engine_has_vision_methods():
    engine = OCREngine.get_instance()
    assert hasattr(engine, "run_vision_analysis")
    assert hasattr(engine, "_execute_vlm_vision")
    assert callable(engine.run_vision_analysis)

def test_tools_registration():
    register_tools()
    tools = [t["name"] for t in registry.list_tools()]
    assert "ocr_extract_text" in tools
    assert "ocr_vision_analyze" in tools

def test_get_ollama_base_url():
    url = get_ollama_base_url()
    assert url.startswith("http://") or url.startswith("https://")

@pytest.mark.skipif(not os.path.exists(SAMPLE_IMG), reason="Sample image not found")
def test_live_vlm_vision_ocr():
    engine = OCREngine.get_instance()
    res = engine.run_ocr(SAMPLE_IMG, mode="vision")
    assert res is not None
    assert res.get("status") == "success"
    assert "full_text" in res
    assert len(res.get("full_text", "")) > 0
    assert any(engine_name in res.get("engine", "") for engine_name in ["vlm", "doctr", "google_vision"])

@pytest.mark.skipif(not os.path.exists(SAMPLE_IMG), reason="Sample image not found")
def test_live_vision_qa_analysis():
    engine = OCREngine.get_instance()
    res = engine.run_vision_analysis(
        SAMPLE_IMG, prompt="Sebutkan tanggal surat yang tertera pada dokumen."
    )
    assert res is not None
    assert "status" in res
    if res.get("status") == "success":
        assert "full_text" in res
    else:
        assert res.get("status") == "error"
        assert "message" in res
