"""
Message Formatters

Formatter untuk Telegram messages.
"""

import re
from typing import List, Dict, Any, Optional


class MessageFormatter:
    """Formatter untuk Telegram messages."""
    
    @staticmethod
    def bold(text: str) -> str:
        """Bold text."""
        return f"*{text}*"
    
    @staticmethod
    def italic(text: str) -> str:
        """Italic text."""
        return f"_{text}_"
    
    @staticmethod
    def code(text: str, language: Optional[str] = None) -> str:
        """Code block."""
        lang = language or ""
        return f"```{lang}\n{text}\n```"
    
    @staticmethod
    def inline_code(text: str) -> str:
        """Inline code."""
        return f"`{text}`"
    
    @staticmethod
    def link(text: str, url: str) -> str:
        """Link."""
        return f"[{text}]({url})"
    
    @staticmethod
    def bullet_list(items: List[str]) -> str:
        """Bullet list."""
        return "\n".join(f"— {item}" for item in items)
    
    @staticmethod
    def numbered_list(items: List[str]) -> str:
        """Numbered list."""
        return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))
    
    @staticmethod
    def quote(text: str) -> str:
        """Quote text."""
        lines = text.split('\n')
        return "\n".join(f"> {line}" for line in lines)
    
    @staticmethod
    def status_emoji(status: str) -> str:
        """Get status emoji."""
        emojis = {
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
            "pending": "⏳",
            "running": "🔄",
            "online": "🟢",
            "offline": "🔴",
        }
        return emojis.get(status.lower(), "•")
    
    @classmethod
    def format_status(
        cls,
        title: str,
        items: Dict[str, Any]
    ) -> str:
        """
        Format status message.
        
        Args:
            title: Status title
            items: Status items dict
            
        Returns:
            Formatted message
        """
        lines = [f"*{title}*", ""]
        
        for key, value in items.items():
            emoji = cls.status_emoji(str(value))
            lines.append(f"— {key}: {emoji} {value}")
        
        return "\n".join(lines)

    @staticmethod
    def markdown_to_telegram_html(text: str) -> str:
        """
        Mengonversi format Markdown (bold, italic, code, link, table) 
        menjadi format HTML yang aman untuk Telegram API.
        """
        if not text:
            return ""

        # 1. Escape HTML special characters
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        # 1.5. Parse Blockquotes (yang diawali dengan &gt;)
        def parse_blockquotes(match):
            block_content = match.group(1)
            lines = []
            for line in block_content.split('\n'):
                cleaned = re.sub(r'^&gt;\s?', '', line)
                lines.append(cleaned)
            # Bersihkan baris kosong di akhir akibat pemisahan split
            if lines and not lines[-1].strip():
                lines.pop()
            return "<blockquote>" + "\n".join(lines) + "</blockquote>\n"

        text = re.sub(r'((?:^&gt;.*(?:\n|$))+)', parse_blockquotes, text, flags=re.MULTILINE)

        # 2. Extract and preserve Code Blocks (```code```)
        code_blocks = []
        def save_code_block(match):
            lang = match.group(1) or ""
            code = match.group(2)
            placeholder = f"TEMPCODEBLOCKXYZ{len(code_blocks)}"
            # Gunakan tag pre di Telegram HTML
            tag = f"<pre>{code}</pre>"
            code_blocks.append(tag)
            return placeholder

        text = re.sub(r'```(\w*)\n(.*?)\n```', save_code_block, text, flags=re.DOTALL)

        # 3. Extract and preserve Inline Code (`code`)
        inline_codes = []
        def save_inline_code(match):
            code = match.group(1)
            placeholder = f"TEMPINLINEXYZ{len(inline_codes)}"
            tag = f"<code>{code}</code>"
            inline_codes.append(tag)
            return placeholder

        text = re.sub(r'`(.*?)`', save_inline_code, text)

        # 4. Parse Markdown Tables
        def parse_tables(match):
            table_str = match.group(0)
            lines = [l.strip() for l in table_str.strip().split('\n') if l.strip()]
            
            rows_cells = []
            for line in lines:
                clean_line = line.strip('|')
                cells = [c.strip() for c in clean_line.split('|')]
                rows_cells.append(cells)
                
            if len(rows_cells) < 2:
                return table_str
                
            is_sep = all(re.match(r'^:?-+:?$', c) for c in rows_cells[1]) if len(rows_cells) > 1 else False
            
            header = rows_cells[0]
            data_rows = rows_cells[2:] if is_sep else rows_cells[1:]
            
            num_cols = max(len(header), max((len(r) for r in data_rows), default=0))
            
            header = header + [""] * (num_cols - len(header))
            normalized_data = []
            for r in data_rows:
                normalized_data.append(r + [""] * (num_cols - len(r)))
                
            col_widths = []
            for col_idx in range(num_cols):
                max_w = len(header[col_idx])
                for r in normalized_data:
                    max_w = max(max_w, len(r[col_idx]))
                col_widths.append(max_w)
                
            top_line = "┌" + "┬".join("─" * (w + 2) for w in col_widths) + "┐"
            mid_line = "├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤"
            bot_line = "└" + "┴".join("─" * (w + 2) for w in col_widths) + "┘"
            
            def format_row(cells):
                formatted_cells = []
                for idx, c in enumerate(cells):
                    w = col_widths[idx]
                    formatted_cells.append(f" {c:<{w}} ")
                return "│" + "│".join(formatted_cells) + "│"
                
            table_lines = []
            table_lines.append(top_line)
            table_lines.append(format_row(header))
            table_lines.append(mid_line)
            for r in normalized_data:
                table_lines.append(format_row(r))
            table_lines.append(bot_line)
            
            formatted_table = "\n".join(table_lines)
            return f"<pre>{formatted_table}</pre>"

        # Regex deteksi tabel markdown
        table_regex = r'((?:^\|.+?\|(?:\s*\n|$))+)'
        text = re.sub(table_regex, parse_tables, text, flags=re.MULTILINE)

        # 5. Parse Bold (**text**)
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

        # 6. Parse Italic (*text* atau _text_)
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        text = re.sub(r'\b_(.*?)_\b', r'<i>\1</i>', text)

        # 7. Parse Link [text](url)
        text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', text)

        # 8. Restore Inline Codes
        for idx, tag in enumerate(inline_codes):
            text = text.replace(f"TEMPINLINEXYZ{idx}", tag)

        # 9. Restore Code Blocks
        for idx, tag in enumerate(code_blocks):
            text = text.replace(f"TEMPCODEBLOCKXYZ{idx}", tag)

        return text
