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
        Process CSV rows and query Copper for each.

        Expected CSV formats:
        1. Simple search: columns like 'name', 'email', 'company', 'type'
        2. Entity-specific: 'entity_type' column with 'search_field' columns

        Args:
            rows: Parsed CSV rows

        Returns:
            Results dictionary with matches and stats
        """
        results = {
            'total_queries': len(rows),
            'successful': 0,
            'failed': 0,
            'matches': []
        }

        for idx, row in enumerate(rows, 1):
            try:
                # Determine entity type
                entity_type = row.get('type', row.get('entity_type', 'people')).lower()

                # Build search criteria from row
                criteria = self._build_criteria_from_row(row, entity_type)

                # Query Copper
                matches = self._query_copper(entity_type, criteria)

                results['matches'].append({
                    'row_number': idx,
                    'query': row,
                    'entity_type': entity_type,
                    'found': len(matches),
                    'results': matches
                })

                results['successful'] += 1

            except Exception as e:
                logger.error(f"Failed to process row {idx}: {str(e)}")
                results['failed'] += 1
                results['matches'].append({
                    'row_number': idx,
                    'query': row,
                    'error': str(e)
                })

        return results

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
        summary = f"*CSV Query Results*\n\n"
        summary += f"📊 Total queries: {results['total_queries']}\n"
        summary += f"✅ Successful: {results['successful']}\n"
        summary += f"❌ Failed: {results['failed']}\n\n"

        # Show results for each row
        output_lines = [summary]

        for match in results['matches'][:10]:  # Limit to first 10 for display
            row_num = match['row_number']

            if 'error' in match:
                output_lines.append(f"*Row {row_num}*: ❌ Error - {match['error']}")
            else:
                found = match['found']
                entity_type = match['entity_type']
                query_str = ', '.join(f"{k}: {v}" for k, v in match['query'].items() if v)

                output_lines.append(
                    f"*Row {row_num}*: {found} {entity_type} found\n"
                    f"Query: {query_str}"
                )

                # Show first result if any
                if match['results']:
                    first_result = match['results'][0]
                    name = first_result.get('name', 'Unknown')
                    output_lines.append(f"  → {name}")

                output_lines.append("")

        if len(results['matches']) > 10:
            output_lines.append(f"\n_Showing first 10 of {len(results['matches'])} results_")

        return "\n".join(output_lines)
