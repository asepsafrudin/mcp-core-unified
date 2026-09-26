"""
LLM Connector - Multi-Provider Resilient LLM Layer
Supports Groq (Primary), OpenAI (Secondary), Gemini (Tertiary), and RunPod vLLM.
"""
import os
import json
import asyncio
from typing import Dict, Any, Optional
import aiohttp
from pathlib import Path
from dotenv import load_dotenv

# Auto-load config/env files
for env_file in [".env.ai", ".env.cloud", ".env.workspace", ".env.core"]:
    p = Path(f"/home/aseps/MCP/config/env/{env_file}")
    if p.exists():
        load_dotenv(p)


class LLMConnector:
    """Connector untuk LLM dengan automatic multi-provider fallback."""
    
    def __init__(self):
        self.groq_api_key = os.getenv('GROQ_API_KEY') or os.getenv('GROQ_API_KEY_BOT_TELEGRAM')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        self.gemini_api_key = os.getenv('GOOGLE_VISION_API_KEY') or os.getenv('GEMINI_API_KEY')
        self.vllm_api_key = os.getenv('RUNPOD_VLLM_API_KEY') or os.getenv('llm-vllm-key')
        self.vllm_endpoint = os.getenv('RUNPOD_VLLM_VISION_ENDPOINT_ID', 'qi2tml56v6cf1p')
        
        # Models
        self.groq_model = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
        self.openai_model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.deepseek_model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        self.gemini_model = 'gemini-1.5-flash'
        self.vllm_model = 'qwen/qwen2.5-vl-7b-instruct'

    async def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 3000
    ) -> Dict[str, Any]:
        """
        Generate text with multi-level resilient fallback:
        1. Groq (Fastest)
        2. OpenAI (High Reasoning)
        3. DeepSeek (Resilient High Reasoning)
        4. RunPod vLLM
        5. Google Gemini
        """
        # 1. Try Groq
        if self.groq_api_key:
            try:
                # Use standard supported models on Groq
                for model in ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'llama3-70b-8192']:
                    result = await self._call_groq(prompt, system_prompt, temperature, max_tokens, model)
                    if result.get('success'):
                        return result
            except Exception as e:
                pass
        
        # 2. Try OpenAI
        if self.openai_api_key:
            try:
                result = await self._call_openai(prompt, system_prompt, temperature, max_tokens)
                if result.get('success'):
                    return result
            except Exception as e:
                pass

        # 3. Try DeepSeek
        if self.deepseek_api_key and not self.deepseek_api_key.startswith('sk-xxx'):
            try:
                result = await self._call_deepseek(prompt, system_prompt, temperature, max_tokens)
                if result.get('success'):
                    return result
            except Exception as e:
                pass

        # 3. Try RunPod vLLM
        if self.vllm_api_key and self.vllm_endpoint:
            try:
                result = await self._call_vllm(prompt, system_prompt, temperature, max_tokens)
                if result.get('success'):
                    return result
            except Exception as e:
                pass

        # 4. Try Gemini
        if self.gemini_api_key and self.gemini_api_key.startswith('AIzaSy'):
            try:
                result = await self._call_gemini(prompt, system_prompt, temperature, max_tokens)
                if result.get('success'):
                    return result
            except Exception as e:
                pass

        return {
            'success': False,
            'error': 'All configured LLM providers failed.',
            'content': None
        }

    async def _call_groq(
        self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int, model: str
    ) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.groq_api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': model,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens
                },
                timeout=aiohttp.ClientTimeout(total=45)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'success': True,
                        'content': data['choices'][0]['message']['content'],
                        'model_used': f"groq/{model}",
                        'tokens': data.get('usage', {})
                    }
                return {'success': False, 'error': f"Groq HTTP {response.status}"}

    async def _call_openai(
        self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int
    ) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.openai.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.openai_api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.openai_model,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens
                },
                timeout=aiohttp.ClientTimeout(total=45)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'success': True,
                        'content': data['choices'][0]['message']['content'],
                        'model_used': f"openai/{self.openai_model}",
                        'tokens': data.get('usage', {})
                    }
                return {'success': False, 'error': f"OpenAI HTTP {response.status}"}

    async def _call_deepseek(
        self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int
    ) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.deepseek.com/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.deepseek_api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.deepseek_model,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens
                },
                timeout=aiohttp.ClientTimeout(total=45)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'success': True,
                        'content': data['choices'][0]['message']['content'],
                        'model_used': f"deepseek/{self.deepseek_model}",
                        'tokens': data.get('usage', {})
                    }
                return {'success': False, 'error': f"DeepSeek HTTP {response.status}"}

    async def _call_vllm(
        self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int
    ) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})
        
        url = f"https://api.runpod.ai/v2/{self.vllm_endpoint}/openai/v1/chat/completions"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers={
                    'Authorization': f'Bearer {self.vllm_api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.vllm_model,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens
                },
                timeout=aiohttp.ClientTimeout(total=45)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'success': True,
                        'content': data['choices'][0]['message']['content'],
                        'model_used': f"vllm/{self.vllm_model}",
                        'tokens': data.get('usage', {})
                    }
                return {'success': False, 'error': f"vLLM HTTP {response.status}"}

    async def _call_gemini(
        self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int
    ) -> Dict[str, Any]:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers={'Content-Type': 'application/json'},
                params={'key': self.gemini_api_key},
                json={
                    'contents': [{'parts': [{'text': full_prompt}]}],
                    'generationConfig': {'temperature': temperature, 'maxOutputTokens': max_tokens}
                },
                timeout=aiohttp.ClientTimeout(total=45)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    content = data['candidates'][0]['content']['parts'][0]['text']
                    return {'success': True, 'content': content, 'model_used': f"gemini/{self.gemini_model}"}
                return {'success': False, 'error': f"Gemini HTTP {response.status}"}
