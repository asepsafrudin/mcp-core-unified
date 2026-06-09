from pathlib import Path

txt_path = Path("/home/aseps/MCP/core/mcp-unified/scratch/combined_uu23_full_ocr_output.txt")

if not txt_path.exists():
    print("Error: file not found.")
else:
    content = txt_path.read_text(encoding="utf-8")
    print(f"Total characters: {len(content)}")
    
    # Search for "LAMPIRAN"
    import re
    matches = [m.start() for m in re.finditer(r"LAMPIRAN", content, re.IGNORECASE)]
    print(f"Total occurrences of 'LAMPIRAN': {len(matches)}")
    
    # Print the surrounding text for the last few occurrences (since lampiran is usually at the end)
    for idx, pos in enumerate(matches[-5:]):
        print(f"\n--- Occurrence {len(matches) - 5 + idx + 1} at char position {pos} ---")
        print(content[pos:pos+500])
        print("-------------------------------------------------------------------")
