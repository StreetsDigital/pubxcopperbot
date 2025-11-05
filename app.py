"""Copper CRM Slack Bot - Main Application."""

import os
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from config import Config
from copper_client import CopperClient
from query_processor import QueryProcessor
from csv_handler import CSVHandler

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validate configuration
try:
    Config.validate()
except ValueError as e:
    logger.error(f"Configuration error: {e}")
    exit(1)

# Initialize Slack app
app = App(token=Config.SLACK_BOT_TOKEN)

# Initialize components
copper_client = CopperClient()
query_processor = QueryProcessor()
csv_handler = CSVHandler(copper_client)


@app.event("app_mention")
def handle_mention(event, say, client):
    """
    Handle when the bot is mentioned in a channel.

    Args:
        event: Slack event data
        say: Function to send messages
        client: Slack client
    """
    try:
        user = event.get("user")
        text = event.get("text", "")

        # Remove bot mention from text
        bot_user_id = client.auth_test()["user_id"]
        text = text.replace(f"<@{bot_user_id}>", "").strip()

        if not text:
            say(
                text=f"Hi <@{user}>! Ask me anything about your Copper CRM data. "
                     "For example:\n"
                     "• 'Find contacts at Acme Corp'\n"
                     "• 'Show me opportunities over $50k'\n"
                     "• 'Search for companies in San Francisco'\n"
                     "• Or upload a CSV file with search criteria!"
            )
            return

        # Process the query
        logger.info(f"Processing query from {user}: {text}")
        say(text=f"Searching Copper CRM... :mag:")

        # Parse query
        parsed = query_processor.parse_query(text)
        entity_type = parsed["entity_type"]
        criteria = parsed["search_criteria"]

        logger.info(f"Entity: {entity_type}, Criteria: {criteria}")

        # Query Copper
        results = []
        if entity_type == "people":
            results = copper_client.search_people(criteria)
        elif entity_type == "companies":
            results = copper_client.search_companies(criteria)
        elif entity_type == "opportunities":
            results = copper_client.search_opportunities(criteria)
        elif entity_type == "leads":
            results = copper_client.search_leads(criteria)

        # Format and send results
        formatted_results = query_processor.format_results(results, entity_type)

        response_text = f"*Query*: {text}\n*Found*: {len(results)} {entity_type}\n\n{formatted_results}"

        say(text=response_text)

    except Exception as e:
        logger.error(f"Error handling mention: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.event("message")
def handle_message(event, say, client):
    """
    Handle direct messages to the bot.

    Args:
        event: Slack event data
        say: Function to send messages
        client: Slack client
    """
    # Only respond to DMs (channel_type = 'im')
    if event.get("channel_type") != "im":
        return

    # Ignore bot messages
    if event.get("subtype") == "bot_message":
        return

    try:
        user = event.get("user")
        text = event.get("text", "").strip()

        if not text:
            return

        # Check for help commands
        if text.lower() in ["help", "?", "commands"]:
            say(
                text="*Copper CRM Bot - Help*\n\n"
                     "*Natural Language Queries:*\n"
                     "Just ask me in plain English! Examples:\n"
                     "• 'Find contacts named John Smith'\n"
                     "• 'Show me companies in New York'\n"
                     "• 'List opportunities over $100,000'\n"
                     "• 'Search for leads from Acme Corp'\n\n"
                     "*CSV Upload:*\n"
                     "Upload a CSV file with search criteria. Supported columns:\n"
                     "• type/entity_type: people, companies, opportunities, leads\n"
                     "• name: Person or company name\n"
                     "• email: Email address\n"
                     "• phone: Phone number\n"
                     "• city, state, country: Location info\n"
                     "• tags: Comma-separated tags\n"
                     "• min_value: Minimum opportunity value\n\n"
                     "Need more help? Contact your admin!"
            )
            return

        # Process the query
        logger.info(f"Processing DM query from {user}: {text}")
        say(text="Searching Copper CRM... :mag:")

        # Parse query
        parsed = query_processor.parse_query(text)
        entity_type = parsed["entity_type"]
        criteria = parsed["search_criteria"]

        logger.info(f"Entity: {entity_type}, Criteria: {criteria}")

        # Query Copper
        results = []
        if entity_type == "people":
            results = copper_client.search_people(criteria)
        elif entity_type == "companies":
            results = copper_client.search_companies(criteria)
        elif entity_type == "opportunities":
            results = copper_client.search_opportunities(criteria)
        elif entity_type == "leads":
            results = copper_client.search_leads(criteria)

        # Format and send results
        formatted_results = query_processor.format_results(results, entity_type)

        response_text = f"*Query*: {text}\n*Found*: {len(results)} {entity_type}\n\n{formatted_results}"

        say(text=response_text)

    except Exception as e:
        logger.error(f"Error handling message: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


@app.event("file_shared")
def handle_file_upload(event, say, client):
    """
    Handle CSV file uploads.

    Args:
        event: Slack event data
        say: Function to send messages
        client: Slack client
    """
    try:
        file_id = event.get("file_id")
        user_id = event.get("user_id")

        # Get file info
        file_info = client.files_info(file=file_id)
        file_data = file_info["file"]

        # Check if it's a CSV file
        if not file_data["name"].endswith(".csv"):
            say(
                text=f"<@{user_id}> Please upload a CSV file. "
                     f"Received: {file_data['name']}"
            )
            return

        logger.info(f"Processing CSV upload from {user_id}: {file_data['name']}")
        say(text="Processing your CSV file... :page_facing_up:")

        # Download file
        file_content = csv_handler.download_file(
            file_data["url_private"],
            Config.SLACK_BOT_TOKEN
        )

        # Parse CSV
        rows = csv_handler.parse_csv(file_content)

        if not rows:
            say(text="The CSV file appears to be empty.")
            return

        # Process queries
        results = csv_handler.process_csv_queries(rows)

        # Format and send results
        formatted_results = csv_handler.format_csv_results(results)
        say(text=formatted_results)

    except Exception as e:
        logger.error(f"Error handling file upload: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error processing your file: {str(e)}")


@app.command("/copper")
def handle_copper_command(ack, command, say):
    """
    Handle /copper slash command.

    Args:
        ack: Acknowledge function
        command: Command data
        say: Function to send messages
    """
    ack()

    try:
        text = command.get("text", "").strip()
        user = command.get("user_id")

        if not text:
            say(
                text=f"<@{user}> Please provide a query. Example: `/copper Find contacts at Acme Corp`"
            )
            return

        # Process the query
        logger.info(f"Processing /copper command from {user}: {text}")
        say(text="Searching Copper CRM... :mag:")

        # Parse query
        parsed = query_processor.parse_query(text)
        entity_type = parsed["entity_type"]
        criteria = parsed["search_criteria"]

        logger.info(f"Entity: {entity_type}, Criteria: {criteria}")

        # Query Copper
        results = []
        if entity_type == "people":
            results = copper_client.search_people(criteria)
        elif entity_type == "companies":
            results = copper_client.search_companies(criteria)
        elif entity_type == "opportunities":
            results = copper_client.search_opportunities(criteria)
        elif entity_type == "leads":
            results = copper_client.search_leads(criteria)

        # Format and send results
        formatted_results = query_processor.format_results(results, entity_type)

        response_text = f"*Query*: {text}\n*Found*: {len(results)} {entity_type}\n\n{formatted_results}"

        say(text=response_text)

    except Exception as e:
        logger.error(f"Error handling /copper command: {str(e)}", exc_info=True)
        say(text=f"Sorry, I encountered an error: {str(e)}")


def main():
    """Start the Slack bot."""
    logger.info("Starting Copper CRM Slack Bot...")

    try:
        # Start the app using Socket Mode
        handler = SocketModeHandler(app, Config.SLACK_APP_TOKEN)
        logger.info("Bot is running in Socket Mode!")
        handler.start()

    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
