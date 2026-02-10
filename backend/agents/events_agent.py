"""
Mock Events Agent - Returns Structured Mock Data
Location: backend/agents/events_agent.py
"""
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
import random

from agents.base_agent import TravelQBaseAgent
from models.trip import Event
from utils.logging_config import log_agent_raw, log_agent_json


class EventsAgent(TravelQBaseAgent):
    """
    Mock Events Agent - Returns structured event data
    """
    
    def __init__(self, **kwargs):
        system_message = """
You are an Events & Activities Agent specializing in finding local events.

Your job:
1. Find concerts, shows, festivals, sports events during travel dates
2. Consider user interests and preferences
3. Include venue, time, pricing information
4. Highlight special or unique events

Always return results in structured format with event details.
"""
        super().__init__(
            name="EventsAgent",
            llm_config=self.create_llm_config(),
            system_message=system_message,
            description="Finds concerts, shows, festivals, and local events during travel dates",  # ✅ Added
            **kwargs
        )
        
        log_agent_raw("🎭 EventsAgent initialized (MOCK MODE)", agent_name="EventsAgent")
    
    def generate_reply(
        self,
        messages: List[Dict[str, Any]] = None,
        sender: Any = None,
        config: Any = None,
    ) -> str:  # ✅ Fixed: Changed from tuple to str
        """
        Generate event search results
        
        Returns structured mock data
        """
        log_agent_raw("🔍 Searching for events (mock data)...", agent_name="EventsAgent")
        
        # ✅ ADD THIS - Log incoming message
        if messages and len(messages) > 0:
            last_message = messages[-1].get("content", "")
            sender_name = sender.name if sender and hasattr(sender, 'name') else "Unknown"
            self.log_conversation_message(
                message_type="INCOMING",
                content=last_message,
                sender=sender_name
            )

        # Get preferences from conversation
        preferences = self._extract_preferences_from_messages(messages)
        
        # Generate mock events
        mock_events = self._generate_mock_events(preferences)
        
        # Create structured response
        response = self._create_structured_response(mock_events, preferences)
        
        log_agent_json({
            "events_found": len(mock_events),
            "destination": preferences.get("destination", "Unknown"),
            "date_range": f"{preferences.get('departure_date')} to {preferences.get('return_date')}"
        }, agent_name="EventsAgent", label="Mock Events Search")
        
        # ✅ ADD THIS - Log outgoing response
        self.log_conversation_message(
            message_type="OUTGOING",
            content=response,
            sender="chat_manager"
        )

        return self.signal_completion(response)  # ✅ Fixed: Return string only
    
    def _extract_preferences_from_messages(self, messages: List[Dict]) -> Dict:
        """Extract preferences from conversation"""
        return {
            "destination": "Tokyo",
            "departure_date": "2026-06-01",
            "return_date": "2026-06-08",
            "interests": ["culture", "food", "music"]
        }
    
    def _generate_mock_events(self, preferences: Dict) -> List[Event]:
        """Generate realistic mock event data"""
        destination = preferences.get("destination", "Tokyo")
        start_date = preferences.get("departure_date", "2026-06-01")
        
        # Parse date
        try:
            start_dt = datetime.fromisoformat(start_date)
        except:
            start_dt = datetime.now() + timedelta(days=30)
        
        # Generate diverse events
        events = [
            Event(
                id="event_001",
                name="Tokyo International Film Festival",
                description="Annual film festival showcasing Japanese and international cinema. Special screenings and director Q&As.",
                venue="Roppongi Hills",
                address="6-10-1 Roppongi, Minato City, Tokyo",
                start_time=start_dt.replace(hour=18, minute=0),
                end_time=start_dt.replace(hour=22, minute=0),
                category="Film & Arts",
                price_range="$15-$45",
                ticket_url="https://example.com/tickets/tiff",
                image_url="https://example.com/images/film-festival.jpg",
                is_free=False
            ),
            Event(
                id="event_002",
                name="Sumo Wrestling Tournament",
                description="Traditional sumo wrestling matches at the historic Ryōgoku Kokugikan. Experience authentic Japanese culture.",
                venue="Ryōgoku Kokugikan",
                address="1-3-28 Yokoami, Sumida City, Tokyo",
                start_time=(start_dt + timedelta(days=2)).replace(hour=16, minute=0),
                end_time=(start_dt + timedelta(days=2)).replace(hour=18, minute=0),
                category="Sports & Culture",
                price_range="$25-$150",
                ticket_url="https://example.com/tickets/sumo",
                image_url="https://example.com/images/sumo.jpg",
                is_free=False
            ),
            Event(
                id="event_003",
                name="Tsukiji Fish Market Food Tour",
                description="Early morning guided tour of the famous Tsukiji Outer Market. Sample fresh sushi and local delicacies.",
                venue="Tsukiji Outer Market",
                address="4 Chome Tsukiji, Chuo City, Tokyo",
                start_time=(start_dt + timedelta(days=1)).replace(hour=7, minute=0),
                end_time=(start_dt + timedelta(days=1)).replace(hour=10, minute=0),
                category="Food & Culture",
                price_range="$65-$85",
                ticket_url="https://example.com/tickets/tsukiji-tour",
                image_url="https://example.com/images/tsukiji.jpg",
                is_free=False
            ),
            Event(
                id="event_004",
                name="Senso-ji Temple Evening Illumination",
                description="Free evening illumination of Tokyo's oldest temple. Beautiful photo opportunities and traditional atmosphere.",
                venue="Senso-ji Temple",
                address="2-3-1 Asakusa, Taito City, Tokyo",
                start_time=(start_dt + timedelta(days=3)).replace(hour=18, minute=30),
                end_time=(start_dt + timedelta(days=3)).replace(hour=21, minute=0),
                category="Culture & Sightseeing",
                price_range="Free",
                ticket_url=None,
                image_url="https://example.com/images/sensoji.jpg",
                is_free=True
            ),
            Event(
                id="event_005",
                name="J-Pop Concert: Tomorrow's Stars",
                description="Popular J-Pop group performing their latest hits. Opening act by emerging local artists.",
                venue="Tokyo Dome City Hall",
                address="1-3-61 Koraku, Bunkyo City, Tokyo",
                start_time=(start_dt + timedelta(days=4)).replace(hour=19, minute=0),
                end_time=(start_dt + timedelta(days=4)).replace(hour=22, minute=0),
                category="Music & Entertainment",
                price_range="$45-$120",
                ticket_url="https://example.com/tickets/jpop",
                image_url="https://example.com/images/jpop.jpg",
                is_free=False
            ),
            Event(
                id="event_006",
                name="Traditional Tea Ceremony Workshop",
                description="Learn the art of Japanese tea ceremony from a master. Includes matcha tasting and kimono rental.",
                venue="Happoen Garden",
                address="1-1-1 Shirokanedai, Minato City, Tokyo",
                start_time=(start_dt + timedelta(days=5)).replace(hour=14, minute=0),
                end_time=(start_dt + timedelta(days=5)).replace(hour=16, minute=30),
                category="Culture & Workshop",
                price_range="$75-$95",
                ticket_url="https://example.com/tickets/tea-ceremony",
                image_url="https://example.com/images/tea-ceremony.jpg",
                is_free=False
            ),
            Event(
                id="event_007",
                name="Shibuya Crossing Night Walk",
                description="Free guided walking tour of Shibuya's iconic crossing and nightlife district. Meet new travelers!",
                venue="Shibuya Crossing",
                address="Shibuya City, Tokyo",
                start_time=(start_dt + timedelta(days=6)).replace(hour=19, minute=30),
                end_time=(start_dt + timedelta(days=6)).replace(hour=21, minute=30),
                category="Sightseeing & Social",
                price_range="Free",
                ticket_url=None,
                image_url="https://example.com/images/shibuya.jpg",
                is_free=True
            ),
        ]
        
        return events
    
    def _create_structured_response(self, events: List[Event], preferences: Dict) -> str:
        """Create response with structured data"""
        
        # ✅ Use model_dump(mode='json') to handle datetime serialization
        event_data = [event.model_dump(mode='json') for event in events]
        
        # Create structured data block
        structured = {
            "agent": "EventsAgent",
            "type": "event_results",
            "data": event_data
        }
        
        # Categorize events
        free_events = [e for e in events if e.is_free]
        cultural_events = [e for e in events if "culture" in e.category.lower()]
        food_events = [e for e in events if "food" in e.category.lower()]
        
        # Create natural language summary
        summary = f"""
I found {len(events)} exciting events happening in {preferences.get('destination', 'Tokyo')} during your trip!

**Event Highlights:**

"""
        
        # Highlight top events
        for i, event in enumerate(events[:3], 1):
            date_str = event.start_time.strftime("%B %d, %I:%M %p")
            free_tag = " 🆓" if event.is_free else ""
            
            summary += f"""
**{i}. {event.name}**{free_tag}
- When: {date_str}
- Where: {event.venue}
- Category: {event.category}
- Price: {event.price_range}
- {event.description}
"""
        
        # Add quick summary of remaining events
        if len(events) > 3:
            summary += f"\n**Plus {len(events) - 3} more events including:**\n"
            for event in events[3:]:
                free_tag = " 🆓" if event.is_free else ""
                summary += f"- {event.name}{free_tag} ({event.category})\n"
        
        # Add recommendations
        summary += f"""

**Recommendations:**
"""
        
        if free_events:
            summary += f"- 💰 {len(free_events)} FREE events available - great for budget-conscious travelers\n"
        
        if cultural_events:
            summary += f"- 🎎 {len(cultural_events)} cultural experiences - perfect for immersing in local traditions\n"
        
        if food_events:
            summary += f"- 🍜 {len(food_events)} food-related events - must-try for foodies\n"
        
        summary += """
**Booking Tips:**
- Popular events sell out fast - book tickets early
- Some venues offer combo deals with nearby attractions
- Check cancellation policies before booking
"""
        
        summary += f"""

<STRUCTURED_DATA>
{json.dumps(structured, indent=2)}
</STRUCTURED_DATA>
"""
        
        return summary


def create_events_agent() -> EventsAgent:
    """Factory function to create EventsAgent"""
    return EventsAgent()