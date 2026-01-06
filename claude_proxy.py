"""Claude API Proxy Service - supports OAuth authentication."""

import os
import logging
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Claude API Proxy")


class ClaudeRequest(BaseModel):
    """Request model for Claude API calls."""
    prompt: str
    max_tokens: int = 1024
    model: str = "claude-3-5-haiku-20241022"
    temperature: float = 0.0


class ClaudeResponse(BaseModel):
    """Response model for Claude API calls."""
    content: str
    model: str
    stop_reason: str


@app.post("/v1/messages", response_model=ClaudeResponse)
async def create_message(request: ClaudeRequest) -> ClaudeResponse:
    """
    Proxy endpoint for Claude Messages API.

    Accepts OAuth or API key authentication from environment.
    """
    # Get auth token from environment
    oauth_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not oauth_token and not api_key:
        raise HTTPException(
            status_code=500,
            detail="No authentication configured. Set CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY"
        )

    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    }

    # Use OAuth if available, otherwise API key
    if oauth_token:
        headers["Authorization"] = f"Bearer {oauth_token}"
        logger.info("Using OAuth authentication")
    else:
        headers["x-api-key"] = api_key
        logger.info("Using API key authentication")

    # Prepare request body
    body = {
        "model": request.model,
        "max_tokens": request.max_tokens,
        "messages": [
            {
                "role": "user",
                "content": request.prompt
            }
        ]
    }

    if request.temperature > 0:
        body["temperature"] = request.temperature

    # Make request to Claude API
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=body
            )
            response.raise_for_status()

            result = response.json()

            # Extract response
            content_text = ""
            if result.get("content"):
                content_text = result["content"][0].get("text", "")

            return ClaudeResponse(
                content=content_text,
                model=result.get("model", request.model),
                stop_reason=result.get("stop_reason", "unknown")
            )

    except httpx.HTTPStatusError as e:
        logger.error(f"Claude API error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Claude API error: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Proxy error: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    oauth_configured = bool(os.getenv("CLAUDE_CODE_OAUTH_TOKEN"))
    api_key_configured = bool(os.getenv("ANTHROPIC_API_KEY"))

    return {
        "status": "healthy",
        "auth_method": "oauth" if oauth_configured else "api_key" if api_key_configured else "none",
        "configured": oauth_configured or api_key_configured
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("CLAUDE_PROXY_PORT", "6969"))
    uvicorn.run(app, host="0.0.0.0", port=port)
