"""
JARVIS-Windows - MCP Server exposing JARVIS tools to the brain.
"""
import json
import sys
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from .data_paths import get_data_paths
from .run_store import get_run_store, RunStatus
from .run_executor import get_run_executor
from .jarvis_memory import get_memory

@dataclass
class Tool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable

class JarvisMCP:
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self._register_tools()
    
    def _register_tools(self):
        """Register all available tools."""
        self._register_tool(Tool(
            name="start_run",
            description="Start a new Claude Code run with a prompt. Returns a run_id.",
            input_schema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project name/directory"},
                    "prompt": {"type": "string", "description": "The prompt for Claude Code"},
                    "model": {"type": "string", "description": "Model to use (sonnet, opus, etc.)", "default": "sonnet"},
                    "brief": {"type": "string", "description": "Optional brief/design document"},
                    "plan": {"type": "string", "description": "Optional execution plan"},
                    "working_dir": {"type": "string", "description": "Working directory for the run"}
                },
                "required": ["project", "prompt"]
            },
            handler=self._handle_start_run
        ))
        
        self._register_tool(Tool(
            name="get_run_status",
            description="Get the status and details of a run.",
            input_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "Run ID to check"}
                },
                "required": ["run_id"]
            },
            handler=self._handle_get_run_status
        ))
        
        self._register_tool(Tool(
            name="cancel_run",
            description="Cancel a running process.",
            input_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "Run ID to cancel"}
                },
                "required": ["run_id"]
            },
            handler=self._handle_cancel_run
        ))
        
        self._register_tool(Tool(
            name="list_runs",
            description="List recent runs, optionally filtered by project or status.",
            input_schema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Filter by project name"},
                    "status": {"type": "string", "description": "Filter by status"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20}
                }
            },
            handler=self._handle_list_runs
        ))
        
        self._register_tool(Tool(
            name="get_run_events",
            description="Get the event log for a specific run.",
            input_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "Run ID"}
                },
                "required": ["run_id"]
            },
            handler=self._handle_get_run_events
        ))
        
        self._register_tool(Tool(
            name="add_memory",
            description="Add a fact to long-term memory.",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The fact to remember"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags"}
                },
                "required": ["content"]
            },
            handler=self._handle_add_memory
        ))
        
        self._register_tool(Tool(
            name="search_memory",
            description="Search long-term memory for relevant facts.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results", "default": 10}
                },
                "required": ["query"]
            },
            handler=self._handle_search_memory
        ))
        
        self._register_tool(Tool(
            name="list_memory",
            description="List recent memory facts, optionally filtered by tag.",
            input_schema={
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "description": "Filter by tag"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20}
                }
            },
            handler=self._handle_list_memory
        ))
        
        self._register_tool(Tool(
            name="get_active_sessions",
            description="Check for Claude Code sessions waiting on human input.",
            input_schema={
                "type": "object",
                "properties": {}
            },
            handler=self._handle_get_active_sessions
        ))
    
    def _register_tool(self, tool: Tool):
        self.tools[tool.name] = tool
    
    # Tool handlers
    
    async def _handle_start_run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        run_id = None
        async for event in get_run_executor().execute_run(
            project=args["project"],
            prompt=args["prompt"],
            model=args.get("model", "sonnet"),
            brief=args.get("brief"),
            plan=args.get("plan"),
            working_dir=args.get("working_dir")
        ):
            if event.get("type") == "run_created":
                run_id = event["run_id"]
        
        if run_id:
            return {"success": True, "run_id": run_id, "message": f"Started run {run_id} for project {args['project']}"}
        return {"success": False, "error": "Failed to start run"}
    
    async def _handle_get_run_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        run = get_run_store().get_run(args["run_id"])
        if not run:
            return {"success": False, "error": f"Run {args['run_id']} not found"}
        
        return {
            "success": True,
            "run": {
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
                "model": run.model
            }
        }
    
    async def _handle_cancel_run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        success = get_run_executor().cancel_run(args["run_id"])
        if success:
            return {"success": True, "message": f"Run {args['run_id']} cancelled"}
        return {"success": False, "error": f"Run {args['run_id']} not found or not running"}
    
    async def _handle_list_runs(self, args: Dict[str, Any]) -> Dict[str, Any]:
        status = None
        if args.get("status"):
            try:
                status = RunStatus(args["status"])
            except ValueError:
                pass
        
        runs = get_run_store().list_runs(
            project=args.get("project"),
            status=status,
            limit=args.get("limit", 20)
        )
        
        return {
            "success": True,
            "runs": [
                {
                    "id": r.id,
                    "project": r.project,
                    "prompt": r.prompt[:100] + "..." if len(r.prompt) > 100 else r.prompt,
                    "status": r.status.value,
                    "created_at": r.created_at.isoformat(),
                    "tokens_used": r.tokens_used
                }
                for r in runs
            ]
        }
    
    async def _handle_get_run_events(self, args: Dict[str, Any]) -> Dict[str, Any]:
        events = get_run_store().get_events(args["run_id"])
        return {
            "success": True,
            "events": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "type": e.event_type,
                    "payload": e.payload
                }
                for e in events
            ]
        }
    
    async def _handle_add_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        fact = get_memory().add_fact(args["content"], args.get("tags", []))
        return {"success": True, "fact_id": fact.id, "message": f"Added memory {fact.id}"}
    
    async def _handle_search_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        results = get_memory().search_facts(args["query"], args.get("limit", 10))
        return {"success": True, "results": results}
    
    async def _handle_list_memory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        results = get_memory().list_facts(args.get("tag"), args.get("limit", 20))
        return {"success": True, "results": results}
    
    async def _handle_get_active_sessions(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # Windows version: check for Claude Code processes
        # This is a placeholder - would need implementation to scan for Claude Code processes
        active_runs = get_run_executor().get_active_runs()
        return {
            "success": True,
            "active_runs": active_runs,
            "note": "Full session watching not yet implemented on Windows"
        }
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions in MCP format."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema
            }
            for tool in self.tools.values()
        ]
    
    async def call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool by name."""
        tool = self.tools.get(name)
        if not tool:
            return {"success": False, "error": f"Unknown tool: {name}"}
        return await tool.handler(args)

# Global instance
_mcp = None

def get_mcp() -> JarvisMCP:
    global _mcp
    if _mcp is None:
        _mcp = JarvisMCP()
    return _mcp