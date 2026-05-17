import asyncio
import logging
from typing import Dict, Optional
from orchestration.antigravity_ledger import ledger

logger = logging.getLogger(__name__)

class VirtualQueue:
    """
    The Traffic Light: Manages request queuing based on RPM/TPM limits.
    """
    
    def __init__(self, max_rpm: int = 50, max_tpm: int = 40000):
        self.max_rpm = max_rpm
        self.max_tpm = max_tpm
        self.queue = asyncio.Queue()

    async def wait_for_quota(self, estimated_tokens: int):
        """
        Check current usage and wait if limits are exceeded.
        """
        while True:
            usage = await ledger.get_quota()
            
            rpm_ok = usage["rpm"] < self.max_rpm
            tpm_ok = (usage["tpm"] + estimated_tokens) < self.max_tpm
            
            if rpm_ok and tpm_ok:
                logger.info(f"[Queue] Quota OK: RPM={usage['rpm']}/{self.max_rpm}, TPM={usage['tpm']}/{self.max_tpm}")
                return True
            
            # If nearly full, stagger execution
            wait_time = 5 # Default wait 5 seconds
            if not rpm_ok:
                logger.warning(f"[Queue] RPM limit reached ({usage['rpm']}/{self.max_rpm}). Waiting...")
            if not tpm_ok:
                logger.warning(f"[Queue] TPM limit reached ({usage['tpm']}/{self.max_tpm}). Waiting...")
                
            await asyncio.sleep(wait_time)

virtual_queue = VirtualQueue()
