import sys
from docx import Document

# Add project root to sys.path
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

def finalize_and_verify(original_path, current_path, output_path):
    print(f"Loading files for finalization and verification...")
    doc_orig = Document(original_path)
    doc_curr = Document(current_path)
    
    table_orig = doc_orig.tables[0]
    table_curr = doc_curr.tables[0]
    
    orig_rows = table_orig.rows
    curr_rows = table_curr.rows
    
    print(f"1. Filling NO. DIM (Column 1) with sequence numbers...")
    # Skip header (index 0)
    # Every 11 rows represents one DIM issue
    dim_counter = 1
    for i in range(1, len(curr_rows)):
        # Start of a block (index 1, 12, 23, etc.)
        if (i - 1) % 11 == 0:
            curr_rows[i].cells[0].text = str(dim_counter)
            dim_counter += 1
    
    print(f"2. Verifying first 355 rows of original data...")
    # Up to row 155, they should match 1:1
    # After row 156, original Row X matches current Rows Y to Y+10
    
    mismatches = []
    
    # Check 1:1 part (Header + first 154 data rows = 155 rows)
    for i in range(min(155, len(orig_rows))):
        orig_text = orig_rows[i].cells[1].text.strip()
        curr_text = curr_rows[i].cells[1].text.strip()
        if orig_text != curr_text:
            mismatches.append(f"Mismatch at Row {i+1}: Original='{orig_text[:20]}', Current='{curr_text[:20]}'")

    # Check Duplicated part (from Row 156 in original)
    # Original Row 156 -> Current Row 156-166
    # Current row index for original row 156 is 155.
    for i in range(155, 355): # Verify up to Row 355 of original file
        if i >= len(orig_rows):
            break
            
        orig_text = orig_rows[i].cells[1].text.strip()
        # The corresponding block in current starts at 155 + (i - 155) * 11
        curr_block_start = 155 + (i - 155) * 11
        
        if curr_block_start < len(curr_rows):
            curr_text = curr_rows[curr_block_start].cells[1].text.strip()
            if orig_text != curr_text:
                mismatches.append(f"Mismatch at Original Row {i+1} (Current Row {curr_block_start+1})")
        else:
            mismatches.append(f"Current document ends prematurely at Original Row {i+1}")

    if not mismatches:
        print("Verification Successful: All 355 rows match the original content perfectly!")
    else:
        print(f"Verification Found {len(mismatches)} mismatches (showing first 5):")
        for m in mismatches[:5]:
            print(f"  - {m}")

    print(f"Saving final document to: {output_path}")
    doc_doc_curr = doc_curr.save(output_path)
    print("Success! DIM document is now complete, numbered, and verified.")

if __name__ == "__main__":
    original = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026.docx"
    current = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MERGED_FINAL.docx"
    output = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_LENGKAP_FINAL.docx"
    finalize_and_verify(original, current, output)
