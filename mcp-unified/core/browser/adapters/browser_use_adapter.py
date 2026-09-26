"""
BrowserUseAdapter — Adapter untuk browser-use (AI-driven browser agent).

browser-use adalah teknologi browser agentic modern yang menggunakan LLM
untuk mengontrol browser secara otonom. Interface mengikuti pola yang sama
dengan playwright_adapter dan agent_browser_adapter agar kompatibel dengan
router & fallback handler.
"""
import logging
import os
from typing import Dict, Any, Optional, List

logger = logging.getLogger("browser_use_adapter")


class BrowserUseAdapter:
    def __init__(self):
        self._browser = None
        self._agent = None
        self._llm = None

    def _get_llm(self):
        """Buat LLM instance. Prioritas: OpenAI -> Groq -> Ollama."""
        if self._llm is not None:
            return self._llm

        if not os.getenv("OPENAI_API_KEY") and not os.getenv("GROQ_API_KEY"):
            try:
                from core.secrets import load_runtime_secrets
                load_runtime_secrets()
            except Exception:
                pass

        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                from browser_use.llm.openai.chat import ChatOpenAI
                self._llm = ChatOpenAI(model="gpt-4o")
                logger.info("BrowserUse: OpenAI gpt-4o")
                return self._llm
            except ImportError:
                pass

        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            try:
                from browser_use.llm.groq.chat import ChatGroq
                self._llm = ChatGroq(model="llama-3.3-70b-versatile")
                logger.info("BrowserUse: Groq llama-3.3-70b")
                return self._llm
            except ImportError:
                pass

        try:
            from browser_use.llm.ollama.chat import ChatOllama
            self._llm = ChatOllama(model="llama3.1")
            logger.info("BrowserUse: Ollama llama3.1")
            return self._llm
        except ImportError:
            pass

        raise RuntimeError(
            "BrowserUse memerlukan LLM. Set OPENAI_API_KEY, GROQ_API_KEY, "
            "atau install langchain-ollama untuk model lokal."
        )

    async def _ensure_browser(self):
        """Inisialisasi browser session jika belum ada."""
        if self._browser is None:
            from browser_use import Browser
            self._browser = Browser(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
            )
            logger.info("BrowserUse: browser session initialized")

    async def navigate(self, url: str, wait_for: str = "load", timeout: int = 25000) -> Dict[str, Any]:
        """Navigasi ke URL menggunakan browser-use agent."""
        try:
            await self._ensure_browser()
            llm = self._get_llm()
            from browser_use import Agent

            task = f"Buka halaman {url} dan berikan ringkasan singkat tentang halaman tersebut."
            self._agent = Agent(
                task=task, llm=llm, browser=self._browser,
                use_vision=False, max_actions_per_step=3,
            )
            result = await self._agent.run(max_steps=5)
            final_text = result.final_result() if hasattr(result, "final_result") else str(result)
            return {
                "success": True, "url": url,
                "title": final_text[:200] if final_text else url,
                "http_status": 200, "engine_used": "browser-use",
            }
        except Exception as e:
            logger.error(f"BrowserUse navigate error: {e}")
            return {"success": False, "error": str(e), "engine_used": "browser-use"}

    async def get_interactive_elements(self) -> List[Dict[str, Any]]:
        """Ambil interactive elements dari halaman saat ini."""
        try:
            await self._ensure_browser()
            if hasattr(self._browser, "get_current_page"):
                page = await self._browser.get_current_page()
                if page:
                    return await page.evaluate('''() => {
                        const els = Array.from(document.querySelectorAll('a, button, input, select, textarea'));
                        return els.map((el, idx) => ({
                            ref: `@e${idx}`,
                            role: el.tagName.toLowerCase(),
                            name: el.innerText || el.value || el.name || '',
                            selector: el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''),
                            state: el.disabled ? 'disabled' : 'enabled'
                        })).slice(0, 100);
                    }''')
            return []
        except Exception as e:
            logger.error(f"BrowserUse get_interactive_elements error: {e}")
            return []

    async def perform_action(self, action: str, target: str, value: Optional[str] = None) -> Dict[str, Any]:
        """Eksekusi aksi tunggal via browser-use agent."""
        try:
            await self._ensure_browser()
            llm = self._get_llm()
            from browser_use import Agent

            action_map = {
                "click": f"Klik elemen dengan selector '{target}' pada halaman saat ini.",
                "fill": f"Isi elemen dengan selector '{target}' dengan nilai '{value}'.",
                "select": f"Pilih opsi '{value}' pada elemen dengan selector '{target}'.",
                "hover": f"Hover elemen dengan selector '{target}'.",
                "press": f"Tekan tombol '{value}' pada elemen dengan selector '{target}'.",
                "clear": f"Bersihkan elemen dengan selector '{target}'.",
            }
            if action not in action_map:
                return {"success": False, "error": f"Unsupported action {action}"}

            self._agent = Agent(
                task=action_map[action], llm=llm, browser=self._browser,
                use_vision=False, max_actions_per_step=3,
            )
            result = await self._agent.run(max_steps=5)
            final_text = result.final_result() if hasattr(result, "final_result") else str(result)
            return {
                "success": True,
                "action_result": f"{action} completed via browser-use",
                "detail": final_text[:200] if final_text else "",
            }
        except Exception as e:
            logger.error(f"BrowserUse perform_action error: {e}")
            return {"success": False, "error": str(e)}

    async def execute_task(self, instruction: str, context: Optional[str] = None, max_steps: int = 10) -> Dict[str, Any]:
        """Eksekusi task multi-step via natural language menggunakan browser-use."""
        try:
            await self._ensure_browser()
            llm = self._get_llm()
            from browser_use import Agent

            task = instruction
            if context:
                task = f"{task}\n\nKonteks: {context}"

            self._agent = Agent(
                task=task, llm=llm, browser=self._browser,
                use_vision=True, max_actions_per_step=5, max_failures=3,
            )
            result = await self._agent.run(max_steps=max_steps)
            final_text = result.final_result() if hasattr(result, "final_result") else str(result)
            return {
                "success": True,
                "result_summary": final_text[:500] if final_text else "Task selesai",
                "steps_taken": max_steps,
                "engine_used": "browser-use",
            }
        except Exception as e:
            logger.error(f"BrowserUse execute_task error: {e}")
            return {"success": False, "error": str(e)}

    async def stop(self):
        """Tutup browser session."""
        if self._browser:
            try:
                if hasattr(self._browser, "stop"):
                    await self._browser.stop()
                elif hasattr(self._browser, "close"):
                    await self._browser.close()
                elif hasattr(self._browser, "reset"):
                    await self._browser.reset()
            except Exception as e:
                logger.debug(f"BrowserUse stop notice: {e}")
            self._browser = None
            self._agent = None


browser_use_adapter = BrowserUseAdapter()