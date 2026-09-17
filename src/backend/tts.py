"""
JARVIS-Windows - TTS with multiple providers.
Supports ElevenLabs, OpenAI, and Fish Audio.
"""
import os
import httpx
from typing import Optional, Literal
from enum import Enum

class TTSProvider(str, Enum):
    ELEVENLABS = "elevenlabs"
    OPENAI = "openai"
    FISH_AUDIO = "fish_audio"

# Configuration from environment
TTS_PROVIDER = TTSProvider(os.environ.get("TTS_PROVIDER", "elevenlabs").lower())

# ElevenLabs
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")

# OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_TTS_VOICE = os.environ.get("OPENAI_TTS_VOICE", "nova")  # alloy, echo, fable, onyx, nova, shimmer
OPENAI_TTS_MODEL = os.environ.get("OPENAI_TTS_MODEL", "tts-1-hd")  # tts-1 or tts-1-hd
OPENAI_API_URL = "https://api.openai.com/v1/audio/speech"

# Fish Audio
FISH_API_KEY = os.environ.get("FISH_API_KEY")
FISH_VOICE_ID = os.environ.get("FISH_VOICE_ID", "default")
FISH_API_URL = "https://api.fish.audio/v1/tts"

async def synthesize(text: str, voice_id: Optional[str] = None, provider: Optional[TTSProvider] = None) -> bytes:
    """
    Synthesize speech using the configured provider.
    Returns audio bytes (MP3 for ElevenLabs/OpenAI, MP3 for Fish Audio).
    """
    prov = provider or TTS_PROVIDER
    
    if prov == TTSProvider.ELEVENLABS:
        return await _synthesize_elevenlabs(text, voice_id)
    elif prov == TTSProvider.OPENAI:
        return await _synthesize_openai(text, voice_id)
    elif prov == TTSProvider.FISH_AUDIO:
        return await _synthesize_fish_audio(text, voice_id)
    else:
        raise ValueError(f"Unknown TTS provider: {prov}")

async def synthesize_streaming(text: str, voice_id: Optional[str] = None, provider: Optional[TTSProvider] = None):
    """
    Synthesize speech with streaming response.
    Yields audio chunks.
    """
    prov = provider or TTS_PROVIDER
    
    if prov == TTSProvider.ELEVENLABS:
        async for chunk in _synthesize_elevenlabs_streaming(text, voice_id):
            yield chunk
    elif prov == TTSProvider.OPENAI:
        # OpenAI doesn't support streaming in the same way, fallback to full
        audio = await _synthesize_openai(text, voice_id)
        yield audio
    elif prov == TTSProvider.FISH_AUDIO:
        async for chunk in _synthesize_fish_audio_streaming(text, voice_id):
            yield chunk
    else:
        raise ValueError(f"Unknown TTS provider: {prov}")

# ElevenLabs implementation
async def _synthesize_elevenlabs(text: str, voice_id: Optional[str] = None) -> bytes:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not set.")
    
    voice = voice_id or ELEVENLABS_VOICE_ID
    url = f"{ELEVENLABS_API_URL}/{voice}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": ELEVENLABS_MODEL,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
            }
        )
        response.raise_for_status()
        return response.content

async def _synthesize_elevenlabs_streaming(text: str, voice_id: Optional[str] = None):
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not set.")
    
    voice = voice_id or ELEVENLABS_VOICE_ID
    url = f"{ELEVENLABS_API_URL}/{voice}/stream"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            url,
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": ELEVENLABS_MODEL,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                }
            }
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(chunk_size=4096):
                if chunk:
                    yield chunk

# OpenAI implementation
async def _synthesize_openai(text: str, voice_id: Optional[str] = None) -> bytes:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set.")
    
    voice = voice_id or OPENAI_TTS_VOICE
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            OPENAI_API_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_TTS_MODEL,
                "input": text,
                "voice": voice,
                "response_format": "mp3",
                "speed": 1.0
            }
        )
        response.raise_for_status()
        return response.content

# Fish Audio implementation
async def _synthesize_fish_audio(text: str, voice_id: Optional[str] = None) -> bytes:
    if not FISH_API_KEY:
        raise RuntimeError("FISH_API_KEY not set.")
    
    voice = voice_id or FISH_VOICE_ID
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            FISH_API_URL,
            headers={
                "Authorization": f"Bearer {FISH_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "voice_id": voice,
                "format": "mp3",
                "sample_rate": 24000,
            }
        )
        response.raise_for_status()
        return response.content

async def _synthesize_fish_audio_streaming(text: str, voice_id: Optional[str] = None):
    if not FISH_API_KEY:
        raise RuntimeError("FISH_API_KEY not set.")
    
    voice = voice_id or FISH_VOICE_ID
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            FISH_API_URL,
            headers={
                "Authorization": f"Bearer {FISH_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "voice_id": voice,
                "format": "mp3",
                "sample_rate": 24000,
            }
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(chunk_size=4096):
                if chunk:
                    yield chunk

def get_available_providers() -> list[str]:
    """Return list of providers that have API keys configured."""
    available = []
    if ELEVENLABS_API_KEY:
        available.append(TTSProvider.ELEVENLABS.value)
    if OPENAI_API_KEY:
        available.append(TTSProvider.OPENAI.value)
    if FISH_API_KEY:
        available.append(TTSProvider.FISH_AUDIO.value)
    return available