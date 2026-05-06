import json
import re

def normalize(text):
    if not text: return ""
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def debug_json_match():
    json_path = "/home/aseps/MCP/storage/office/master_dim.json"
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    search_keyword = "Dana Perimbangan adalah jenis dana transfer"
    search_norm = normalize(search_keyword)
    
    print(f"Searching for: '{search_keyword}'")
    print(f"Search Norm: {search_norm}")
    
    found = False
    for i, row in enumerate(data):
        m_txt = row['draft_2020']
        m_norm = normalize(m_txt)
        
        # Check if "Dana Perimbangan" is in m_txt
        if "Dana Perimbangan" in m_txt:
            print(f"\nMatch Found at Record {i}:")
            print(f"Original: {m_txt}")
            print(f"Normalized: {m_norm}")
            
            # Why did partial match fail?
            if m_norm in search_norm:
                print("m_norm is IN search_norm: TRUE")
            if search_norm in m_norm:
                print("search_norm is IN m_norm: TRUE")
            else:
                print("Both partial matches failed.")
            found = True
            break
            
    if not found:
        print("Keyword not found in JSON database.")

if __name__ == "__main__":
    debug_json_match()
