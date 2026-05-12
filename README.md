# LLM API Gateway with Automatic Failover

A production-ready API gateway that routes prompts to multiple LLM providers with automatic failover. Free providers are tried first; paid providers are used only as a fallback.

## Architecture

```
User → FastAPI Gateway (/generate) → Failover Orchestrator
                                          │
                    ┌─── Free Tier ────────┼─── Paid Tier (fallback) ───┐
                    │                      │                            │
                    ├─ Groq               ├─ OpenAI                   │
                    ├─ Hugging Face       ├─ Anthropic                │
                    ├─ Together AI        ├─ Google Gemini            │
                    └─ Ollama (local)     └─ Cohere                   │
                                                                       │
                    Streamlit Dashboard ──── API key mgmt, logs, test ─┘
```

## Features

- **Automatic failover** — if a provider fails (rate limit, auth error, timeout), the next provider is tried automatically
- **Free-first routing** — free-tier providers are always tried before paid ones
- **Response caching** — identical prompts return cached results to save API calls
- **8 providers** supported out of the box (4 free + 4 paid)
- **Streamlit dashboard** — manage API keys, select models, test prompts, view logs
- **FastAPI REST endpoint** — call `/generate` from any application
- **Structured logging** — every attempt and failover chain is logged with latency metrics

## Quick Start

### 1. Install dependencies

```bash
cd "AI APIS"
pip install -r requirements.txt
```

### 2. Configure API keys

Copy the example env file and add your keys:

```bash
cp .env.example .env
```

Edit `.env` and add at least one API key:

```env
GROQ_API_KEY=gsk_your_key_here
HUGGINGFACE_API_KEY=hf_your_key_here
```

You can also add keys through the Streamlit dashboard UI.

### 3. Start the FastAPI server

```bash
python run_server.py
```

The API is now available at `http://localhost:8000`. Try it:

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain quantum computing in one paragraph"}'
```

### 4. Start the Streamlit dashboard (optional)

In a second terminal:

```bash
streamlit run streamlit_app.py
```

Open `http://localhost:8501` in your browser.

## API Reference

### `POST /generate`

Send a prompt through the failover chain.

**Request body:**
```json
{
  "prompt": "Your prompt here",
  "max_tokens": 1024,
  "temperature": 0.7,
  "use_cache": true
}
```

**Response:**
```json
{
  "response": "Generated text...",
  "provider": "Groq",
  "model": "llama-3.3-70b-versatile",
  "cached": false,
  "attempts": 1,
  "request_id": "a1b2c3d4"
}
```

### `GET /providers`

List all configured providers and their status.

### `POST /providers/key`

Set an API key: `{"provider": "groq", "api_key": "gsk_..."}`

### `POST /providers/toggle`

Enable/disable a provider: `{"provider": "groq", "enabled": false}`

### `POST /providers/model`

Select a model: `{"provider": "groq", "model": "llama-3.1-8b-instant"}`

### `GET /logs`

View recent failover logs and statistics.

### `GET /health`

Health check endpoint.

## Supported Providers

### Free Tier (tried first)

| Provider | Models | How to get a key |
|----------|--------|------------------|
| **Groq** | Llama 3.3 70B, Llama 3.1 8B, Gemma 2, Mixtral | [console.groq.com](https://console.groq.com) |
| **Hugging Face** | Mistral 7B, Llama 3 8B, Gemma 2, Phi-3 | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |
| **Together AI** | Llama 3.3 70B, Mixtral, Qwen 2.5 | [api.together.xyz](https://api.together.xyz) |
| **Ollama** | Any local model | Install from [ollama.com](https://ollama.com) |

### Paid Tier (fallback)

| Provider | Models | How to get a key |
|----------|--------|------------------|
| **OpenAI** | GPT-4o, GPT-4o-mini, GPT-4, o1 | [platform.openai.com](https://platform.openai.com) |
| **Anthropic** | Claude 4 Sonnet, Claude 3.5 Haiku, Claude 3 Opus | [console.anthropic.com](https://console.anthropic.com) |
| **Google Gemini** | Gemini 2.0 Flash, 1.5 Flash, 1.5 Pro | [aistudio.google.com](https://aistudio.google.com) |
| **Cohere** | Command R+, Command R | [dashboard.cohere.com](https://dashboard.cohere.com) |

## Failover Behavior

The system routes requests in this order:

1. **Check cache** — if an identical prompt was recently answered, return the cached result
2. **Try free providers** — in priority order (Groq → HuggingFace → Together → Ollama)
3. **Try paid providers** — only if all free providers fail (OpenAI → Anthropic → Google → Cohere)
4. **Return error** — if all configured providers fail

Error types that trigger failover to the next provider:
- Rate limit exceeded (HTTP 429)
- Server errors (HTTP 5xx)
- Timeouts
- Token limit exceeded

Errors that **do not** trigger failover (provider is skipped permanently):
- Authentication failure (invalid API key)

## Deployment

### Render (recommended, free tier)

1. Push your code to a Git repo
2. Create a new Web Service on [render.com](https://render.com)
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `uvicorn gateway.main:app --host 0.0.0.0 --port $PORT`
5. Add API keys as environment variables in the Render dashboard

### Railway

1. Connect your Git repo at [railway.app](https://railway.app)
2. Railway auto-detects the `Procfile`
3. Add API keys as environment variables

### Streamlit Cloud (dashboard only)

1. Push to GitHub
2. Deploy at [share.streamlit.io](https://share.streamlit.io)
3. Set `GATEWAY_API_URL` in Streamlit secrets to point to your FastAPI deployment
4. Add API keys in `.streamlit/secrets.toml` or the Streamlit Cloud secrets UI

## Project Structure

```
AI APIS/
├── gateway/
│   ├── __init__.py
│   ├── main.py              # FastAPI app with all endpoints
│   ├── config.py             # Configuration loading/saving
│   ├── cache.py              # In-memory response cache
│   ├── failover.py           # Failover orchestrator
│   ├── logger.py             # Structured logging
│   └── providers/
│       ├── __init__.py
│       ├── base.py           # Abstract base provider
│       ├── groq_provider.py
│       ├── huggingface_provider.py
│       ├── together_provider.py
│       ├── ollama_provider.py
│       ├── openai_provider.py
│       ├── anthropic_provider.py
│       ├── google_provider.py
│       └── cohere_provider.py
├── streamlit_app.py          # Dashboard UI
├── run_server.py             # Server entry point
├── requirements.txt
├── .env.example
├── .gitignore
├── Procfile                  # For Render/Railway/Heroku
└── .streamlit/
    └── config.toml           # Streamlit theme
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key | — |
| `HUGGINGFACE_API_KEY` | Hugging Face token | — |
| `TOGETHER_API_KEY` | Together AI key | — |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `ANTHROPIC_API_KEY` | Anthropic API key | — |
| `GOOGLE_API_KEY` | Google AI Studio key | — |
| `COHERE_API_KEY` | Cohere API key | — |
| `GATEWAY_CONFIG_DIR` | Directory for config files | `./data` |
| `GATEWAY_API_URL` | FastAPI URL (for Streamlit) | `http://localhost:8000` |
| `PORT` | Server port | `8000` |
