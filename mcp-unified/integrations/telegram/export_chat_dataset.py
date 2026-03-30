"""
Export Chat History untuk ML/AI Training Dataset

Menyimpan chat history dalam format yang bisa digunakan untuk:
- Training data untuk analitik/ML
- Dataset legacy untuk eksperimen Text-to-SQL
- Analisis kualitas interaksi
"""
import asyncio
import json
import csv
from datetime import datetime
from typing import List, Dict
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "services"))
from knowledge_service import KnowledgeService


class ChatDatasetExporter:
    """Export chat history untuk ML training dan dataset legacy."""
    
    def __init__(self):
        self.knowledge = KnowledgeService()
    
    async def export_to_json(self, output_file: str = "chat_dataset.json") -> int:
        """
        Export chat history ke JSON format.
        
        Format legacy untuk Text-to-SQL training:
        {
            "instruction": "berapa dokumen PUU 2026?",
            "input": "",
            "output": "SELECT COUNT(*) FROM vision_results WHERE file_name ILIKE '%PUU%2026%'",
            "history": [
                ["user", "berapa dokumen PUU 2026?"],
                ["assistant", "SELECT COUNT(*)..."]
            ]
        }
        """
        await self.knowledge.initialize()
        
        query = """
            SELECT 
                user_id,
                username,
                message,
                response,
                created_at
            FROM telegram_messages
            WHERE message NOT LIKE '/%'
            AND LENGTH(message) > 5
            ORDER BY created_at DESC
        """
        
        result = await self.knowledge.sql_query(query)
        
        dataset = []
        for row in result.rows:
            user_id, username, message, response, created_at = row
            
            # Format legacy untuk eksperimen Text-to-SQL
            entry = {
                "instruction": message,
                "input": "",
                "output": response,
                "history": [
                    ["user", message],
                    ["assistant", response]
                ],
                "metadata": {
                    "user_id": user_id,
                    "username": username,
                    "timestamp": created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at),
                    "type": "text_to_sql"
                }
            }
            dataset.append(entry)
        
        # Save to JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Exported {len(dataset)} records to {output_file}")
        return len(dataset)
    
    async def export_to_csv(self, output_file: str = "chat_dataset.csv") -> int:
        """Export chat history ke CSV format."""
        await self.knowledge.initialize()
        
        query = """
            SELECT 
                username,
                message,
                response,
                created_at
            FROM telegram_messages
            WHERE message NOT LIKE '/%'
            AND LENGTH(message) > 5
            ORDER BY created_at DESC
        """
        
        result = await self.knowledge.sql_query(query)
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['username', 'question', 'sql_response', 'timestamp'])
            
            for row in result.rows:
                username, message, response, created_at = row
                writer.writerow([
                    username,
                    message,
                    response,
                    created_at
                ])
        
        print(f"✅ Exported {result.row_count} records to {output_file}")
        return result.row_count
    
    async def export_sql_pairs(self, output_file: str = "sql_pairs.jsonl") -> int:
        """
        Export natural language -> SQL pairs untuk training legacy.
        
        Format JSONL (one JSON per line):
        {"question": "...", "sql": "...", "database": "mcp_knowledge"}
        """
        await self.knowledge.initialize()
        
        query = """
            SELECT 
                message,
                response
            FROM telegram_messages
            WHERE message LIKE '/query %'
            AND response LIKE '%```sql%'
            ORDER BY created_at DESC
        """
        
        result = await self.knowledge.sql_query(query)
        
        count = 0
        with open(output_file, 'w', encoding='utf-8') as f:
            for row in result.rows:
                message, response = row
                
                # Extract question (remove /query prefix)
                question = message[7:].strip()  # Remove "/query "
                
                # Extract SQL from response
                import re
                sql_match = re.search(r'```sql\s*(.*?)\s*```', response, re.DOTALL)
                if sql_match:
                    sql = sql_match.group(1).strip()
                    
                    entry = {
                        "question": question,
                        "sql": sql,
                        "database": "mcp_knowledge",
                        "type": "text_to_sql"
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
                    count += 1
        
        print(f"✅ Exported {count} SQL pairs to {output_file}")
        return count
    
    async def get_stats(self) -> Dict:
        """Get chat statistics."""
        await self.knowledge.initialize()
        
        stats = {}
        
        # Total messages
        result = await self.knowledge.sql_query(
            "SELECT COUNT(*) FROM telegram_messages"
        )
        stats['total_messages'] = result.rows[0][0] if result.rows else 0
        
        # Total users
        result = await self.knowledge.sql_query(
            "SELECT COUNT(DISTINCT user_id) FROM telegram_messages"
        )
        stats['total_users'] = result.rows[0][0] if result.rows else 0
        
        # Messages today
        result = await self.knowledge.sql_query(
            "SELECT COUNT(*) FROM telegram_messages WHERE DATE(created_at) = CURRENT_DATE"
        )
        stats['messages_today'] = result.rows[0][0] if result.rows else 0
        
        # Top users
        result = await self.knowledge.sql_query("""
            SELECT username, COUNT(*) as count
            FROM telegram_messages
            GROUP BY username
            ORDER BY count DESC
            LIMIT 5
        """)
        stats['top_users'] = [(row[0], row[1]) for row in result.rows]
        
        return stats


async def main():
    exporter = ChatDatasetExporter()
    
    print("📊 Chat Dataset Exporter")
    print("=" * 50)
    
    # Get stats
    stats = await exporter.get_stats()
    print(f"\n📈 Statistics:")
    print(f"   Total Messages: {stats['total_messages']}")
    print(f"   Total Users: {stats['total_users']}")
    print(f"   Messages Today: {stats['messages_today']}")
    print(f"   Top Users: {stats['top_users']}")
    
    # Export formats
    print(f"\n📁 Exporting datasets...")
    
    await exporter.export_to_json("chat_dataset.json")
    await exporter.export_to_csv("chat_dataset.csv")
    await exporter.export_sql_pairs("sql_pairs.jsonl")
    
    print(f"\n✅ All exports complete!")
    print(f"\nFiles generated:")
    print(f"   📄 chat_dataset.json - Full conversation data")
    print(f"   📄 chat_dataset.csv - CSV format for analysis")
    print(f"   📄 sql_pairs.jsonl - Text-to-SQL training pairs")
    print(f"\n💡 Use these files for:")
    print(f"   • Fine-tuning SQLCoder or other Text2SQL models")
    print(f"   • Training custom ML models")
    print(f"   • Analytics and bot improvement")


if __name__ == "__main__":
    asyncio.run(main())
