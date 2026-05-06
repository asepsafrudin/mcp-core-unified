from docx import Document
from docx.shared import Pt
import re

def normalize_dim(dim_text):
    return re.sub(r'[^0-9a-zA-Z]', '', dim_text).strip()

def get_setkab_data_list(file_path):
    print(f"Reading Setkab data from {file_path}...")
    doc = Document(file_path)
    table = doc.tables[0]
    data_list = []
    
    for i, row in enumerate(table.rows):
        if i == 0: continue
        try:
            dim_raw = row.cells[0].text.strip()
            sub_raw = row.cells[5].text.strip()
            # We store everything in order
            data_list.append({'dim_key': normalize_dim(dim_raw), 'content': sub_raw})
        except Exception:
            continue
    return data_list

def complete_and_format():
    setkab_path = "/home/aseps/MCP/storage/office/DIM RUU Daerah Kepulauan_Setkab.docx"
    # Using the previous updated file as source to preserve existing work
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_UPDATED.docx"
    output_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_PERFECT.docx"
    
    setkab_data = get_setkab_data_list(setkab_path)
    # Create a lookup for DIM-based matching (for 15+)
    setkab_dict = {d['dim_key']: d['content'] for d in setkab_data if d['dim_key']}
    
    print(f"Opening Master file for final touch: {master_path}")
    doc = Document(master_path)
    table = doc.tables[0]
    
    current_dim_key = ""
    
    print("Processing Master rows (Items 1-15 and Formatting)...")
    all_rows = list(table.rows)
    for i, row in enumerate(all_rows):
        if i == 0: continue
        
        row_cells = row.cells
        dim_text = row_cells[0].text.strip()
        if dim_text:
            current_dim_key = normalize_dim(dim_text)
        
        # Determine if this is a SETKAB row (Col 8)
        # Agency names are in Col 8
        if len(row_cells) > 8:
            agency_text = row_cells[8].text.strip()
            
            # 1. SPECIAL LOGIC FOR ITEMS 1-14 (Using row offset)
            # Row 1-154 in Master correspond to items 1-14
            if i <= 154:
                # SETKAB rows are 5, 16, 27, 38, 49, 60, 71, 82, 93, 104, 115, 126, 137, 148
                if (i - 5) % 11 == 0:
                    item_idx = (i - 5) // 11
                    if item_idx < len(setkab_data):
                        content = setkab_data[item_idx]['content']
                        row_cells[8].text = f"SETKAB: {content}"
            
            # 2. FORMATTING STEP (Arial 10)
            # Apply to every row where Column 8 starts with "SETKAB:" or was just updated
            text = row_cells[8].text.strip()
            if text.startswith("SETKAB:"):
                # Clear and re-apply with formatting
                row_cells[8].text = text # Reset to clear nested formatting
                for paragraph in row_cells[8].paragraphs:
                    for run in paragraph.runs:
                        run.font.name = 'Arial'
                        run.font.size = Pt(10)
        
        if i % 500 == 0:
            print(f"  Processed {i} / {len(all_rows)} rows...")

    print(f"Saving final perfect document to: {output_path}")
    doc.save(output_path)
    print("Done!")

if __name__ == "__main__":
    complete_and_format()
