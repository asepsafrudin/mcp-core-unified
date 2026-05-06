from docx import Document
from docx.shared import Pt
import re

def migrate_data():
    source_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_GABUNG_KL.docx"
    output_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_MIGRATED.docx"
    
    print(f"Opening file for migration: {source_path}")
    doc = Document(source_path)
    table = doc.tables[0]
    
    agencies_list = [
        "KEMENKOPOLHUKAM", "KEMENKO BIDANG HUKUM", "KEMENDAGRI", "KEMENLU", 
        "SETKAB", "KKP", "KEMENKUM", "KEMENKEU", "SETNEG", "BAPPENAS", "KEMENHAN"
    ]
    
    updated_count = 0
    print("Processing rows...")
    
    all_rows = list(table.rows)
    for i, row in enumerate(all_rows):
        if i == 0: continue # Skip header
        
        col5_cell = row.cells[5]
        col7_cell = row.cells[7]
        
        text_7 = col7_cell.text.strip()
        
        if text_7:
            # Check for "AGENCY: CONTENT" pattern
            if ":" in text_7:
                parts = text_7.split(":", 1)
                agency_name = parts[0].strip()
                content = parts[1].strip()
                
                col5_cell.text = agency_name
                col7_cell.text = content
                updated_count += 1
            else:
                # Check if it's just an agency name
                is_agency_only = False
                for agency in agencies_list:
                    if text_7.upper().startswith(agency.upper()):
                        is_agency_only = True
                        break
                
                if is_agency_only:
                    col5_cell.text = text_7
                    col7_cell.text = "" # Clear Column 7
                    updated_count += 1
            
            # Apply Arial 10 formatting to both updated cells
            for cell in [col5_cell, col7_cell]:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.name = 'Arial'
                        run.font.size = Pt(10)
                        
        if i % 500 == 0:
            print(f"  Processed {i} / {len(all_rows)} rows...")

    print(f"Successfully migrated {updated_count} agency names to Column 5.")
    print(f"Saving to: {output_path}")
    doc.save(output_path)
    print("Done!")

if __name__ == "__main__":
    migrate_data()
