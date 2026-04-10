import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.getcwd())

from core.monitoring.self_healing_agent import SelfHealingAgent
from core.monitoring.health_check import HealthCheckService

async def main():
    logging.basicConfig(level=logging.INFO)
    print("🏥 Starting Self-Healing Agent with Security SOP...")
    
    agent = SelfHealingAgent()
    result = await agent.run_once()
    
    print("\n📊 Health Check Result:")
    print(f"Status: {result.get('status')}")
    print(f"Security: {result.get('checks', {}).get('security', {}).get('status')}")
    
    if result.get("recovery"):
        print("\n🛠️ Recovery Actions Taken:")
        for action in result["recovery"].get("actions", []):
            if action.get("action") == "security_remediation":
                print(f"- Security Remediation: {action.get('fixes_count')} fixes applied.")
                for detail in action.get("details", []):
                    print(f"  * Fixed {detail['vulnerability']} in {detail['file']}")
            else:
                print(f"- Script {action.get('script')}: Return code {action.get('returncode')}")

if __name__ == "__main__":
    asyncio.run(main())
