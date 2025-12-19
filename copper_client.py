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

    # ============================================================================
    # PIPELINES AND STAGES
    # ============================================================================

    def get_pipelines(self) -> List[Dict]:
        """
        Get all pipelines.

        Returns:
            List of pipelines
        """
        result = self._make_request("GET", "pipelines")
        if isinstance(result, dict) and "error" in result:
            return []
        return result if isinstance(result, list) else []

    def get_pipeline_by_name(self, name: str) -> Optional[Dict]:
        """
        Get a pipeline by name.

        Args:
            name: Pipeline name

        Returns:
            Pipeline data or None
        """
        pipelines = self.get_pipelines()
        for pipeline in pipelines:
            if pipeline.get('name', '').lower() == name.lower():
                return pipeline
        return None

    def get_pipeline_stages(self, pipeline_id: int) -> List[Dict]:
        """
        Get stages for a pipeline.

        Args:
            pipeline_id: Pipeline ID

        Returns:
            List of pipeline stages
        """
        result = self._make_request("GET", f"pipelines/{pipeline_id}/stages")
        if isinstance(result, dict) and "error" in result:
            return []
        return result if isinstance(result, list) else []

    def find_opportunity_by_name(self, name: str, pipeline_id: int = None) -> Optional[Dict]:
        """
        Find an opportunity by name, optionally filtering by pipeline.

        Args:
            name: Opportunity name
            pipeline_id: Optional pipeline ID to filter by

        Returns:
            Opportunity data or None
        """
        criteria = {'name': name}
        if pipeline_id:
            criteria['pipeline_ids'] = [pipeline_id]

        results = self.search_opportunities(criteria)
        if results:
            return results[0]
        return None

    def get_lead(self, lead_id: int) -> Optional[Dict]:
        """
        Get a specific lead by ID.

        Args:
            lead_id: Lead ID

        Returns:
            Lead data or None
        """
        result = self._make_request("GET", f"leads/{lead_id}")
        if isinstance(result, dict) and "error" in result:
            return None
        return result
