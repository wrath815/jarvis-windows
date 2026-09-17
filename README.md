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
        speech.py → Fish Audio → speaker    MCP tools (jarvis_mcp.py       session_watch.py
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
- **Fish Audio API key** — Required for voice (no fallback)

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/jarvis-windows.git
cd jarvis-windows

# Backend
pip install -r requirements.txt

# Frontend
cd src/frontend
npm install
cd ../..

# Generate SSL certificates for HTTPS (required for Web Speech API)
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj '/CN=localhost'

# Configure environment
cp .env.example .env
# Edit .env and add your FISH_API_KEY
```

## Running

Two terminals needed:

```bash
# Terminal 1 - Backend
python -m src.backend.server --host 127.0.0.1

# Terminal 2 - Frontend dev server
cd src/frontend && npm run dev
```

Open **Chrome/Edge** at `http://localhost:5173`, click the page once to allow audio, and speak.

The dashboard is at `http://localhost:5173/dashboard.html` (when implemented).

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FISH_API_KEY` | Yes | Fish Audio API key for TTS |
| `JARVIS_BRAIN_MODEL` | No | Brain model (default: sonnet) |
| `FISH_VOICE_ID` | No | Custom Fish Audio voice |
| `USER_NAME` | No | What JARVIS calls you |
| `JARVIS_DATA_DIR` | No | Custom data directory |
| `JARVIS_HOST` | No | Server host (default: 127.0.0.1) |
| `JARVIS_PORT` | No | Server port (default: 8340) |

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
│   │   └── jarvis_memory.py   # Markdown memory system
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
- Runs on [Claude Code](https://claude.com/claude-code) and [Fish Audio](https://fish.audio)
- Inspired by Tony Stark's JARVIS (Marvel Entertainment)

> **Disclaimer:** Independent fan project, not affiliated with Marvel/Disney.