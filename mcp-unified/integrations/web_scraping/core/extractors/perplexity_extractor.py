"""
Perplexity Extractor - Ekstrak conversation threads dari Perplexity.ai.

Features:
- Extract Q&A conversation
- Extract sources/citations
- Handle code blocks
- Parse thread metadata
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_extractor import BaseExtractor, ExtractedContent


class PerplexityExtractor(BaseExtractor):
    """
    Extractor untuk Perplexity.ai conversation threads.
    
    Supports:
    - https://www.perplexity.ai/search/*
    - https://www.perplexity.ai/collections/*
    """
    
    URL_PATTERNS = [
        "https://www.perplexity.ai/search/*",
        "https://www.perplexity.ai/collections/*",
        "https://perplexity.ai/search/*",
    ]
    
    DOMAINS = ["perplexity.ai", "www.perplexity.ai"]
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Perplexity extractor."""
        super().__init__(config)
        self.selectors = {
            "message_content": "[data-testid='message-content']",
            "query_text": ".prose",
            "answer_text": ".prose",
            "source_link": "[data-testid='source-link']",
            "citation": "[data-testid='citation']",
            "thread_title": "h1",
        }
    
    def can_handle(self, url: str) -> bool:
        """Check if URL is a Perplexity thread."""
        return self._match_url_pattern(url)
    
    async def extract(self, page) -> ExtractedContent:
        """
        Extract conversation from Perplexity page.
        
        Args:
            page: Playwright page object
            
        Returns:
            ExtractedContent dengan conversation structure
        """
        url = page.url
        
        # Wait untuk content load
        await self._wait_for_selector(page, self.selectors["message_content"], timeout=15000)
        
        # Extract conversation menggunakan JavaScript
        conversation_data = await page.evaluate("""
            () => {
                const messages = [];
                const messageElements = document.querySelectorAll('[data-testid="message-content"]');
                
                messageElements.forEach((el, index) => {
                    const role = index % 2 === 0 ? 'user' : 'assistant';
                    
                    // Get text content
                    let content = '';
                    const proseElements = el.querySelectorAll('.prose');
                    proseElements.forEach(p => {
                        content += p.innerText + '\\n';
                    });
                    
                    // Extract code blocks
                    const codeBlocks = [];
                    el.querySelectorAll('pre code').forEach(code => {
                        codeBlocks.push({
                            language: code.className.match(/language-(\\w+)/)?.[1] || 'text',
                            code: code.innerText
                        });
                    });
                    
                    messages.push({
                        role: role,
                        content: content.trim(),
                        code_blocks: codeBlocks,
                        index: index
                    });
                });
                
                return messages;
            }
        """)
        
        # Extract sources/citations
        sources = await page.evaluate("""
            () => {
                const sources = [];
                const sourceElements = document.querySelectorAll('[data-testid="source-link"], .citation');
                
                sourceElements.forEach(el => {
                    const link = el.querySelector('a') || el;
                    if (link.href) {
                        sources.push({
                            title: el.innerText.trim(),
                            url: link.href,
                            domain: new URL(link.href).hostname
                        });
                    }
                });
                
                return sources;
            }
        """)
        
        # Extract thread title
        title = await self._safe_evaluate(
            page,
            "() => document.querySelector('h1')?.innerText || 'Perplexity Conversation'",
            "Perplexity Conversation"
        )
        
        # Build structured content
        query = ""
        answer = ""
        full_conversation = []
        
        for msg in conversation_data:
            if msg['role'] == 'user':
                query = msg['content']
                full_conversation.append(f"Q: {msg['content']}")
            else:
                answer = msg['content']
                full_conversation.append(f"A: {msg['content']}")
                
                # Add code blocks jika ada
                if msg.get('code_blocks'):
                    for block in msg['code_blocks']:
                        full_conversation.append(f"```\n{block['code']}\n```")
        
        # Combine content
        content_text = f"""# {title}

## Query
{query}

## Answer
{answer}

## Sources ({len(sources)})
"""
        for i, source in enumerate(sources[:10], 1):  # Max 10 sources
            content_text += f"{i}. [{source['title']}]({source['url']})\n"
        
        content_text += f"\n## Full Conversation\n"
        content_text += "\n\n".join(full_conversation)
        
        # Create metadata
        metadata = {
            "source_type": "perplexity_ai",
            "conversation": conversation_data,
            "sources": sources,
            "query": query,
            "has_code_blocks": any(
                msg.get('code_blocks') for msg in conversation_data
            ),
        }
        
        return ExtractedContent(
            url=url,
            title=title,
            content=self._clean_text(content_text),
            metadata=metadata,
            extracted_at=datetime.now()
        )
    
    def validate(self, content: ExtractedContent) -> bool:
        """Validate Perplexity content."""
        if not super().validate(content):
            return False
        
        # Check untuk conversation structure
        if "Q:" not in content.content or "A:" not in content.content:
            return False
        
        return True


class PerplexityCollectionExtractor(PerplexityExtractor):
    """Extractor untuk Perplexity Collections."""
    
    URL_PATTERNS = ["https://www.perplexity.ai/collections/*"]
    
    async def extract(self, page) -> ExtractedContent:
        """Extract collection dengan multiple threads."""
        url = page.url
        
        # Extract collection info
        collection_data = await page.evaluate("""
            () => {
                const title = document.querySelector('h1')?.innerText || 'Collection';
                const description = document.querySelector('[data-testid="collection-description"]')?.innerText || '';
                
                const threads = [];
                document.querySelectorAll('[data-testid="collection-thread"]').forEach(el => {
                    const threadTitle = el.querySelector('h3')?.innerText || '';
                    const threadUrl = el.querySelector('a')?.href || '';
                    threads.push({ title: threadTitle, url: threadUrl });
                });
                
                return { title, description, threads };
            }
        """)
        
        content_text = f"""# {collection_data['title']}

## Description
{collection_data['description']}

## Threads ({len(collection_data['threads'])})
"""
        for thread in collection_data['threads']:
            content_text += f"- [{thread['title']}]({thread['url']})\n"
        
        return ExtractedContent(
            url=url,
            title=collection_data['title'],
            content=self._clean_text(content_text),
            metadata={
                "source_type": "perplexity_collection",
                "thread_count": len(collection_data['threads']),
                "threads": collection_data['threads'],
            },
            extracted_at=datetime.now()
        )