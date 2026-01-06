"""Configuration management for the Copper Slack Bot."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration."""

    # Slack Configuration
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
    SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

    # Copper CRM Configuration
    COPPER_API_KEY = os.getenv("COPPER_API_KEY")
    COPPER_USER_EMAIL = os.getenv("COPPER_USER_EMAIL")
    COPPER_BASE_URL = "https://api.copper.com/developer_api/v1"

    # Anthropic Claude Configuration (for NLP)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    CLAUDE_CODE_OAUTH_TOKEN = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
    CLAUDE_PROXY_URL = os.getenv("CLAUDE_PROXY_URL", "http://localhost:6969")

    # Application Settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # CSV Processing Settings
    DEFAULT_PIPELINE_NAME = os.getenv("DEFAULT_PIPELINE_NAME", "Bid Intelligence - Supply")

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        required = {
            "SLACK_BOT_TOKEN": cls.SLACK_BOT_TOKEN,
            "SLACK_SIGNING_SECRET": cls.SLACK_SIGNING_SECRET,
            "SLACK_APP_TOKEN": cls.SLACK_APP_TOKEN,
            "COPPER_API_KEY": cls.COPPER_API_KEY,
            "COPPER_USER_EMAIL": cls.COPPER_USER_EMAIL,
        }

        missing = [key for key, value in required.items() if not value]

        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}\n"
                "Please check your .env file."
            )

        return True
