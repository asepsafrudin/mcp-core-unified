"""
Test Suite for Office Tools Enhancement (P0 Features)
Run with: python test_office_tools.py
"""
import os
import tempfile
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock the register_tool decorator and BaseTool
class MockBaseTool:
    pass

def mock_register_tool(func):
    """Mock decorator that just returns the function"""
    return func

# Mock the tools.base module
import types
mock_base = types.ModuleType('tools.base')
mock_base.BaseTool = MockBaseTool
mock_base.register_tool = mock_register_tool
sys.modules['tools.base'] = mock_base
sys.modules['tools'] = types.ModuleType('tools')
sys.modules['tools'].base = mock_base

from docx_tools import (
    read_docx, write_docx, extract_text_docx, 
    search_replace_docx, apply_paragraph_style_docx
)
from xlsx_tools import (
    read_xlsx, write_xlsx, extract_data_xlsx,
    import_csv_xlsx, export_to_csv_xlsx, set_cell_formula_xlsx
)


def test_docx_search_replace():
    """Test search and replace functionality"""
    print("\n📝 Testing DOCX Search & Replace...")
    
    # Create test document
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
        test_file = f.name
    
    # Write test content
    content = [
        {'type': 'paragraph', 'text': 'Hello World'},
        {'type': 'paragraph', 'text': 'Hello Universe'},
        {'type': 'paragraph', 'text': 'Test Document'}
    ]
    result = write_docx(test_file, content)
    assert result['success'], f"Failed to create test doc: {result}"
    
    # Test search and replace
    result = search_replace_docx(test_file, 'Hello', 'Hi')
    assert result['success'], f"Search replace failed: {result}"
    assert result['replacements_made'] > 0, "No replacements made"
    print(f"  ✅ Search & Replace: {result['replacements_made']} paragraphs modified")
    
    # Verify replacement
    result = read_docx(test_file)
    assert result['success'], f"Failed to read doc: {result}"
    assert 'Hi World' in str(result['paragraphs']), "Replacement not applied"
    print("  ✅ Replacement verified")
    
    # Cleanup
    os.unlink(test_file)
    return True


def test_docx_styling():
    """Test paragraph styling functionality"""
    print("\n🎨 Testing DOCX Paragraph Styling...")
    
    # Create test document
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
        test_file = f.name
    
    # Write test content
    content = [
        {'type': 'paragraph', 'text': 'Test Paragraph'}
    ]
    result = write_docx(test_file, content)
    assert result['success'], f"Failed to create test doc: {result}"
    
    # Test styling
    result = apply_paragraph_style_docx(
        test_file,
        paragraph_idx=0,
        font_name='Arial',
        font_size=14,
        bold=True,
        italic=True,
        alignment='CENTER',
        color='FF0000'
    )
    assert result['success'], f"Styling failed: {result}"
    assert len(result['styles_applied']) > 0, "No styles applied"
    print(f"  ✅ Styles applied: {list(result['styles_applied'].keys())}")
    
    # Cleanup
    os.unlink(test_file)
    return True


def test_csv_import_export():
    """Test CSV import and export functionality"""
    print("\n📊 Testing CSV Import/Export...")
    
    # Create test CSV
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("Name,Age,City\n")
        f.write("Alice,30,New York\n")
        f.write("Bob,25,Los Angeles\n")
        csv_file = f.name
    
    # Create test Excel file path
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        xlsx_file = f.name
    
    # Test CSV to Excel import
    result = import_csv_xlsx(csv_file, xlsx_file, sheet_name='TestSheet')
    assert result['success'], f"CSV import failed: {result}"
    assert result['rows_imported'] == 3, f"Expected 3 rows, got {result['rows_imported']}"
    print(f"  ✅ CSV imported: {result['rows_imported']} rows, {result['columns_imported']} columns")
    
    # Verify Excel file was created
    result = read_xlsx(xlsx_file)
    assert result['success'], f"Failed to read created xlsx: {result}"
    assert 'TestSheet' in result['sheet_names'], "Sheet not created"
    print("  ✅ Excel file verified")
    
    # Test Excel to CSV export
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
        exported_csv = f.name
    
    result = export_to_csv_xlsx(xlsx_file, exported_csv, sheet_name='TestSheet')
    assert result['success'], f"Excel export failed: {result}"
    assert result['rows_exported'] == 3, f"Expected 3 rows, got {result['rows_exported']}"
    print(f"  ✅ Excel exported: {result['rows_exported']} rows")
    
    # Cleanup
    os.unlink(csv_file)
    os.unlink(xlsx_file)
    os.unlink(exported_csv)
    return True


def test_xlsx_formula():
    """Test Excel formula functionality"""
    print("\n🔢 Testing XLSX Formula Support...")
    
    # Create test Excel file
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        test_file = f.name
    
    # Write data with formulas
    data = {
        'Sheet1': [
            [10, 20, 30],
            [40, 50, 60],
            ['=SUM(A1:C1)', '=SUM(A2:C2)', '=A1+A2']
        ]
    }
    result = write_xlsx(test_file, data)
    assert result['success'], f"Failed to create test xlsx: {result}"
    
    # Test setting formula
    result = set_cell_formula_xlsx(test_file, 'Sheet1', 'D1', '=A1+B1+C1')
    assert result['success'], f"Formula setting failed: {result}"
    assert result['formula'] == '=A1+B1+C1', "Formula not set correctly"
    print(f"  ✅ Formula set: {result['formula']}")
    
    # Cleanup
    os.unlink(test_file)
    return True


def run_all_tests():
    """Run all test cases"""
    print("=" * 60)
    print("🧪 OFFICE TOOLS ENHANCEMENT - TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("DOCX Search & Replace", test_docx_search_replace),
        ("DOCX Paragraph Styling", test_docx_styling),
        ("CSV Import/Export", test_csv_import_export),
        ("XLSX Formula Support", test_xlsx_formula),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} - PASSED")
            else:
                failed += 1
                print(f"❌ {test_name} - FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} - ERROR: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 TEST RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
