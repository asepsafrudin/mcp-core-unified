import os
import sys
import copy
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Add project root to sys.path
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

def set_vmerge_xml(tc, merge_type):
    tcPr = tc.get_or_add_tcPr()
    vMerge_list = tcPr.xpath('w:vMerge')
    if vMerge_list:
        vMerge = vMerge_list[0]
    else:
        vMerge = OxmlElement('w:vMerge')
        tcPr.append(vMerge)
    if merge_type == 'restart':
        vMerge.set(qn('w:val'), 'restart')
    else:
        if qn('w:val') in vMerge.attrib:
            del vMerge.attrib[qn('w:val')]

def copy_cell_content_xml(src_cell, dst_cell):
    """
    Deep copy all paragraphs from src_cell to dst_cell at XML level
    to preserve numbering, styles, and multi-paragraph structure.
    """
    # Remove the default empty paragraph in the new cell
    for p in dst_cell.paragraphs:
        p._element.getparent().remove(p._element)
    
    # Deep copy each paragraph element from source
    for p in src_cell.paragraphs:
        new_p = copy.deepcopy(p._p)
        dst_cell._tc.append(new_p)

def rebuild_dim_with_master_format(input_path, output_path):
    print(f"Loading original master: {input_path}")
    doc_src = Document(input_path)
    table_src = doc_src.tables[0]
    
    agencies = [
        "KEMENKOPOLHUKAM", "KEMENKO BIDANG HUKUM, HAM, IMIGRASI DAN PEMASYARAKATAN",
        "KEMENDAGRI", "KEMENLU", "SETKAB", "KKP", "KEMENKUM", "KEMENKEU",
        "SETNEG", "BAPPENAS", "KEMENHAN"
    ]

    new_doc = Document()
    # Copy section properties from original if possible (page size, orientation)
    # new_doc.sections[0].page_width = doc_src.sections[0].page_width
    # new_doc.sections[0].page_height = doc_src.sections[0].page_height
    
    new_table = new_doc.add_table(rows=0, cols=9)
    new_table.style = 'Table Grid'

    print("Building full table with deep XML copying...")
    dim_counter = 0
    
    for i, src_row in enumerate(table_src.rows):
        # Determine if we should duplicate this row
        is_data_row = i >= 1 # Row 1 is header
        has_content = src_row.cells[1].text.strip() or src_row.cells[4].text.strip()
        
        # If it's a data row with content, we duplicate 11 times
        # Special case: first 155 rows are already 11-row blocks? 
        # No, let's treat every row that is NOT part of an existing 11-block as a new block.
        # Actually, simpler: if it's the original file, rows 1-155 are already agencies.
        # Rows 156-496 are single lines.
        
        if i == 0: # Header
            new_row = new_table.add_row()
            for j in range(9):
                new_row.cells[j].text = src_row.cells[j].text
        elif i < 156: # Already agencies block
            new_row = new_table.add_row()
            # Copy Col 1-6 using Deep Copy
            for j in range(6):
                copy_cell_content_xml(src_row.cells[j], new_row.cells[j])
            # Set agency
            new_row.cells[8].text = src_row.cells[8].text
            # No Dim number for existing blocks for now or keep original?
            new_row.cells[0].text = src_row.cells[0].text
        else: # Single line that needs duplication
            if has_content:
                dim_counter += 1
                for idx, agency in enumerate(agencies):
                    new_row = new_table.add_row()
                    # Copy Col 1-6 using Deep Copy
                    for j in range(6):
                        copy_cell_content_xml(src_row.cells[j], new_row.cells[j])
                    # Set agency
                    new_row.cells[8].text = agency
                    # Fill NO. DIM on the first row of block
                    if idx == 0:
                        new_row.cells[0].text = f"N.{dim_counter}"
                    # Apply Vertical Merge (Continue) while building for efficiency
                    if idx > 0:
                        for j in range(6):
                            set_vmerge_xml(new_row.cells[j]._tc, 'continue')
                    else:
                        for j in range(6):
                            set_vmerge_xml(new_row.cells[j]._tc, 'restart')
            else:
                # Empty row
                new_row = new_table.add_row()
                for j in range(9):
                    copy_cell_content_xml(src_row.cells[j], new_row.cells[j])

        if i % 100 == 0:
            print(f"  Processed {i} source rows...")

    print(f"Saving formatted master: {output_path}")
    new_doc.save(output_path)
    print("Success! Document rebuilt with preserved paragraph formatting and numbering.")

if __name__ == "__main__":
    src = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026.docx"
    out = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_FORMATTED.docx"
    rebuild_dim_with_master_format(src, out)
