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
            Entity type (people, companies, opportunities, leads, tasks, projects)
        """
        if any(keyword in query for keyword in ['task', 'tasks', 'todo', 'todos', 'to-do']):
            return 'tasks'
        elif any(keyword in query for keyword in ['project', 'projects']):
            return 'projects'
        elif any(keyword in query for keyword in ['person', 'people', 'contact', 'contacts']):
            return 'people'
        elif any(keyword in query for keyword in ['company', 'companies', 'organization', 'business']):
            return 'companies'
        elif any(keyword in query for keyword in ['opportunity', 'opportunities', 'deal', 'deals', 'sale', 'sales']):
            return 'opportunities'
        elif any(keyword in query for keyword in ['lead', 'leads', 'prospect', 'prospects']):
            return 'leads'
        else:
            # Default to people for general searches
            return 'people'

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

Extract the following information and return ONLY a JSON object:
- name: for person or company names
- emails: for email addresses (as array)
- phone_numbers: for phone numbers (as array)
- city: for city
- state: for state
- country: for country
- tags: for tags or keywords (as array)
- minimum_monetary_value: for opportunity amounts (if mentioned, as number)
- status: for status or stage information

Example outputs:
{{"name": "John Smith", "city": "San Francisco"}}
{{"name": "Acme Corp", "city": "New York", "state": "NY"}}
{{"minimum_monetary_value": 50000, "status": "active"}}

If no specific criteria is mentioned, return an empty object: {{}}

Return ONLY the JSON object, no other text."""

            message = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
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
        Basic fallback parsing without OpenAI.

        Args:
            query: Natural language query
            entity_type: Determined entity type

        Returns:
            Structured query data
        """
        criteria = {}

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
                company_pattern = r'(?:at|from|with|over at)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)'
                companies = re.findall(company_pattern, query)
                if companies:
                    criteria['company_name'] = companies[0].strip('?,.')
                    logger.info(f"Extracted company name from query: {criteria['company_name']}")

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
