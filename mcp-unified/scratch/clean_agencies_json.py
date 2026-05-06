import json
import re

def clean_json_data():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_full.json"
    output_path = "/home/aseps/MCP/storage/office/data/dim_v3_cleaned.json"
    
    with open(json_path, "r") as f:
        data = json.load(f)
    
    agencies = [
        "KEMENKOPOLHUKAM", "KEMENKO BIDANG HUKUM, HAM, IMIGRASI DAN PEMASYARAKATAN",
        "KEMENDAGRI", "KEMENLU", "SETKAB", "KKP", "KEMENKUM", "KEMENKEU", 
        "SETNEG", "BAPPENAS", "KEMENHAN", "SETNEG", "KEMENKUMHAM"
    ]
    
    # Patterns to catch:
    # 1. AGENCY: content
    # 2. AGENCY REVIU: content
    # 3. AGENCY - content
    # 4. AGENCY (at start of line, followed by newline)
    
    agency_regex = r'^(' + '|'.join([re.escape(a) for a in agencies]) + r')(?: REVIU| -|:|\s)*[:\-\s\n]+(.*)$'
    
    cleaned_count = 0
    
    for item in data:
        keterangan = item.get('keterangan', '').strip()
        tanggapan = item.get('tanggapan_pemerintah', '').strip()
        
        match = re.match(agency_regex, keterangan, re.IGNORECASE | re.DOTALL)
        if match:
            found_agency = match.group(1).upper()
            remaining_text = match.group(2).strip()
            
            # Clean up: if remaining text starts with "REVIU:" or ":" or "-", strip it again
            remaining_text = re.sub(r'^(?:REVIU|:|-|\s)+', '', remaining_text, flags=re.IGNORECASE).strip()
            
            # Update tanggapan if needed
            if not tanggapan or tanggapan == "PEMERINTAH" or found_agency in tanggapan.upper():
                item['tanggapan_pemerintah'] = found_agency
                item['keterangan'] = remaining_text
                cleaned_count += 1
            else:
                # If they are different, keep both or prioritize?
                # User said: "pindah ke field tanggapan_pemerintah"
                item['tanggapan_pemerintah'] = found_agency
                item['keterangan'] = remaining_text
                cleaned_count += 1

    print(f"Cleaning Results:")
    print(f"- Cleaned {cleaned_count} entries from Keterangan.")
    
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved cleaned JSON to {output_path}")

if __name__ == "__main__":
    clean_json_data()
