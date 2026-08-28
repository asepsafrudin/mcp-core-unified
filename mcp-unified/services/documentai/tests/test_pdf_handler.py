"""
Unit tests untuk pdf_handler.py — page range parsing & PDF slicing.
"""
import sys
import unittest
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pdf_handler import parse_page_range, get_pdf_page_count, slice_pdf, PDFProcessingError


class TestParsePageRange(unittest.TestCase):
    """Test parse_page_range function."""

    def test_none_returns_none(self):
        self.assertIsNone(parse_page_range(None))

    def test_all_returns_none(self):
        self.assertIsNone(parse_page_range("all"))
        self.assertIsNone(parse_page_range("ALL"))
        self.assertIsNone(parse_page_range(""))

    def test_single_page(self):
        self.assertEqual(parse_page_range("1"), [1])

    def test_range(self):
        self.assertEqual(parse_page_range("4-7"), [4, 5, 6, 7])

    def test_comma_separated(self):
        self.assertEqual(parse_page_range("1,3,5"), [1, 3, 5])

    def test_mixed(self):
        self.assertEqual(parse_page_range("1,4-6,9"), [1, 4, 5, 6, 9])

    def test_list_input(self):
        self.assertEqual(parse_page_range([1, 2, 3]), [1, 2, 3])

    def test_invalid_format(self):
        with self.assertRaises(ValueError):
            parse_page_range("abc")

    def test_invalid_range(self):
        with self.assertRaises(ValueError):
            parse_page_range("7-4")

    def test_zero_page(self):
        with self.assertRaises(ValueError):
            parse_page_range("0")


class TestGetPdfPageCount(unittest.TestCase):
    """Test get_pdf_page_count function."""

    def test_file_not_found(self):
        with self.assertRaises(PDFProcessingError):
            get_pdf_page_count("/nonexistent/file.pdf")


class TestSlicePdf(unittest.TestCase):
    """Test slice_pdf function."""

    def test_file_not_found(self):
        with self.assertRaises(PDFProcessingError):
            slice_pdf("/nonexistent/file.pdf", "1-2")


if __name__ == "__main__":
    unittest.main()