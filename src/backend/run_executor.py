"""
JARVIS-Windows - Run executor.
Spawns and manages Claude Code runs, driving them to terminal states.
"""
import subprocess
import asyncio
import uuid
import os
import signal
from datetime import datetime
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass

from .data_paths import get_data_paths
from .claude_env import child_env, check_env_warnings
from .run_store import get_run_store, Run, RunStatus
from .stream_parser import parse_stream, StreamEventType, extract_text_from_message

# Default to skipping permissions since we can't handle interactive prompts
JARVIS_SKIP_PERMISSIONS = os.environ.get("JARVIS_SKIP_PERMISSIONS", "1") == "1"

@dataclass
class RunResult:
    run: Run
    events: List[Dict[str, Any]]

class RunExecutor:
    def __init__(self):
        self.run_store = get_run_store()
        self.active_processes: Dict[str, subprocess.Popen] = {}
    
    async def execute_run(
        self,
        project: str,
        prompt: str,
        model: str = "sonnet",
        brief: Optional[str] = None,
        plan: Optional[str] = None,
        working_dir: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute a Claude Code run and yield events as they happen.
        The run will always reach a terminal state.
        """
        run_id = str(uuid.uuid4())[:8]
        now = datetime.now()
        
        # Create run record
        run = Run(
            id=run_id,
            project=project,
            prompt=prompt,
            status=RunStatus.PENDING,
            created_at=now,
            model=model,
            brief=brief,
            plan=plan
        )
        self.run_store.create_run(run)
        
        # Emit created event
        yield {"type": "run_created", "run_id": run_id, "project": project}
        self.run_store.add_event(run_id, "created", {"project": project, "prompt": prompt[:200]})
        
        # Check env warnings
        warnings = check_env_warnings()
        for w in warnings:
            yield {"type": "warning", "message": w}
            self.run_store.add_event(run_id, "warning", {"message": w})
        
        # Prepare command
        cmd = ["claude", "-p", "--model", model]
        if JARVIS_SKIP_PERMISSIONS:
            cmd.append("--dangerously-skip-permissions")
        cmd.append(prompt)
        
        # Prepare environment
        env = child_env()
        
        # Working directory
        cwd = working_dir or os.getcwd()
        
        # Update status to running
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now()
        self.run_store.update_run(run)
        yield {"type": "run_started", "run_id": run_id}
        self.run_store.add_event(run_id, "started", {"cmd": " ".join(cmd[:3]) + " ..."})
        
        # Spawn process
        try:
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace'
            )
            self.active_processes[run_id] = process
            
            # Read stdout line by line
            tokens_used = 0
            full_output = []
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if not line:
                    await asyncio.sleep(0.05)
                    continue
                
                full_output.append(line)
                
                # Parse stream events
                for event in parse_stream([line]):
                    if event.type == StreamEventType.MESSAGE:
                        text = extract_text_from_message(event.data)
                        if text:
                            yield {"type": "output", "run_id": run_id, "text": text}
                            self.run_store.add_event(run_id, "output", {"text": text[:500]})
                    elif event.type == StreamEventType.TOOL_USE:
                        tool_name = event.data.get("name", "unknown")
                        yield {"type": "tool_use", "run_id": run_id, "tool": tool_name, "input": event.data.get("input", {})}
                        self.run_store.add_event(run_id, "tool_use", {"tool": tool_name, "input": str(event.data.get("input", {}))[:500]})
                    elif event.type == StreamEventType.TOOL_RESULT:
                        tool_id = event.data.get("tool_use_id", "unknown")
                        yield {"type": "tool_result", "run_id": run_id, "tool_use_id": tool_id}
                        self.run_store.add_event(run_id, "tool_result", {"tool_use_id": tool_id})
                    elif event.type == StreamEventType.COMPLETE:
                        # Extract token usage if available
                        usage = event.data.get("usage", {})
                        if usage:
                            tokens_used += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                
                # Also forward stderr
                # (in a real implementation, we'd read stderr in a separate thread)
            
            # Wait for process to complete
            exit_code = process.wait()
            
            # Read any remaining stderr
            stderr_output = process.stderr.read() if process.stderr else ""
            
        except Exception as e:
            exit_code = -1
            stderr_output = str(e)
        finally:
            self.active_processes.pop(run_id, None)
        
        # Determine final status
        now = datetime.now()
        run.finished_at = now
        run.exit_code = exit_code
        run.tokens_used = tokens_used
        
        if exit_code == 0:
            run.status = RunStatus.SUCCEEDED
        elif exit_code == -1:
            run.status = RunStatus.FAILED
            run.error = stderr_output[:1000] if stderr_output else "Process failed to start"
        else:
            run.status = RunStatus.FAILED
            run.error = stderr_output[:1000] if stderr_output else f"Exit code {exit_code}"
        
        self.run_store.update_run(run)
        
        yield {"type": "run_finished", "run_id": run_id, "status": run.status.value, "exit_code": exit_code}
        self.run_store.add_event(run_id, "finished", {"status": run.status.value, "exit_code": exit_code, "tokens": tokens_used})
        
        if run.error:
            yield {"type": "error", "run_id": run_id, "error": run.error}
    
    def cancel_run(self, run_id: str) -> bool:
        """Cancel a running process."""
        process = self.active_processes.get(run_id)
        if process and process.poll() is None:
            try:
                process.terminate()
                # Give it a moment
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                
                run = self.run_store.get_run(run_id)
                if run:
                    run.status = RunStatus.CANCELLED
                    run.finished_at = datetime.now()
                    run.exit_code = -15
                    self.run_store.update_run(run)
                    self.run_store.add_event(run_id, "cancelled", {})
                return True
            except Exception:
                pass
        return False
    
    def get_active_runs(self) -> List[str]:
        return list(self.active_processes.keys())

# Global instance
_run_executor = None

def get_run_executor() -> RunExecutor:
    global _run_executor
    if _run_executor is None:
        _run_executor = RunExecutor()
    return _run_executor