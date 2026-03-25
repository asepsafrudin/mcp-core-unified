"""
LLM Connector - Groq Primary + Gemini Fallback
"""

import os
import asyncio
from typing import Dict, Any, Optional
import aiohttp
import json


class LLMConnector:
    """Connector untuk LLM dengan fallback mechanism."""
    
    def __init__(self):
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.groq_base_url = 'https://api.groq.com/openai/v1'
        self.gemini_base_url = 'https://generativelanguage.googleapis.com/v1beta'
        self.primary_model = 'mixtral-8x7b-32768'
        self.fallback_model = 'gemini-pro'
    
    async def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Generate text dengan Groq primary, Gemini fallback.
        
        Returns:
            Dict dengan 'content', 'model_used', 'success'
        """
        # Try Groq first
        if self.groq_api_key:
            try:
                result = await self._call_groq(
                    prompt, system_prompt, temperature, max_tokens
                )
                if result['success']:
                    return result
            except Exception as e:
                print(f"Groq failed: {e}")
        
        # Fallback to Gemini
        if self.gemini_api_key:
            try:
                result = await self._call_gemini(
                    prompt, system_prompt, temperature, max_tokens
                )
                if result['success']:
                    return result
            except Exception as e:
                print(f"Gemini failed: {e}")
        
        return {
            'success': False,
            'error': 'Both LLM providers failed',
            'content': None
        }
    
    async def _call_groq(
        self, 
        prompt: str, 
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Call Groq API."""
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{self.groq_base_url}/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.groq_api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.primary_model,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'success': True,
                        'content': data['choices'][0]['message']['content'],
                        'model_used': f"groq/{self.primary_model}",
                        'tokens': data.get('usage', {})
                    }
                else:
                    error_text = await response.text()
                    return {
                        'success': False,
                        'error': f"Groq HTTP {response.status}: {error_text}"
                    }
    
    async def _call_gemini(
        self, 
        prompt: str, 
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Call Gemini API."""
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{self.gemini_base_url}/models/{self.fallback_model}:generateContent',
                headers={'Content-Type': 'application/json'},
                params={'key': self.gemini_api_key},
                json={
                    'contents': [{
                        'parts': [{'text': full_prompt}]
                    }],
                    'generationConfig': {
                        'temperature': temperature,
                        'maxOutputTokens': max_tokens
                    }
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    content = data['candidates'][0]['content']['parts'][0]['text']
                    return {
                        'success': True,
                        'content': content,
                        'model_used': f"gemini/{self.fallback_model}"
                    }
                else:
                    error_text = await response.text()
                    return {
                        'success': False,
                        'error': f"Gemini HTTP {response.status}: {error_text}"
                    }
