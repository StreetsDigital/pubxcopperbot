"""Natural language query processor for Copper CRM."""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

from config import Config

logger: logging.Logger = logging.getLogger(__name__)

# Type aliases for common patterns
JsonDict = Dict[str, Any]
SearchCriteria = Dict[str, Any]
ParsedQuery = Dict[str, Any]


class QueryProcessor:
    """Process natural language queries and convert them to Copper API calls."""

    claude_client: Optional[Anthropic]

    def __init__(self) -> None:
        """Initialize the query processor."""
        self.claude_client = None
        if Config.ANTHROPIC_API_KEY:
            self.claude_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    def parse_query(self, query: str) -> ParsedQuery:
        """
        Parse a natural language query into structured search criteria.

        Args:
            query: Natural language query from user

        Returns:
            Dictionary with entity_type and search_criteria
        """
        query_lower: str = query.lower()

        # Determine entity type
        entity_type: str = self._determine_entity_type(query_lower)

        # Use Claude if available for better parsing
        if self.claude_client:
            return self._parse_with_claude(query, entity_type)

        # Fallback to basic parsing
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

    def _parse_with_claude(self, query: str, entity_type: str) -> ParsedQuery:
        """
        Use Claude to parse the query into structured criteria.

        Args:
            query: Natural language query
            entity_type: Determined entity type

        Returns:
            Structured query data
        """
        try:
            prompt: str = f"""Convert this natural language query into Copper CRM search criteria.

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

            # claude_client is guaranteed to be non-None here (checked by caller)
            assert self.claude_client is not None
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
            first_block = message.content[0]
            if not hasattr(first_block, 'text'):
                raise ValueError("Unexpected response format from Claude")
            response_text: str = first_block.text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            criteria: SearchCriteria = json.loads(response_text)

            return {
                "entity_type": entity_type,
                "search_criteria": criteria,
                "original_query": query
            }

        except (json.JSONDecodeError, IndexError, AssertionError, ValueError) as e:
            logger.error(f"Claude parsing failed: {str(e)}")
            return self._parse_basic(query, entity_type)

    def _parse_basic(self, query: str, entity_type: str) -> ParsedQuery:
        """
        Basic fallback parsing without Claude.

        Args:
            query: Natural language query
            entity_type: Determined entity type

        Returns:
            Structured query data
        """
        criteria: SearchCriteria = {}

        # Extract email addresses
        email_pattern: str = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails: List[str] = re.findall(email_pattern, query)
        if emails:
            criteria['emails'] = emails

        # Extract phone numbers (basic pattern)
        phone_pattern: str = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        phones: List[str] = re.findall(phone_pattern, query)
        if phones:
            criteria['phone_numbers'] = phones

        # Extract quoted names or capitalize words (potential names)
        quoted: List[str] = re.findall(r'"([^"]+)"', query)
        if quoted:
            criteria['name'] = quoted[0]
        else:
            # Try to extract capitalized words as potential names
            words: List[str] = query.split()
            capitalized: List[str] = [
                w for w in words if w and w[0].isupper() and len(w) > 2
            ]
            if capitalized and entity_type in ['people', 'companies']:
                criteria['name'] = ' '.join(capitalized[:3])  # Take up to 3 words

        # Extract city names (words after "in", "from", "at")
        location_pattern: str = r'(?:in|from|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        locations: List[str] = re.findall(location_pattern, query)
        if locations:
            criteria['city'] = locations[0]

        return {
            "entity_type": entity_type,
            "search_criteria": criteria,
            "original_query": query
        }

    def format_results(self, results: List[JsonDict], entity_type: str) -> str:
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

        total_count: int = len(results)
        truncated_msg: str = ""
        if total_count > 20:
            results = results[:20]
            truncated_msg = f"\n\n_Showing first 20 of {total_count} results_"

        formatted: List[str] = []

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

    def _format_person(self, person: JsonDict) -> str:
        """Format a person record."""
        name: str = person.get('name', 'Unknown')
        emails_list: List[JsonDict] = person.get('emails', [])
        email: str = (
            emails_list[0].get('email', 'No email')
            if emails_list else 'No email'
        )
        phones_list: List[JsonDict] = person.get('phone_numbers', [])
        phone: str = (
            phones_list[0].get('number', 'No phone')
            if phones_list else 'No phone'
        )
        company: str = person.get('company_name', 'No company')

        return f"*{name}*\n📧 {email}\n📱 {phone}\n🏢 {company}"

    def _format_company(self, company: JsonDict) -> str:
        """Format a company record."""
        name: str = company.get('name', 'Unknown')
        city: str = company.get('city', 'Unknown')
        state: str = company.get('state', '')
        phones_list: List[JsonDict] = company.get('phone_numbers', [])
        phone: str = (
            phones_list[0].get('number', 'No phone')
            if phones_list else 'No phone'
        )

        location: str = f"{city}, {state}" if state else city
        return f"*{name}*\n📍 {location}\n📱 {phone}"

    def _format_opportunity(self, opp: JsonDict) -> str:
        """Format an opportunity record."""
        name: str = opp.get('name', 'Unknown')
        value: float = opp.get('monetary_value', 0) or 0
        status: str = opp.get('status', 'Unknown')
        company: str = opp.get('company_name', 'No company')

        return f"*{name}*\n💰 ${value:,.2f}\n📊 Status: {status}\n🏢 {company}"

    def _format_lead(self, lead: JsonDict) -> str:
        """Format a lead record."""
        name: str = lead.get('name', 'Unknown')
        email_obj: Optional[JsonDict] = lead.get('email')
        email: str = (
            email_obj.get('email', 'No email')
            if email_obj else 'No email'
        )
        company: str = lead.get('company_name', 'No company')
        status: str = lead.get('status', 'Unknown')

        return f"*{name}*\n📧 {email}\n🏢 {company}\n📊 Status: {status}"
