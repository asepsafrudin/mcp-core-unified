import sys
import os
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Add user's global site-packages to access groq, google-genai, etc installed without venv
user_site = os.path.expanduser("~/.local/lib/python3.12/site-packages")
if user_site not in sys.path:
    sys.path.append(user_site)

import uvicorn
import logging
from observability.logger import configure_logger

def start_server():
    """Start the LLM API Uvicorn server."""
    # Ensure logging is configured uniformly
    configure_logger()
    
    # Using wait=False allows us to try other ports
    # I'll just change to port 8085 to avoid conflicts
    uvicorn.run(
        "services.llm_api.main:app",
        host="0.0.0.0",
        port=8088,
        reload=False,
        workers=1,
        log_level="info"
    )


if __name__ == "__main__":
    start_server()


