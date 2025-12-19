"""CSV and Excel file handler for batch queries and opportunity imports."""

import csv
import io
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import requests
from config import Config

# Try to import openpyxl for Excel support
try:
    import openpyxl
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False

logger = logging.getLogger(__name__)

# Standard field mappings for opportunity imports
OPPORTUNITY_FIELD_MAPPINGS = {
    # Name fields
    'name': ['name', 'opportunity_name', 'opportunity', 'deal', 'deal_name', 'title'],
    # Company fields
    'company_name': ['company', 'company_name', 'account', 'account_name', 'advertiser', 'client'],
    # Contact fields
    'primary_contact_name': ['contact', 'contact_name', 'main_contact', 'primary_contact'],
    # Value fields
    'monetary_value': ['value', 'amount', 'deal_value', 'revenue', 'monetary_value', 'monthly_impressions', 'impressions'],
    # Date fields
    'close_date': ['close_date', 'expected_close', 'close', 'end_date'],
    # Status/Stage
    'status': ['status', 'stage', 'pipeline_stage'],
    # Custom fields
    'monthly_impressions': ['monthly_impressions', 'impressions', 'monthly_imps', 'imps'],
}


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

    def parse_excel(self, content: bytes) -> List[Dict[str, str]]:
        """
        Parse Excel (.xlsx) content.

        Args:
            content: Excel file content as bytes

        Returns:
            List of dictionaries representing rows
        """
        if not EXCEL_SUPPORT:
            raise ImportError("openpyxl is required for Excel support. Install with: pip install openpyxl")

        try:
            # Load workbook from bytes
            workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            sheet = workbook.active

            rows = []
            headers = []

            for row_idx, row in enumerate(sheet.iter_rows(values_only=True)):
                if row_idx == 0:
                    # First row is headers
                    headers = [str(cell).strip() if cell else f'column_{i}' for i, cell in enumerate(row)]
                else:
                    # Skip empty rows
                    if all(cell is None or str(cell).strip() == '' for cell in row):
                        continue

                    row_dict = {}
                    for i, cell in enumerate(row):
                        if i < len(headers):
                            # Convert cell value to string
                            value = str(cell).strip() if cell is not None else ''
                            row_dict[headers[i]] = value
                    rows.append(row_dict)

            logger.info(f"Parsed {len(rows)} rows from Excel")
            return rows

        except Exception as e:
            logger.error(f"Failed to parse Excel: {str(e)}")
            raise

    def parse_file(self, content: bytes, filename: str) -> List[Dict[str, str]]:
        """
        Parse a file based on its extension.

        Args:
            content: File content as bytes
            filename: Original filename

        Returns:
            List of dictionaries representing rows
        """
        filename_lower = filename.lower()

        if filename_lower.endswith('.xlsx') or filename_lower.endswith('.xls'):
            return self.parse_excel(content)
        elif filename_lower.endswith('.csv'):
            return self.parse_csv(content)
        else:
            # Try CSV as default
            return self.parse_csv(content)

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

    # =========================================================================
    # Opportunity Import (Create/Update from CSV/Excel)
    # =========================================================================

    def detect_import_mode(self, rows: List[Dict[str, str]]) -> str:
        """
        Detect if the CSV is for lookup or import based on columns.

        Args:
            rows: Parsed CSV rows

        Returns:
            'import' if it looks like opportunity data, 'lookup' otherwise
        """
        if not rows:
            return 'lookup'

        # Get column names from first row
        columns = set(k.lower() for k in rows[0].keys())

        # Check for import indicators
        import_indicators = {
            'value', 'amount', 'revenue', 'monetary_value',
            'close_date', 'expected_close', 'stage', 'pipeline_stage',
            'monthly_impressions', 'impressions'
        }

        matches = columns.intersection(import_indicators)
        if len(matches) >= 1:
            return 'import'

        return 'lookup'

    def _normalize_field_name(self, field: str) -> str:
        """
        Normalize a field name to its canonical form.

        Args:
            field: Field name from CSV

        Returns:
            Canonical field name
        """
        field_lower = field.lower().strip()

        for canonical, aliases in OPPORTUNITY_FIELD_MAPPINGS.items():
            if field_lower in aliases:
                return canonical

        return field_lower

    def _parse_monetary_value(self, value: str) -> Optional[float]:
        """
        Parse a monetary value from various formats.

        Args:
            value: Value string (e.g., "$50,000", "50000", "50k")

        Returns:
            Float value or None
        """
        if not value:
            return None

        try:
            # Remove common currency symbols and whitespace
            cleaned = value.strip().replace('$', '').replace(',', '').replace(' ', '')

            # Handle "k" suffix for thousands
            if cleaned.lower().endswith('k'):
                return float(cleaned[:-1]) * 1000

            # Handle "m" suffix for millions
            if cleaned.lower().endswith('m'):
                return float(cleaned[:-1]) * 1000000

            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _parse_date(self, value: str) -> Optional[int]:
        """
        Parse a date string to Unix timestamp.

        Args:
            value: Date string

        Returns:
            Unix timestamp or None
        """
        if not value:
            return None

        # Common date formats to try
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%m-%d-%Y',
            '%d-%m-%Y',
            '%Y/%m/%d',
            '%B %d, %Y',
            '%b %d, %Y',
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(value.strip(), fmt)
                return int(dt.timestamp())
            except ValueError:
                continue

        return None

    def process_opportunity_import(
        self,
        rows: List[Dict[str, str]],
        pipeline_id: Optional[int] = None,
        pipeline_stage_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process CSV rows for opportunity import (create/update).

        Args:
            rows: Parsed CSV rows
            pipeline_id: Pipeline ID to use (or default from config)
            pipeline_stage_id: Initial stage ID for new opportunities

        Returns:
            Results dictionary with operations to perform
        """
        # Get pipeline configuration
        if not pipeline_id and Config.DEFAULT_PIPELINE_ID:
            try:
                pipeline_id = int(Config.DEFAULT_PIPELINE_ID)
            except (ValueError, TypeError):
                pass

        # If still no pipeline ID, try to find by name
        if not pipeline_id and Config.DEFAULT_PIPELINE_NAME:
            pipeline = self.copper_client.get_pipeline_by_name(Config.DEFAULT_PIPELINE_NAME)
            if pipeline:
                pipeline_id = pipeline.get('id')
                # Get first stage as default
                stages = self.copper_client.get_pipeline_stages(pipeline_id)
                if stages and not pipeline_stage_id:
                    pipeline_stage_id = stages[0].get('id')

        results = {
            'total_rows': len(rows),
            'to_create': [],
            'to_update': [],
            'errors': [],
            'pipeline_id': pipeline_id,
            'pipeline_stage_id': pipeline_stage_id,
        }

        for idx, row in enumerate(rows, 1):
            try:
                # Normalize field names
                normalized = {}
                for key, value in row.items():
                    norm_key = self._normalize_field_name(key)
                    normalized[norm_key] = value

                # Check if opportunity exists
                opp_name = normalized.get('name')
                if not opp_name:
                    results['errors'].append({
                        'row': idx,
                        'error': 'Missing opportunity name',
                        'data': row
                    })
                    continue

                existing = self.copper_client.find_opportunity_by_name(opp_name, pipeline_id)

                # Build opportunity data
                opp_data = {'name': opp_name}

                # Map fields
                if normalized.get('monetary_value'):
                    value = self._parse_monetary_value(normalized['monetary_value'])
                    if value:
                        opp_data['monetary_value'] = value

                if normalized.get('close_date'):
                    close_date = self._parse_date(normalized['close_date'])
                    if close_date:
                        opp_data['close_date'] = close_date

                # Company lookup
                if normalized.get('company_name'):
                    companies = self.copper_client.search_companies({'name': normalized['company_name']})
                    if companies:
                        opp_data['company_id'] = companies[0].get('id')
                        opp_data['company_name'] = companies[0].get('name')

                # Contact lookup
                if normalized.get('primary_contact_name'):
                    contacts = self.copper_client.search_people({'name': normalized['primary_contact_name']})
                    if contacts:
                        opp_data['primary_contact_id'] = contacts[0].get('id')

                # Pipeline
                if pipeline_id:
                    opp_data['pipeline_id'] = pipeline_id

                if pipeline_stage_id and not existing:
                    opp_data['pipeline_stage_id'] = pipeline_stage_id

                # Store any extra fields (will be stored as custom fields later if needed)
                opp_data['_source_row'] = idx
                opp_data['_raw_data'] = row

                if existing:
                    results['to_update'].append({
                        'id': existing['id'],
                        'name': opp_name,
                        'data': opp_data,
                        'existing': existing
                    })
                else:
                    results['to_create'].append({
                        'name': opp_name,
                        'data': opp_data
                    })

            except Exception as e:
                logger.error(f"Error processing row {idx}: {e}")
                results['errors'].append({
                    'row': idx,
                    'error': str(e),
                    'data': row
                })

        return results

    def execute_opportunity_import(
        self,
        import_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the opportunity import (create/update operations).

        Args:
            import_results: Results from process_opportunity_import

        Returns:
            Execution results
        """
        execution = {
            'created': [],
            'updated': [],
            'failed': []
        }

        # Create new opportunities
        for item in import_results['to_create']:
            try:
                # Remove internal fields
                data = {k: v for k, v in item['data'].items() if not k.startswith('_')}
                result = self.copper_client.create_opportunity(data)
                if result and result.get('id'):
                    execution['created'].append({
                        'name': item['name'],
                        'id': result['id']
                    })
                else:
                    execution['failed'].append({
                        'name': item['name'],
                        'error': 'Failed to create'
                    })
            except Exception as e:
                execution['failed'].append({
                    'name': item['name'],
                    'error': str(e)
                })

        # Update existing opportunities
        for item in import_results['to_update']:
            try:
                # Remove internal fields
                data = {k: v for k, v in item['data'].items() if not k.startswith('_')}
                # Remove fields that shouldn't be updated
                data.pop('name', None)  # Don't rename
                data.pop('pipeline_id', None)  # Don't change pipeline

                if data:  # Only update if there's something to update
                    result = self.copper_client.update_opportunity(item['id'], data)
                    if result:
                        execution['updated'].append({
                            'name': item['name'],
                            'id': item['id']
                        })
                    else:
                        execution['failed'].append({
                            'name': item['name'],
                            'error': 'Failed to update'
                        })
                else:
                    execution['updated'].append({
                        'name': item['name'],
                        'id': item['id'],
                        'note': 'No changes'
                    })
            except Exception as e:
                execution['failed'].append({
                    'name': item['name'],
                    'error': str(e)
                })

        return execution

    def format_import_preview(self, import_results: Dict[str, Any]) -> str:
        """
        Format import preview for approval.

        Args:
            import_results: Results from process_opportunity_import

        Returns:
            Formatted string
        """
        lines = ["*Opportunity Import Preview*\n"]

        lines.append(f"📊 Total rows: {import_results['total_rows']}")
        lines.append(f"➕ To create: {len(import_results['to_create'])}")
        lines.append(f"✏️ To update: {len(import_results['to_update'])}")
        lines.append(f"❌ Errors: {len(import_results['errors'])}")

        if import_results.get('pipeline_id'):
            lines.append(f"\n📋 Target pipeline ID: {import_results['pipeline_id']}")

        # Show first few creates
        if import_results['to_create'][:5]:
            lines.append("\n*New opportunities:*")
            for item in import_results['to_create'][:5]:
                value = item['data'].get('monetary_value', 'N/A')
                if isinstance(value, (int, float)):
                    value = f"${value:,.0f}"
                lines.append(f"  • {item['name']} ({value})")
            if len(import_results['to_create']) > 5:
                lines.append(f"  ... and {len(import_results['to_create']) - 5} more")

        # Show first few updates
        if import_results['to_update'][:5]:
            lines.append("\n*Updates:*")
            for item in import_results['to_update'][:5]:
                lines.append(f"  • {item['name']} (ID: {item['id']})")
            if len(import_results['to_update']) > 5:
                lines.append(f"  ... and {len(import_results['to_update']) - 5} more")

        # Show errors
        if import_results['errors'][:3]:
            lines.append("\n*Errors:*")
            for err in import_results['errors'][:3]:
                lines.append(f"  • Row {err['row']}: {err['error']}")

        return '\n'.join(lines)

    def format_import_results(self, execution: Dict[str, Any]) -> str:
        """
        Format import execution results.

        Args:
            execution: Results from execute_opportunity_import

        Returns:
            Formatted string
        """
        lines = ["*Import Complete*\n"]

        lines.append(f"✅ Created: {len(execution['created'])}")
        lines.append(f"✏️ Updated: {len(execution['updated'])}")
        lines.append(f"❌ Failed: {len(execution['failed'])}")

        if execution['failed'][:5]:
            lines.append("\n*Failures:*")
            for item in execution['failed'][:5]:
                lines.append(f"  • {item['name']}: {item['error']}")

        return '\n'.join(lines)
