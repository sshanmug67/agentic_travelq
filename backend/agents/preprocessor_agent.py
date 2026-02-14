"""
Preprocessor Agent — Natural Language Override Layer
Location: backend/agents/preprocessor_agent.py

Parses user-typed text from the "Refine Your Search" text box and merges
the extracted intent into the existing TravelPreferences.

This agent runs BEFORE the orchestrator — it's a gatekeeper, not a
group chat participant. It uses the same LLM + logging infrastructure
as other agents but operates independently.

Priority model:
    User text  >  Preferences panel  >  Summary bar
    (highest)     (medium)              (lowest)

Merge semantics (determined by LLM):
    REPLACE — User states a new value: "fly to Boston" → destination = Boston
    ADD     — User says "also add" or "include": "add AA" → append to carriers
    DELETE  — User says "remove" or "no": "remove Delta" → remove from carriers
    KEEP    — Field not mentioned → unchanged

Usage:
    from agents.preprocessor_agent import PreprocessorAgent

    agent = PreprocessorAgent(trip_id=trip_id, trip_storage=storage)
    merged_prefs, changes = agent.process(
        user_text="Find direct flights to Boston, add American Airlines",
        base_prefs=travel_preferences
    )
"""
import json
import re
import time
from typing import Dict, Any, List, Optional, Tuple

from agents.base_agent import TravelQBaseAgent
from services.storage.storage_base import TripStorageInterface
from config.settings import settings
from utils.logging_config import log_agent_raw, log_agent_json
import openai


class PreprocessorAgent(TravelQBaseAgent):
    """
    Pre-orchestration agent that parses natural language user requests
    and merges them into TravelPreferences.
    
    Runs BEFORE the group chat — not a participant in multi-agent conversation.
    Uses LLM to interpret user intent (replace/add/delete) per field.
    """

    def __init__(self, trip_id: str, trip_storage: TripStorageInterface, **kwargs):
        system_message = """You are a travel preferences parser. Given a user's natural language request
and their current travel preferences, extract ONLY the fields the user wants to change.

RULES:
1. ONLY include fields the user explicitly mentions or clearly implies.
2. For each field, determine the ACTION:
   - "replace": User states a new value (e.g., "fly to Boston" → replace destination)
   - "add": User says "add", "also", "include", "as well" (e.g., "add American Airlines")
   - "delete": User says "remove", "drop", "no", "without" (e.g., "remove Delta")
3. If a field is NOT mentioned, do NOT include it in the output.
4. For budget changes, just change total_budget — sub-budgets will be recalculated.
5. For dates, output in YYYY-MM-DD format.
6. For airlines/hotels/cuisines/activities, use standard names.

You MUST respond with ONLY valid JSON — no markdown, no backticks, no extra text."""

        super().__init__(
            name="PreprocessorAgent",
            llm_config=TravelQBaseAgent.create_llm_config(),
            agent_type="PreprocessorAgent",
            system_message=system_message,
            description="Parses natural language travel requests into structured preference overrides",
            **kwargs
        )

        self.trip_id = trip_id
        self.trip_storage = trip_storage

        log_agent_raw("🧠 PreprocessorAgent initialized", agent_name="PreprocessorAgent")

    # ─────────────────────────────────────────────────────────────────────
    # PUBLIC API — called by trip_planning_service BEFORE orchestrator
    # ─────────────────────────────────────────────────────────────────────

    def process(
        self,
        user_text: str,
        base_prefs: Any,
    ) -> Tuple[Any, List[Dict[str, str]]]:
        """
        Parse user's natural language text and merge into TravelPreferences.

        Args:
            user_text: Raw text from "Refine Your Search" text box
            base_prefs: Current TravelPreferences (from summary bar + preferences panel)

        Returns:
            Tuple of:
                - merged TravelPreferences (updated Pydantic model)
                - changes_log: list of {"field", "action", "old", "new"}
        """
        if not user_text or not user_text.strip():
            return base_prefs, []

        user_text = user_text.strip()

        log_agent_raw("=" * 80, agent_name="PreprocessorAgent")
        log_agent_raw("🧠 PREPROCESSING USER REQUEST", agent_name="PreprocessorAgent")
        log_agent_raw("=" * 80, agent_name="PreprocessorAgent")
        log_agent_raw(f"   User text: \"{user_text}\"", agent_name="PreprocessorAgent")

        self.log_conversation_message(
            message_type="INCOMING",
            content=user_text,
            sender="User",
            truncate=500
        )

        start_time = time.time()

        # Step 1: Get current preferences as dict for LLM context
        current_prefs_dict = base_prefs.model_dump()

        # Step 2: LLM extracts structured overrides
        overrides = self._extract_overrides(user_text, current_prefs_dict)

        if not overrides:
            log_agent_raw("   ℹ️  No actionable overrides extracted — using base preferences",
                         agent_name="PreprocessorAgent")
            return base_prefs, []

        log_agent_json(
            overrides,
            label="Extracted Overrides",
            agent_name="PreprocessorAgent"
        )

        # Step 3: Merge overrides into base preferences
        merged_prefs, changes_log = self._merge_overrides(base_prefs, overrides)

        duration = time.time() - start_time

        # Step 4: Log results
        if changes_log:
            log_agent_raw(f"   📝 {len(changes_log)} field(s) changed in {duration:.2f}s:",
                         agent_name="PreprocessorAgent")
            for change in changes_log:
                icon = {"replace": "🔄", "add": "➕", "delete": "➖"}.get(change["action"], "❓")
                log_agent_raw(
                    f"     {icon} {change['field']}: {change.get('old', '?')} → {change.get('new', '?')}",
                    agent_name="PreprocessorAgent"
                )
        else:
            log_agent_raw("   ℹ️  No changes applied after merge",
                         agent_name="PreprocessorAgent")

        # Log API call for cost tracking
        self.trip_storage.log_api_call(
            trip_id=self.trip_id,
            agent_name="PreprocessorAgent",
            api_name="OpenAI",
            duration=duration
        )

        self.log_conversation_message(
            message_type="OUTGOING",
            content=f"Applied {len(changes_log)} override(s): "
                    + ", ".join(c["field"] for c in changes_log),
            sender="PreprocessorAgent",
            truncate=1000
        )

        log_agent_raw("=" * 80, agent_name="PreprocessorAgent")

        return merged_prefs, changes_log

    # ─────────────────────────────────────────────────────────────────────
    # generate_reply — NOT USED (this agent doesn't join group chat)
    # Required by TravelQBaseAgent but we never call it.
    # ─────────────────────────────────────────────────────────────────────

    def generate_reply(
        self,
        messages: List[Dict[str, Any]] = None,
        sender: Any = None,
        config: Any = None
    ) -> str:
        """Not used — PreprocessorAgent runs before the group chat."""
        return self.signal_completion(
            "PreprocessorAgent does not participate in group chat."
        )

    # ─────────────────────────────────────────────────────────────────────
    # LLM EXTRACTION
    # ─────────────────────────────────────────────────────────────────────

    _EXTRACTION_PROMPT = """USER'S TEXT: "{user_text}"

CURRENT PREFERENCES:
{current_prefs_json}

Extract the user's intended changes. Return ONLY a JSON object with this structure:
{{
  "changes": [
    {{
      "field": "<dot-path to field>",
      "action": "<replace | add | delete>",
      "value": <the new value — string, number, or array depending on field>
    }}
  ]
}}

FIELD MAPPING (use these exact dot-paths):
- Trip details: "destination", "origin", "departure_date", "return_date", "num_travelers", "trip_purpose"
- Flight: "flight_prefs.preferred_carriers", "flight_prefs.interested_carriers",
          "flight_prefs.max_stops", "flight_prefs.cabin_class", "flight_prefs.time_preference",
          "flight_prefs.seat_preference"
- Hotel: "hotel_prefs.preferred_chains", "hotel_prefs.interested_chains",
         "hotel_prefs.min_rating", "hotel_prefs.preferred_location", "hotel_prefs.amenities",
         "hotel_prefs.room_type", "hotel_prefs.price_range"
- Activities: "activity_prefs.preferred_interests", "activity_prefs.interested_interests",
              "activity_prefs.pace"
- Restaurant: "restaurant_prefs.preferred_cuisines", "restaurant_prefs.interested_cuisines",
              "restaurant_prefs.meals", "restaurant_prefs.price_level"
- Budget: "budget.total_budget"
- Special: "special_requirements"

EXAMPLES:

User: "Find direct flights to Boston"
→ {{"changes": [
    {{"field": "destination", "action": "replace", "value": "Boston"}},
    {{"field": "flight_prefs.max_stops", "action": "replace", "value": 0}}
  ]}}

User: "Add American Airlines and remove Delta"
→ {{"changes": [
    {{"field": "flight_prefs.preferred_carriers", "action": "add", "value": ["American Airlines"]}},
    {{"field": "flight_prefs.preferred_carriers", "action": "delete", "value": ["Delta"]}}
  ]}}

User: "I want Hilton hotels, budget $5000, and Japanese food"
→ {{"changes": [
    {{"field": "hotel_prefs.preferred_chains", "action": "replace", "value": ["Hilton"]}},
    {{"field": "budget.total_budget", "action": "replace", "value": 5000}},
    {{"field": "restaurant_prefs.preferred_cuisines", "action": "replace", "value": ["Japanese"]}}
  ]}}

User: "Find cheaper flights"
→ {{"changes": [
    {{"field": "flight_prefs.cabin_class", "action": "replace", "value": "economy"}}
  ]}}

User: "3 travelers, business class"
→ {{"changes": [
    {{"field": "num_travelers", "action": "replace", "value": 3}},
    {{"field": "flight_prefs.cabin_class", "action": "replace", "value": "business"}}
  ]}}

User: "I prefer direct flights only"
→ {{"changes": [
    {{"field": "flight_prefs.max_stops", "action": "replace", "value": 0}}
  ]}}

User: "Also include Italian restaurants and add walking tours"
→ {{"changes": [
    {{"field": "restaurant_prefs.preferred_cuisines", "action": "add", "value": ["Italian"]}},
    {{"field": "activity_prefs.preferred_interests", "action": "add", "value": ["Walking Tours"]}}
  ]}}

User: "Remove museums, I want nightlife instead"
→ {{"changes": [
    {{"field": "activity_prefs.preferred_interests", "action": "delete", "value": ["Museums"]}},
    {{"field": "activity_prefs.preferred_interests", "action": "add", "value": ["Nightlife"]}}
  ]}}

User: "Find flights for next Friday to Sunday"
→ {{"changes": [
    {{"field": "departure_date", "action": "replace", "value": "<YYYY-MM-DD for next Friday>"}},
    {{"field": "return_date", "action": "replace", "value": "<YYYY-MM-DD for next Sunday>"}}
  ]}}

Now extract changes for the given user text. Return valid JSON only.
"""

    def _extract_overrides(
        self,
        user_text: str,
        current_prefs_dict: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Call LLM to extract structured overrides from user's natural language.
        Returns list of {field, action, value} dicts, or None on failure.
        """
        prefs_json = json.dumps(current_prefs_dict, indent=2, default=str)

        prompt = self._EXTRACTION_PROMPT.format(
            user_text=user_text,
            current_prefs_json=prefs_json
        )

        log_agent_raw("   🤖 Calling LLM to extract overrides...", agent_name="PreprocessorAgent")

        try:
            client = openai.OpenAI(api_key=settings.openai_api_key)

            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=600
            )

            raw_response = response.choices[0].message.content.strip()
            log_agent_raw(f"   📥 LLM response: {raw_response[:500]}",
                         agent_name="PreprocessorAgent")

            result = self._parse_llm_json(raw_response)
            if not result:
                log_agent_raw("   ❌ Failed to parse LLM JSON response",
                             agent_name="PreprocessorAgent")
                return None

            changes = result.get("changes", [])
            if not isinstance(changes, list):
                log_agent_raw(f"   ❌ 'changes' is not a list: {type(changes)}",
                             agent_name="PreprocessorAgent")
                return None

            # Validate each change
            validated = []
            for change in changes:
                if all(k in change for k in ("field", "action", "value")):
                    if change["action"] in ("replace", "add", "delete"):
                        validated.append(change)
                    else:
                        log_agent_raw(
                            f"   ⚠️  Unknown action '{change['action']}', skipping",
                            agent_name="PreprocessorAgent"
                        )
                else:
                    log_agent_raw(
                        f"   ⚠️  Malformed change entry, skipping: {change}",
                        agent_name="PreprocessorAgent"
                    )

            return validated if validated else None

        except Exception as e:
            log_agent_raw(f"   ❌ LLM extraction failed: {str(e)}",
                         agent_name="PreprocessorAgent")
            return None

    # ─────────────────────────────────────────────────────────────────────
    # MERGE LOGIC
    # ─────────────────────────────────────────────────────────────────────

    def _merge_overrides(
        self,
        base_prefs: Any,
        overrides: List[Dict[str, Any]]
    ) -> Tuple[Any, List[Dict[str, str]]]:
        """
        Apply overrides to TravelPreferences using replace/add/delete semantics.
        Returns (new_prefs, changes_log).
        """
        prefs_dict = base_prefs.model_dump()
        changes_log = []

        for override in overrides:
            field_path = override["field"]
            action = override["action"]
            value = override["value"]

            try:
                old_value = _get_nested(prefs_dict, field_path)

                if action == "replace":
                    _set_nested(prefs_dict, field_path, value)
                    changes_log.append({
                        "field": field_path,
                        "action": "replace",
                        "old": _safe_str(old_value),
                        "new": _safe_str(value)
                    })

                elif action == "add":
                    if isinstance(old_value, list):
                        items_to_add = value if isinstance(value, list) else [value]
                        existing_lower = {
                            item.lower() for item in old_value if isinstance(item, str)
                        }
                        new_items = [
                            item for item in items_to_add
                            if isinstance(item, str) and item.lower() not in existing_lower
                        ]
                        if new_items:
                            merged_list = old_value + new_items
                            _set_nested(prefs_dict, field_path, merged_list)
                            changes_log.append({
                                "field": field_path,
                                "action": "add",
                                "old": _safe_str(old_value),
                                "new": _safe_str(merged_list)
                            })
                    else:
                        # Non-list field: "add" falls back to "replace"
                        _set_nested(prefs_dict, field_path, value)
                        changes_log.append({
                            "field": field_path,
                            "action": "replace",
                            "old": _safe_str(old_value),
                            "new": _safe_str(value)
                        })

                elif action == "delete":
                    if isinstance(old_value, list):
                        items_to_remove = value if isinstance(value, list) else [value]
                        remove_lower = {
                            item.lower() for item in items_to_remove
                            if isinstance(item, str)
                        }
                        filtered_list = [
                            item for item in old_value
                            if not (isinstance(item, str) and item.lower() in remove_lower)
                        ]
                        if len(filtered_list) != len(old_value):
                            _set_nested(prefs_dict, field_path, filtered_list)
                            changes_log.append({
                                "field": field_path,
                                "action": "delete",
                                "old": _safe_str(old_value),
                                "new": _safe_str(filtered_list)
                            })
                    else:
                        _set_nested(prefs_dict, field_path, None)
                        changes_log.append({
                            "field": field_path,
                            "action": "delete",
                            "old": _safe_str(old_value),
                            "new": "None"
                        })

            except Exception as e:
                log_agent_raw(
                    f"   ⚠️  Failed to apply override for '{field_path}': {e}",
                    agent_name="PreprocessorAgent"
                )
                continue

        # Recalculate sub-budgets if total changed
        if any(c["field"] == "budget.total_budget" for c in changes_log):
            self._recalculate_budget(prefs_dict)
            log_agent_raw("   💰 Sub-budgets recalculated from new total",
                         agent_name="PreprocessorAgent")

        # Rebuild TravelPreferences from modified dict
        try:
            from models.user_preferences import TravelPreferences
            merged_prefs = TravelPreferences(**prefs_dict)
            return merged_prefs, changes_log
        except Exception as e:
            log_agent_raw(f"   ❌ Failed to rebuild TravelPreferences: {e}",
                         agent_name="PreprocessorAgent")
            return base_prefs, []

    # ─────────────────────────────────────────────────────────────────────
    # BUDGET RECALCULATION
    # ─────────────────────────────────────────────────────────────────────

    def _recalculate_budget(self, prefs_dict: Dict[str, Any]):
        """
        Recalculate sub-budgets proportionally when total_budget changes.
        Same heuristic ratios as to_request_dict().
        """
        budget = prefs_dict.get("budget", {})
        total = budget.get("total_budget", 0)
        if not total or total <= 0:
            return

        num_days = 1
        dep = prefs_dict.get("departure_date", "")
        ret = prefs_dict.get("return_date", "")
        if dep and ret:
            try:
                from datetime import datetime
                start = datetime.fromisoformat(dep)
                end = datetime.fromisoformat(ret)
                num_days = max((end - start).days, 1)
            except (ValueError, TypeError):
                num_days = 5

        budget["flight_budget"] = round(total * 0.30, 2)
        budget["hotel_budget_per_night"] = round((total * 0.35) / num_days, 2)
        budget["daily_activity_budget"] = round((total * 0.15) / num_days, 2)
        budget["daily_food_budget"] = round((total * 0.15) / num_days, 2)
        budget["transport_budget"] = round(total * 0.05, 2)

    # ─────────────────────────────────────────────────────────────────────
    # JSON PARSING
    # ─────────────────────────────────────────────────────────────────────

    def _parse_llm_json(self, text: str) -> Optional[Dict]:
        """Parse LLM JSON response, handling markdown fences."""
        cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned.strip())
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            brace_start = cleaned.find('{')
            if brace_start >= 0:
                depth = 0
                for i in range(brace_start, len(cleaned)):
                    if cleaned[i] == '{':
                        depth += 1
                    elif cleaned[i] == '}':
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(cleaned[brace_start:i + 1])
                            except json.JSONDecodeError:
                                break
        return None


# ============================================================================
# MODULE-LEVEL HELPERS (pure functions — no LLM, no state)
# ============================================================================

def _get_nested(d: Dict, path: str) -> Any:
    """Get a value from a nested dict using dot-notation path."""
    keys = path.split(".")
    current = d
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


def _set_nested(d: Dict, path: str, value: Any):
    """Set a value in a nested dict using dot-notation path."""
    keys = path.split(".")
    current = d
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def _safe_str(val: Any) -> str:
    """Safely convert a value to string for logging."""
    if val is None:
        return "None"
    if isinstance(val, list):
        if len(val) > 5:
            return f"[{', '.join(str(v) for v in val[:5])}, ... +{len(val) - 5} more]"
        return str(val)
    return str(val)


# ============================================================================
# FACTORY
# ============================================================================

def create_preprocessor_agent(
    trip_id: str,
    trip_storage: TripStorageInterface,
    **kwargs
) -> PreprocessorAgent:
    """Factory function to create PreprocessorAgent."""
    return PreprocessorAgent(trip_id=trip_id, trip_storage=trip_storage, **kwargs)