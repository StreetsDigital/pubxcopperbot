"""Copper CRM API Client."""

import requests
import logging
from typing import Dict, List, Optional, Any
from config import Config

logger = logging.getLogger(__name__)


class CopperClient:
    """Client for interacting with Copper CRM API."""

    def __init__(self):
        """Initialize the Copper API client."""
        self.base_url = Config.COPPER_BASE_URL
        self.headers = {
            'X-PW-AccessToken': Config.COPPER_API_KEY,
            'X-PW-Application': 'developer_api',
            'X-PW-UserEmail': Config.COPPER_USER_EMAIL,
            'Content-Type': 'application/json'
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Dict:
        """
        Make a request to the Copper API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request payload

        Returns:
            API response as dictionary
        """
        url = f"{self.base_url}/{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=30
            )

            # Handle rate limiting
            if response.status_code == 429:
                logger.warning("Rate limit exceeded")
                return {
                    "error": "Rate limit exceeded. Please try again in a moment.",
                    "status_code": 429
                }

            response.raise_for_status()
            return response.json() if response.content else {}

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            return {
                "error": f"API request failed: {str(e)}",
                "status_code": getattr(e.response, 'status_code', 500) if hasattr(e, 'response') else 500
            }

    def search_people(self, criteria: Dict) -> List[Dict]:
        """
        Search for people in Copper.

        Args:
            criteria: Search criteria (name, email, etc.)

        Returns:
            List of matching people
        """
        result = self._make_request("POST", "people/search", criteria)
        if isinstance(result, dict) and "error" in result:
            return []
        return result if isinstance(result, list) else []

    def search_companies(self, criteria: Dict) -> List[Dict]:
        """
        Search for companies in Copper.

        Args:
            criteria: Search criteria (name, etc.)

        Returns:
            List of matching companies
        """
        result = self._make_request("POST", "companies/search", criteria)
        if isinstance(result, dict) and "error" in result:
            return []
        return result if isinstance(result, list) else []

    def search_opportunities(self, criteria: Dict) -> List[Dict]:
        """
        Search for opportunities in Copper.

        Args:
            criteria: Search criteria (name, status, etc.)

        Returns:
            List of matching opportunities
        """
        result = self._make_request("POST", "opportunities/search", criteria)
        if isinstance(result, dict) and "error" in result:
            return []
        return result if isinstance(result, list) else []

    def search_leads(self, criteria: Dict) -> List[Dict]:
        """
        Search for leads in Copper.

        Args:
            criteria: Search criteria

        Returns:
            List of matching leads
        """
        result = self._make_request("POST", "leads/search", criteria)
        if isinstance(result, dict) and "error" in result:
            return []
        return result if isinstance(result, list) else []

    def get_person(self, person_id: int) -> Optional[Dict]:
        """
        Get a specific person by ID.

        Args:
            person_id: Person ID

        Returns:
            Person data or None
        """
        result = self._make_request("GET", f"people/{person_id}")
        if isinstance(result, dict) and "error" in result:
            return None
        return result

    def get_company(self, company_id: int) -> Optional[Dict]:
        """
        Get a specific company by ID.

        Args:
            company_id: Company ID

        Returns:
            Company data or None
        """
        result = self._make_request("GET", f"companies/{company_id}")
        if isinstance(result, dict) and "error" in result:
            return None
        return result

    def get_opportunity(self, opportunity_id: int) -> Optional[Dict]:
        """
        Get a specific opportunity by ID.

        Args:
            opportunity_id: Opportunity ID

        Returns:
            Opportunity data or None
        """
        result = self._make_request("GET", f"opportunities/{opportunity_id}")
        if isinstance(result, dict) and "error" in result:
            return None
        return result

    def update_person(self, person_id: int, updates: Dict) -> Optional[Dict]:
        """
        Update a person/contact in Copper.

        Args:
            person_id: Person ID
            updates: Dictionary of fields to update

        Returns:
            Updated person data or None
        """
        result = self._make_request("PUT", f"people/{person_id}", updates)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to update person {person_id}: {result.get('error')}")
            return None
        return result

    def update_company(self, company_id: int, updates: Dict) -> Optional[Dict]:
        """
        Update a company in Copper.

        Args:
            company_id: Company ID
            updates: Dictionary of fields to update

        Returns:
            Updated company data or None
        """
        result = self._make_request("PUT", f"companies/{company_id}", updates)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to update company {company_id}: {result.get('error')}")
            return None
        return result

    def update_opportunity(self, opportunity_id: int, updates: Dict) -> Optional[Dict]:
        """
        Update an opportunity in Copper.

        Args:
            opportunity_id: Opportunity ID
            updates: Dictionary of fields to update

        Returns:
            Updated opportunity data or None
        """
        result = self._make_request("PUT", f"opportunities/{opportunity_id}", updates)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to update opportunity {opportunity_id}: {result.get('error')}")
            return None
        return result

    def update_lead(self, lead_id: int, updates: Dict) -> Optional[Dict]:
        """
        Update a lead in Copper.

        Args:
            lead_id: Lead ID
            updates: Dictionary of fields to update

        Returns:
            Updated lead data or None
        """
        result = self._make_request("PUT", f"leads/{lead_id}", updates)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to update lead {lead_id}: {result.get('error')}")
            return None
        return result
