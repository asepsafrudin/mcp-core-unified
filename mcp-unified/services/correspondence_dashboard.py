"""
Correspondence Dashboard Service.
Provides analytical views and search capabilities across multiple directorate spreadsheets.
"""
import os
import sys
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional

PROJECT_ROOT = "/home/aseps/MCP/mcp-unified"
sys.path.insert(0, PROJECT_ROOT)

from observability.logger import logger

STORAGE_DIR = "/home/aseps/MCP/storage/admin_data/korespondensi"
SYNC_CONFIG = os.path.join(PROJECT_ROOT, "knowledge/sync_targets.json")
SYNC_STATE = os.path.join(STORAGE_DIR, "sync_state.json")

class CorrespondenceDashboard:
    def __init__(self):
        self.targets = self._load_targets()
    
    def _load_targets(self) -> List[Dict]:
        if os.path.exists(SYNC_CONFIG):
            with open(SYNC_CONFIG, 'r') as f:
                return json.load(f)
        return []

    def get_sync_status(self) -> Dict[str, Any]:
        """Get the last sync time and status for all targets."""
        state = {}
        if os.path.exists(SYNC_STATE):
            with open(SYNC_STATE, 'r') as f:
                state = json.load(f)
        
        status_report = []
        for target in self.targets:
            ns = target['namespace']
            ns_state = state.get(ns, {})
            last_sync = ns_state.get('last_sync', 'Never')
            
            status_report.append({
                "name": target['name'],
                "namespace": ns,
                "last_sync": last_sync,
                "spreadsheet_id": target['spreadsheet_id']
            })
        return status_report

    def get_recent_summary(self, limit_per_ns: int = 2) -> str:
        """Generate a text summary of recent PUU letters for a dashboard view."""
        report = "📊 *DASHBOARD KORESPONDENSI PUU*\n\n"
        
        # 1. POSISI PUU (Internal/Kompilasi) - Filtered by POSISI (Index 5) contains "PUU"
        internal_masuk_ns = "korespondensi_sekretariat_internal_masuk"
        file_path = os.path.join(STORAGE_DIR, f"{internal_masuk_ns}_data.json")
        report += "*📂 SURAT POSISI DI PUU*\n"
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    values = data.get("values", [])
                    if len(values) > 1:
                        rows = values[1:]
                        # Filter rows where index 5 (POSISI) contains "PUU"
                        # Pattern example: "SES 28/1 PRC PUU 29/1"
                        puu_rows = []
                        for r in rows:
                            if len(r) > 5 and "PUU" in str(r[5]).upper():
                                puu_rows.append(r)
                        
                        # Take latest N from filtered list
                        latest = puu_rows[-limit_per_ns:][::-1]
                        
                        if not latest:
                            report += "   _Tidak ada surat dengan posisi PUU_\n"
                        for row in latest:
                            tgl = row[1].split(' ')[0] if len(row) > 1 and row[1] else "?"
                            no = row[2] if len(row) > 2 else "-"
                            hal = row[4] if len(row) > 4 else "-"
                            pos = row[5] if len(row) > 5 else "-"
                            report += f"   • [{tgl}] *{no}*\n     _{hal[:100]}..._\n     📍 _{pos}_\n"
                    else:
                        report += "   _Data kosong_\n"
            except Exception as e:
                report += f"   ⚠️ Error loading data: {str(e)}\n"
        else:
            report += "   _Data tracking belum tersinkron_\n"
            
        report += "\n"
        
        # 2. MASUK/EKSTERNAL - Using Dispo PUU sheet
        dispo_ns = "korespondensi_sekretariat_dispo_puu"
        file_path = os.path.join(STORAGE_DIR, f"{dispo_ns}_data.json")
        report += "*📥 DISPOSISI SURAT (EKSTERNAL)*\n"
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    values = data.get("values", [])
                    if len(values) > 1:
                        # Skip header and filter out empty rows (Dari/index 7 is usually key)
                        rows = [r for r in values[1:] if len(r) > 7 and r[7] and str(r[7]).strip() and str(r[7]).lower() != "null"]
                        latest = rows[-limit_per_ns:][::-1]
                        
                        if not latest:
                            report += "   _Tidak ada disposisi terbaru_\n"
                        for row in latest:
                            # Index 7: Dari, Index 8: No Surat, Index 9: Perihal
                            dari = row[7] if len(row) > 7 else "Instansi ?"
                            no = row[8] if len(row) > 8 else "-"
                            pri = row[9] if len(row) > 9 else "-"
                            report += f"   • *{dari}*\n     _{no}_ | _{pri[:80]}..._\n"
                    else:
                        report += "   _Data kosong_\n"
            except Exception as e:
                report += f"   ⚠️ Error loading data: {str(e)}\n"
        else:
            report += "   _Data disposisi belum tersinkron_\n"
            
        return report

    def search_letters(self, query: str, namespace: Optional[str] = None) -> List[Dict]:
        """Search letters locally for high-speed bot interaction."""
        query = query.lower()
        results = []
        
        targets_to_search = self.targets
        if namespace:
            targets_to_search = [t for t in self.targets if t['namespace'] == namespace]
            
        for target in targets_to_search:
            ns = target['namespace']
            file_path = os.path.join(STORAGE_DIR, f"{ns}_data.json")
            
            if not os.path.exists(file_path):
                continue
                
            with open(file_path, 'r') as f:
                data = json.load(f)
                values = data.get('values', [])
                
            header = values[0] if values else []
            for row_idx, row in enumerate(values[1:]):
                row_str = " ".join([str(cell) for cell in row]).lower()
                if query in row_str:
                    results.append({
                        "direktorat": target['name'],
                        "row_data": row,
                        "header": header,
                        "spreadsheet_id": target['spreadsheet_id'],
                        "row_num": row_idx + 2
                    })
                    
        return results

# Helper for bot integration
def format_search_results(results: List[Dict], query: str) -> str:
    if not results:
        return f"🔍 Tidak ditemukan hasil untuk: *{query}*"
    
    output = f"🔍 Hasil pencarian untuk: *{query}* ({len(results)} temuan)\n\n"
    # Show top 5
    for res in results[:5]:
        data = res['row_data']
        # Try to extract key info
        date = data[0] if len(data) > 0 else "N/A"
        no_surat = data[1] if len(data) > 1 else "N/A"
        subject = data[2] if len(data) > 2 else "N/A"
        
        output += f"📌 *{res['direktorat']}*\n"
        output += f"📅 Tgl: {date}\n"
        output += f"📂 No: {no_surat}\n"
        output += f"📝 Hal: {subject}\n"
        output += f"🔗 [Detail Baris {res['row_num']}](https://docs.google.com/spreadsheets/d/{res['spreadsheet_id']}/edit#gid=0&range={res['row_num']}:{res['row_num']})\n\n"
        
    if len(results) > 5:
        output += f"_...dan {len(results)-5} hasil lainnya._"
        
    return output

if __name__ == "__main__":
    db = CorrespondenceDashboard()
    print(db.get_recent_summary())
