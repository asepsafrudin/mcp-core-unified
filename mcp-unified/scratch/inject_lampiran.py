import json
from pathlib import Path

ssot_path = Path('/home/aseps/MCP/workspace/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_single_source_of_truth.json')
lamp_path = Path('/home/aseps/MCP/workspace/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_lampiran.json')

with open(ssot_path, 'r', encoding='utf-8') as f:
    ssot_data = json.load(f)

with open(lamp_path, 'r', encoding='utf-8') as f:
    lamp_data = json.load(f)

# The lampiran file IS the lampiran section
ssot_data['lampiran'] = lamp_data

with open(ssot_path, 'w', encoding='utf-8') as f:
    json.dump(ssot_data, f, ensure_ascii=False, indent=2)

print("Injected fixed lampiran into SSOT JSON.")
