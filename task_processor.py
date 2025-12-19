"""Natural language task processor for Copper CRM."""

import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU
from anthropic import Anthropic
from config import Config

logger = logging.getLogger(__name__)

# Day name to dateutil weekday mapping
WEEKDAY_MAP = {
    'monday': MO, 'mon': MO,
    'tuesday': TU, 'tue': TU, 'tues': TU,
    'wednesday': WE, 'wed': WE,
    'thursday': TH, 'thu': TH, 'thur': TH, 'thurs': TH,
    'friday': FR, 'fri': FR,
    'saturday': SA, 'sat': SA,
    'sunday': SU, 'sun': SU,
}


class TaskProcessor:
    """Process natural language task requests."""

    def __init__(self, copper_client=None):
        """Initialize the task processor.

        Args:
            copper_client: CopperClient instance for entity lookups.
        """
        self.copper_client = copper_client
        self.claude_client = None
        if Config.ANTHROPIC_API_KEY:
            self.claude_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    def is_task_request(self, text: str) -> bool:
        """Check if the text is a task creation request.

        Args:
            text: User message text.

        Returns:
            True if this looks like a task request.
        """
        text_lower = text.lower()

        # Task-like patterns
        task_patterns = [
            r'\bremind\s+(me|us)\b',
            r'\bfollow\s*up\b',
            r'\bschedule\b',
            r'\bset\s+(a\s+)?task\b',
            r'\bcreate\s+(a\s+)?task\b',
            r'\badd\s+(a\s+)?task\b',
            r'\btask\s*:\s*',
            r'\bto\s*-?\s*do\b',
            r'\bneed\s+to\b.*\bby\b',
            r'\bdon\'?t\s+forget\b',
            r'\bmake\s+sure\s+to\b',
            r'\bassign\s+(me|@)',
        ]

        for pattern in task_patterns:
            if re.search(pattern, text_lower):
                return True

        return False

    def parse_task(self, text: str, requester_slack_id: str) -> Dict[str, Any]:
        """Parse a natural language task request.

        Args:
            text: The task request text.
            requester_slack_id: Slack user ID of the requester.

        Returns:
            Dictionary with parsed task details.
        """
        if self.claude_client:
            return self._parse_with_claude(text, requester_slack_id)
        return self._parse_basic(text, requester_slack_id)

    def _parse_with_claude(self, text: str, requester_slack_id: str) -> Dict[str, Any]:
        """Use Claude to parse task details.

        Args:
            text: The task request text.
            requester_slack_id: Slack user ID of the requester.

        Returns:
            Parsed task details.
        """
        try:
            today = datetime.now()
            prompt = f"""Parse this task request and extract the details.

Task request: "{text}"
Today's date: {today.strftime('%A, %B %d, %Y')}

Extract the following and return ONLY a JSON object:
- task_description: What needs to be done (clean, actionable description)
- assignee: Who should do it ("self" if "me/I", or the @mentioned user, or null)
- due_date: When it's due (ISO format YYYY-MM-DD, or null if not specified)
- due_time: Time if specified (HH:MM 24hr format, or null)
- related_entity_name: Company, person, or opportunity name mentioned (or null)
- related_entity_type: "company", "person", "opportunity", or null
- priority: "high", "normal", or "low" (infer from urgency words)

Examples:
Input: "remind me to follow up with CNN next Monday"
Output: {{"task_description": "Follow up with CNN", "assignee": "self", "due_date": "2024-01-15", "due_time": null, "related_entity_name": "CNN", "related_entity_type": "company", "priority": "normal"}}

Input: "urgent: call John at Acme Corp tomorrow at 2pm"
Output: {{"task_description": "Call John at Acme Corp", "assignee": "self", "due_date": "2024-01-10", "due_time": "14:00", "related_entity_name": "Acme Corp", "related_entity_type": "company", "priority": "high"}}

Input: "assign @sarah to send proposal to Netflix by Friday"
Output: {{"task_description": "Send proposal to Netflix", "assignee": "@sarah", "due_date": "2024-01-12", "due_time": null, "related_entity_name": "Netflix", "related_entity_type": "company", "priority": "normal"}}

Return ONLY the JSON object, no other text."""

            message = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()

            # Clean up markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            import json
            parsed = json.loads(response_text)

            # Convert assignee
            if parsed.get('assignee') == 'self':
                parsed['assignee_slack_id'] = requester_slack_id
            elif parsed.get('assignee') and parsed['assignee'].startswith('@'):
                # Extract Slack user ID from mention
                parsed['assignee_slack_id'] = self._extract_slack_id(parsed['assignee'])
            else:
                parsed['assignee_slack_id'] = requester_slack_id

            # Ensure we have a task description
            if not parsed.get('task_description'):
                parsed['task_description'] = text

            parsed['original_text'] = text
            parsed['requester_slack_id'] = requester_slack_id

            return parsed

        except Exception as e:
            logger.error(f"Claude task parsing failed: {e}")
            return self._parse_basic(text, requester_slack_id)

    def _parse_basic(self, text: str, requester_slack_id: str) -> Dict[str, Any]:
        """Basic fallback parsing without Claude.

        Args:
            text: The task request text.
            requester_slack_id: Slack user ID of the requester.

        Returns:
            Parsed task details.
        """
        result = {
            'task_description': text,
            'assignee_slack_id': requester_slack_id,
            'due_date': None,
            'due_time': None,
            'related_entity_name': None,
            'related_entity_type': None,
            'priority': 'normal',
            'original_text': text,
            'requester_slack_id': requester_slack_id,
        }

        text_lower = text.lower()

        # Extract due date
        due_date = self._parse_due_date(text_lower)
        if due_date:
            result['due_date'] = due_date.strftime('%Y-%m-%d')

        # Extract time
        time_match = re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text_lower)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            ampm = time_match.group(3)
            if ampm == 'pm' and hour < 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
            result['due_time'] = f"{hour:02d}:{minute:02d}"

        # Check for urgency
        if any(word in text_lower for word in ['urgent', 'asap', 'immediately', 'critical']):
            result['priority'] = 'high'

        # Extract mentioned Slack user
        slack_mention = re.search(r'<@([A-Z0-9]+)(?:\|[^>]+)?>', text)
        if slack_mention:
            result['assignee_slack_id'] = slack_mention.group(1)

        # Try to extract company/entity name (capitalized words after "with", "for", "to", "at")
        entity_match = re.search(
            r'(?:with|for|to|at|from)\s+([A-Z][A-Za-z0-9\s&]+?)(?:\s+(?:by|on|next|tomorrow|today|this)|$)',
            text
        )
        if entity_match:
            result['related_entity_name'] = entity_match.group(1).strip()
            result['related_entity_type'] = 'company'  # Default assumption

        # Clean up task description
        result['task_description'] = self._clean_task_description(text)

        return result

    def _parse_due_date(self, text: str) -> Optional[datetime]:
        """Parse due date from text.

        Args:
            text: Text to parse (lowercase).

        Returns:
            datetime object or None.
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Today/tomorrow
        if 'today' in text:
            return today
        if 'tomorrow' in text:
            return today + timedelta(days=1)

        # This week / next week
        if 'next week' in text:
            # Next Monday
            return today + relativedelta(weekday=MO(+1))
        if 'this week' in text:
            # This Friday
            return today + relativedelta(weekday=FR(0))
        if 'end of week' in text or 'eow' in text:
            return today + relativedelta(weekday=FR(0))
        if 'end of day' in text or 'eod' in text:
            return today

        # In X days/weeks
        in_days = re.search(r'in\s+(\d+)\s+days?', text)
        if in_days:
            return today + timedelta(days=int(in_days.group(1)))

        in_weeks = re.search(r'in\s+(\d+)\s+weeks?', text)
        if in_weeks:
            return today + timedelta(weeks=int(in_weeks.group(1)))

        # Specific day names
        for day_name, weekday in WEEKDAY_MAP.items():
            if day_name in text:
                # Check if "next" is before the day
                if re.search(rf'next\s+{day_name}', text):
                    return today + relativedelta(weekday=weekday(+1))
                else:
                    # This week's occurrence (or next if already passed)
                    return today + relativedelta(weekday=weekday(0))

        # Try dateutil parser for explicit dates
        date_patterns = [
            r'(?:by|on|due)\s+(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)',
            r'(?:by|on|due)\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?)',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return date_parser.parse(match.group(1), fuzzy=True)
                except Exception:
                    pass

        return None

    def _clean_task_description(self, text: str) -> str:
        """Clean up task description.

        Args:
            text: Original text.

        Returns:
            Cleaned task description.
        """
        # Remove common prefixes
        prefixes = [
            r'^remind\s+me\s+to\s+',
            r'^don\'t\s+forget\s+to\s+',
            r'^make\s+sure\s+to\s+',
            r'^task\s*:\s*',
            r'^create\s+(?:a\s+)?task\s+(?:to\s+)?',
            r'^add\s+(?:a\s+)?task\s+(?:to\s+)?',
            r'^set\s+(?:a\s+)?task\s+(?:to\s+)?',
            r'^need\s+to\s+',
        ]

        result = text
        for prefix in prefixes:
            result = re.sub(prefix, '', result, flags=re.IGNORECASE)

        # Remove date/time suffixes
        suffixes = [
            r'\s+by\s+(?:next\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday).*$',
            r'\s+by\s+tomorrow.*$',
            r'\s+by\s+today.*$',
            r'\s+by\s+end\s+of\s+(?:day|week).*$',
            r'\s+next\s+(?:week|monday|tuesday|wednesday|thursday|friday).*$',
            r'\s+on\s+\d{1,2}[/-]\d{1,2}.*$',
            r'\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?.*$',
        ]

        for suffix in suffixes:
            result = re.sub(suffix, '', result, flags=re.IGNORECASE)

        # Capitalize first letter
        result = result.strip()
        if result:
            result = result[0].upper() + result[1:]

        return result

    def _extract_slack_id(self, mention: str) -> Optional[str]:
        """Extract Slack user ID from mention string.

        Args:
            mention: Mention string like @username or <@U123|name>.

        Returns:
            Slack user ID or None.
        """
        # Format: <@U12345|username> or <@U12345>
        match = re.search(r'<@([A-Z0-9]+)', mention)
        if match:
            return match.group(1)
        return None

    def find_related_entity(
        self,
        entity_name: str,
        entity_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Find a related entity in Copper by name.

        Args:
            entity_name: Name to search for.
            entity_type: Type hint (company, person, opportunity).

        Returns:
            Entity data with id and type, or None.
        """
        if not self.copper_client or not entity_name:
            return None

        # Search in order of likelihood
        search_order = ['companies', 'opportunities', 'people']
        if entity_type == 'person':
            search_order = ['people', 'companies', 'opportunities']
        elif entity_type == 'opportunity':
            search_order = ['opportunities', 'companies', 'people']

        for search_type in search_order:
            try:
                if search_type == 'companies':
                    results = self.copper_client.search_companies({'name': entity_name})
                elif search_type == 'people':
                    results = self.copper_client.search_people({'name': entity_name})
                elif search_type == 'opportunities':
                    results = self.copper_client.search_opportunities({'name': entity_name})
                else:
                    continue

                if results:
                    # Return the best match
                    entity = results[0]
                    return {
                        'id': entity.get('id'),
                        'name': entity.get('name'),
                        'type': search_type.rstrip('s') if search_type != 'companies' else 'company',
                        'copper_type': search_type,
                    }
            except Exception as e:
                logger.error(f"Error searching {search_type}: {e}")

        return None

    def build_copper_task(
        self,
        parsed: Dict[str, Any],
        assignee_copper_id: Optional[int] = None,
        related_entity: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Build a Copper task payload from parsed data.

        Args:
            parsed: Parsed task data.
            assignee_copper_id: Copper user ID for assignee.
            related_entity: Related entity data from find_related_entity.

        Returns:
            Copper task creation payload.
        """
        task = {
            'name': parsed['task_description'],
        }

        # Set assignee
        if assignee_copper_id:
            task['assignee_id'] = assignee_copper_id

        # Set due date
        if parsed.get('due_date'):
            due_str = parsed['due_date']
            if parsed.get('due_time'):
                due_str += f" {parsed['due_time']}"
            else:
                due_str += " 17:00"  # Default to 5 PM

            try:
                due_dt = date_parser.parse(due_str)
                task['due_date'] = int(due_dt.timestamp())
            except Exception as e:
                logger.error(f"Error parsing due date: {e}")

        # Set priority (Copper uses: None, High)
        if parsed.get('priority') == 'high':
            task['priority'] = 'High'

        # Set related resource
        if related_entity:
            # Copper uses singular type names for related_resource
            copper_type_map = {
                'company': 'company',
                'person': 'person',
                'opportunity': 'opportunity',
                'lead': 'lead',
                'project': 'project',
            }
            task['related_resource'] = {
                'type': copper_type_map.get(related_entity['type'], related_entity['type']),
                'id': related_entity['id']
            }

        return task

    def format_task_confirmation(self, parsed: Dict, related_entity: Optional[Dict] = None) -> str:
        """Format a confirmation message for the task.

        Args:
            parsed: Parsed task data.
            related_entity: Related entity if found.

        Returns:
            Formatted confirmation string.
        """
        lines = [f"*Task:* {parsed['task_description']}"]

        if parsed.get('due_date'):
            due_str = parsed['due_date']
            if parsed.get('due_time'):
                due_str += f" at {parsed['due_time']}"
            lines.append(f"*Due:* {due_str}")

        if parsed.get('priority') == 'high':
            lines.append("*Priority:* High")

        if related_entity:
            lines.append(f"*Linked to:* {related_entity['name']} ({related_entity['type']})")
        elif parsed.get('related_entity_name'):
            lines.append(f"*Related to:* {parsed['related_entity_name']} (not found in CRM)")

        return '\n'.join(lines)
