#!/usr/bin/env bash
# Start both FastAPI (backend) and Streamlit (dashboard) in one process.
# Render provides a single PORT — FastAPI gets it, Streamlit uses PORT+1.

set -e

FASTAPI_PORT="${PORT:-8000}"
STREAMLIT_PORT=$((FASTAPI_PORT + 1))

export GATEWAY_API_URL="http://localhost:${FASTAPI_PORT}"

echo "Starting FastAPI on port ${FASTAPI_PORT}..."
uvicorn gateway.main:app --host 0.0.0.0 --port "${FASTAPI_PORT}" &

echo "Starting Streamlit on port ${STREAMLIT_PORT}..."
streamlit run streamlit_app.py --server.port "${STREAMLIT_PORT}" --server.headless true --server.address 0.0.0.0 &

wait -n
