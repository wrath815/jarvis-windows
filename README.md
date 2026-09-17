# JARVIS-Windows

**Just A Rather Very Intelligent System — a voice assistant for Claude Code on Windows.**

JARVIS-Windows is a Windows port of the [original JARVIS](https://github.com/ethanplusai/jarvis) — a British butler who sits on top of the Claude Code you already pay for. You talk to him. He brainstorms a project with you out loud, one question at a time; when you have settled on something he writes the design down as a file in your project; then he starts a real Claude Code session on it and drives it through plan → review → execute.

## Features

- **Voice-first interaction** — Talk to JARVIS using Web Speech API (Chrome/Edge)
- **Brainstorms out loud** — One question at a time, offers approaches, doesn't start until you agree
- **Writes designs to disk** — `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` before execution
- **Drives builds** — Real `claude -p` sessions with phased plans, TDD, checkbox tracking
- **Watches all Claude Code sessions** — Not just his own. Tells you which ones need human input
- **Interrupts when it matters** — Blocked sessions announced immediately; finished ones batched
- **Long-term memory** — Plain Markdown files, one fact per file, with an index
- **Records everything** — Every run in SQLite with prompt, project, status, tokens, full event stream
- **Beautiful orb visualization** — Ported from original JARVIS (Three.js particles + connections + electrons)
- **Multi-provider TTS** — ElevenLabs, OpenAI, or Fish Audio (pick one)

## Architecture

```
Microphone → Chrome Web Speech API → WebSocket → FastAPI (server.py)
                                                      │
                                                      ▼
                                        the brain (brain.py) — ONE long-lived
                                        `claude -p` process on your subscription
                                                      │
                    ┌─────────────────────────────────┼──────────────────────────────┐
                    ▼                                 ▼                              ▼
        speech.py → TTS Provider → speaker    MCP tools (jarvis_mcp.py       session_watch.py
                                             → POST /internal/tool)     (every Claude Code
                                                      │                  session on the machine)
                                                      ▼
                                        RunExecutor → run store (SQLite)
                                                      │
                                                      ▼
                                        /api/runs + /ws/runs → /dashboard
```

## Requirements

- **Windows 10/11** (tested on Windows 11)
- **Google Chrome or Microsoft Edge** — Web Speech API requirement
- **Claude Code** installed and logged in (`npm install -g @anthropic-ai/claude-code`)
- **Python 3.11+**
- **Node.js 18+**
- **At least one TTS provider API key** — ElevenLabs, OpenAI, or Fish Audio

## Setup

```bash
git clone https://github.com/wrath815/jarvis-windows.git
cd jarvis-windows

# Backend dependencies
pip install -r requirements.txt

# Frontend dependencies
cd src/frontend
npm install
cd ../..

# Generate SSL certificates for HTTPS (required for microphone access)
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj '/CN=localhost'

# Configure environment
cp .env.example .env
# Edit .env - add your TTS provider API key(s) and choose provider
```

## Configuration (`.env`)

```bash
# ============================================================
# REQUIRED: Choose ONE TTS provider and add its API key
# ============================================================
TTS_PROVIDER=elevenlabs        # Options: elevenlabs, openai, fish_audio

# ElevenLabs (recommended - best quality, streaming support)
ELEVENLABS_API_KEY=your_key_here
# ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Rachel (default)
# ELEVENLABS_MODEL=eleven_multilingual_v2

# OpenAI TTS (good quality, no streaming)
# OPENAI_API_KEY=your_key_here
# OPENAI_TTS_VOICE=nova  # alloy, echo, fable, onyx, nova, shimmer
# OPENAI_TTS_MODEL=tts-1-hd

# Fish Audio (original JARVIS provider)
# FISH_API_KEY=your_key_here
# FISH_VOICE_ID=your_custom_voice_id

# ============================================================
# OPTIONAL: JARVIS Configuration
# ============================================================
# JARVIS_BRAIN_MODEL=sonnet  # sonnet, opus, haiku
# USER_NAME=Tony  # What JARVIS calls you

# ============================================================
# OPTIONAL: Server Configuration
# ============================================================
# JARVIS_HOST=127.0.0.1
# JARVIS_PORT=8340

# ============================================================
# OPTIONAL: Data Directory
# ============================================================
# JARVIS_DATA_DIR=C:\Users\YourName\jarvis-data

# ============================================================
# OPTIONAL: Terminal Preference (Windows)
# ============================================================
# JARVIS_TERMINAL=wt  # Windows Terminal (default), cmd, or powershell
```

## Running

Two terminals needed:

```bash
# Terminal 1 - Backend
python -m src.backend.server

# Terminal 2 - Frontend dev server
cd src/frontend && npm run dev
```

Open **Chrome/Edge** at `http://localhost:5173`, click the page once to allow audio, and speak.

The dashboard will be at `http://localhost:5173/dashboard.html` (when implemented).

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `TTS_PROVIDER` | Yes* | `elevenlabs`, `openai`, or `fish_audio` |
| `ELEVENLABS_API_KEY` | If using ElevenLabs | ElevenLabs API key |
| `ELEVENLABS_VOICE_ID` | No | Voice ID (default: Rachel) |
| `ELEVENLABS_MODEL` | No | Model (default: `eleven_multilingual_v2`) |
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key |
| `OPENAI_TTS_VOICE` | No | Voice (default: `nova`) |
| `OPENAI_TTS_MODEL` | No | Model (default: `tts-1-hd`) |
| `FISH_API_KEY` | If using Fish Audio | Fish Audio API key |
| `FISH_VOICE_ID` | No | Custom voice ID |
| `JARVIS_BRAIN_MODEL` | No | Brain model (default: `sonnet`) |
| `USER_NAME` | No | What JARVIS calls you |
| `JARVIS_DATA_DIR` | No | Custom data directory |
| `JARVIS_HOST` | No | Server host (default: `127.0.0.1`) |
| `JARVIS_PORT` | No | Server port (default: `8340`) |
| `JARVIS_TERMINAL` | No | `wt`, `cmd`, or `powershell` |

*At least one provider's API key must be present.

## Project Structure

```
jarvis-windows/
├── .env.example
├── requirements.txt
├── README.md
├── jarvis_home/
│   └── CLAUDE.md          # JARVIS personality template
├── src/
│   ├── backend/
│   │   ├── server.py          # FastAPI + WebSocket server
│   │   ├── brain.py           # Main orchestration logic
│   │   ├── claude_env.py      # Environment scrubbing
│   │   ├── data_paths.py      # Path management
│   │   ├── run_store.py       # SQLite run storage
│   │   ├── run_executor.py    # Spawns & manages runs
│   │   ├── stream_parser.py   # Claude Code JSON parsing
│   │   ├── jarvis_mcp.py      # MCP server for brain tools
│   │   ├── jarvis_memory.py   # Markdown memory system
│   │   ├── speech.py          # Sentence splitting, echo rejection
│   │   └── tts.py             # Multi-provider TTS
│   └── frontend/
│       ├── index.html
│       ├── package.json
│       ├── tsconfig.json
│       ├── vite.config.ts
│       └── src/
│           ├── main.ts        # Voice UI + orb integration
│           └── orb.ts         # Original JARVIS orb (ported)
├── data/                    # Runtime data (gitignored)
│   ├── memory/              # Long-term memory files
│   ├── runs.sqlite          # Run database
│   └── jarvis/
│       ├── tool-token       # Internal auth token
│       ├── connections.json # MCP server configs
│       └── CLAUDE.md        # Active personality
└── docs/
```

## License

Free for personal, non-commercial use. Based on [JARVIS](https://github.com/ethanplusai/jarvis) by [Ethan](https://ethanplus.ai).

## Credits

- Original JARVIS by [Ethan](https://ethanplus.ai)
- Runs on [Claude Code](https://claude.com/claude-code) with multi-provider TTS
- Inspired by Tony Stark's JARVIS (Marvel Entertainment)

> **Disclaimer:** Independent fan project, not affiliated with Marvel/Disney.
