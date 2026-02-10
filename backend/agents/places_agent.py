"""
Mock Places Agent - Returns Structured Mock Data
Location: backend/agents/places_agent.py

This is a MOCK agent for testing. Returns realistic place/attraction data without calling real APIs.
Replace with real Google Places API integration later.
"""
import json
from typing import Dict, Any, List
import random

from agents.base_agent import TravelQBaseAgent
from models.trip import Place
from utils.logging_config import log_agent_raw, log_agent_json


class PlacesAgent(TravelQBaseAgent):
    """
    Mock Places Agent - Returns structured place/attraction data
    
    For testing purposes only. Returns realistic mock places.
    """
    
    def __init__(self, **kwargs):
        system_message = """
You are a Places & Attractions Agent specializing in finding interesting locations.

Your job:
1. Find restaurants, attractions, landmarks, shopping areas
2. Consider user interests and trip pace
3. Include ratings, addresses, opening hours
4. Provide variety (mix of popular and hidden gems)

Always return results in structured format with detailed information.
"""
        super().__init__(
            name="PlacesAgent",                    # ✅ Add this
            llm_config=self.create_llm_config(),        # ✅ Add this
            agent_type="PlacesAgent",
            system_message=system_message,
            description="Finds restaurants, attractions, and points of interest",  # ✅ Add this
            **kwargs
        )
        
        log_agent_raw("📍 PlacesAgent initialized (MOCK MODE)", agent_name="PlacesAgent")
    
    def generate_reply(
        self,
        messages: List[Dict[str, Any]] = None,
        sender: Any = None,
        config: Any = None,
    ) -> str:  # ✅ Fixed return type
        """
        Generate place search results
        
        Returns structured mock data
        """
        log_agent_raw("🔍 Searching for places (mock data)...", agent_name="PlacesAgent")
        
        # ✅ ADD THIS - Log incoming message
        if messages and len(messages) > 0:
            last_message = messages[-1].get("content", "")
            sender_name = sender.name if sender and hasattr(sender, 'name') else "Unknown"
            self.log_full_conversation(
                message_type="INCOMING",
                content=last_message,
                sender=sender_name
            )

        # Get preferences from conversation
        preferences = self._extract_preferences_from_messages(messages)
        
        # Generate mock places
        mock_places = self._generate_mock_places(preferences)
        
        # Create structured response
        response = self._create_structured_response(mock_places, preferences)
        
        log_agent_json({
            "places_found": len(mock_places),
            "destination": preferences.get("destination", "Unknown"),
            "categories": list(set(p.category for p in mock_places))
        }, agent_name="PlacesAgent", label="Mock Places Search")
        
        # ✅ ADD THIS - Log outgoing response
        self.log_full_conversation(
            message_type="OUTGOING",
            content=response,
            sender="chat_manager"
        )

        return self.signal_completion(response)  # ✅ Fixed: return string only
    
    def _extract_preferences_from_messages(self, messages: List[Dict]) -> Dict:
        """Extract preferences from conversation"""
        return {
            "destination": "Tokyo",
            "interests": ["culture", "food", "sightseeing"]
        }
    
    def _generate_mock_places(self, preferences: Dict) -> List[Place]:
        """Generate realistic mock place data"""
        
        places = [
            # Temples & Shrines
            Place(
                id="place_001",
                name="Senso-ji Temple",
                address="2-3-1 Asakusa, Taito City, Tokyo 111-0032",
                latitude=35.7148,
                longitude=139.7967,
                rating=4.6,
                category="Temple & Shrine",
                description="Tokyo's oldest and most famous Buddhist temple. Beautiful architecture, traditional shopping street (Nakamise), and cultural significance.",
                photos=[
                    "https://example.com/photos/sensoji-1.jpg",
                    "https://example.com/photos/sensoji-2.jpg"
                ],
                opening_hours={
                    "monday": "6:00 AM - 5:00 PM",
                    "tuesday": "6:00 AM - 5:00 PM",
                    "everyday": "6:00 AM - 5:00 PM"
                },
                price_level=0,
                website="https://www.senso-ji.jp"
            ),
            Place(
                id="place_002",
                name="Meiji Shrine",
                address="1-1 Yoyogikamizonocho, Shibuya City, Tokyo 151-8557",
                latitude=35.6764,
                longitude=139.6993,
                rating=4.7,
                category="Temple & Shrine",
                description="Peaceful Shinto shrine set in a beautiful forested area. Walk through impressive torii gates and experience traditional Japanese spirituality.",
                photos=["https://example.com/photos/meiji.jpg"],
                opening_hours={
                    "everyday": "Sunrise to Sunset (varies by season)"
                },
                price_level=0,
                website="https://www.meijijingu.or.jp"
            ),
            
            # Restaurants
            Place(
                id="place_003",
                name="Sukiyabashi Jiro",
                address="Tsukamoto Sogyo Building B1F, 4-2-15 Ginza, Chuo City, Tokyo",
                latitude=35.6712,
                longitude=139.7636,
                rating=4.8,
                category="Sushi Restaurant",
                description="World-famous three-Michelin-star sushi restaurant. Intimate omakase experience with master chef Jiro Ono. Reservations required months in advance.",
                photos=["https://example.com/photos/jiro.jpg"],
                opening_hours={
                    "monday": "Closed",
                    "tuesday-saturday": "11:30 AM - 2:00 PM, 5:30 PM - 8:30 PM",
                    "sunday": "Closed"
                },
                price_level=4,
                website="https://example.com/sukiyabashi-jiro"
            ),
            Place(
                id="place_004",
                name="Ichiran Ramen Shibuya",
                address="1-22-7 Jinnan, Shibuya City, Tokyo",
                latitude=35.6627,
                longitude=139.6989,
                rating=4.3,
                category="Ramen Restaurant",
                description="Famous ramen chain with individual booths for focused eating. Customize your perfect bowl. Great for solo travelers.",
                photos=["https://example.com/photos/ichiran.jpg"],
                opening_hours={
                    "everyday": "24 hours"
                },
                price_level=1,
                website="https://en.ichiran.com"
            ),
            Place(
                id="place_005",
                name="Tsukiji Outer Market",
                address="4 Chome Tsukiji, Chuo City, Tokyo",
                latitude=35.6654,
                longitude=139.7707,
                rating=4.5,
                category="Food Market",
                description="Historic fish market with hundreds of vendors selling fresh seafood, street food, and cooking supplies. Best visited early morning.",
                photos=["https://example.com/photos/tsukiji.jpg"],
                opening_hours={
                    "everyday": "5:00 AM - 2:00 PM (most shops)",
                    "note": "Many shops closed on Sundays and Wednesdays"
                },
                price_level=2,
                website=None
            ),
            
            # Attractions & Landmarks
            Place(
                id="place_006",
                name="Tokyo Skytree",
                address="1-1-2 Oshiage, Sumida City, Tokyo",
                latitude=35.7101,
                longitude=139.8107,
                rating=4.5,
                category="Observation Tower",
                description="Tallest structure in Japan at 634 meters. Stunning 360° views of Tokyo from observation decks at 350m and 450m.",
                photos=["https://example.com/photos/skytree.jpg"],
                opening_hours={
                    "everyday": "8:00 AM - 10:00 PM"
                },
                price_level=3,
                website="https://www.tokyo-skytree.jp"
            ),
            Place(
                id="place_007",
                name="Shibuya Crossing",
                address="Shibuya City, Tokyo",
                latitude=35.6595,
                longitude=139.7004,
                rating=4.6,
                category="Landmark",
                description="World's busiest pedestrian crossing. Iconic Tokyo experience. Best viewed from Starbucks in Tsutaya building for overhead perspective.",
                photos=["https://example.com/photos/shibuya.jpg"],
                opening_hours={
                    "everyday": "24 hours (viewing)"
                },
                price_level=0,
                website=None
            ),
            Place(
                id="place_008",
                name="teamLab Borderless",
                address="1-3-8 Aomi, Koto City, Tokyo",
                latitude=35.6241,
                longitude=139.7754,
                rating=4.7,
                category="Digital Art Museum",
                description="Immersive digital art museum with interactive installations. Unique blend of technology and art. Very Instagram-worthy!",
                photos=["https://example.com/photos/teamlab.jpg"],
                opening_hours={
                    "monday": "Closed",
                    "tuesday-sunday": "10:00 AM - 7:00 PM"
                },
                price_level=3,
                website="https://borderless.teamlab.art"
            ),
            
            # Shopping
            Place(
                id="place_009",
                name="Takeshita Street",
                address="Jingumae, Shibuya City, Tokyo",
                latitude=35.6707,
                longitude=139.7058,
                rating=4.2,
                category="Shopping Street",
                description="Trendy shopping street in Harajuku. Fashion boutiques, quirky shops, crepe stands, and people watching. Very crowded on weekends.",
                photos=["https://example.com/photos/takeshita.jpg"],
                opening_hours={
                    "everyday": "10:00 AM - 8:00 PM (varies by shop)"
                },
                price_level=2,
                website=None
            ),
            Place(
                id="place_010",
                name="Don Quijote Shibuya",
                address="28-6 Udagawacho, Shibuya City, Tokyo",
                latitude=35.6617,
                longitude=139.6981,
                rating=4.1,
                category="Shopping & Souvenirs",
                description="Massive discount store selling everything: snacks, cosmetics, electronics, souvenirs. Open 24 hours. Tourist tax-free shopping available.",
                photos=["https://example.com/photos/donki.jpg"],
                opening_hours={
                    "everyday": "24 hours"
                },
                price_level=1,
                website="https://www.donki.com"
            ),
            
            # Parks & Nature
            Place(
                id="place_011",
                name="Shinjuku Gyoen National Garden",
                address="11 Naitomachi, Shinjuku City, Tokyo",
                latitude=35.6852,
                longitude=139.7100,
                rating=4.6,
                category="Park & Garden",
                description="Beautiful traditional Japanese garden with French and English garden sections. Perfect for hanami (cherry blossoms) and autumn leaves.",
                photos=["https://example.com/photos/gyoen.jpg"],
                opening_hours={
                    "monday": "Closed",
                    "tuesday-sunday": "9:00 AM - 4:30 PM"
                },
                price_level=1,
                website="https://fng.or.jp/shinjuku"
            ),
            
            # Hidden Gems
            Place(
                id="place_012",
                name="Omoide Yokocho",
                address="1-2 Nishishinjuku, Shinjuku City, Tokyo",
                latitude=35.6938,
                longitude=139.7003,
                rating=4.4,
                category="Food Alley",
                description="Narrow alleyways packed with tiny yakitori restaurants and bars. Authentic local atmosphere. Cash only in most places.",
                photos=["https://example.com/photos/omoide.jpg"],
                opening_hours={
                    "everyday": "5:00 PM - Midnight (most shops)"
                },
                price_level=2,
                website=None
            ),
        ]
        
        return places
    
    def _create_structured_response(self, places: List[Place], preferences: Dict) -> str:
        """Create response with structured data"""
        
        # Convert places to dict for JSON
        place_data = [place.model_dump() for place in places]
        
        # Create structured data block
        structured = {
            "agent": "PlacesAgent",
            "type": "place_results",
            "data": place_data
        }
        
        # Categorize places
        categories = {}
        for place in places:
            if place.category not in categories:
                categories[place.category] = []
            categories[place.category].append(place)
        
        # Create natural language summary
        summary = f"""
I found {len(places)} amazing places to visit in {preferences.get('destination', 'Tokyo')}!

**Top Recommendations by Category:**

"""
        
        # Group by category and highlight top picks
        for category, category_places in sorted(categories.items()):
            summary += f"\n**{category}:**\n"
            for place in category_places[:2]:  # Show top 2 per category
                stars = "⭐" * int(place.rating)
                price_level_str = "$" * (place.price_level or 0) if place.price_level else "Free"
                
                summary += f"""
• **{place.name}** {stars}
  {place.description[:100]}...
  📍 {place.address[:50]}...
  💰 {price_level_str}
"""
        
        # Add curated itinerary suggestions
        summary += """

**Suggested Itinerary Combinations:**

**Day 1 - Cultural Immersion:**
→ Morning: Senso-ji Temple (2 hours)
→ Lunch: Tsukiji Outer Market
→ Afternoon: Meiji Shrine (1.5 hours)
→ Evening: Shibuya Crossing + dinner nearby

**Day 2 - Food & Shopping:**
→ Morning: Shinjuku Gyoen Garden
→ Lunch: Ramen at Ichiran
→ Afternoon: Shopping at Takeshita Street & Harajuku
→ Evening: Omoide Yokocho for yakitori

**Day 3 - Modern Tokyo:**
→ Morning: teamLab Borderless (2-3 hours)
→ Afternoon: Tokyo Skytree observation deck
→ Evening: Explore Shibuya nightlife

**Insider Tips:**
💡 Book teamLab Borderless tickets online in advance - they sell out!
💡 Visit temples early morning for peaceful experience (6-8 AM)
💡 Shibuya Crossing is busiest at 6-7 PM on weekdays
💡 Many shops closed on Sundays/Wednesdays in Tsukiji
💡 Get a Suica card for easy train travel between locations
"""
        
        summary += f"""

<STRUCTURED_DATA>
{json.dumps(structured, indent=2)}
</STRUCTURED_DATA>
"""
        
        return summary


def create_places_agent() -> PlacesAgent:
    """
    Factory function to create PlacesAgent
    
    Returns:
        Configured PlacesAgent instance (mock mode)
    """
    return PlacesAgent()