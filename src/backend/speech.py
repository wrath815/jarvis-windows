"""
JARVIS-Windows - Speech handling.
Sentence splitting, echo rejection, barge-in, and audio queue.
"""
import asyncio
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Deque
from enum import Enum

from .tts import synthesize, synthesize_streaming

class SpeechState(str, Enum):
    IDLE = "idle"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"

@dataclass
class SpeechChunk:
    text: str
    audio_data: bytes = b""
    sent_at: float = field(default_factory=time.time)
    acked_at: Optional[float] = None

class SpeechManager:
    def __init__(self):
        self.queue: Deque[SpeechChunk] = deque()
        self.current_chunk: Optional[SpeechChunk] = None
        self.state = SpeechState.IDLE
        self.last_spoken_text = ""
        self.ack_timeout = 45.0  # seconds
        
    def split_sentences(self, text: str) -> list[str]:
        """
        Split text into sentences for streaming TTS.
        Handles abbreviations, numbers, etc.
        """
        # Simple sentence splitting - can be improved
        # Split on . ! ? followed by space and capital letter
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text.strip())
        # Filter out empty
        return [s.strip() for s in sentences if s.strip()]
    
    def add_to_queue(self, text: str) -> list[SpeechChunk]:
        """Split text into sentences and add to queue."""
        sentences = self.split_sentences(text)
        chunks = []
        for sent in sentences:
            chunk = SpeechChunk(text=sent)
            self.queue.append(chunk)
            chunks.append(chunk)
        return chunks
    
    async def process_queue(self, on_audio_chunk: callable, on_chunk_complete: callable):
        """
        Process the speech queue.
        on_audio_chunk: callback(audio_bytes) - called for each audio chunk
        on_chunk_complete: callback(text) - called when a sentence finishes
        """
        self.state = SpeechState.SPEAKING
        
        while self.queue and self.state != SpeechState.INTERRUPTED:
            chunk = self.queue.popleft()
            self.current_chunk = chunk
            
            try:
                # Synthesize and stream
                async for audio_chunk in synthesize_streaming(chunk.text):
                    if self.state == SpeechState.INTERRUPTED:
                        break
                    await on_audio_chunk(audio_chunk)
                    chunk.audio_data += audio_chunk
                
                if self.state != SpeechState.INTERRUPTED:
                    chunk.acked_at = time.time()
                    await on_chunk_complete(chunk.text)
                    
            except Exception as e:
                print(f"TTS error: {e}")
                # Continue with next chunk
        
        self.current_chunk = None
        if self.state != SpeechState.INTERRUPTED:
            self.state = SpeechState.IDLE
    
    def interrupt(self):
        """Interrupt current speech (barge-in)."""
        self.state = SpeechState.INTERRUPTED
        self.queue.clear()
        self.current_chunk = None
    
    def acknowledge_chunk(self, text: str):
        """Acknowledge that a chunk was played (from client ack)."""
        if self.current_chunk and self.current_chunk.text == text:
            self.current_chunk.acked_at = time.time()
    
    def check_echo(self, recognized_text: str) -> bool:
        """
        Check if recognized text might be an echo of our own speech.
        Returns True if it looks like an echo.
        """
        if not self.last_spoken_text:
            return False
        
        # Simple check: if recognized text is a substring of recent speech
        # and the chunk was recently acked (or not yet acked)
        recognized_lower = recognized_text.lower().strip()
        spoken_lower = self.last_spoken_text.lower().strip()
        
        if recognized_lower in spoken_lower:
            # Check if the chunk was acked recently
            if self.current_chunk and self.current_chunk.acked_at:
                if time.time() - self.current_chunk.acked_at < 2.0:
                    return True
        return False
    
    def record_spoken(self, text: str):
        """Record what we just spoke for echo detection."""
        self.last_spoken_text = text
    
    def is_speaking(self) -> bool:
        return self.state == SpeechState.SPEAKING
    
    def get_queue_length(self) -> int:
        return len(self.queue)

# Global instance
_speech_manager = None

def get_speech_manager() -> SpeechManager:
    global _speech_manager
    if _speech_manager is None:
        _speech_manager = SpeechManager()
    return _speech_manager