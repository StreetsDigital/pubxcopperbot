"""Fuzzy matching engine for CRM queries with phonetic and string similarity."""

import logging
from typing import Any, Dict, List, Optional, Tuple

import jellyfish
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Type aliases
JsonDict = Dict[str, Any]
JsonList = List[JsonDict]
MatchResult = Tuple[JsonDict, float]  # (record, score)


class FuzzyMatcher:
    """Multi-strategy fuzzy matching for CRM entities."""

    def __init__(self, threshold: int = 65):
        """Initialize fuzzy matcher.

        Args:
            threshold: Minimum match score (0-100) to consider a match
        """
        self.threshold = threshold

    def match_contacts(
        self,
        query: str,
        contacts: JsonList,
        company_filter: Optional[str] = None
    ) -> List[MatchResult]:
        """Fuzzy match contacts by name, email, phone, or company.

        Args:
            query: Search term (name, email, phone)
            contacts: List of contact dicts from CRM
            company_filter: Optional company name filter

        Returns:
            List of (contact, score) tuples sorted by score descending
        """
        results = []

        for contact in contacts:
            # Apply company filter if specified
            if company_filter:
                company_name = contact.get("company_name", "")
                if not self._fuzzy_compare(company_filter, company_name, threshold=70):
                    continue

            # Build searchable fields
            searchable = self._build_contact_searchable(contact)

            # Calculate best match score
            score = self._calculate_best_score(query, searchable)

            if score >= self.threshold:
                results.append((contact, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def match_companies(
        self,
        query: str,
        companies: JsonList,
        industry_filter: Optional[str] = None
    ) -> List[MatchResult]:
        """Fuzzy match companies by name, domain, or industry.

        Args:
            query: Search term
            companies: List of company dicts from CRM
            industry_filter: Optional industry filter

        Returns:
            List of (company, score) tuples sorted by score descending
        """
        results = []

        for company in companies:
            # Apply industry filter if specified
            if industry_filter:
                industry = company.get("industry", "")
                if not self._fuzzy_compare(industry_filter, industry, threshold=70):
                    continue

            # Build searchable fields
            searchable = self._build_company_searchable(company)

            # Calculate best match score
            score = self._calculate_best_score(query, searchable)

            if score >= self.threshold:
                results.append((company, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def match_opportunities(
        self,
        query: str,
        opportunities: JsonList,
        stage_filter: Optional[str] = None
    ) -> List[MatchResult]:
        """Fuzzy match opportunities/deals by name, contact, company, or stage.

        Args:
            query: Search term
            opportunities: List of opportunity dicts from CRM
            stage_filter: Optional stage filter

        Returns:
            List of (opportunity, score) tuples sorted by score descending
        """
        results = []

        for opp in opportunities:
            # Apply stage filter if specified
            if stage_filter:
                stage = opp.get("status", "") or opp.get("stage", "")
                if not self._fuzzy_compare(stage_filter, stage, threshold=70):
                    continue

            # Build searchable fields
            searchable = self._build_opportunity_searchable(opp)

            # Calculate best match score
            score = self._calculate_best_score(query, searchable)

            if score >= self.threshold:
                results.append((opp, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def match_tasks(
        self,
        query: str,
        tasks: JsonList,
        assignee_filter: Optional[str] = None
    ) -> List[MatchResult]:
        """Fuzzy match tasks by name, description, or assignee.

        Args:
            query: Search term
            tasks: List of task dicts from CRM
            assignee_filter: Optional assignee filter

        Returns:
            List of (task, score) tuples sorted by score descending
        """
        results = []

        for task in tasks:
            # Apply assignee filter if specified
            if assignee_filter:
                assignee = task.get("assignee_name", "") or task.get("assignee", {}).get("name", "")
                if not self._fuzzy_compare(assignee_filter, assignee, threshold=70):
                    continue

            # Build searchable fields
            searchable = self._build_task_searchable(task)

            # Calculate best match score
            score = self._calculate_best_score(query, searchable)

            if score >= self.threshold:
                results.append((task, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _build_contact_searchable(self, contact: JsonDict) -> List[str]:
        """Build list of searchable strings for a contact."""
        searchable = []

        # Names
        if contact.get("name"):
            searchable.append(contact["name"])
        if contact.get("first_name") and contact.get("last_name"):
            full_name = f"{contact['first_name']} {contact['last_name']}"
            searchable.append(full_name)

        # Email
        if contact.get("emails"):
            for email_obj in contact["emails"]:
                if email_obj.get("email"):
                    searchable.append(email_obj["email"])

        # Phone
        if contact.get("phone_numbers"):
            for phone_obj in contact["phone_numbers"]:
                if phone_obj.get("number"):
                    searchable.append(phone_obj["number"])

        # Company
        if contact.get("company_name"):
            searchable.append(contact["company_name"])

        # Title
        if contact.get("title"):
            searchable.append(contact["title"])

        return searchable

    def _build_company_searchable(self, company: JsonDict) -> List[str]:
        """Build list of searchable strings for a company."""
        searchable = []

        # Name
        if company.get("name"):
            searchable.append(company["name"])

        # Website/Domain
        if company.get("website"):
            searchable.append(company["website"])

        # Industry
        if company.get("industry"):
            searchable.append(company["industry"])

        # Location
        if company.get("address"):
            addr = company["address"]
            if addr.get("city"):
                searchable.append(addr["city"])
            if addr.get("state"):
                searchable.append(addr["state"])

        return searchable

    def _build_opportunity_searchable(self, opp: JsonDict) -> List[str]:
        """Build list of searchable strings for an opportunity."""
        searchable = []

        # Name
        if opp.get("name"):
            searchable.append(opp["name"])

        # Company name (if available)
        if opp.get("company_name"):
            searchable.append(opp["company_name"])

        # Contact name (if available)
        if opp.get("contact_name"):
            searchable.append(opp["contact_name"])

        # Stage/Status
        if opp.get("status"):
            searchable.append(opp["status"])
        if opp.get("stage"):
            searchable.append(opp["stage"])

        return searchable

    def _build_task_searchable(self, task: JsonDict) -> List[str]:
        """Build list of searchable strings for a task."""
        searchable = []

        # Name/Title
        if task.get("name"):
            searchable.append(task["name"])

        # Description/Details
        if task.get("details"):
            searchable.append(task["details"])

        # Assignee name
        if task.get("assignee_name"):
            searchable.append(task["assignee_name"])
        elif task.get("assignee") and isinstance(task["assignee"], dict):
            if task["assignee"].get("name"):
                searchable.append(task["assignee"]["name"])

        # Related entity names (if available)
        if task.get("related_resource"):
            related = task["related_resource"]
            if related.get("name"):
                searchable.append(related["name"])

        # Status
        if task.get("status"):
            searchable.append(task["status"])

        # Priority
        if task.get("priority"):
            searchable.append(task["priority"])

        return searchable

    def _calculate_best_score(self, query: str, candidates: List[str]) -> float:
        """Calculate best match score across multiple matching strategies.

        Args:
            query: Search query string
            candidates: List of strings to match against

        Returns:
            Best score (0-100) across all strategies
        """
        if not candidates:
            return 0.0

        best_score = 0.0

        for candidate in candidates:
            if not candidate:
                continue

            score = self._match_score(query, candidate)
            best_score = max(best_score, score)

        return best_score

    def _match_score(self, query: str, candidate: str) -> float:
        """Calculate match score between query and candidate using multiple strategies.

        Matching priority:
        1. Exact match (score: 100)
        2. Phonetic match + high fuzzy score (boost +15)
        3. Token set ratio > 80
        4. Partial ratio > 75

        Args:
            query: Search query
            candidate: Candidate string to match

        Returns:
            Match score (0-100)
        """
        query_lower = query.lower().strip()
        candidate_lower = candidate.lower().strip()

        # 1. Exact match
        if query_lower == candidate_lower:
            return 100.0

        # 2. Check for phonetic similarity
        phonetic_match = self._phonetic_similarity(query_lower, candidate_lower)

        # 3. String similarity scores
        token_set = fuzz.token_set_ratio(query_lower, candidate_lower)
        partial = fuzz.partial_ratio(query_lower, candidate_lower)
        ratio = fuzz.ratio(query_lower, candidate_lower)

        # Take the best string similarity score
        best_fuzzy = max(token_set, partial, ratio)

        # 4. Apply phonetic boost if applicable
        if phonetic_match and best_fuzzy >= 70:
            # Phonetic match + good fuzzy score = boost
            final_score = min(100.0, best_fuzzy + 15)
        else:
            final_score = best_fuzzy

        return final_score

    def _phonetic_similarity(self, str1: str, str2: str) -> bool:
        """Check if two strings are phonetically similar.

        Uses both metaphone and soundex for broader coverage.

        Args:
            str1: First string
            str2: Second string

        Returns:
            True if phonetically similar
        """
        try:
            # Metaphone comparison (better for names)
            meta1 = jellyfish.metaphone(str1)
            meta2 = jellyfish.metaphone(str2)

            if meta1 and meta2 and meta1 == meta2:
                return True

            # Soundex comparison (backup)
            soundex1 = jellyfish.soundex(str1)
            soundex2 = jellyfish.soundex(str2)

            if soundex1 and soundex2 and soundex1 == soundex2:
                return True

        except Exception as e:
            logger.debug(f"Phonetic comparison error: {e}")

        return False

    def _fuzzy_compare(self, query: str, target: str, threshold: int = 80) -> bool:
        """Simple fuzzy comparison for filtering.

        Args:
            query: Query string
            target: Target string to compare
            threshold: Minimum score to consider a match

        Returns:
            True if match score exceeds threshold
        """
        if not query or not target:
            return False

        score = fuzz.token_set_ratio(query.lower(), target.lower())
        return score >= threshold

    def get_top_matches(
        self,
        results: List[MatchResult],
        top_n: int = 5
    ) -> List[MatchResult]:
        """Get top N matches from results.

        Args:
            results: List of (record, score) tuples
            top_n: Number of top matches to return

        Returns:
            Top N matches
        """
        return results[:top_n]

    def has_multiple_close_matches(
        self,
        results: List[MatchResult],
        score_delta: float = 10.0
    ) -> bool:
        """Check if there are multiple matches with similar scores.

        Args:
            results: List of (record, score) tuples
            score_delta: Maximum score difference to consider "close"

        Returns:
            True if multiple matches within score_delta of top score
        """
        if len(results) < 2:
            return False

        top_score = results[0][1]

        close_matches = sum(
            1 for _, score in results
            if top_score - score <= score_delta
        )

        return close_matches >= 2
