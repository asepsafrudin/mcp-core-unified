import pytest
from services.ocr.service import OCREngine
from services.ocr.utils import validate_file

def test_ocr_engine_singleton():
    e1 = OCREngine.get_instance()
    e2 = OCREngine.get_instance()
    assert e1 is e2

def test_validate_file():
    # Test dengan file placeholder - akan skip jika no fixture
    try:
        validate_file("services/ocr/tests/fixtures/sample.jpg")
    except FileNotFoundError:
        pytest.skip("No fixture file - normal untuk initial setup")

