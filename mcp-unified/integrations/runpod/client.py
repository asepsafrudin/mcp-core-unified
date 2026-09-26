"""
RunPod Serverless & GPU API Client for MCP Unified.
Supports async execution, sync execution, job status polling, and health checks.
"""
from __future__ import annotations

import os
import asyncio
import logging
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger("mcp-unified.runpod")

RUNPOD_API_BASE = "https://api.runpod.ai/v2"


class RunPodClient:
    """Async Client for RunPod Serverless v2 REST API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("RUNPOD_API_KEY", "").strip()

    def _get_headers(
        self, custom_key: Optional[str] = None, endpoint_id: Optional[str] = None
    ) -> Dict[str, str]:
        heavy_ep = os.getenv("RUNPOD_HEAVY_OCR_ENDPOINT_ID", "lhpduw3m4ro1w1").strip()
        ep = (endpoint_id or "").strip()

        if custom_key:
            key = custom_key.strip()
        elif ep and ep == heavy_ep:
            key = (
                os.getenv("RUNPOD_HEAVY_OCR_API_KEY")
                or os.getenv("RUNPOD_API_KEY_SURYA_OCR")
                or os.getenv("RUNPOD_API_KEY", "")
            ).strip()
        else:
            key = (
                self.api_key
                or os.getenv("RUNPOD_API_KEY", "")
                or os.getenv("RUNPOD_HEAVY_OCR_API_KEY", "")
                or os.getenv("RUNPOD_API_KEY_SURYA_OCR", "")
            ).strip()

        if not key:
            raise ValueError(
                "RunPod API key tidak ditemukan. Set environment variable RUNPOD_API_KEY "
                "atau RUNPOD_HEAVY_OCR_API_KEY."
            )
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }


    async def check_health(
        self, endpoint_id: Optional[str] = None, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cek status kesehatan dan jumlah worker di endpoint RunPod Serverless."""
        ep_id = (endpoint_id or os.getenv("RUNPOD_ENDPOINT_ID", "")).strip()
        if not ep_id:
            return {"success": False, "error": "endpoint_id wajib diisi atau diset di RUNPOD_ENDPOINT_ID."}

        url = f"{RUNPOD_API_BASE}/{ep_id}/health"
        headers = self._get_headers(api_key, endpoint_id=ep_id)

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "success": True,
                        "endpoint_id": ep_id,
                        "health": data,
                        "workers_ready": data.get("workers", {}).get("ready", 0),
                        "workers_idle": data.get("workers", {}).get("idle", 0),
                        "workers_running": data.get("workers", {}).get("running", 0),
                    }
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "error": resp.text,
                    "endpoint_id": ep_id,
                }
            except Exception as e:
                logger.error("runpod_health_check_failed", error=str(e), endpoint_id=ep_id)
                return {"success": False, "error": str(e), "endpoint_id": ep_id}

    async def run_job(
        self,
        input_data: Dict[str, Any],
        endpoint_id: Optional[str] = None,
        sync: bool = False,
        timeout_seconds: int = 120,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Kirim job ke RunPod Serverless endpoint.
        Jika sync=True, akan memanggil /runsync atau menunggu hingga selesai.
        """
        ep_id = (endpoint_id or os.getenv("RUNPOD_ENDPOINT_ID", "")).strip()
        if not ep_id:
            return {"success": False, "error": "endpoint_id wajib diisi atau diset di RUNPOD_ENDPOINT_ID."}

        headers = self._get_headers(api_key, endpoint_id=ep_id)
        payload = {"input": input_data}

        async with httpx.AsyncClient(timeout=float(timeout_seconds + 10)) as client:
            if sync:
                # Coba endpoint /runsync terlebih dahulu
                url = f"{RUNPOD_API_BASE}/{ep_id}/runsync"
                try:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        # Jika job selesai langsung
                        if data.get("status") == "COMPLETED":
                            return {"success": True, "status": "COMPLETED", "job_id": data.get("id"), "output": data.get("output")}
                        # Jika status in progress / queued, poll sampai timeout
                        job_id = data.get("id")
                        if job_id:
                            return await self.poll_job_completion(ep_id, job_id, timeout_seconds=timeout_seconds, api_key=api_key)
                        return {"success": True, "status": data.get("status"), "data": data}
                except httpx.TimeoutException:
                    return {"success": False, "error": f"Request timeout setelah {timeout_seconds} detik"}
                except Exception as e:
                    logger.warning("runsync_call_failed_falling_back_to_async_poll", error=str(e))

            # Async mode atau fallback: panggil /run lalu poll
            url = f"{RUNPOD_API_BASE}/{ep_id}/run"
            try:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code not in (200, 201):
                    return {"success": False, "status_code": resp.status_code, "error": resp.text}
                
                data = resp.json()
                job_id = data.get("id")
                status = data.get("status")

                if not sync:
                    return {
                        "success": True,
                        "status": status,
                        "job_id": job_id,
                        "endpoint_id": ep_id,
                        "message": "Job berhasil disubmit secara asinkron. Gunakan runpod_get_job_status untuk cek status.",
                    }

                # Jika sync=True tapi lewat jalur /run, poll sampai selesai
                return await self.poll_job_completion(ep_id, job_id, timeout_seconds=timeout_seconds, api_key=api_key)
            except Exception as e:
                logger.error("runpod_run_job_failed", error=str(e), endpoint_id=ep_id)
                return {"success": False, "error": str(e), "endpoint_id": ep_id}

    async def get_job_status(
        self, job_id: str, endpoint_id: Optional[str] = None, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cek status spesifik job ID pada endpoint RunPod."""
        ep_id = (endpoint_id or os.getenv("RUNPOD_ENDPOINT_ID", "")).strip()
        if not ep_id:
            return {"success": False, "error": "endpoint_id wajib diisi atau diset di RUNPOD_ENDPOINT_ID."}

        url = f"{RUNPOD_API_BASE}/{ep_id}/status/{job_id}"
        headers = self._get_headers(api_key, endpoint_id=ep_id)

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")
                    return {
                        "success": True,
                        "job_id": job_id,
                        "status": status,
                        "output": data.get("output"),
                        "error": data.get("error"),
                        "execution_time_ms": data.get("executionTime"),
                    }
                return {"success": False, "status_code": resp.status_code, "error": resp.text}
            except Exception as e:
                logger.error("runpod_get_status_failed", error=str(e), job_id=job_id)
                return {"success": False, "error": str(e), "job_id": job_id}

    async def cancel_job(
        self, job_id: str, endpoint_id: Optional[str] = None, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Batalkan eksekusi job yang sedang berjalan/antri."""
        ep_id = (endpoint_id or os.getenv("RUNPOD_ENDPOINT_ID", "")).strip()
        if not ep_id:
            return {"success": False, "error": "endpoint_id wajib diisi atau diset di RUNPOD_ENDPOINT_ID."}

        url = f"{RUNPOD_API_BASE}/{ep_id}/cancel/{job_id}"
        headers = self._get_headers(api_key, endpoint_id=ep_id)

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, headers=headers)
                if resp.status_code == 200:
                    return {"success": True, "job_id": job_id, "data": resp.json()}
                return {"success": False, "status_code": resp.status_code, "error": resp.text}
            except Exception as e:
                logger.error("runpod_cancel_job_failed", error=str(e), job_id=job_id)
                return {"success": False, "error": str(e), "job_id": job_id}

    async def poll_job_completion(
        self,
        endpoint_id: str,
        job_id: str,
        timeout_seconds: int = 120,
        interval_seconds: float = 2.0,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Polling berulang hingga job mencapai status COMPLETED atau FAILED."""
        start_time = asyncio.get_event_loop().time()
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout_seconds:
                return {
                    "success": False,
                    "status": "TIMEOUT",
                    "job_id": job_id,
                    "error": f"Job execution timed out after {timeout_seconds} seconds.",
                }

            status_res = await self.get_job_status(job_id, endpoint_id=endpoint_id, api_key=api_key)
            if not status_res.get("success"):
                return status_res

            status = status_res.get("status")
            if status == "COMPLETED":
                return {
                    "success": True,
                    "status": "COMPLETED",
                    "job_id": job_id,
                    "output": status_res.get("output"),
                    "execution_time_ms": status_res.get("execution_time_ms"),
                }
            elif status in ("FAILED", "CANCELLED", "TIMED_OUT"):
                return {
                    "success": False,
                    "status": status,
                    "job_id": job_id,
                    "error": status_res.get("error") or f"Job terminated with status {status}",
                }

            await asyncio.sleep(interval_seconds)


_global_client: Optional[RunPodClient] = None


def get_runpod_client() -> RunPodClient:
    """Singleton getter untuk RunPodClient."""
    global _global_client
    if _global_client is None:
        _global_client = RunPodClient()
    return _global_client
