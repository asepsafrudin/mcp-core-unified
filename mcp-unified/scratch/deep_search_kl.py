from docx import Document

def deep_search_numbers(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    print(f"Deep searching numbers in: {file_path}")
    found = False
    for i, row in enumerate(table.rows):
        dim = row.cells[0].text.strip()
        if any(char.isdigit() for char in dim) and dim != "NO. DIM":
            print(f"Number found! Row {i} | DIM: {dim} | Agency: {row.cells[2].text.strip()}")
            found = True
            # Print next few rows to see pattern
            for j in range(i+1, i+5):
                if j < len(table.rows):
                    print(f"  Row {j} | DIM: {table.rows[j].cells[0].text.strip()} | Agency: {table.rows[j].cells[2].text.strip()}")
            break
    if not found:
        print("No numbers found in the entire Col 0.")

if __name__ == "__main__":
    deep_search_numbers("/home/aseps/MCP/storage/office/21042026 DIM RUU DAERAH KEPULAUAN GABUNG KL.docx")
