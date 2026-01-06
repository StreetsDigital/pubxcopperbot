"""Claude Code CLI Wrapper - HTTP API for Claude Code CLI."""

import os
import logging
import subprocess
import tempfile
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Claude Code CLI Wrapper")


class ClaudeRequest(BaseModel):
    """Request model for Claude Code CLI calls."""
    prompt: str
    max_tokens: int = 1024
    model: str = "claude-3-5-haiku-20241022"
    temperature: float = 0.0


class ClaudeResponse(BaseModel):
    """Response model for Claude Code CLI calls."""
    content: str
    model: str
    stop_reason: str = "end_turn"


@app.on_event("startup")
async def setup_claude_auth():
    """Configure Claude Code authentication on startup."""
    oauth_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")

    if not oauth_token:
        logger.warning("No CLAUDE_CODE_OAUTH_TOKEN found - Claude Code may not work")
        return

    try:
        # Set up Claude Code authentication
        config_dir = os.path.expanduser("~/.config/claude-code")
        os.makedirs(config_dir, exist_ok=True)

        # Create auth config
        auth_file = os.path.join(config_dir, "auth.json")
        with open(auth_file, "w") as f:
            f.write(f'{{"token":"{oauth_token}"}}\n')

        logger.info("Claude Code authentication configured")

    except Exception as e:
        logger.error(f"Failed to configure Claude Code auth: {e}")


@app.post("/v1/messages", response_model=ClaudeResponse)
async def create_message(request: ClaudeRequest) -> ClaudeResponse:
    """
    Execute Claude Code CLI and return response.

    Uses the `claude` CLI tool with OAuth authentication.
    """
    try:
        # Create a temporary file for the prompt
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(request.prompt)
            prompt_file = f.name

        try:
            # Execute Claude Code CLI
            # Use --model flag if available, otherwise use default
            cmd = [
                "claude",
                "--file", prompt_file,
                "--no-stream"  # Don't stream, return all at once
            ]

            logger.info(f"Executing Claude Code CLI: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,  # 60 second timeout
                env={**os.environ, "CLAUDE_API_KEY": os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "")}
            )

            if result.returncode != 0:
                logger.error(f"Claude Code CLI error: {result.stderr}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Claude Code CLI error: {result.stderr}"
                )

            # Extract response
            output = result.stdout.strip()

            logger.info(f"Claude Code response received ({len(output)} chars)")

            return ClaudeResponse(
                content=output,
                model=request.model,
                stop_reason="end_turn"
            )

        finally:
            # Clean up temp file
            try:
                os.unlink(prompt_file)
            except Exception:
                pass

    except subprocess.TimeoutExpired:
        logger.error("Claude Code CLI timeout")
        raise HTTPException(
            status_code=504,
            detail="Claude Code CLI timeout"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Wrapper error: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    oauth_configured = bool(os.getenv("CLAUDE_CODE_OAUTH_TOKEN"))

    # Check if Claude Code CLI is available
    cli_available = False
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        cli_available = result.returncode == 0
        version = result.stdout.strip() if cli_available else None
    except Exception:
        version = None

    return {
        "status": "healthy" if (oauth_configured and cli_available) else "degraded",
        "auth_method": "oauth" if oauth_configured else "none",
        "configured": oauth_configured,
        "claude_cli_available": cli_available,
        "claude_cli_version": version
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("CLAUDE_PROXY_PORT", "6969"))
    uvicorn.run(app, host="0.0.0.0", port=port)
