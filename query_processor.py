"""Natural language query processor for Copper CRM."""

import re
import logging
import json
from typing import Dict, List, Optional, Any
from anthropic import Anthropic
from config import Config

logger = logging.getLogger(__name__)


class QueryProcessor:
    """Process natural language queries and convert them to Copper API calls."""

    def __init__(self):
        """Initialize the query processor."""
        self.claude_client = None
        if Config.ANTHROPIC_API_KEY:
            self.claude_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    def parse_query(self, query: str) -> Dict[str, Any]:
        """
        Parse a natural language query into structured search criteria.

        Args:
            query: Natural language query from user

        Returns:
            Dictionary with entity_type and search_criteria
        """
        logger.info("=" * 60)
        logger.info("🔍 STEP 1: PARSING USER QUERY")
        logger.info(f"User query: '{query}'")

        query_lower = query.lower()

        # Determine entity type
        entity_type = self._determine_entity_type(query_lower)
        logger.info(f"📋 Determined entity type: {entity_type}")

        # Use Claude if available for better parsing
        if self.claude_client:
            logger.info("🤖 Using Claude AI for advanced query parsing...")
            return self._parse_with_claude(query, entity_type)

        # Fallback to basic parsing
        logger.info("⚡ Using basic regex parsing (Claude not available)")
        return self._parse_basic(query, entity_type)

    def _determine_entity_type(self, query: str) -> str:
        """
        Determine what type of entity the user is querying.

        Args:
            query: Query text

        Returns:
            Entity type (people, companies, opportunities, leads, tasks, projects, activities)
        """
        # Check for activities/communications keywords FIRST (most specific)
        if any(keyword in query for keyword in [
            'email', 'emails', 'call', 'calls', 'meeting', 'meetings',
            'communication', 'communications', 'comms', 'activity', 'activities',
            'latest', 'recent', 'last', 'conversation', 'conversations',
            'interaction', 'interactions', 'touchpoint', 'touchpoints'
        ]):
            return 'activities'

        # Then check for other specific entity types
        if any(keyword in query for keyword in ['task', 'tasks', 'todo', 'todos', 'to-do']):
            return 'tasks'
        elif any(keyword in query for keyword in ['project', 'projects']):
            return 'projects'
        elif any(keyword in query for keyword in ['opportunity', 'opportunities', 'deal', 'deals', 'sale', 'sales', 'pipeline']):
            return 'opportunities'
        elif any(keyword in query for keyword in ['lead', 'leads', 'prospect', 'prospects']):
            return 'leads'
        elif any(keyword in query for keyword in ['company', 'companies', 'organization', 'business', 'businesses']):
            return 'companies'
        elif any(keyword in query for keyword in ['person', 'people', 'contact', 'contacts', 'who', 'anyone', 'someone']):
            return 'people'
        else:
            # If query mentions "at/from [Company]", likely asking about people
            if any(word in query for word in [' at ', ' from ', ' with ']):
                return 'people'
            # Default to activities for generic "tell me about" queries
            return 'activities'

    def _parse_with_claude(self, query: str, entity_type: str) -> Dict[str, Any]:
        """
        Use Claude to parse the query into structured criteria.

        Args:
            query: Natural language query
            entity_type: Determined entity type

        Returns:
            Structured query data
        """
        try:
            prompt = f"""Convert this natural language query into Copper CRM search criteria.

Entity type: {entity_type}
Query: "{query}"

Extract the following information based on the entity type and return ONLY a JSON object:

For people/contacts:
- name: person name or company name (if asking "who at Company X")
- emails: email addresses (as array)
- phone_numbers: phone numbers (as array)

For companies:
- name: company name

For opportunities/deals:
- name: opportunity name
- minimum_monetary_value: for amounts (as number)
- status: for pipeline stage

For activities/communications:
- company_name: the company to search activities for
- activity_type: type of communication (email, call, meeting, or leave empty for all)
- time_frame: "recent", "latest", "last_week", etc.

For tasks/projects:
- name: task or project name
- related_to: company or person name

General fields (any type):
- city, state, country: for location-based searches
- tags: for tags or keywords (as array)

Example outputs:
{{"name": "John Smith"}}
{{"name": "Acme Corp"}}
{{"company_name": "Venatus"}}
{{"company_name": "Guardian", "time_frame": "latest"}}
{{"minimum_monetary_value": 50000}}

If the query is vague and needs clarification, include:
{{"clarify": true, "reason": "not enough specific details provided"}}

Return ONLY the JSON object, no other text."""

            message = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=1024,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Extract JSON from Claude's response
            response_text = message.content[0].text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            criteria = json.loads(response_text)

            logger.info(f"✅ Claude extracted criteria: {json.dumps(criteria, indent=2)}")

            result = {
                "entity_type": entity_type,
                "search_criteria": criteria,
                "original_query": query
            }
            logger.info(f"📦 Final parsed query structure: {json.dumps(result, indent=2)}")
            logger.info("=" * 60)
            return result

        except Exception as e:
            logger.error(f"❌ Claude parsing failed: {str(e)}")
            logger.info("⚡ Falling back to basic parsing...")
            return self._parse_basic(query, entity_type)

    def _parse_basic(self, query: str, entity_type: str) -> Dict[str, Any]:
        """
        Basic fallback parsing without Claude.

        Args:
            query: Natural language query
            entity_type: Determined entity type

        Returns:
            Structured query data
        """
        criteria = {}

        # For activities, extract company name differently
        if entity_type == 'activities':
            # Patterns like "latest with X", "comms from X", "about X"
            activity_patterns = [
                r'(?:with|from|about|for|regarding|at)\s+(?:the\s+)?([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*?)(?:\s+please|\s+thanks|,|\?|$)',
                r'(?:latest|recent)\s+(?:comms|communications|activity|activities|emails|calls|meetings)?\s*(?:with|from|for|at)?\s+(?:the\s+)?([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*?)(?:\s+please|\s+thanks|,|\?|$)',
                # "tell me about X" or "what about X"
                r'(?:tell me about|what about|about)\s+(?:the\s+)?([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*?)(?:\s+please|\s+thanks|,|\?|$)',
            ]

            for pattern in activity_patterns:
                matches = re.findall(pattern, query, re.IGNORECASE)
                if matches:
                    company_name = matches[0].strip('?,. ')
                    # Remove polite words
                    for word in ['please', 'thanks', 'thank you']:
                        if company_name.lower().endswith(word):
                            company_name = company_name[:-len(word)].strip()
                    company_name = company_name.title()
                    criteria['company_name'] = company_name
                    logger.info(f"Extracted company name for activities: {criteria['company_name']}")
                    break

            # Detect activity type
            if 'email' in query.lower():
                criteria['activity_type'] = 'email'
            elif 'call' in query.lower():
                criteria['activity_type'] = 'call'
            elif 'meeting' in query.lower():
                criteria['activity_type'] = 'meeting'

            return {
                "entity_type": entity_type,
                "search_criteria": criteria,
                "original_query": query
            }

        # Extract email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, query)
        if emails:
            criteria['emails'] = emails

        # Extract phone numbers (basic pattern)
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        phones = re.findall(phone_pattern, query)
        if phones:
            criteria['phone_numbers'] = phones

        # Extract quoted names or capitalize words (potential names)
        quoted = re.findall(r'"([^"]+)"', query)
        if quoted:
            criteria['name'] = quoted[0]
        else:
            # For people queries, look for names after "at", "from", "with" (likely company names)
            if entity_type == 'people':
                # Pattern to match company names, including "the Guardian", "NY Times", etc.
                # More flexible pattern that handles various phrasings
                company_keywords = r'(?:at|from|with|over at|someone at|anyone at|contacts at|people at)'
                # Match "the X", "The X", or just "X" after keywords, excluding polite words
                company_pattern = company_keywords + r'\s+(?:the\s+)?([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*?)(?:\s+please|\s+thanks|,|\?|$|;|\s+and\s+|\s+or\s+)'

                companies = re.findall(company_pattern, query, re.IGNORECASE)
                if companies:
                    # Clean up the company name - remove trailing polite words
                    company_name = companies[0].strip('?,. ')
                    # Remove common polite words that might have been captured
                    polite_words = ['please', 'thanks', 'thank you']
                    for word in polite_words:
                        if company_name.lower().endswith(word):
                            company_name = company_name[:-len(word)].strip()
                    # Capitalize properly
                    company_name = company_name.title()
                    criteria['name'] = company_name  # Use 'name' field to search companies
                    logger.info(f"Extracted company name from query: {criteria['name']}")

            # Try to extract capitalized words as potential names
            if 'company_name' not in criteria:
                words = query.split()
                # Remove common words and get capitalized ones
                capitalized = [w.strip('?,.:;!') for w in words if w and w[0].isupper() and len(w) > 2
                             and w.lower() not in ['who', 'what', 'when', 'where', 'why', 'how']]
                if capitalized:
                    if entity_type == 'people':
                        # First capitalized word might be company name
                        criteria['company_name'] = capitalized[0]
                    else:
                        criteria['name'] = ' '.join(capitalized[:3])  # Take up to 3 words

        # Extract city names (words after "in", "from")
        location_pattern = r'(?:in|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        locations = re.findall(location_pattern, query)
        if locations:
            criteria['city'] = locations[0]

        return {
            "entity_type": entity_type,
            "search_criteria": criteria,
            "original_query": query
        }

    def format_results(self, results: List[Dict], entity_type: str) -> str:
        """
        Format search results for Slack display.

        Args:
            results: Search results from Copper API
            entity_type: Type of entity

        Returns:
            Formatted string for Slack
        """
        if not results:
            return "No results found."

        if len(results) > 20:
            results = results[:20]
            truncated_msg = f"\n\n_Showing first 20 of {len(results)} results_"
        else:
            truncated_msg = ""

        formatted = []

        for item in results:
            if entity_type == 'people':
                formatted.append(self._format_person(item))
            elif entity_type == 'companies':
                formatted.append(self._format_company(item))
            elif entity_type == 'opportunities':
                formatted.append(self._format_opportunity(item))
            elif entity_type == 'leads':
                formatted.append(self._format_lead(item))
            elif entity_type == 'activities':
                formatted.append(self._format_activity(item))
            elif entity_type == 'tasks':
                formatted.append(self._format_task(item))
            elif entity_type == 'projects':
                formatted.append(self._format_project(item))

        return "\n\n".join(formatted) + truncated_msg

    def _format_person(self, person: Dict) -> str:
        """Format a person record."""
        name = person.get('name', 'Unknown')
        email = person.get('emails', [{}])[0].get('email', 'No email') if person.get('emails') else 'No email'
        phone = person.get('phone_numbers', [{}])[0].get('number', 'No phone') if person.get('phone_numbers') else 'No phone'
        company = person.get('company_name', 'No company')

        return f"*{name}*\n📧 {email}\n📱 {phone}\n🏢 {company}"

    def _format_company(self, company: Dict) -> str:
        """Format a company record."""
        name = company.get('name', 'Unknown')
        city = company.get('city', 'Unknown')
        state = company.get('state', '')
        phone = company.get('phone_numbers', [{}])[0].get('number', 'No phone') if company.get('phone_numbers') else 'No phone'

        location = f"{city}, {state}" if state else city
        return f"*{name}*\n📍 {location}\n📱 {phone}"

    def _format_opportunity(self, opp: Dict) -> str:
        """Format an opportunity record."""
        name = opp.get('name', 'Unknown')
        value = opp.get('monetary_value', 0)
        status = opp.get('status', 'Unknown')
        company = opp.get('company_name', 'No company')

        return f"*{name}*\n💰 ${value:,.2f}\n📊 Status: {status}\n🏢 {company}"

    def _format_lead(self, lead: Dict) -> str:
        """Format a lead record."""
        name = lead.get('name', 'Unknown')
        email = lead.get('email', {}).get('email', 'No email') if lead.get('email') else 'No email'
        company = lead.get('company_name', 'No company')
        status = lead.get('status', 'Unknown')

        return f"*{name}*\n📧 {email}\n🏢 {company}\n📊 Status: {status}"

    def _format_activity(self, activity: Dict) -> str:
        """Format an activity record."""
        import datetime

        # Activity type mapping
        activity_types = {
            0: '📧 Email',
            1: '👤 User Activity',
            2: '📝 Note',
            3: '📞 Call',
            4: '🤝 Meeting',
            5: '📄 Document',
        }

        activity_type_id = activity.get('type', {}).get('id', 0) if isinstance(activity.get('type'), dict) else 0
        activity_icon = activity_types.get(activity_type_id, '📌 Activity')

        # Get details
        details = activity.get('details') or 'No details'
        company_name = activity.get('_company_name', 'Unknown Company')

        # Format date
        activity_date = activity.get('activity_date')
        if activity_date:
            try:
                # Convert Unix timestamp to readable date
                dt = datetime.datetime.fromtimestamp(activity_date)
                date_str = dt.strftime('%b %d, %Y at %I:%M %p')
            except:
                date_str = 'Unknown date'
        else:
            date_str = 'Unknown date'

        # Truncate details if too long
        if details and len(details) > 200:
            details = details[:200] + '...'

        return f"{activity_icon}\n🏢 {company_name}\n📅 {date_str}\n{details}"

    def _format_task(self, task: Dict) -> str:
        """Format a task record."""
        name = task.get('name', 'Untitled Task')
        status = '✅ Complete' if task.get('completed') else '⏳ Pending'
        assignee = task.get('assignee', {}).get('name', 'Unassigned') if task.get('assignee') else 'Unassigned'
        due_date = task.get('due_date', 'No due date')

        return f"*{name}*\n{status}\n👤 Assigned to: {assignee}\n📅 Due: {due_date}"

    def _format_project(self, project: Dict) -> str:
        """Format a project record."""
        name = project.get('name', 'Untitled Project')
        status = project.get('status', 'Unknown')
        assignee = project.get('assignee', {}).get('name', 'Unassigned') if project.get('assignee') else 'Unassigned'

        return f"*{name}*\n📊 Status: {status}\n👤 Owner: {assignee}"
