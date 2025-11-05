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

    # OpenAI Configuration (for NLP)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Application Settings
    PORT = int(os.getenv("PORT", 3000))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

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
