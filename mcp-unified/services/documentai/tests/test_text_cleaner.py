"""
Unit tests untuk text_cleaner.py — data cleansing.
"""
import sys
import unittest
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from text_cleaner import clean_cell_text, clean_table_data, normalize_currency


class TestCleanCellText(unittest.TestCase):
    """Test clean_cell_text function."""

    def test_none_returns_empty(self):
        self.assertEqual(clean_cell_text(None), "")

    def test_newlines_removed(self):
        self.assertEqual(clean_cell_text("Hello\nWorld"), "Hello World")

    def test_tabs_removed(self):
        self.assertEqual(clean_cell_text("Hello\tWorld"), "Hello World")

    def test_multiple_spaces_collapsed(self):
        self.assertEqual(clean_cell_text("Hello   World"), "Hello World")

    def test_strip_whitespace(self):
        self.assertEqual(clean_cell_text("  Hello World  "), "Hello World")

    def test_non_breaking_space(self):
        self.assertEqual(clean_cell_text("Hello\u00a0World"), "Hello World")

    def test_number_converted_to_string(self):
        self.assertEqual(clean_cell_text(123), "123")


class TestNormalizeCurrency(unittest.TestCase):
    """Test normalize_currency function."""

    def test_currency_symbol_removed(self):
        self.assertEqual(normalize_currency("Rp 1.234.567"), "1234567")

    def test_thousand_separator_removed(self):
        self.assertEqual(normalize_currency("1.234.567"), "1234567")

    def test_decimal_comma_converted(self):
        self.assertEqual(normalize_currency("1.234.567,89"), "1234567.89")

    def test_none_returns_empty(self):
        self.assertEqual(normalize_currency(None), "")


class TestCleanTableData(unittest.TestCase):
    """Test clean_table_data function."""

    def test_cleans_all_cells(self):
        rows = [
            ["Header 1", "Header 2"],
            ["Value 1\n", "  Value 2  "],
        ]
        result = clean_table_data(rows)
        self.assertEqual(result[0], ["Header 1", "Header 2"])
        self.assertEqual(result[1], ["Value 1", "Value 2"])


if __name__ == "__main__":
    unittest.main()