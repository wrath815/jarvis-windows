"""
JARVIS-Windows - Stream parser for Claude Code JSON output.
Pure parsing, no I/O.
"""
import json
from typing import Generator, Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

class StreamEventType(str, Enum):
    MESSAGE = "message"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    ERROR = "error"
    COMPLETE = "complete"

@dataclass
class StreamEvent:
    type: StreamEventType
    data: Dict[str, Any]
    raw: str

def parse_stream(lines: Generator[str, None, None]) -> Generator[StreamEvent, None, None]:
    """
    Parse Claude Code's streaming JSON output.
    Each line is a complete JSON object.
    """
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            yield StreamEvent(StreamEventType.ERROR, {"error": "JSON decode failed", "line": line}, line)
            continue
        
        # Determine event type from the object structure
        event_type = obj.get("type", "unknown")
        
        if event_type == "message":
            yield StreamEvent(StreamEventType.MESSAGE, obj, line)
        elif event_type == "tool_use":
            yield StreamEvent(StreamEventType.TOOL_USE, obj, line)
        elif event_type == "tool_result":
            yield StreamEvent(StreamEventType.TOOL_RESULT, obj, line)
        elif event_type == "thinking":
            yield StreamEvent(StreamEventType.THINKING, obj, line)
        elif event_type == "error":
            yield StreamEvent(StreamEventType.ERROR, obj, line)
        elif event_type == "result" or event_type == "complete":
            yield StreamEvent(StreamEventType.COMPLETE, obj, line)
        else:
            yield StreamEvent(StreamEventType.MESSAGE, obj, line)

def extract_text_from_message(message: Dict[str, Any]) -> str:
    """Extract text content from a message object."""
    content = message.get("content", [])
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
        return "".join(texts)
    return ""

def extract_tool_uses(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract tool use blocks from a message."""
    content = message.get("content", [])
    if isinstance(content, list):
        return [item for item in content if isinstance(item, dict) and item.get("type") == "tool_use"]
    return []

def is_final_message(message: Dict[str, Any]) -> bool:
    """Check if this is a final result message (not a tool use)."""
    content = message.get("content", [])
    if isinstance(content, list):
        has_tool_use = any(isinstance(item, dict) and item.get("type") == "tool_use" for item in content)
        return not has_tool_use
    return True