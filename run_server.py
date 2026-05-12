"""
Entry point for running the FastAPI server directly with `python run_server.py`.
Loads environment variables from .env before starting.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "gateway.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
