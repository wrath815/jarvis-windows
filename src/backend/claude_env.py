"""
JARVIS-Windows - Environment scrubbing.
Ensures child processes never see ANTHROPIC_* or CLAUDE_CODE_* variables.
"""
import os
from typing import Dict, List, Tuple

# Environment variable prefixes to scrub
SCRUBBED_ENV_PREFIXES = ("CLAUDE_CODE_", "ANTHROPIC_")
# Specific keys to scrub (exact match)
SCRUBBED_ENV_KEYS = {"CLAUDECODE"}

def scrub_env(env: Dict[str, str] = None) -> Dict[str, str]:
    """
    Return a copy of the environment with sensitive variables removed.
    Defaults to os.environ if none provided.
    """
    if env is None:
        env = dict(os.environ)
    
    cleaned = {}
    for key, value in env.items():
        # Check exact key matches
        if key in SCRUBBED_ENV_KEYS:
            continue
        # Check prefix matches
        if any(key.startswith(prefix) for prefix in SCRUBBED_ENV_PREFIXES):
            continue
        cleaned[key] = value
    
    return cleaned

def child_env(env: Dict[str, str] = None) -> Dict[str, str]:
    """
    Get the environment for child processes.
    This is the main entry point - use this for all subprocess spawning.
    """
    cleaned = scrub_env(env)
    # Ensure we don't accidentally pass through any API keys
    # Add any Windows-specific adjustments here if needed
    return cleaned

def check_env_warnings() -> List[str]:
    """
    Check for environment variables that might cause issues.
    Returns a list of warning messages.
    """
    warnings = []
    env = os.environ
    
    # Check for ANTHROPIC_API_KEY - the big one that Claude Code silently prefers
    if "ANTHROPIC_API_KEY" in env:
        warnings.append(
            "WARNING: ANTHROPIC_API_KEY is set in environment. "
            "Claude Code will silently prefer this over your login, "
            "billing will move to the API key. JARVIS scrubs this for child processes, "
            "but you should consider unsetting it in your shell profile."
        )
    
    # Check for other ANTHROPIC_* vars
    for key in env:
        if key.startswith("ANTHROPIC_") and key != "ANTHROPIC_API_KEY":
            warnings.append(f"Note: {key} is set and will be scrubbed from child processes.")
    
    return warnings