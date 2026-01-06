"""Business Intelligence module for comprehensive Copper CRM queries."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import Config
from copper_client import CopperClient
from fuzzy_matcher import FuzzyMatcher

logger = logging.getLogger(__name__)

# Type aliases
JsonDict = Dict[str, Any]
JsonList = List[JsonDict]
MatchResult = Tuple[JsonDict, float]  # (record, score)


class BusinessIntelligence:
    """Intelligent business query processor for Copper CRM."""

    def __init__(self, copper_client: CopperClient, fuzzy_threshold: int = 65):
        """Initialize business intelligence processor.

        Args:
            copper_client: Copper CRM client instance
            fuzzy_threshold: Minimum fuzzy match score (0-100) to consider a match
        """
        self.copper_client = copper_client
        self.claude_proxy_url = Config.CLAUDE_PROXY_URL
        self.fuzzy_matcher = FuzzyMatcher(threshold=fuzzy_threshold)
        self.use_claude = False

        # Check if Claude proxy is available
        if Config.CLAUDE_PROXY_URL:
            try:
                response = requests.get(f"{self.claude_proxy_url}/health", timeout=10)
                if response.status_code == 200:
                    health = response.json()
                    if health.get("configured"):
                        self.use_claude = True
                        auth_method = health.get("auth_method", "unknown")
                        logger.info(f"Business Intelligence initialized with Claude proxy ({auth_method})")
                    else:
                        logger.warning("Claude proxy available but not configured")
                else:
                    logger.warning("Claude proxy health check failed - using basic query parsing")
            except Exception as e:
                logger.warning(f"Claude proxy not available ({e}) - using basic query parsing")
        else:
            logger.warning("No Claude proxy URL - using basic query parsing")

    def analyze_query(self, query: str) -> Dict[str, Any]:
        """Analyze a natural language business query.

        Args:
            query: Natural language query from user

        Returns:
            Dict with:
                - intent: What the user wants (status, overview, contacts, deals, etc)
                - entity_type: Primary entity type (company, person, opportunity)
                - entity_name: Name/identifier to search for
                - include: List of related data to include
        """
        if not self.use_claude:
            return self._basic_query_analysis(query)

        try:
            prompt = f"""Analyze this business intelligence query and extract structured information.

Query: "{query}"

Extract:
1. INTENT - What does the user want? (status, overview, contacts, deals, history, all)
2. ENTITY_TYPE - What are they asking about? (company, person, opportunity, lead, or general)
3. ENTITY_NAME - The specific name/identifier mentioned (if any)
4. INCLUDE - What related data should be included? (contacts, opportunities, leads, tasks, companies, notes, history, all)

Respond ONLY with valid JSON:
{{
  "intent": "status|overview|contacts|deals|history|all",
  "entity_type": "company|person|opportunity|lead|general",
  "entity_name": "specific name or null",
  "include": ["contacts", "opportunities", "leads", "tasks", "notes"]
}}

Examples:
"What's the status of PubX?" -> {{"intent": "status", "entity_type": "company", "entity_name": "PubX", "include": ["contacts", "opportunities", "leads", "tasks"]}}
"Show me everything about John Doe" -> {{"intent": "all", "entity_type": "person", "entity_name": "John Doe", "include": ["companies", "opportunities", "tasks", "notes"]}}
"Who are we talking to at Microsoft?" -> {{"intent": "contacts", "entity_type": "company", "entity_name": "Microsoft", "include": ["contacts", "opportunities"]}}
"What deals are in progress?" -> {{"intent": "deals", "entity_type": "general", "entity_name": null, "include": ["opportunities"]}}
"""

            # Call Claude proxy
            response = requests.post(
                f"{self.claude_proxy_url}/v1/messages",
                json={
                    "prompt": prompt,
                    "max_tokens": 1024,
                    "model": "claude-3-5-haiku-20241022",
                    "temperature": 0.0
                },
                timeout=30
            )
            response.raise_for_status()

            # Extract JSON from Claude's response
            result = response.json()
            content = result.get("content", "").strip()
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            analysis = json.loads(content.strip())
            logger.info(f"Query analysis: {analysis}")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing query with Claude: {e}", exc_info=True)
            return self._basic_query_analysis(query)

    def _basic_query_analysis(self, query: str) -> Dict[str, Any]:
        """Basic query analysis without Claude.

        Args:
            query: Natural language query

        Returns:
            Basic analysis dict
        """
        query_lower = query.lower()

        # Determine intent
        intent = "all"
        if any(word in query_lower for word in ["status", "update"]):
            intent = "status"
        elif any(word in query_lower for word in ["contact", "who", "people"]):
            intent = "contacts"
        elif any(word in query_lower for word in ["deal", "opportunity", "pipeline"]):
            intent = "deals"

        # Determine entity type
        entity_type = "company"  # Default to company for most queries
        if any(word in query_lower for word in ["person", "contact", "someone", "who is"]):
            entity_type = "person"
        elif any(word in query_lower for word in ["deal", "opportunity"]):
            entity_type = "opportunity"

        # Extract entity name using simple heuristics
        entity_name = None

        # Remove common question words and prepositions
        stop_words = {
            "what", "what's", "tell", "me", "about", "can", "you", "show",
            "the", "status", "of", "information", "on", "for", "is", "are",
            "who", "where", "when", "how", "with", "at", "in", "a", "an"
        }

        # Split query into words
        words = query.split()
        cleaned_words = []

        for word in words:
            # Remove punctuation
            clean_word = word.strip("?!.,;:")
            if clean_word.lower() not in stop_words:
                cleaned_words.append(clean_word)

        # Join remaining words as the entity name
        if cleaned_words:
            entity_name = " ".join(cleaned_words)

        return {
            "intent": intent,
            "entity_type": entity_type,
            "entity_name": entity_name,
            "include": ["contacts", "opportunities", "leads", "tasks"]
        }

    def gather_intelligence(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Gather comprehensive business intelligence based on query analysis.

        Args:
            analysis: Query analysis from analyze_query()

        Returns:
            Dict containing all gathered intelligence and optional confirmation request
            If confirmation is needed:
                {
                    "needs_confirmation": True,
                    "entity_type": "company|person|opportunity",
                    "query": "original search query",
                    "matches": [(entity, score), ...]
                }
            Otherwise:
                {
                    "needs_confirmation": False,
                    "primary_entity": {...},
                    "related_contacts": [...],
                    ...
                }
        """
        entity_type = analysis.get("entity_type")
        entity_name = analysis.get("entity_name")
        include = analysis.get("include", [])

        intelligence = {
            "needs_confirmation": False,
            "primary_entity": None,
            "related_contacts": [],
            "related_companies": [],
            "related_opportunities": [],
            "related_leads": [],
            "related_tasks": [],
            "summary": "",
            "debug_info": {}  # Track debug information
        }

        # Find primary entity with fuzzy matching
        if entity_name:
            all_matches = []
            total_search_count = 0

            if entity_type == "company":
                # For company names, search across multiple entity types
                # 1. Search actual companies
                companies = self.copper_client.search_companies({})
                if companies:
                    company_matches = self.fuzzy_matcher.match_companies(entity_name, companies)
                    all_matches.extend([(match, score, "company") for match, score in company_matches])
                    total_search_count += len(companies)

                # 2. Search leads (could have company name)
                leads = self.copper_client.search_leads({})
                if leads:
                    lead_matches = self.fuzzy_matcher.match_companies(entity_name, leads)
                    all_matches.extend([(match, score, "lead") for match, score in lead_matches])
                    total_search_count += len(leads)

                # 3. Search opportunities (could have company name)
                opportunities = self.copper_client.search_opportunities({})
                if opportunities:
                    opp_matches = self.fuzzy_matcher.match_opportunities(entity_name, opportunities)
                    all_matches.extend([(match, score, "opportunity") for match, score in opp_matches])
                    total_search_count += len(opportunities)

                # Sort all matches by score
                all_matches.sort(key=lambda x: x[1], reverse=True)

                # Convert back to (entity, score) format, prioritizing companies
                matches = []
                for match, score, match_type in all_matches:
                    # Boost company matches slightly
                    if match_type == "company":
                        score = min(100, score + 5)
                    matches.append((match, score))

            elif entity_type == "person":
                # For person names, search across multiple entity types
                # 1. Search actual people/contacts
                people = self.copper_client.search_people({})
                if people:
                    person_matches = self.fuzzy_matcher.match_contacts(entity_name, people)
                    all_matches.extend([(match, score, "person") for match, score in person_matches])
                    total_search_count += len(people)

                # 2. Search leads (could have contact person)
                leads = self.copper_client.search_leads({})
                if leads:
                    # Match against lead contact names
                    lead_matches = self.fuzzy_matcher.match_contacts(entity_name, leads)
                    all_matches.extend([(match, score, "lead") for match, score in lead_matches])
                    total_search_count += len(leads)

                # 3. Search opportunities (could have associated contact)
                opportunities = self.copper_client.search_opportunities({})
                if opportunities:
                    # Match against opportunity names (might contain person info)
                    opp_matches = self.fuzzy_matcher.match_opportunities(entity_name, opportunities)
                    all_matches.extend([(match, score, "opportunity") for match, score in opp_matches])
                    total_search_count += len(opportunities)

                # Sort all matches by score
                all_matches.sort(key=lambda x: x[1], reverse=True)

                # Convert back to (entity, score) format, prioritizing people
                matches = []
                for match, score, match_type in all_matches:
                    # Boost person matches slightly
                    if match_type == "person":
                        score = min(100, score + 5)
                    matches.append((match, score))

            elif entity_type == "opportunity":
                # For opportunities, search across multiple entity types
                # 1. Search actual opportunities
                opportunities = self.copper_client.search_opportunities({})
                if opportunities:
                    opp_matches = self.fuzzy_matcher.match_opportunities(entity_name, opportunities)
                    all_matches.extend([(match, score, "opportunity") for match, score in opp_matches])
                    total_search_count += len(opportunities)

                # 2. Search companies (opportunity might be company-related)
                companies = self.copper_client.search_companies({})
                if companies:
                    company_matches = self.fuzzy_matcher.match_companies(entity_name, companies)
                    all_matches.extend([(match, score, "company") for match, score in company_matches])
                    total_search_count += len(companies)

                # 3. Search leads (could be pre-opportunity)
                leads = self.copper_client.search_leads({})
                if leads:
                    lead_matches = self.fuzzy_matcher.match_companies(entity_name, leads)
                    all_matches.extend([(match, score, "lead") for match, score in lead_matches])
                    total_search_count += len(leads)

                # Sort all matches by score
                all_matches.sort(key=lambda x: x[1], reverse=True)

                # Convert back to (entity, score) format, prioritizing opportunities
                matches = []
                for match, score, match_type in all_matches:
                    # Boost opportunity matches slightly
                    if match_type == "opportunity":
                        score = min(100, score + 5)
                    matches.append((match, score))

            elif entity_type == "task":
                # For tasks, search tasks by name or description
                tasks = self.copper_client.search_tasks({})
                if tasks:
                    task_matches = self.fuzzy_matcher.match_tasks(entity_name, tasks)
                    all_matches.extend([(match, score, "task") for match, score in task_matches])
                    total_search_count = len(tasks)

                # Sort all matches by score
                all_matches.sort(key=lambda x: x[1], reverse=True)

                # Convert back to (entity, score) format
                matches = [(match, score) for match, score, _ in all_matches]

            else:
                # Fallback: Search all entity types
                logger.info(f"Unknown entity type '{entity_type}', searching all types")

                # Search companies
                companies = self.copper_client.search_companies({})
                if companies:
                    company_matches = self.fuzzy_matcher.match_companies(entity_name, companies)
                    all_matches.extend([(match, score, "company") for match, score in company_matches])
                    total_search_count += len(companies)

                # Search people
                people = self.copper_client.search_people({})
                if people:
                    person_matches = self.fuzzy_matcher.match_contacts(entity_name, people)
                    all_matches.extend([(match, score, "person") for match, score in person_matches])
                    total_search_count += len(people)

                # Search opportunities
                opportunities = self.copper_client.search_opportunities({})
                if opportunities:
                    opp_matches = self.fuzzy_matcher.match_opportunities(entity_name, opportunities)
                    all_matches.extend([(match, score, "opportunity") for match, score in opp_matches])
                    total_search_count += len(opportunities)

                # Search leads
                leads = self.copper_client.search_leads({})
                if leads:
                    lead_matches = self.fuzzy_matcher.match_companies(entity_name, leads)
                    all_matches.extend([(match, score, "lead") for match, score in lead_matches])
                    total_search_count += len(leads)

                # Sort all matches by score
                all_matches.sort(key=lambda x: x[1], reverse=True)

                # Convert back to (entity, score) format
                matches = [(match, score) for match, score, _ in all_matches]

            # Store debug info
            intelligence["debug_info"]["search_count"] = total_search_count
            intelligence["debug_info"]["matches_found"] = len(matches) if matches else 0
            if matches:
                intelligence["debug_info"]["best_score"] = matches[0][1]

            # Check if we need confirmation
            if matches and self.fuzzy_matcher.has_multiple_close_matches(matches):
                # Return for confirmation
                return {
                    "needs_confirmation": True,
                    "entity_type": entity_type,
                    "query": entity_name,
                    "matches": matches[:5],  # Top 5 matches
                    "debug_info": intelligence["debug_info"]
                }

            # Single clear match or best match
            if matches:
                intelligence["primary_entity"] = matches[0][0]  # Best match
        else:
            # No entity name extracted - log this for debugging
            intelligence["debug_info"]["error"] = "Could not extract entity name from query"
            intelligence["debug_info"]["search_count"] = 0
            intelligence["debug_info"]["matches_found"] = 0
            logger.warning(f"No entity name extracted from query: '{query}'")

        # Gather related data
        if intelligence["primary_entity"]:
            primary_id = intelligence["primary_entity"].get("id")
            primary_type = entity_type

            if "contacts" in include or "all" in include:
                intelligence["related_contacts"] = self._get_related_contacts(
                    primary_id, primary_type
                )

            if "opportunities" in include or "deals" in include or "all" in include:
                intelligence["related_opportunities"] = self._get_related_opportunities(
                    primary_id, primary_type
                )

            if "leads" in include or "all" in include:
                intelligence["related_leads"] = self._get_related_leads(
                    primary_id, primary_type
                )

            if "tasks" in include or "all" in include:
                intelligence["related_tasks"] = self._get_related_tasks(
                    primary_id, primary_type
                )

            if "companies" in include or "all" in include:
                intelligence["related_companies"] = self._get_related_companies(
                    primary_id, primary_type
                )

        return intelligence

    def _find_company_matches(self, name: str) -> List[MatchResult]:
        """Find company matches by name using fuzzy matching.

        Args:
            name: Company name to search for

        Returns:
            List of (company, score) tuples sorted by score descending
        """
        try:
            results = self.copper_client.search_companies({})
            if not results:
                logger.info(f"No companies found in CRM to search")
                return []

            logger.info(f"Searching {len(results)} companies for '{name}'")
            matches = self.fuzzy_matcher.match_companies(name, results)
            logger.info(f"Found {len(matches)} company matches for '{name}'")
            return matches

        except Exception as e:
            logger.error(f"Error finding company matches: {e}")
            return []

    def _find_person_matches(self, name: str) -> List[MatchResult]:
        """Find person matches by name using fuzzy matching.

        Args:
            name: Person name to search for

        Returns:
            List of (person, score) tuples sorted by score descending
        """
        try:
            results = self.copper_client.search_people({})
            if not results:
                return []

            matches = self.fuzzy_matcher.match_contacts(name, results)
            logger.info(f"Found {len(matches)} person matches for '{name}'")
            return matches

        except Exception as e:
            logger.error(f"Error finding person matches: {e}")
            return []

    def _find_opportunity_matches(self, name: str) -> List[MatchResult]:
        """Find opportunity matches by name using fuzzy matching.

        Args:
            name: Opportunity name to search for

        Returns:
            List of (opportunity, score) tuples sorted by score descending
        """
        try:
            results = self.copper_client.search_opportunities({})
            if not results:
                return []

            matches = self.fuzzy_matcher.match_opportunities(name, results)
            logger.info(f"Found {len(matches)} opportunity matches for '{name}'")
            return matches

        except Exception as e:
            logger.error(f"Error finding opportunity matches: {e}")
            return []

    def _find_company(self, name: str) -> Optional[JsonDict]:
        """Find a company by name using fuzzy matching.

        Args:
            name: Company name to search for

        Returns:
            Best matching company or None if no matches found
        """
        try:
            # Get all companies (or search with broad criteria)
            # Note: Copper API may have pagination limits
            results = self.copper_client.search_companies({})

            if not results:
                logger.info(f"No companies found in CRM")
                return None

            # Use fuzzy matcher to find best match
            matches = self.fuzzy_matcher.match_companies(name, results)

            if not matches:
                logger.info(f"No fuzzy matches found for company '{name}'")
                return None

            # Check if we have multiple close matches
            if self.fuzzy_matcher.has_multiple_close_matches(matches):
                logger.info(f"Multiple close matches found for '{name}': {[(m[0].get('name'), m[1]) for m in matches[:3]]}")
                # For now, return the best match but log the ambiguity
                # TODO: Implement confirmation flow

            best_match, score = matches[0]
            logger.info(f"Best company match: {best_match.get('name')} (score: {score:.1f})")
            return best_match

        except Exception as e:
            logger.error(f"Error finding company: {e}")
        return None

    def _find_person(self, name: str) -> Optional[JsonDict]:
        """Find a person by name using fuzzy matching.

        Args:
            name: Person name to search for

        Returns:
            Best matching person or None if no matches found
        """
        try:
            # Get all people (or search with broad criteria)
            results = self.copper_client.search_people({})

            if not results:
                logger.info(f"No people found in CRM")
                return None

            # Use fuzzy matcher to find best match
            matches = self.fuzzy_matcher.match_contacts(name, results)

            if not matches:
                logger.info(f"No fuzzy matches found for person '{name}'")
                return None

            # Check if we have multiple close matches
            if self.fuzzy_matcher.has_multiple_close_matches(matches):
                logger.info(f"Multiple close matches found for '{name}': {[(m[0].get('name'), m[1]) for m in matches[:3]]}")
                # For now, return the best match but log the ambiguity
                # TODO: Implement confirmation flow

            best_match, score = matches[0]
            logger.info(f"Best person match: {best_match.get('name')} (score: {score:.1f})")
            return best_match

        except Exception as e:
            logger.error(f"Error finding person: {e}")
        return None

    def _find_opportunity(self, name: str) -> Optional[JsonDict]:
        """Find an opportunity by name using fuzzy matching.

        Args:
            name: Opportunity name to search for

        Returns:
            Best matching opportunity or None if no matches found
        """
        try:
            # Get all opportunities (or search with broad criteria)
            results = self.copper_client.search_opportunities({})

            if not results:
                logger.info(f"No opportunities found in CRM")
                return None

            # Use fuzzy matcher to find best match
            matches = self.fuzzy_matcher.match_opportunities(name, results)

            if not matches:
                logger.info(f"No fuzzy matches found for opportunity '{name}'")
                return None

            # Check if we have multiple close matches
            if self.fuzzy_matcher.has_multiple_close_matches(matches):
                logger.info(f"Multiple close matches found for '{name}': {[(m[0].get('name'), m[1]) for m in matches[:3]]}")
                # For now, return the best match but log the ambiguity
                # TODO: Implement confirmation flow

            best_match, score = matches[0]
            logger.info(f"Best opportunity match: {best_match.get('name')} (score: {score:.1f})")
            return best_match

        except Exception as e:
            logger.error(f"Error finding opportunity: {e}")
        return None

    def _get_related_contacts(
        self, entity_id: int, entity_type: str
    ) -> JsonList:
        """Get contacts related to an entity."""
        try:
            if entity_type == "company":
                # Get people at this company
                return self.copper_client.search_people({"company_id": entity_id})
            elif entity_type == "opportunity":
                # Get primary contact for opportunity
                opp = self.copper_client.get_opportunity(entity_id)
                if opp and opp.get("primary_contact_id"):
                    person = self.copper_client.get_person(opp["primary_contact_id"])
                    return [person] if person else []
        except Exception as e:
            logger.error(f"Error getting related contacts: {e}")
        return []

    def _get_related_companies(
        self, entity_id: int, entity_type: str
    ) -> JsonList:
        """Get companies related to an entity."""
        try:
            if entity_type == "person":
                # Get company for this person
                person = self.copper_client.get_person(entity_id)
                if person and person.get("company_id"):
                    company = self.copper_client.get_company(person["company_id"])
                    return [company] if company else []
        except Exception as e:
            logger.error(f"Error getting related companies: {e}")
        return []

    def _get_related_opportunities(
        self, entity_id: int, entity_type: str
    ) -> JsonList:
        """Get opportunities related to an entity."""
        try:
            if entity_type == "company":
                return self.copper_client.search_opportunities({"company_ids": [entity_id]})
            elif entity_type == "person":
                return self.copper_client.search_opportunities({"primary_contact_ids": [entity_id]})
        except Exception as e:
            logger.error(f"Error getting related opportunities: {e}")
        return []

    def _get_related_leads(
        self, entity_id: int, entity_type: str
    ) -> JsonList:
        """Get leads related to an entity."""
        try:
            if entity_type == "company":
                return self.copper_client.search_leads({"company_id": entity_id})
            elif entity_type == "person":
                # Leads are linked by email/name matching
                person = self.copper_client.get_person(entity_id)
                if person and person.get("emails"):
                    email = person["emails"][0].get("email")
                    if email:
                        return self.copper_client.search_leads({"email": email})
        except Exception as e:
            logger.error(f"Error getting related leads: {e}")
        return []

    def _get_related_tasks(
        self, entity_id: int, entity_type: str
    ) -> JsonList:
        """Get tasks related to an entity."""
        try:
            # Tasks can be related to companies, people, or opportunities
            search_criteria = {}
            if entity_type == "company":
                search_criteria["related_resource"] = {"id": entity_id, "type": "company"}
            elif entity_type == "person":
                search_criteria["related_resource"] = {"id": entity_id, "type": "person"}
            elif entity_type == "opportunity":
                search_criteria["related_resource"] = {"id": entity_id, "type": "opportunity"}

            if search_criteria:
                return self.copper_client.search_tasks(search_criteria)
        except Exception as e:
            logger.error(f"Error getting related tasks: {e}")
        return []

    def format_intelligence(self, intelligence: Dict[str, Any], query: str, debug_info: Dict[str, Any] = None) -> str:
        """Format intelligence into a readable Slack message.

        Args:
            intelligence: Gathered intelligence data
            query: Original user query
            debug_info: Optional debug information to append

        Returns:
            Formatted message string
        """
        if not intelligence.get("primary_entity"):
            debug_section = self._format_debug_info(debug_info) if debug_info else ""
            return f"❌ I couldn't find any information matching your query.{debug_section}"

        primary = intelligence["primary_entity"]
        sections = []

        # Primary entity header
        entity_name = primary.get("name", "Unknown")
        sections.append(f"📊 *Business Intelligence: {entity_name}*\n")

        # Primary entity details
        if "company" in str(type(primary)).lower() or primary.get("type") == "company":
            sections.append(self._format_company(primary))
        elif "person" in str(type(primary)).lower() or primary.get("type") == "person":
            sections.append(self._format_person(primary))
        elif "opportunity" in str(type(primary)).lower():
            sections.append(self._format_opportunity(primary))

        # Related contacts
        if intelligence.get("related_contacts"):
            sections.append(f"\n👥 *Contacts ({len(intelligence['related_contacts'])})*")
            for contact in intelligence["related_contacts"][:5]:  # Limit to 5
                name = contact.get("name", "Unknown")
                email = contact.get("emails", [{}])[0].get("email", "No email")
                sections.append(f"  • {name} - {email}")
            if len(intelligence["related_contacts"]) > 5:
                sections.append(f"  _... and {len(intelligence['related_contacts']) - 5} more_")

        # Related companies
        if intelligence.get("related_companies"):
            sections.append(f"\n🏢 *Companies ({len(intelligence['related_companies'])})*")
            for company in intelligence["related_companies"][:5]:
                name = company.get("name", "Unknown")
                sections.append(f"  • {name}")

        # Related opportunities
        if intelligence.get("related_opportunities"):
            sections.append(f"\n💰 *Opportunities ({len(intelligence['related_opportunities'])})*")
            for opp in intelligence["related_opportunities"][:5]:
                name = opp.get("name", "Unknown")
                value = opp.get("monetary_value", 0)
                status = opp.get("status", "Unknown")
                sections.append(f"  • {name} - ${value:,} ({status})")
            if len(intelligence["related_opportunities"]) > 5:
                sections.append(f"  _... and {len(intelligence['related_opportunities']) - 5} more_")

        # Related leads
        if intelligence.get("related_leads"):
            sections.append(f"\n🎯 *Leads ({len(intelligence['related_leads'])})*")
            for lead in intelligence["related_leads"][:3]:
                name = lead.get("name", "Unknown")
                status = lead.get("status", "Unknown")
                sections.append(f"  • {name} ({status})")

        # Related tasks
        if intelligence.get("related_tasks"):
            sections.append(f"\n✅ *Tasks ({len(intelligence['related_tasks'])})*")
            for task in intelligence["related_tasks"][:3]:
                name = task.get("name", "Unknown")
                due = task.get("due_date", "No due date")
                sections.append(f"  • {name} - Due: {due}")

        # Add debug information
        if debug_info:
            sections.append(self._format_debug_info(debug_info))

        return "\n".join(sections)

    def format_confirmation_request(self, confirmation_data: Dict[str, Any]) -> str:
        """Format a confirmation request for ambiguous matches.

        Args:
            confirmation_data: Dict with entity_type, query, and matches

        Returns:
            Formatted message string asking user to confirm
        """
        entity_type = confirmation_data.get("entity_type", "entity")
        query = confirmation_data.get("query", "")
        matches = confirmation_data.get("matches", [])

        if not matches:
            return f"❌ No matches found for '{query}'"

        sections = [
            f"🔍 *Multiple matches found for '{query}'*\n",
            "Please confirm which one you meant:\n"
        ]

        # Format each match with score
        for idx, (entity, score) in enumerate(matches, 1):
            name = entity.get("name", "Unknown")

            # Add relevant context based on entity type
            context = ""
            if entity_type == "company":
                website = entity.get("website", "")
                if website:
                    context = f" - {website}"
                city = entity.get("address", {}).get("city", "")
                if city:
                    context += f" ({city})"
            elif entity_type == "person":
                title = entity.get("title", "")
                company_name = entity.get("company_name", "")
                if title or company_name:
                    context = f" - {title}" if title else ""
                    context += f" @ {company_name}" if company_name else ""
                email = entity.get("emails", [{}])[0].get("email", "")
                if email:
                    context += f" ({email})"
            elif entity_type == "opportunity":
                value = entity.get("monetary_value", 0)
                status = entity.get("status", "")
                if value or status:
                    context = f" - ${value:,}" if value else ""
                    context += f" ({status})" if status else ""

            sections.append(f"{idx}. {name}{context} _(match: {score:.0f}%)_")

        sections.append(
            "\n_Reply with the number (1-5) to confirm your choice, or 'cancel' to abort._"
        )

        return "\n".join(sections)

    def _format_debug_info(self, debug_info: Dict[str, Any]) -> str:
        """Format debug information for Slack message.

        Args:
            debug_info: Debug information dictionary

        Returns:
            Formatted debug section
        """
        lines = ["\n\n_🔍 Debug Info:_"]

        # Query analysis
        if "analysis" in debug_info and debug_info["analysis"]:
            analysis = debug_info["analysis"]
            lines.append(f"• Query understood as: *{analysis.get('entity_type', 'unknown')}* search")
            if analysis.get("entity_name"):
                lines.append(f"• Searching for: `{analysis.get('entity_name')}`")
            lines.append(f"• Intent: {analysis.get('intent', 'unknown')}")

        # Search results
        if "search_count" in debug_info:
            lines.append(f"• Searched {debug_info['search_count']} records")

        if "matches_found" in debug_info:
            lines.append(f"• Found {debug_info['matches_found']} fuzzy matches")

        if "best_score" in debug_info:
            lines.append(f"• Best match score: {debug_info['best_score']:.0f}%")

        # Errors
        if "error" in debug_info and debug_info["error"]:
            lines.append(f"• Error: {debug_info['error']}")

        return "\n".join(lines)

    def _format_company(self, company: JsonDict) -> str:
        """Format company details."""
        lines = ["*Company Details*"]
        if company.get("name"):
            lines.append(f"Name: {company['name']}")
        if company.get("website"):
            lines.append(f"Website: {company['website']}")
        if company.get("phone_numbers"):
            phone = company["phone_numbers"][0].get("number", "")
            if phone:
                lines.append(f"Phone: {phone}")
        if company.get("address"):
            addr = company["address"]
            city = addr.get("city", "")
            state = addr.get("state", "")
            if city or state:
                lines.append(f"Location: {city}, {state}")
        return "\n".join(lines)

    def _format_person(self, person: JsonDict) -> str:
        """Format person details."""
        lines = ["*Contact Details*"]
        if person.get("name"):
            lines.append(f"Name: {person['name']}")
        if person.get("title"):
            lines.append(f"Title: {person['title']}")
        if person.get("emails"):
            email = person["emails"][0].get("email", "")
            if email:
                lines.append(f"Email: {email}")
        if person.get("phone_numbers"):
            phone = person["phone_numbers"][0].get("number", "")
            if phone:
                lines.append(f"Phone: {phone}")
        return "\n".join(lines)

    def _format_opportunity(self, opp: JsonDict) -> str:
        """Format opportunity details."""
        lines = ["*Opportunity Details*"]
        if opp.get("name"):
            lines.append(f"Name: {opp['name']}")
        if opp.get("monetary_value"):
            lines.append(f"Value: ${opp['monetary_value']:,}")
        if opp.get("status"):
            lines.append(f"Status: {opp['status']}")
        if opp.get("close_date"):
            lines.append(f"Close Date: {opp['close_date']}")
        if opp.get("win_probability"):
            lines.append(f"Win Probability: {opp['win_probability']}%")
        return "\n".join(lines)

    def process_query(self, query: str) -> Dict[str, Any]:
        """Process a natural language business intelligence query.

        Args:
            query: Natural language query from user

        Returns:
            Dict with:
                - needs_confirmation: bool
                - message: str (formatted response)
                - confirmation_data: dict (if needs_confirmation is True)
                - analysis: dict (original query analysis)
        """
        try:
            # Analyze what the user is asking for
            analysis = self.analyze_query(query)
            logger.info(f"Query analysis: {analysis}")

            # Gather comprehensive intelligence
            intelligence = self.gather_intelligence(analysis)

            # Check if confirmation is needed
            if intelligence.get("needs_confirmation"):
                logger.info("Multiple matches found - requesting user confirmation")
                return {
                    "needs_confirmation": True,
                    "message": self.format_confirmation_request(intelligence),
                    "confirmation_data": intelligence,
                    "analysis": analysis
                }

            # Single match or no matches
            primary_entity = intelligence.get('primary_entity') or {}
            entity_name = primary_entity.get('name', 'unknown')
            logger.info(f"Gathered intelligence for {entity_name}")

            # Prepare debug info
            debug_info = intelligence.get("debug_info", {})
            debug_info["analysis"] = analysis

            # Format and return
            return {
                "needs_confirmation": False,
                "message": self.format_intelligence(intelligence, query, debug_info),
                "confirmation_data": None,
                "analysis": analysis
            }

        except Exception as e:
            logger.error(f"Error processing business intelligence query: {e}", exc_info=True)
            error_debug = {"error": str(e), "analysis": None}
            return {
                "needs_confirmation": False,
                "message": f"❌ Sorry, I encountered an error processing your query: {str(e)}\n\n{self._format_debug_info(error_debug)}",
                "confirmation_data": None,
                "analysis": None
            }
