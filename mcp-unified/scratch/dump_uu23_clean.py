import os
import json
import psycopg2
from decimal import Decimal
from datetime import datetime, date

DB_PARAMS = {
    "host": "localhost",
    "port": 5433,
    "database": "mcp_knowledge",
    "user": "mcp_user",
    "password": "mcp_password_2024"
}

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def dump_table_to_json(table_name, output_file):
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        
        # Get column names
        cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}' ORDER BY ordinal_position")
        columns = [row[0] for row in cur.fetchall()]
        
        # Get data
        cur.execute(f"SELECT * FROM {table_name}")
        rows = cur.fetchall()
        
        # Convert to list of dicts
        data = []
        for row in rows:
            data.append(dict(zip(columns, row)))
            
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
            
        print(f"Successfully dumped {len(data)} rows from {table_name} to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    out_path = "/home/aseps/MCP/storage/office/data/uu23_implementasi_clean.json"
    dump_table_to_json("uu23_implementasi_clean", out_path)
