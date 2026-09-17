"""
JARVIS-Windows - Memory system.
Plain Markdown files, one fact per file, with an index.
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass

from .data_paths import get_data_paths

@dataclass
class MemoryFact:
    id: str
    content: str
    created_at: datetime
    tags: List[str]

class JarvisMemory:
    def __init__(self):
        self.memory_dir = get_data_paths().memory_dir
        self.index_path = self.memory_dir / "index.json"
        self._ensure_index()
    
    def _ensure_index(self):
        if not self.index_path.exists():
            self.index_path.write_text(json.dumps({"facts": []}))
    
    def _load_index(self) -> Dict:
        return json.loads(self.index_path.read_text())
    
    def _save_index(self, index: Dict):
        self.index_path.write_text(json.dumps(index, indent=2))
    
    def add_fact(self, content: str, tags: List[str] = None) -> MemoryFact:
        """Add a new fact to memory."""
        fact_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        if tags is None:
            tags = []
        
        fact = MemoryFact(
            id=fact_id,
            content=content,
            created_at=datetime.now(),
            tags=tags
        )
        
        # Write fact file
        fact_file = self.memory_dir / f"{fact_id}.md"
        fact_file.write_text(content)
        
        # Update index
        index = self._load_index()
        index["facts"].append({
            "id": fact_id,
            "file": f"{fact_id}.md",
            "created_at": fact.created_at.isoformat(),
            "tags": tags,
            "preview": content[:200]
        })
        self._save_index(index)
        
        return fact
    
    def get_fact(self, fact_id: str) -> Optional[MemoryFact]:
        """Get a specific fact by ID."""
        index = self._load_index()
        for fact_info in index["facts"]:
            if fact_info["id"] == fact_id:
                fact_file = self.memory_dir / fact_info["file"]
                if fact_file.exists():
                    return MemoryFact(
                        id=fact_id,
                        content=fact_file.read_text(),
                        created_at=datetime.fromisoformat(fact_info["created_at"]),
                        tags=fact_info.get("tags", [])
                    )
        return None
    
    def list_facts(self, tag: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """List facts, optionally filtered by tag."""
        index = self._load_index()
        facts = index["facts"]
        
        if tag:
            facts = [f for f in facts if tag in f.get("tags", [])]
        
        # Sort by created_at descending
        facts.sort(key=lambda f: f["created_at"], reverse=True)
        
        return facts[:limit]
    
    def search_facts(self, query: str, limit: int = 20) -> List[Dict]:
        """Simple text search across facts."""
        index = self._load_index()
        query_lower = query.lower()
        results = []
        
        for fact_info in index["facts"]:
            if query_lower in fact_info["preview"].lower():
                results.append(fact_info)
        
        results.sort(key=lambda f: f["created_at"], reverse=True)
        return results[:limit]
    
    def delete_fact(self, fact_id: str) -> bool:
        """Delete a fact."""
        index = self._load_index()
        for i, fact_info in enumerate(index["facts"]):
            if fact_info["id"] == fact_id:
                fact_file = self.memory_dir / fact_info["file"]
                if fact_file.exists():
                    fact_file.unlink()
                index["facts"].pop(i)
                self._save_index(index)
                return True
        return False
    
    def format_for_brain(self, max_facts: int = 20) -> str:
        """Format recent facts for the brain's context."""
        facts = self.list_facts(limit=max_facts)
        if not facts:
            return "No long-term memories stored yet."
        
        lines = ["## Long-term Memory (recent)"]
        for f in facts:
            tags = f" [{', '.join(f.get('tags', []))}]" if f.get('tags') else ""
            lines.append(f"- {f['preview']}{tags}  (id: {f['id']})")
        
        return "\n".join(lines)

# Global instance
_memory = None

def get_memory() -> JarvisMemory:
    global _memory
    if _memory is None:
        _memory = JarvisMemory()
    return _memory