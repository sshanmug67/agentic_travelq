"""
Icon Mapper for TravelQ Daily Schedule
Location: backend/utils/icon_mapper.py

Maps Google Places types, cuisine tags, and interest tags to appropriate emojis.
Used by PlacesAgent to enrich the structured daily schedule with icons.

Usage:
    from utils.icon_mapper import get_venue_icon, get_cuisine_icon, get_activity_icon

    icon = get_venue_icon(place_dict)           # uses primary_type + types[]
    icon = get_cuisine_icon("Indian")           # cuisine tag → emoji
    icon = get_activity_icon("Museum")          # interest/category → emoji
    icon = get_time_icon("morning")             # time slot → emoji
"""

from typing import Dict, Optional


# ─── Cuisine → Emoji ─────────────────────────────────────────────────────

CUISINE_ICONS: Dict[str, str] = {
    # Asian
    "japanese": "🍣",
    "sushi": "🍣",
    "ramen": "🍜",
    "chinese": "🥡",
    "thai": "🍜",
    "indian": "🍛",
    "korean": "🥘",
    "vietnamese": "🍜",
    "dim sum": "🥟",
    "asian": "🥢",
    "asian fusion": "🥢",
    "indian fusion": "🍛",

    # European
    "italian": "🍝",
    "pizza": "🍕",
    "french": "🥐",
    "spanish": "🥘",
    "greek": "🫒",
    "mediterranean": "🫒",
    "british": "🍖",
    "german": "🥨",
    "turkish": "🥙",

    # Americas
    "mexican": "🌮",
    "american": "🍔",
    "burger": "🍔",
    "bbq": "🍖",
    "barbecue": "🍖",
    "brazilian": "🥩",
    "peruvian": "🐟",
    "latin": "🌮",

    # Other cuisines
    "middle eastern": "🥙",
    "lebanese": "🥙",
    "moroccan": "🥘",
    "african": "🍲",
    "ethiopian": "🍲",
    "caribbean": "🍹",

    # By food type
    "seafood": "🦐",
    "steak": "🥩",
    "steakhouse": "🥩",
    "vegetarian": "🥗",
    "vegan": "🌱",
    "brunch": "🥞",
    "breakfast": "🥞",
    "street food": "🍢",
    "fusion": "🍽️",
    "tapas": "🫒",
    "noodle": "🍜",
    "curry": "🍛",
    "fine dining": "🍷",
    "upscale": "🍷",

    # Drinks / desserts
    "cafe": "☕",
    "coffee": "☕",
    "tea": "🍵",
    "bakery": "🥐",
    "dessert": "🍰",
    "ice cream": "🍦",
    "cocktail": "🍸",
    "wine": "🍷",
    "pub": "🍺",
    "bar": "🍸",
}

# ─── Activity / Interest → Emoji ─────────────────────────────────────────

ACTIVITY_ICONS: Dict[str, str] = {
    # Museums & galleries
    "museum": "🏛️",
    "art museum": "🎨",
    "art gallery": "🎨",
    "art": "🎨",
    "contemporary art": "🎭",
    "science museum": "🔬",
    "natural history": "🦕",
    "history museum": "🏛️",
    "art & design": "🎨",

    # Landmarks & sightseeing
    "landmark": "📸",
    "historic landmark": "⛪",
    "historic": "⛪",
    "monument": "🗽",
    "castle": "🏰",
    "palace": "👑",
    "cathedral": "⛪",
    "church": "⛪",
    "temple": "⛩️",
    "shrine": "⛩️",
    "ruins": "🏛️",
    "bridge": "🌉",
    "tower": "🗼",
    "tourist attraction": "📸",
    "sightseeing": "📸",

    # Nature & outdoors
    "park": "🌳",
    "garden": "🌺",
    "botanical garden": "🌿",
    "beach": "🏖️",
    "hiking": "🥾",
    "nature": "🌲",
    "lake": "🏞️",
    "mountain": "⛰️",
    "waterfall": "💧",
    "zoo": "🐘",
    "aquarium": "🐠",
    "wildlife": "🦁",

    # Entertainment
    "theater": "🎭",
    "performing arts": "🎭",
    "performing_arts_theater": "🎭",
    "performing arts theater": "🎭",
    "cinema": "🎬",
    "concert": "🎵",
    "music": "🎵",
    "nightlife": "🌙",
    "club": "🪩",
    "comedy": "😂",
    "festival": "🎪",
    "event": "🎪",
    "carnival": "🎠",
    "amusement park": "🎢",

    # Culture & learning
    "cultural": "🎭",
    "cultural experiences": "🎭",
    "culture": "🎭",
    "traditional culture": "🎭",
    "library": "📚",
    "bookshop": "📖",
    "workshop": "🎓",
    "cooking class": "👨‍🍳",

    # Shopping
    "shopping": "🛍️",
    "market": "🏪",
    "mall": "🏬",
    "department store": "🏬",
    "souvenir": "🎁",
    "antique": "🏺",
    "flea market": "🏪",

    # Sports & recreation
    "sports": "⚽",
    "stadium": "🏟️",
    "golf": "⛳",
    "swimming": "🏊",
    "spa": "💆",
    "wellness": "🧘",
    "gym": "💪",
    "cycling": "🚴",
    "kayak": "🛶",
    "surfing": "🏄",
    "skiing": "⛷️",
    "diving": "🤿",

    # Tours
    "walking tour": "🚶",
    "tour": "🚶",
    "guided tour": "🗣️",
    "boat tour": "⛵",
    "bus tour": "🚌",
    "food tour": "🍽️",
    "bike tour": "🚴",

    # Tech & modern
    "modern technology": "🤖",
    "technology": "💻",
    "gaming": "🎮",
    "arcade": "🕹️",

    # Misc
    "explore": "🚶",
    "relax": "☕",
    "photography": "📷",
    "viewpoint": "🔭",
    "rooftop": "🏙️",
    "cherry blossoms": "🌸",
    "hanami": "🌸",
}

# ─── Google Places primary_type → Emoji ──────────────────────────────────

GOOGLE_TYPE_ICONS: Dict[str, str] = {
    # Food & drink
    "restaurant": "🍽️",
    "cafe": "☕",
    "bar": "🍸",
    "bakery": "🥐",
    "meal_delivery": "🍱",
    "meal_takeaway": "🍱",

    # Culture
    "museum": "🏛️",
    "art_gallery": "🎨",
    "performing_arts_theater": "🎭",
    "library": "📚",

    # Tourism
    "tourist_attraction": "📸",
    "amusement_park": "🎢",
    "zoo": "🐘",
    "aquarium": "🐠",

    # Nature
    "park": "🌳",
    "botanical_garden": "🌿",
    "hiking_area": "🥾",
    "campground": "⛺",

    # Shopping
    "shopping_mall": "🏬",
    "department_store": "🏬",
    "market": "🏪",

    # Entertainment
    "movie_theater": "🎬",
    "casino": "🎰",
    "bowling_alley": "🎳",
    "stadium": "🏟️",

    # Wellness
    "spa": "💆",
    "gym": "💪",

    # Religious
    "church": "⛪",
    "mosque": "🕌",
    "hindu_temple": "🛕",
    "synagogue": "🕍",

    # Other
    "night_club": "🪩",
    "marina": "⛵",
    "golf_course": "⛳",
}

# ─── Time slot → Emoji ───────────────────────────────────────────────────

TIME_ICONS: Dict[str, str] = {
    "morning": "🌅",
    "brunch": "🥞",
    "lunch": "🍽️",
    "afternoon": "☀️",
    "evening": "🌆",
    "dinner": "🍷",
    "night": "🌙",
}


# ─── Public API ──────────────────────────────────────────────────────────

def get_cuisine_icon(cuisine_tag: str) -> str:
    """Map a cuisine tag (e.g. 'Indian', 'British') to an emoji."""
    if not cuisine_tag:
        return "🍽️"
    key = cuisine_tag.lower().strip()
    # Exact match
    if key in CUISINE_ICONS:
        return CUISINE_ICONS[key]
    # Partial match (e.g. 'Indian Fusion' matches 'indian')
    for pattern, icon in CUISINE_ICONS.items():
        if pattern in key or key in pattern:
            return icon
    return "🍽️"


def get_activity_icon(category_or_tag: str) -> str:
    """Map an activity category or interest tag to an emoji."""
    if not category_or_tag:
        return "🎯"
    key = category_or_tag.lower().strip()
    # Exact match
    if key in ACTIVITY_ICONS:
        return ACTIVITY_ICONS[key]
    # Partial match
    for pattern, icon in ACTIVITY_ICONS.items():
        if pattern in key or key in pattern:
            return icon
    return "🎯"


def get_venue_icon(place_dict: Dict) -> str:
    """
    Get the best icon for a Google Places result dict.
    Checks primary_type first, then cuisine_tag/interest_tag, then types[].
    """
    # 1. Check cuisine_tag (for restaurants)
    cuisine_tag = place_dict.get("cuisine_tag", "")
    if cuisine_tag:
        icon = get_cuisine_icon(cuisine_tag)
        if icon != "🍽️":
            return icon

    # 2. Check interest_tag (for activities)
    interest_tag = place_dict.get("interest_tag", "")
    if interest_tag:
        icon = get_activity_icon(interest_tag)
        if icon != "🎯":
            return icon

    # 3. Check primary_type
    primary_type = (place_dict.get("primary_type") or place_dict.get("category") or "").lower()
    if primary_type in GOOGLE_TYPE_ICONS:
        return GOOGLE_TYPE_ICONS[primary_type]

    # 4. Check types array
    for t in (place_dict.get("types") or []):
        t_lower = t.lower()
        if t_lower in GOOGLE_TYPE_ICONS:
            return GOOGLE_TYPE_ICONS[t_lower]

    # 5. Fallback based on whether it's a restaurant or activity
    if primary_type in {"restaurant", "cafe", "bar", "bakery"}:
        return "🍽️"

    return "📍"


def get_time_icon(time_slot: str) -> str:
    """Get an icon for a time slot."""
    return TIME_ICONS.get(time_slot.lower().strip(), "⏰")


def get_weather_icon(description: str, precipitation_prob: float = 0) -> str:
    """Map weather description to an emoji."""
    desc = (description or "").lower()

    if "thunder" in desc or "storm" in desc:
        return "⛈️"
    if "heavy rain" in desc or "downpour" in desc:
        return "🌧️"
    if "rain" in desc or "drizzle" in desc or "shower" in desc:
        return "🌧️"
    if "snow" in desc or "sleet" in desc:
        return "🌨️"
    if "fog" in desc or "mist" in desc:
        return "🌫️"
    if "overcast" in desc:
        return "☁️"
    if "partly cloudy" in desc or "mostly cloudy" in desc:
        return "⛅"
    if "cloudy" in desc:
        return "☁️"
    if "clear" in desc or "sunny" in desc:
        return "☀️"
    if "partly sunny" in desc:
        return "🌤️"
    if "fair" in desc or "fine" in desc:
        return "🌤️"

    # Fallback based on precipitation probability
    if precipitation_prob > 60:
        return "🌧️"
    if precipitation_prob > 30:
        return "⛅"
    return "🌤️"