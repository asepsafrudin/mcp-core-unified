import re
text = 'KEMENKEU REVIU: \n8 Pasal 20 DIHAPUS'
prefix_pattern = r'^([A-Z0-9\s\-\.]{3,40}):\s*(.*)$'
match = re.match(prefix_pattern, text, re.DOTALL)
if match:
    print("Match!")
    print("G1:", repr(match.group(1)))
    print("G2:", repr(match.group(2)))
else:
    print("No match")
