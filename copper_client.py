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

        logger.info("=" * 60)
        logger.info("🔌 STEP 2: CALLING COPPER CRM API")
        logger.info(f"Method: {method}")
        logger.info(f"Endpoint: {endpoint}")
        logger.info(f"URL: {url}")
        logger.info(f"Payload: {data}")
        logger.info(f"Auth Email: {self.headers.get('X-PW-UserEmail', 'NOT SET')}")
        logger.info(f"API Key (first 10 chars): {self.headers.get('X-PW-AccessToken', 'NOT SET')[:10]}...")

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=30
            )

            logger.info(f"Response status code: {response.status_code}")

            # Handle rate limiting
            if response.status_code == 429:
                logger.warning("⚠️ Rate limit exceeded")
                return {
                    "error": "Rate limit exceeded. Please try again in a moment.",
                    "status_code": 429
                }

            response.raise_for_status()
            result = response.json() if response.content else {}

            if isinstance(result, list):
                logger.info(f"✅ API returned {len(result)} results")
            else:
                logger.info(f"✅ API returned: {result}")
            logger.info("=" * 60)

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ API request failed: {str(e)}")
            logger.info("=" * 60)
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

    # ============================================================================
    # CREATE METHODS
    # ============================================================================

    def create_person(self, data: Dict) -> Optional[Dict]:
        """
        Create a new person/contact in Copper.

        Args:
            data: Dictionary with person data
                Required: name
                Optional: emails, phone_numbers, address, company_id, etc.

        Returns:
            Created person data or None
        """
        result = self._make_request("POST", "people", data)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to create person: {result.get('error')}")
            return None
        return result

    def create_company(self, data: Dict) -> Optional[Dict]:
        """
        Create a new company in Copper.

        Args:
            data: Dictionary with company data
                Required: name
                Optional: address, phone_numbers, email_domain, etc.

        Returns:
            Created company data or None
        """
        result = self._make_request("POST", "companies", data)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to create company: {result.get('error')}")
            return None
        return result

    def create_opportunity(self, data: Dict) -> Optional[Dict]:
        """
        Create a new opportunity in Copper.

        Args:
            data: Dictionary with opportunity data
                Required: name
                Optional: primary_contact_id, company_id, monetary_value, etc.

        Returns:
            Created opportunity data or None
        """
        result = self._make_request("POST", "opportunities", data)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to create opportunity: {result.get('error')}")
            return None
        return result

    def create_lead(self, data: Dict) -> Optional[Dict]:
        """
        Create a new lead in Copper.

        Args:
            data: Dictionary with lead data
                Required: name
                Optional: email, phone_numbers, company_name, etc.

        Returns:
            Created lead data or None
        """
        result = self._make_request("POST", "leads", data)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to create lead: {result.get('error')}")
            return None
        return result

    def create_task(self, data: Dict) -> Optional[Dict]:
        """
        Create a new task in Copper.

        Args:
            data: Dictionary with task data
                Required: name, related_resource (type and id)
                Optional: due_date, priority, assignee_id, etc.

        Returns:
            Created task data or None
        """
        result = self._make_request("POST", "tasks", data)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to create task: {result.get('error')}")
            return None
        return result

    def create_project(self, data: Dict) -> Optional[Dict]:
        """
        Create a new project in Copper.

        Args:
            data: Dictionary with project data
                Required: name
                Optional: related_resource, assignee_id, status, etc.

        Returns:
            Created project data or None
        """
        result = self._make_request("POST", "projects", data)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to create project: {result.get('error')}")
            return None
        return result

    # ============================================================================
    # DELETE METHODS
    # ============================================================================

    def delete_person(self, person_id: int) -> bool:
        """
        Delete a person/contact from Copper.

        Args:
            person_id: Person ID

        Returns:
            True if successful, False otherwise
        """
        result = self._make_request("DELETE", f"people/{person_id}")
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to delete person {person_id}: {result.get('error')}")
            return False
        return True

    def delete_company(self, company_id: int) -> bool:
        """
        Delete a company from Copper.

        Args:
            company_id: Company ID

        Returns:
            True if successful, False otherwise
        """
        result = self._make_request("DELETE", f"companies/{company_id}")
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to delete company {company_id}: {result.get('error')}")
            return False
        return True

    def delete_opportunity(self, opportunity_id: int) -> bool:
        """
        Delete an opportunity from Copper.

        Args:
            opportunity_id: Opportunity ID

        Returns:
            True if successful, False otherwise
        """
        result = self._make_request("DELETE", f"opportunities/{opportunity_id}")
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to delete opportunity {opportunity_id}: {result.get('error')}")
            return False
        return True

    def delete_lead(self, lead_id: int) -> bool:
        """
        Delete a lead from Copper.

        Args:
            lead_id: Lead ID

        Returns:
            True if successful, False otherwise
        """
        result = self._make_request("DELETE", f"leads/{lead_id}")
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to delete lead {lead_id}: {result.get('error')}")
            return False
        return True

    def delete_task(self, task_id: int) -> bool:
        """
        Delete a task from Copper.

        Args:
            task_id: Task ID

        Returns:
            True if successful, False otherwise
        """
        result = self._make_request("DELETE", f"tasks/{task_id}")
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to delete task {task_id}: {result.get('error')}")
            return False
        return True

    def delete_project(self, project_id: int) -> bool:
        """
        Delete a project from Copper.

        Args:
            project_id: Project ID

        Returns:
            True if successful, False otherwise
        """
        result = self._make_request("DELETE", f"projects/{project_id}")
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to delete project {project_id}: {result.get('error')}")
            return False
        return True

    # ============================================================================
    # TASKS, PROJECTS, AND ACTIVITIES
    # ============================================================================

    def search_tasks(self, criteria: Dict) -> List[Dict]:
        """
        Search for tasks in Copper.

        Args:
            criteria: Search criteria

        Returns:
            List of matching tasks
        """
        result = self._make_request("POST", "tasks/search", criteria)
        if isinstance(result, dict) and "error" in result:
            return []
        return result if isinstance(result, list) else []

    def get_task(self, task_id: int) -> Optional[Dict]:
        """
        Get a specific task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task data or None
        """
        result = self._make_request("GET", f"tasks/{task_id}")
        if isinstance(result, dict) and "error" in result:
            return None
        return result

    def update_task(self, task_id: int, updates: Dict) -> Optional[Dict]:
        """
        Update a task in Copper.

        Args:
            task_id: Task ID
            updates: Dictionary of fields to update

        Returns:
            Updated task data or None
        """
        result = self._make_request("PUT", f"tasks/{task_id}", updates)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to update task {task_id}: {result.get('error')}")
            return None
        return result

    def search_projects(self, criteria: Dict) -> List[Dict]:
        """
        Search for projects in Copper.

        Args:
            criteria: Search criteria

        Returns:
            List of matching projects
        """
        result = self._make_request("POST", "projects/search", criteria)
        if isinstance(result, dict) and "error" in result:
            return []
        return result if isinstance(result, list) else []

    def get_project(self, project_id: int) -> Optional[Dict]:
        """
        Get a specific project by ID.

        Args:
            project_id: Project ID

        Returns:
            Project data or None
        """
        result = self._make_request("GET", f"projects/{project_id}")
        if isinstance(result, dict) and "error" in result:
            return None
        return result

    def update_project(self, project_id: int, updates: Dict) -> Optional[Dict]:
        """
        Update a project in Copper.

        Args:
            project_id: Project ID
            updates: Dictionary of fields to update

        Returns:
            Updated project data or None
        """
        result = self._make_request("PUT", f"projects/{project_id}", updates)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Failed to update project {project_id}: {result.get('error')}")
            return None
        return result

    def search_activities(self, criteria: Dict) -> List[Dict]:
        """
        Search for activities in Copper.

        Args:
            criteria: Search criteria

        Returns:
            List of matching activities
        """
        result = self._make_request("POST", "activities/search", criteria)
        if isinstance(result, dict) and "error" in result:
            return []
        return result if isinstance(result, list) else []

    def get_related_items(self, entity_type: str, entity_id: int, related_type: Optional[str] = None) -> List[Dict]:
        """
        Get related items for an entity.

        Args:
            entity_type: Type of entity (people, companies, opportunities, etc.)
            entity_id: Entity ID
            related_type: Optional - specific type of related items (tasks, projects, etc.)

        Returns:
            List of related items
        """
        if related_type:
            endpoint = f"{entity_type}/{entity_id}/related/{related_type}"
        else:
            endpoint = f"{entity_type}/{entity_id}/related"

        result = self._make_request("GET", endpoint)
        if isinstance(result, dict) and "error" in result:
            return []
        return result if isinstance(result, list) else []

    def find_companies_fuzzy(self, search_term: str) -> List[Dict]:
        """
        Find companies using fuzzy/partial matching.

        Tries multiple strategies:
        1. Exact match
        2. Partial match (contains)
        3. Word-based match

        Args:
            search_term: Company name or partial name to search for

        Returns:
            List of matching companies, sorted by relevance
        """
        search_term_lower = search_term.lower().strip()
        logger.info(f"Fuzzy searching for companies matching: '{search_term}'")

        # Strategy 1: Try exact match first
        exact_matches = self.search_companies({'name': search_term})
        if exact_matches:
            logger.info(f"Found {len(exact_matches)} exact matches")
            return exact_matches

        # Strategy 2: Get MORE companies and do client-side partial matching
        # Copper API doesn't support wildcard searches, so we fetch more and filter
        logger.info("No exact match, trying partial matching...")

        # Fetch multiple pages of companies to increase chances of finding a match
        all_companies = []
        page_size = 200  # Copper's max page size

        # Try to get up to 200 companies (should cover most use cases)
        result = self.search_companies({'page_size': page_size})
        all_companies.extend(result if result else [])

        logger.info(f"Fetched {len(all_companies)} companies for fuzzy matching")

        if not all_companies:
            return []

        # Log sample of company names for debugging
        sample_names = [c.get('name', 'Unknown') for c in all_companies[:5]]
        logger.info(f"Sample company names: {sample_names}")

        # Partial matches - company name contains search term
        partial_matches = []
        word_matches = []

        search_words = search_term_lower.split()

        for company in all_companies:
            company_name = company.get('name', '').lower()

            # Check if company name contains the search term
            if search_term_lower in company_name:
                partial_matches.append(company)
                logger.info(f"✅ Partial match: '{company.get('name')}' contains '{search_term}'")
            # Check if any word from search term is in company name
            elif any(word in company_name for word in search_words if len(word) > 2):
                word_matches.append(company)
                logger.info(f"✅ Word match: '{company.get('name')}' contains word from '{search_term}'")

        # Return partial matches first, then word matches
        results = partial_matches + word_matches

        if results:
            logger.info(f"Fuzzy search found {len(results)} potential matches")
        else:
            logger.warning(f"No fuzzy matches found for '{search_term}' in {len(all_companies)} companies")

        return results[:10]  # Limit to top 10 matches

    def select_best_company(self, companies: List[Dict]) -> Dict[str, Any]:
        """
        Select the best company from multiple matches based on recent activity.

        Strategy: Pick the company with the most recent activity date.
        This assumes the most actively used company is the "correct" one.

        Args:
            companies: List of company matches

        Returns:
            Dictionary with:
            - company: The selected company
            - reason: Why this company was selected
            - alternatives: Other companies that were considered
        """
        if not companies:
            return None

        if len(companies) == 1:
            return {
                'company': companies[0],
                'reason': 'only match',
                'alternatives': []
            }

        logger.info(f"Selecting best company from {len(companies)} matches...")

        # Check activities for each company to find most recent
        best_company = None
        best_activity_date = 0
        company_activity_info = []

        for company in companies:
            company_id = company.get('id')
            company_name = company.get('name')

            # Get recent activities for this company
            criteria = {'parent': {'id': company_id, 'type': 'company'}}
            activities = self.search_activities(criteria)

            if activities:
                # Get the most recent activity date
                most_recent = max(activities, key=lambda a: a.get('activity_date', 0))
                activity_date = most_recent.get('activity_date', 0)
            else:
                activity_date = 0

            company_activity_info.append({
                'company': company,
                'activity_date': activity_date,
                'activity_count': len(activities)
            })

            logger.info(f"  {company_name}: {len(activities)} activities, most recent: {activity_date}")

            if activity_date > best_activity_date:
                best_activity_date = activity_date
                best_company = company

        # If no activities found for any company, pick the first one
        if not best_company:
            logger.info("No activities found for any company, using first match")
            best_company = companies[0]
            reason = "first match (no activity data)"
        else:
            # Calculate days since last activity
            import time
            if best_activity_date > 0:
                days_ago = int((time.time() - best_activity_date) / 86400)
                if days_ago == 0:
                    reason = f"most recent activity today"
                elif days_ago == 1:
                    reason = f"most recent activity yesterday"
                else:
                    reason = f"most recent activity {days_ago} days ago"
            else:
                reason = "most records"

        # Get alternatives (other companies not selected)
        alternatives = [c['company'] for c in company_activity_info if c['company'].get('id') != best_company.get('id')]

        logger.info(f"✅ Selected: {best_company.get('name')} ({reason})")

        return {
            'company': best_company,
            'reason': reason,
            'alternatives': alternatives
        }

    def search_activities_by_company(self, company_name: str, activity_type: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """
        Search for activities related to a company.

        Args:
            company_name: Name of the company
            activity_type: Optional - filter by type (0=email, 1=user, 2=note, etc.)
            limit: Maximum number of results

        Returns:
            List of activities
        """
        logger.info(f"Searching for activities related to company: {company_name}")

        # Use fuzzy search to find the company
        companies = self.find_companies_fuzzy(company_name)
        if not companies:
            logger.info(f"No companies found matching '{company_name}'")
            return []

        all_activities = []
        for company in companies[:5]:  # Limit to first 5 matching companies
            company_id = company.get('id')
            company_actual_name = company.get('name')
            logger.info(f"Found company: {company_actual_name} (ID: {company_id})")

            # Search for activities related to this company
            criteria = {'parent': {'id': company_id, 'type': 'company'}}
            if activity_type is not None:
                criteria['activity_types'] = [{'id': activity_type}]

            activities = self.search_activities(criteria)
            logger.info(f"Found {len(activities)} activities for {company_actual_name}")

            # Add company name to each activity for context
            for activity in activities:
                activity['_company_name'] = company_actual_name

            all_activities.extend(activities)

        # Sort by date (most recent first)
        all_activities.sort(key=lambda x: x.get('activity_date', 0), reverse=True)

        return all_activities[:limit]
