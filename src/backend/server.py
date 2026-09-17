"""
JARVIS-Windows - Main FastAPI server.
WebSocket handler, HTTP API, internal tool endpoint.
"""
import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from dotenv import load_dotenv

from .data_paths import get_data_paths, reset_data_paths
from .claude_env import check_env_warnings
from .run_store import get_run_store, RunStatus
from .run_executor import get_run_executor
from .jarvis_mcp import get_mcp
from .jarvis_memory import get_memory
from .brain import get_brain
from .tts import get_available_providers, TTSProvider, synthesize

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
    
    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
    
    async def send_json(self, client_id: str, data: Dict[str, Any]):
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(client_id)
    
    async def broadcast(self, data: Dict[str, Any]):
        for client_id in list(self.active_connections.keys()):
            await self.send_json(client_id, data)

manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    load_dotenv()  # Load .env file
    print("JARVIS-Windows starting up...")
    # Initialize data paths
    get_data_paths()
    # Check env warnings
    warnings = check_env_warnings()
    for w in warnings:
        print(w)
    # Initialize components
    get_run_store()
    get_run_executor()
    get_mcp()
    get_memory()
    get_brain()
    # Check TTS providers
    available = get_available_providers()
    if available:
        print(f"TTS providers available: {', '.join(available)}")
    else:
        print("WARNING: No TTS providers configured. JARVIS will be silent.")
    print("JARVIS-Windows ready")
    yield
    # Shutdown
    print("JARVIS-Windows shutting down...")

app = FastAPI(title="JARVIS-Windows", lifespan=lifespan)

# CORS - allow local origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request models
class StartRunRequest(BaseModel):
    project: str
    prompt: str
    model: str = "sonnet"
    brief: Optional[str] = None
    plan: Optional[str] = None
    working_dir: Optional[str] = None

class ToolCallRequest(BaseModel):
    tool: str
    args: Dict[str, Any]

class MemoryRequest(BaseModel):
    content: str
    tags: Optional[List[str]] = None

class SearchMemoryRequest(BaseModel):
    query: str
    limit: int = 10

# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "service": "jarvis-windows"}

# Tool token endpoint
@app.get("/api/tool-token")
async def get_tool_token():
    token = get_data_paths().ensure_tool_token()
    return {"token": token}

# Run endpoints
@app.post("/api/runs")
async def start_run(request: StartRunRequest):
    """Start a new run."""
    run_id = str(uuid.uuid4())[:8]
    
    # We'll use the run executor directly
    # For API, we'll just create the run and return immediately
    # The actual execution happens via WebSocket
    from .run_store import Run
    run = Run(
        id=run_id,
        project=request.project,
        prompt=request.prompt,
        status=RunStatus.PENDING,
        created_at=datetime.now(),
        model=request.model,
        brief=request.brief,
        plan=request.plan
    )
    get_run_store().create_run(run)
    
    return {"run_id": run_id, "status": "pending"}

@app.get("/api/runs")
async def list_runs(project: Optional[str] = None, status: Optional[str] = None, limit: int = 50):
    run_status = None
    if status:
        try:
            run_status = RunStatus(status)
        except ValueError:
            pass
    runs = get_run_store().list_runs(project=project, status=run_status, limit=limit)
    return {
        "runs": [
            {
                "id": r.id,
                "project": r.project,
                "prompt": r.prompt[:200] + "..." if len(r.prompt) > 200 else r.prompt,
                "status": r.status.value,
                "created_at": r.created_at.isoformat(),
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "exit_code": r.exit_code,
                "error": r.error,
                "tokens_used": r.tokens_used,
                "model": r.model
            }
            for r in runs
        ]
    }

@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    run = get_run_store().get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return {
        "id": run.id,
        "project": run.project,
        "prompt": run.prompt,
        "status": run.status.value,
        "created_at": run.created_at.isoformat(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "exit_code": run.exit_code,
        "error": run.error,
        "tokens_used": run.tokens_used,
        "model": run.model,
        "brief": run.brief,
        "plan": run.plan
    }

@app.get("/api/runs/{run_id}/events")
async def get_run_events(run_id: str):
    events = get_run_store().get_events(run_id)
    return {
        "events": [
            {
                "timestamp": e.timestamp.isoformat(),
                "type": e.event_type,
                "payload": e.payload
            }
            for e in events
        ]
    }

# Internal tool endpoint (for MCP)
@app.post("/internal/tool")
async def internal_tool(request: ToolCallRequest):
    """Internal tool endpoint for the brain's MCP connection."""
    result = await get_mcp().call_tool(request.tool, request.args)
    return result

# Memory endpoints
@app.post("/api/memory")
async def add_memory(request: MemoryRequest):
    fact = get_memory().add_fact(request.content, request.tags or [])
    return {"success": True, "fact_id": fact.id}

@app.get("/api/memory")
async def list_memory(tag: Optional[str] = None, limit: int = 50):
    facts = get_memory().list_facts(tag, limit)
    return {"facts": facts}

@app.post("/api/memory/search")
async def search_memory(request: SearchMemoryRequest):
    results = get_memory().search_facts(request.query, request.limit)
    return {"results": results}

# Sessions endpoint (placeholder for Windows)
@app.get("/api/sessions")
async def get_sessions():
    active_runs = get_run_executor().get_active_runs()
    return {
        "active_runs": active_runs,
        "note": "Full session watching not yet implemented on Windows"
    }

# TTS status endpoint
@app.get("/api/tts/status")
async def tts_status():
    available = get_available_providers()
    current = os.environ.get("TTS_PROVIDER", "elevenlabs")
    return {
        "current_provider": current,
        "available_providers": available,
        "providers": {
            "elevenlabs": bool(os.environ.get("ELEVENLABS_API_KEY")),
            "openai": bool(os.environ.get("OPENAI_API_KEY")),
            "fish_audio": bool(os.environ.get("FISH_API_KEY"))
        }
    }

# Test TTS endpoint
class TTSTestRequest(BaseModel):
    text: str
    provider: Optional[str] = None
    voice_id: Optional[str] = None

@app.post("/api/tts/test")
async def test_tts(request: TTSTestRequest):
    provider = None
    if request.provider:
        try:
            provider = TTSProvider(request.provider.lower())
        except ValueError:
            raise HTTPException(400, f"Unknown provider: {request.provider}")
    
    try:
        audio = await synthesize(request.text, request.voice_id, provider)
        # Return base64 encoded audio
        import base64
        return {
            "success": True,
            "audio_base64": base64.b64encode(audio).decode(),
            "format": "mp3",
            "provider": provider.value if provider else os.environ.get("TTS_PROVIDER", "elevenlabs")
        }
    except Exception as e:
        raise HTTPException(500, f"TTS error: {str(e)}")

# WebSocket for real-time updates
@app.websocket("/ws/runs")
async def websocket_runs(websocket: WebSocket):
    client_id = str(uuid.uuid4())[:8]
    await manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Handle incoming messages if needed
            if data.get("type") == "ping":
                await manager.send_json(client_id, {"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(client_id)

# Voice WebSocket
@app.websocket("/ws/voice")
async def websocket_voice(websocket: WebSocket):
    client_id = str(uuid.uuid4())[:8]
    await manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "speech":
                # Process speech input through brain
                text = data.get("text", "")
                if text:
                    brain = get_brain()
                    async for event in brain.process_turn(text):
                        await manager.send_json(client_id, event)
            elif data.get("type") == "ack":
                # Audio acknowledgment from client
                pass
    except WebSocketDisconnect:
        manager.disconnect(client_id)

# Static files (frontend) - will mount after build
# app.mount("/", StaticFiles(directory="src/frontend/dist", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("JARVIS_HOST", "127.0.0.1")
    port = int(os.environ.get("JARVIS_PORT", "8340"))
    uvicorn.run(app, host=host, port=port)