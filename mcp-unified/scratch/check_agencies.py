import json

def check_agencies():
    with open("/home/aseps/MCP/storage/office/data/dim_v3_full.json", "r") as f:
        data = json.load(f)
    
    print("Sample Agency Data (First 20):")
    for i, item in enumerate(data[:20]):
        print(f"Row {i+1}:")
        print(f"  Tanggapan: {item.get('tanggapan_pemerintah')}")
        print(f"  Keterangan: {item.get('keterangan')}")
        print("-" * 20)

if __name__ == "__main__":
    check_agencies()
