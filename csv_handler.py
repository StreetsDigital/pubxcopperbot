"""CSV file handler for batch queries."""

import csv
import io
import logging
from typing import List, Dict, Any
import requests

logger = logging.getLogger(__name__)


class CSVHandler:
    """Handle CSV file uploads and process batch queries."""

    def __init__(self, copper_client):
        """
        Initialize CSV handler.

        Args:
            copper_client: Instance of CopperClient
        """
        self.copper_client = copper_client

    def download_file(self, url: str, token: str) -> bytes:
        """
        Download a file from Slack.

        Args:
            url: File URL
            token: Slack bot token

        Returns:
            File content as bytes
        """
        try:
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to download file: {str(e)}")
            raise

    def parse_csv(self, content: bytes) -> List[Dict[str, str]]:
        """
        Parse CSV content.

        Args:
            content: CSV file content as bytes

        Returns:
            List of dictionaries representing CSV rows
        """
        try:
            # Decode content
            text = content.decode('utf-8')

            # Parse CSV
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)

            logger.info(f"Parsed {len(rows)} rows from CSV")
            return rows

        except Exception as e:
            logger.error(f"Failed to parse CSV: {str(e)}")
            raise

    def process_csv_queries(self, rows: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Process CSV rows and check existence in Copper CRM.

        Checks for:
        - Contact/Person existence
        - Company existence
        - Opportunity existence

        Args:
            rows: Parsed CSV rows

        Returns:
            Results dictionary with enriched rows
        """
        results = {
            'total_queries': len(rows),
            'successful': 0,
            'failed': 0,
            'enriched_rows': []
        }

        for idx, row in enumerate(rows, 1):
            try:
                # Create enriched row with original data
                enriched_row = dict(row)

                # Check for contact/person
                contact_exists = self._check_contact_exists(row)
                enriched_row['Contact is in CRM'] = 'Yes' if contact_exists else 'No'

                # Check for company
                company_exists = self._check_company_exists(row)
                enriched_row['Company is in CRM'] = 'Yes' if company_exists else 'No'

                # Check for opportunity
                opportunity_exists = self._check_opportunity_exists(row)
                enriched_row['Opportunity exists'] = 'Yes' if opportunity_exists else 'No'

                results['enriched_rows'].append(enriched_row)
                results['successful'] += 1

            except Exception as e:
                logger.error(f"Failed to process row {idx}: {str(e)}")
                results['failed'] += 1
                enriched_row = dict(row)
                enriched_row['Contact is in CRM'] = 'Error'
                enriched_row['Company is in CRM'] = 'Error'
                enriched_row['Opportunity exists'] = 'Error'
                results['enriched_rows'].append(enriched_row)

        return results

    def _check_contact_exists(self, row: Dict[str, str]) -> bool:
        """
        Check if a contact/person exists in Copper.

        Args:
            row: CSV row data

        Returns:
            True if contact exists, False otherwise
        """
        criteria = {}

        # Try to find by email (most accurate)
        if 'email' in row and row['email']:
            criteria['emails'] = [row['email']]
        # Try by name as fallback
        elif 'name' in row and row['name']:
            criteria['name'] = row['name']
        # Try by contact_name
        elif 'contact_name' in row and row['contact_name']:
            criteria['name'] = row['contact_name']
        else:
            return False

        results = self.copper_client.search_people(criteria)
        return len(results) > 0

    def _check_company_exists(self, row: Dict[str, str]) -> bool:
        """
        Check if a company exists in Copper.

        Args:
            row: CSV row data

        Returns:
            True if company exists, False otherwise
        """
        criteria = {}

        # Try to find by company name
        if 'company' in row and row['company']:
            criteria['name'] = row['company']
        elif 'company_name' in row and row['company_name']:
            criteria['name'] = row['company_name']
        else:
            return False

        results = self.copper_client.search_companies(criteria)
        return len(results) > 0

    def _check_opportunity_exists(self, row: Dict[str, str]) -> bool:
        """
        Check if an opportunity exists in Copper.

        Args:
            row: CSV row data

        Returns:
            True if opportunity exists, False otherwise
        """
        criteria = {}

        # Try to find by opportunity name
        if 'opportunity' in row and row['opportunity']:
            criteria['name'] = row['opportunity']
        elif 'opportunity_name' in row and row['opportunity_name']:
            criteria['name'] = row['opportunity_name']
        elif 'deal' in row and row['deal']:
            criteria['name'] = row['deal']
        else:
            return False

        results = self.copper_client.search_opportunities(criteria)
        return len(results) > 0

    def generate_enriched_csv(self, enriched_rows: List[Dict[str, str]]) -> bytes:
        """
        Generate a CSV file with enriched data.

        Args:
            enriched_rows: Rows with added CRM existence columns

        Returns:
            CSV content as bytes
        """
        if not enriched_rows:
            return b""

        output = io.StringIO()

        # Get all field names (original + new columns)
        fieldnames = list(enriched_rows[0].keys())

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(enriched_rows)

        # Convert to bytes
        return output.getvalue().encode('utf-8')

    def _build_criteria_from_row(self, row: Dict[str, str], entity_type: str) -> Dict:
        """
        Build Copper search criteria from CSV row.

        Args:
            row: CSV row as dictionary
            entity_type: Type of entity to search

        Returns:
            Search criteria dictionary
        """
        criteria = {}

        # Common fields
        if 'name' in row and row['name']:
            criteria['name'] = row['name']

        if 'email' in row and row['email']:
            criteria['emails'] = [row['email']]

        if 'phone' in row and row['phone']:
            criteria['phone_numbers'] = [row['phone']]

        if 'city' in row and row['city']:
            criteria['city'] = row['city']

        if 'state' in row and row['state']:
            criteria['state'] = row['state']

        if 'country' in row and row['country']:
            criteria['country'] = row['country']

        # Opportunity-specific
        if entity_type == 'opportunities':
            if 'status' in row and row['status']:
                criteria['status'] = row['status']

            if 'min_value' in row and row['min_value']:
                try:
                    criteria['minimum_monetary_value'] = float(row['min_value'])
                except ValueError:
                    pass

        # Tags
        if 'tags' in row and row['tags']:
            criteria['tags'] = [tag.strip() for tag in row['tags'].split(',')]

        return criteria

    def _query_copper(self, entity_type: str, criteria: Dict) -> List[Dict]:
        """
        Query Copper API based on entity type.

        Args:
            entity_type: Entity type
            criteria: Search criteria

        Returns:
            List of results
        """
        if entity_type == 'people' or entity_type == 'person':
            return self.copper_client.search_people(criteria)
        elif entity_type == 'companies' or entity_type == 'company':
            return self.copper_client.search_companies(criteria)
        elif entity_type == 'opportunities' or entity_type == 'opportunity':
            return self.copper_client.search_opportunities(criteria)
        elif entity_type == 'leads' or entity_type == 'lead':
            return self.copper_client.search_leads(criteria)
        else:
            return []

    def format_csv_results(self, results: Dict[str, Any]) -> str:
        """
        Format CSV query results for Slack.

        Args:
            results: Results from process_csv_queries

        Returns:
            Formatted string
        """
        summary = f"*CSV Processing Results*\n\n"
        summary += f"📊 Total rows: {results['total_queries']}\n"
        summary += f"✅ Successful: {results['successful']}\n"
        summary += f"❌ Failed: {results['failed']}\n\n"

        # Count totals
        enriched_rows = results['enriched_rows']
        contacts_found = sum(1 for row in enriched_rows if row.get('Contact is in CRM') == 'Yes')
        companies_found = sum(1 for row in enriched_rows if row.get('Company is in CRM') == 'Yes')
        opportunities_found = sum(1 for row in enriched_rows if row.get('Opportunity exists') == 'Yes')

        summary += f"👤 Contacts in CRM: {contacts_found}/{len(enriched_rows)}\n"
        summary += f"🏢 Companies in CRM: {companies_found}/{len(enriched_rows)}\n"
        summary += f"💼 Opportunities exist: {opportunities_found}/{len(enriched_rows)}\n\n"
        summary += "📥 *Download the enriched CSV file below to see all results with new columns added.*"

        return summary
