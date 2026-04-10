"""
Text-to-SQL Service

Konversi pertanyaan bahasa natural menjadi SQL query
untuk query database PostgreSQL.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TextToSQLResult:
    """Hasil konversi text-to-SQL."""
    sql: str
    explanation: str
    is_valid: bool
    error: Optional[str] = None


class TextToSQLService:
    """
    Service untuk konversi text natural ke SQL query.
    
    Menggunakan AI untuk generate SQL dari pertanyaan user,
    dengan validasi dan sanitasi keamanan.
    """
    
    # Schema database untuk context - Auto-detected dari database
    DATABASE_SCHEMA = """
## Database Schema - MCP Korespondensi (Port 5433)

### 📬 Tabel: correspondence_letters
Tabel utama yang menyimpan data surat masuk, keluar, dan disposisi.

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| letter_number | TEXT | Nomor surat resmi |
| letter_date | DATE | Tanggal surat |
| received_date | DATE | Tanggal diterima |
| sender | TEXT | Pengirim surat |
| recipient | TEXT | Penerima surat |
| subject | TEXT | Perihal surat |
| position_raw | TEXT | Posisi terkini surat (e.g. 'PUU', 'MEJA KEPALA') |
| status | TEXT | Status surat |
| source_type | TEXT | 'internal', 'external', atau 'outgoing' |

### 📝 Tabel: surat_masuk_puu
Detail data surat masuk khusus unit PUU.

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| nomor_nd | TEXT | Nomor Nota Dinas |
| dari | TEXT | Pengirim |
| hal | TEXT | Perihal |
| tanggal_surat | DATE | Tanggal surat |
| no_agenda_dispo | TEXT | Nomor agenda disposisi |

### 📄 Tabel: knowledge_documents
Dokumen knowledge base dengan embeddings.

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| content | TEXT | Konten teks |
| metadata | JSONB | Source, doc_type, dll |
| namespace | TEXT | 'default', 'legal', 'puu_2026' |

### 🖼️ Tabel: vision_results  
Hasil OCR file PDF dan gambar.

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| file_name | TEXT | Nama file (e.g. '0161-UND-PUU-2026.pdf') |
| extracted_text | TEXT | Teks hasil OCR |
| status | VARCHAR | Status pemrosesan |
"""
    
    # Query patterns yang tidak diizinkan
    FORBIDDEN_PATTERNS = [
        r'DROP\s+',
        r'DELETE\s+FROM',
        r'UPDATE\s+\w+\s+SET',
        r'INSERT\s+INTO',
        r'ALTER\s+',
        r'TRUNCATE\s+',
        r'CREATE\s+',
        r'EXEC\s*\(',
        r'EXECUTE\s*\(',
        r'UNION\s+SELECT',
        r'--',
        r'/\*',
    ]
    
    def __init__(self, ai_service=None):
        """
        Initialize TextToSQL service.
        
        Args:
            ai_service: Instance AIService untuk generate SQL
        """
        self.ai_service = ai_service
        self._schema_cache: Optional[str] = None
    
    def _build_system_prompt(self) -> str:
        """Build system prompt untuk SQL generation."""
        return f"""Kamu adalah SQL expert untuk PostgreSQL database.

{self.DATABASE_SCHEMA}

## Instruksi
1. Konversi pertanyaan user menjadi SQL query SELECT yang valid
2. Hanya gunakan SELECT statements - tidak boleh INSERT, UPDATE, DELETE, DROP
3. Gunakan fungsi PostgreSQL yang tepat (COUNT, SUM, AVG, etc.)
4. Untuk text search, gunakan ILIKE atau LIKE
5. Untuk date filtering, gunakan CURRENT_DATE, CURRENT_TIMESTAMP
6. Urutkan hasil jika relevan (ORDER BY)
7. Limit hasil maksimal 50 rows

## Format Output
Kembalikan JSON dengan format:
{{
    "sql": "SELECT ...",
    "explanation": "Penjelasan singkat query dalam Bahasa Indonesia"
}}

## Contoh
User: "Berapa dokumen PUU tahun 2026?"
Output: {{
    "sql": "SELECT COUNT(*) FROM vision_results WHERE file_name ILIKE '%PUU%2026%'",
    "explanation": "Menghitung jumlah file PUU 2026 dari hasil OCR"
}}
"""
    
    def _validate_sql(self, sql: str) -> Tuple[bool, Optional[str]]:
        """
        Validasi SQL query untuk keamanan.
        
        Returns:
            (is_valid, error_message)
        """
        sql_upper = sql.strip().upper()
        
        # Must start with SELECT
        if not sql_upper.startswith('SELECT'):
            return False, "Query harus dimulai dengan SELECT"
        
        # Check forbidden patterns
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                return False, f"Query mengandung pattern yang tidak diizinkan"
        
        # Basic SQL validation
        if sql.count('(') != sql.count(')'):
            return False, "Unbalanced parentheses"
        
        return True, None
    
    def _sanitize_sql(self, sql: str) -> str:
        """
        Sanitasi SQL query tambahan.
        
        Args:
            sql: Raw SQL dari AI
            
        Returns:
            Clean SQL
        """
        # Remove markdown code blocks if present
        sql = re.sub(r'```sql\s*', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'```\s*$', '', sql)
        
        # Clean up whitespace
        sql = sql.strip()
        
        # Ensure LIMIT if not present and not a count query
        sql_upper = sql.upper()
        if 'LIMIT' not in sql_upper and 'COUNT' not in sql_upper:
            sql = sql.rstrip(';') + ' LIMIT 50'
        
        return sql
    
    def _extract_json_from_response(self, text: str) -> Dict[str, Any]:
        """
        Extract JSON dari response AI.
        
        Args:
            text: Response text dari AI
            
        Returns:
            Dictionary dengan sql dan explanation
        """
        import json
        
        # Try to find JSON in response
        json_match = re.search(r'\{[\s\S]*?\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Fallback: parse manually
        sql_match = re.search(r'(?:sql|query)\s*[:=]\s*["\']?(SELECT[^"\']+)["\']?', text, re.IGNORECASE)
        explanation_match = re.search(r'explanation\s*[:=]\s*["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        
        return {
            "sql": sql_match.group(1).strip() if sql_match else "",
            "explanation": explanation_match.group(1).strip() if explanation_match else "Query database"
        }
    
    async def convert_to_sql(self, question: str, user_id: int = 0) -> TextToSQLResult:
        """
        Konversi pertanyaan bahasa natural ke SQL.
        
        Supports both legacy AI service and new HybridSQLProvider.
        
        Args:
            question: Pertanyaan user dalam bahasa natural
            user_id: User ID untuk tracking
            
        Returns:
            TextToSQLResult dengan SQL query dan metadata
        """
        if not self.ai_service:
            logger.error("AI service not available")
            return TextToSQLResult(
                sql="",
                explanation="",
                is_valid=False,
                error="AI service tidak tersedia"
            )
        
        try:
            # Check if using HybridSQLProvider (new)
            if hasattr(self.ai_service, 'generate_sql'):
                # Hybrid provider with Ollama + Fallback
                response = await self.ai_service.generate_sql(
                    question=question,
                    schema=self.DATABASE_SCHEMA,
                    user_id=user_id
                )
                
                if not response.success:
                    return TextToSQLResult(
                        sql="",
                        explanation="",
                        is_valid=False,
                        error=response.error or "Failed to generate SQL"
                    )
                
                raw_sql = response.text
                
                # Determine provider used
                provider = response.provider
                if "ollama" in provider:
                    explanation = "SQL generated by local SQLCoder (private & accurate)"
                else:
                    explanation = f"SQL generated by {provider} (fast fallback)"
                
            else:
                # Legacy AI service (Groq/Gemini direct)
                system_prompt = self._build_system_prompt()
                
                ai_response = await self.ai_service.generate_response(
                    user_id=user_id,
                    message=question,
                    system_prompt=system_prompt
                )
                
                # Parse response
                result_data = self._extract_json_from_response(ai_response.text)
                
                raw_sql = result_data.get("sql", "")
                explanation = result_data.get("explanation", "AI-generated SQL")
            
            # Sanitize SQL
            sql = self._sanitize_sql(raw_sql)
            
            # Validate SQL
            is_valid, error = self._validate_sql(sql)
            
            if not is_valid:
                logger.warning(f"Invalid SQL generated: {error}")
                return TextToSQLResult(
                    sql="",
                    explanation=explanation,
                    is_valid=False,
                    error=f"SQL tidak valid: {error}"
                )
            
            logger.info(f"✅ Text-to-SQL ({provider if 'provider' in locals() else 'legacy'}): '{question[:50]}...' → '{sql[:50]}...'")
            
            return TextToSQLResult(
                sql=sql,
                explanation=explanation,
                is_valid=True
            )
            
        except Exception as e:
            logger.error(f"Text-to-SQL conversion failed: {e}")
            return TextToSQLResult(
                sql="",
                explanation="",
                is_valid=False,
                error=f"Gagal konversi: {str(e)}"
            )
    
    def get_hybrid_stats(self) -> Dict[str, Any]:
        """
        Get hybrid provider statistics if available.
        
        Returns:
            Dictionary dengan statistik atau empty dict
        """
        if hasattr(self.ai_service, 'get_stats'):
            return self.ai_service.get_stats()
        return {}
    
    async def execute_natural_query(
        self, 
        question: str, 
        knowledge_service
    ) -> Dict[str, Any]:
        """
        Execute query dari pertanyaan bahasa natural.
        
        Args:
            question: Pertanyaan user
            knowledge_service: Instance KnowledgeService untuk eksekusi SQL
            
        Returns:
            Dictionary dengan hasil query
        """
        # Convert to SQL
        sql_result = await self.convert_to_sql(question)
        
        if not sql_result.is_valid:
            return {
                "success": False,
                "error": sql_result.error,
                "question": question,
                "sql": None
            }
        
        # Execute SQL
        try:
            result = await knowledge_service.sql_query(sql_result.sql)
            
            return {
                "success": True,
                "question": question,
                "sql": sql_result.sql,
                "explanation": sql_result.explanation,
                "columns": result.columns if result else [],
                "rows": result.rows if result else [],
                "row_count": result.row_count if result else 0
            }
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return {
                "success": False,
                "error": f"Eksekusi query gagal: {str(e)}",
                "question": question,
                "sql": sql_result.sql
            }
    
    def format_result_as_text(self, result: Dict[str, Any]) -> str:
        """
        Format hasil query menjadi text untuk Telegram.
        
        Args:
            result: Dictionary hasil dari execute_natural_query
            
        Returns:
            Formatted text
        """
        if not result["success"]:
            return (
                f"❌ *Query Gagal*\n\n"
                f"Pertanyaan: _{result['question']}_\n"
                f"Error: `{result.get('error', 'Unknown error')}`"
            )
        
        lines = [
            f"📊 *Hasil Query*\n",
            f"❓ Pertanyaan: _{result['question'][:100]}_",
            f"💡 Penjelasan: {result.get('explanation', 'Query database')}",
            f"```sql\n{result['sql'][:200]}{'...' if len(result['sql']) > 200 else ''}\n```\n",
        ]
        
        if result['row_count'] == 0:
            lines.append("📭 *Tidak ada data ditemukan*")
        else:
            lines.append(f"📋 *{result['row_count']} baris ditemukan*\n")
            
            # Format header
            headers = result['columns']
            lines.append(" | ".join(f"*{h}*" for h in headers))
            lines.append("—" * 40)
            
            # Format rows (max 10 untuk Telegram)
            for row in result['rows'][:10]:
                formatted_row = []
                for cell in row:
                    cell_str = str(cell)[:30]  # Truncate long cells
                    formatted_row.append(cell_str)
                lines.append(" | ".join(formatted_row))
            
            if result['row_count'] > 10:
                lines.append(f"\n_... dan {result['row_count'] - 10} baris lainnya_")
        
        return "\n".join(lines)