"""
JARVIS-Windows - Core path management.
Single source of truth for where JARVIS writes data.
"""
import os
from pathlib import Path
from typing import Optional

class DataPaths:
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir:
            self.root = Path(data_dir).resolve()
        else:
            # Default to project/data
            self.root = Path(__file__).parent.parent.parent / "data"
        
        self.root.mkdir(parents=True, exist_ok=True)
        
        # Subdirectories
        self.memory_dir = self.root / "memory"
        self.memory_dir.mkdir(exist_ok=True)
        
        self.runs_db = self.root / "runs.sqlite"
        self.tool_token_path = self.root / "jarvis" / "tool-token"
        self.tool_token_path.parent.mkdir(exist_ok=True)
        
        self.connections_file = self.root / "jarvis" / "connections.json"
        self.connections_file.parent.mkdir(exist_ok=True)
        
        self.claude_md_path = self.root / "jarvis" / "CLAUDE.md"
        self.claude_md_path.parent.mkdir(exist_ok=True)
    
    def ensure_tool_token(self) -> str:
        """Ensure tool token exists, create if missing. Returns the token."""
        if not self.tool_token_path.exists():
            import secrets
            token = secrets.token_urlsafe(32)
            self.tool_token_path.write_text(token)
            # On Windows, we can't easily chmod 0600, but we can try to restrict
            try:
                import stat
                self.tool_token_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            except Exception:
                pass
        return self.tool_token_path.read_text().strip()
    
    def get_claude_md(self) -> str:
        """Get the CLAUDE.md content, copying from template if needed."""
        template_path = Path(__file__).parent.parent.parent / "jarvis_home" / "CLAUDE.md"
        if not self.claude_md_path.exists() and template_path.exists():
            self.claude_md_path.write_text(template_path.read_text())
        return self.claude_md_path.read_text() if self.claude_md_path.exists() else ""

# Global instance
_data_paths: Optional[DataPaths] = None

def get_data_paths() -> DataPaths:
    global _data_paths
    if _data_paths is None:
        data_dir = os.environ.get("JARVIS_DATA_DIR")
        _data_paths = DataPaths(data_dir)
    return _data_paths

def reset_data_paths() -> None:
    global _data_paths
    _data_paths = None