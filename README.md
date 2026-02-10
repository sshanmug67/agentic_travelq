# Travel Dashboard

A multi-agent travel planning system built with Autogen framework, FastAPI, and React/TypeScript.

## Features

- 🛫 **Flight Search**: Search flights using Amadeus API
- 🌤️ **Weather Forecasts**: Get weather forecasts for your destination
- 🎭 **Events**: Discover events and activities at your destination
- 📍 **Places**: Find attractions and places to visit
- 🤖 **AI-Powered Suggestions**: Get intelligent trip recommendations

## Architecture

### Backend (Python)
- **FastAPI**: REST API framework
- **Autogen**: Multi-agent orchestration
- **Amadeus API**: Flight data
- **OpenWeather API**: Weather forecasts

### Frontend (React/TypeScript)
- **React 18**: UI library
- **TypeScript**: Type safety
- **Vite**: Build tool
- **Tailwind CSS**: Styling
- **Lucide React**: Icons

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- Amadeus API credentials
- OpenWeather API key

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys

# Run the server
python main.py
```

The backend will start on `http://localhost:8000`

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy and configure environment variables
cp .env.example .env

# Run development server
npm run dev
```

The frontend will start on `http://localhost:3000`

## API Endpoints

### POST `/api/trips/search`
Search for trip information

**Request Body:**
```json
{
  "origin": "NYC",
  "destination": "London",
  "start_date": "2025-03-15",
  "end_date": "2025-03-20",
  "interests": ["museums", "concerts"],
  "budget": 5000
}
```

**Response:**
```json
{
  "trip_id": "uuid",
  "flights": [...],
  "weather_forecast": [...],
  "events": [...],
  "places": [...],
  "ai_suggestions": "...",
  "created_at": "2025-02-08T10:00:00"
}
```

### GET `/api/trips/health`
Health check endpoint

## Project Structure

```
travel-dashboard/
├── backend/
│   ├── agents/              # Autogen agents
│   ├── services/            # External API integrations
│   ├── api/                 # FastAPI routes
│   ├── models/              # Data models
│   ├── config/              # Configuration
│   └── main.py             # Entry point
│
└── frontend/
    └── src/
        ├── components/      # React components
        ├── pages/          # Page components
        ├── hooks/          # Custom hooks
        ├── services/       # API services
        ├── types/          # TypeScript types
        └── styles/         # CSS styles
```

## Agents

The system uses 5 specialized agents:

1. **OrchestratorAgent**: Coordinates all other agents
2. **FlightAgent**: Searches flights via Amadeus API
3. **WeatherAgent**: Fetches weather forecasts
4. **EventsAgent**: Finds local events
5. **PlacesAgent**: Discovers attractions

## Development

### Backend Development
```bash
cd backend
python main.py  # Auto-reload enabled
```

### Frontend Development
```bash
cd frontend
npm run dev  # Hot module replacement
```

### Build for Production

**Backend:**
```bash
cd backend
# Use a production ASGI server like Gunicorn
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

**Frontend:**
```bash
cd frontend
npm run build
# Output in dist/ directory
```

## Environment Variables

### Backend (.env)
- `AMADEUS_CLIENT_ID`: Your Amadeus API client ID
- `AMADEUS_CLIENT_SECRET`: Your Amadeus API secret
- `WEATHER_API_KEY`: OpenWeather API key
- `GOOGLE_PLACES_API_KEY`: (Optional) Google Places API key
- `TICKETMASTER_API_KEY`: (Optional) Ticketmaster API key

### Frontend (.env)
- `VITE_API_URL`: Backend API URL (default: http://localhost:8000)

## Next Steps

1. **Integrate Google Places API** for real places data
2. **Add Ticketmaster/Eventbrite** for real events
3. **Implement interactive map** with Leaflet/Mapbox
4. **Add user authentication**
5. **Implement trip saving/bookmarking**
6. **Add WebSocket support** for real-time updates
7. **Implement itinerary builder**
8. **Add budget tracking**

## License

MIT
