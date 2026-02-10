// frontend/src/pages/Dashboard.tsx
import React from 'react';
import { TripSearchForm } from '../components/common/TripSearchForm';
import { FlightCard } from '../components/flight/FlightCard';
import { WeatherTimeline } from '../components/weather/WeatherTimeline';
import { EventCard } from '../components/events/EventCard';
import { Loading } from '../components/common/Loading';
import { useTripData } from '../hooks/useTripData';
import type { TripRequest } from '../types/trip';

export const Dashboard: React.FC = () => {
  const { tripData, loading, error, searchTrip } = useTripData();

  const handleSearch = async (request: TripRequest) => {
    try {
      await searchTrip(request);
    } catch (err) {
      console.error('Search failed:', err);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm mb-8">
        <div className="container mx-auto px-4 py-6">
          <h1 className="text-4xl font-bold text-gray-900">
            Travel Dashboard
          </h1>
          <p className="text-gray-600 mt-2">AI-powered trip planning with multi-agent coordination</p>
        </div>
      </header>

      {/* Search Form */}
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <TripSearchForm onSubmit={handleSearch} loading={loading} />
        </div>

        {/* Loading State */}
        {loading && (
          <div className="flex justify-center items-center py-12">
            <Loading />
            <p className="ml-4 text-gray-600">Planning your perfect trip...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-8">
            <h3 className="text-red-800 font-semibold mb-2">Error</h3>
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Results */}
        {tripData && !loading && (
          <div className="space-y-8">
            {/* Flights */}
            {tripData.flights && tripData.flights.length > 0 && (
              <section className="bg-white p-6 rounded-lg shadow-md">
                <h2 className="text-2xl font-bold mb-4 text-gray-800">✈️ Flights</h2>
                <div className="grid gap-4">
                  {tripData.flights.map((flight) => (
                    <FlightCard key={flight.id} flight={flight} />
                  ))}
                </div>
              </section>
            )}

            {/* Weather */}
            {tripData.weather_forecast && tripData.weather_forecast.length > 0 && (
              <section className="bg-white p-6 rounded-lg shadow-md">
                <h2 className="text-2xl font-bold mb-4 text-gray-800">🌤️ Weather Forecast</h2>
                <WeatherTimeline forecast={tripData.weather_forecast} />
              </section>
            )}

            {/* Events */}
            {tripData.events && tripData.events.length > 0 && (
              <section className="bg-white p-6 rounded-lg shadow-md">
                <h2 className="text-2xl font-bold mb-4 text-gray-800">🎭 Events & Activities</h2>
                <div className="grid gap-4">
                  {tripData.events.map((event) => (
                    <EventCard key={event.id} event={event} />
                  ))}
                </div>
              </section>
            )}

            {/* Places */}
            {tripData.places && tripData.places.length > 0 && (
              <section className="bg-white p-6 rounded-lg shadow-md">
                <h2 className="text-2xl font-bold mb-4 text-gray-800">📍 Places to Visit</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {tripData.places.map((place) => (
                    <div key={place.id} className="border border-gray-200 rounded-lg p-4">
                      <h3 className="font-semibold text-lg text-gray-900">{place.name}</h3>
                      <p className="text-sm text-gray-600 mt-1">{place.category}</p>
                      {place.rating && (
                        <div className="flex items-center gap-1 mt-2">
                          <span className="text-yellow-500">⭐</span>
                          <span className="text-sm font-medium">{place.rating}</span>
                        </div>
                      )}
                      {place.description && (
                        <p className="text-sm text-gray-700 mt-2">{place.description}</p>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Empty State */}
            {(!tripData.flights || tripData.flights.length === 0) &&
             (!tripData.weather_forecast || tripData.weather_forecast.length === 0) &&
             (!tripData.events || tripData.events.length === 0) &&
             (!tripData.places || tripData.places.length === 0) && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
                <p className="text-yellow-800">
                  No results found. The agents may still be processing your request or no data was returned.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};