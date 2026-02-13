// frontend/src/pages/Dashboard.tsx

import React, { useState, useEffect } from 'react';
import { ItinerarySidebar } from '../components/itinerary/ItinerarySidebar';
import { NaturalLanguageInput } from '../components/common/NaturalLanguageInput';
import { PreferencesPanel } from '../components/common/PreferencesPanel';
import { PreferencesSummary } from '../components/common/PreferencesSummary';
import { TripSummaryBar } from '../components/common/TripSummaryBar';
import { FlightCard } from '../components/flight/FlightCard';
import { HotelCard } from '../components/hotel/HotelCard';
import { useTripData } from '../hooks/useTripData';
import { useItinerary } from '../hooks/useItinerary';
import { tripApi } from '../services/api';
import type { TripPlanResponse } from '../types/trip';

type ResultsTab = 'flights' | 'hotels' | 'restaurants' | 'activities';

export const Dashboard: React.FC = () => {
  const {
    tripData, preferences, flights, hotels,
    setTripData, setFlights, setHotels, setRestaurants, setActivities, setWeather
  } = useTripData();
  const {
    flight: selectedFlight, hotel: selectedHotel,
    restaurants: selectedRestaurants, activities: selectedActivities,
    selectFlight, selectHotel
  } = useItinerary();

  const [naturalLanguageRequest, setNaturalLanguageRequest] = useState('');
  const [isPlanning, setIsPlanning] = useState(false);
  const [activeResultsTab, setActiveResultsTab] = useState<ResultsTab>('flights');
  const [aiRecommendedFlightId, setAiRecommendedFlightId] = useState<string | null>(null);
  const [aiRecommendedHotelId, setAiRecommendedHotelId] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<Record<string, any> | null>(null);

  const hasResults = flights.length > 0 || hotels.length > 0;

  useEffect(() => {
    const { flights, hotels, restaurants, activities } = useTripData.getState();
    const hasAnyResults = flights.length > 0 || hotels.length > 0 ||
                           restaurants.length > 0 || activities.length > 0;
    if (!hasAnyResults) {
      try { localStorage.removeItem('itinerary-storage'); } catch (e) { /* ignore */ }
      useItinerary.getState().clearItinerary();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handlePlanTrip = async (userRequest: string) => {
    if (!tripData.destination) {
      alert('Please enter a destination');
      return;
    }
    if (!tripData.startDate || !tripData.endDate) {
      alert('Please enter travel dates');
      return;
    }

    setIsPlanning(true);


    
    try {
      const response = await tripApi.planTrip({
        tripId: tripData.id,
        userRequest: userRequest,
        tripDetails: {
          origin: tripData.origin,
          destination: tripData.destination,
          startDate: tripData.startDate,
          endDate: tripData.endDate,
          travelers: tripData.travelers,
          budget: tripData.totalBudget,
        },
        preferences: preferences,
        currentItinerary: {
          flight: selectedFlight,
          hotel: selectedHotel,
          restaurants: selectedRestaurants,
          activities: selectedActivities,
        },
      }) as TripPlanResponse;

      const resolvedTripId = response.tripId || response.trip_id;
      if (resolvedTripId) {
        setTripData({ id: resolvedTripId });
      }

      const results: Record<string, any> =
        response.results || response.options || {};

      const flightResults = results.flights || [];
      setFlights(flightResults);
      setHotels(results.hotels || []);
      setRestaurants(results.restaurants || []);
      setActivities(results.activities || []);
      setWeather(results.weather || []);

      if (flightResults.length > 0) {
        const recFlightId = response.recommendations?.flight?.recommended_id;
        const aiPick = recFlightId
          ? flightResults.find((f: any) => String(f.id) === String(recFlightId))
          : null;
        const flightToSelect = aiPick || flightResults[0];
        setAiRecommendedFlightId(flightToSelect.id);
        selectFlight(flightToSelect, 'ai');
        setActiveResultsTab('flights');
      }

      const hotelResults = results.hotels || [];
      if (hotelResults.length > 0) {
        const recHotelId = response.recommendations?.hotel?.recommended_id;
        const aiHotelPick = recHotelId
          ? hotelResults.find((h: any) => String(h.id) === String(recHotelId))
          : null;
        const hotelToSelect = aiHotelPick || hotelResults[0];
        setAiRecommendedHotelId(hotelToSelect.id);
        selectHotel(hotelToSelect, 'ai');
        if (flightResults.length === 0) {
          setActiveResultsTab('hotels');
        }
      }

      if (response.recommendations) {
        setRecommendations(response.recommendations);
      }

      setNaturalLanguageRequest('');

    } catch (error: any) {
      console.error('Failed to plan trip:', error);
      alert('Failed to plan trip: ' + (error.message || 'Unknown error'));
    } finally {
      setIsPlanning(false);
    }
  };

  const handleSelectFlight = (flight: any) => {
    const source = flight.id === aiRecommendedFlightId ? 'ai' : 'user';
    selectFlight(flight, source);
  };

  const handleSelectHotel = (hotel: any) => {
    const source = hotel.id === aiRecommendedHotelId ? 'ai' : 'user';
    selectHotel(hotel, source);
  };

  const resultsTabs: { id: ResultsTab; label: string; icon: string; count: number }[] = [
    { id: 'flights', label: 'Flights', icon: '✈️', count: flights.length },
    { id: 'hotels', label: 'Hotels', icon: '🏨', count: hotels.length },
    { id: 'restaurants', label: 'Restaurants', icon: '🍽️', count: useTripData.getState().restaurants.length },
    { id: 'activities', label: 'Activities', icon: '🎭', count: useTripData.getState().activities.length },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-pink-50 to-orange-50">
      {/* Header */}
      <div className="bg-white shadow-md sticky top-0 z-40">
        <div className="px-6 lg:px-[10%] py-3 flex items-center justify-between">
          <h1 className="text-[25px] font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
            TravelQ
          </h1>
          <div className="flex items-center gap-4">
            <button className="text-gray-600 hover:text-gray-800">🔍</button>
            <button className="text-gray-600 hover:text-gray-800">🔔</button>
            <button className="text-gray-600 hover:text-gray-800">👤 Profile</button>
            <button className="text-gray-600 hover:text-gray-800">⚙️</button>
          </div>
        </div>
      </div>

      <TripSummaryBar />
      <PreferencesSummary preferences={preferences} />

      {/* Natural Language Input & Preferences */}
      <div className="px-6 lg:px-[10%] py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
            <NaturalLanguageInput
              value={naturalLanguageRequest}
              onChange={setNaturalLanguageRequest}
              onSubmit={handlePlanTrip}
              isProcessing={isPlanning}
            />
          </div>
          <PreferencesPanel
            preferences={preferences}
            onUpdate={useTripData.getState().updatePreferences}
          />
        </div>

        <div className="max-w-4xl mx-auto">
          <button
            onClick={() => handlePlanTrip(naturalLanguageRequest)}
            disabled={isPlanning || !tripData.destination || !tripData.startDate || !tripData.endDate}
            className="w-full bg-gradient-to-r from-purple-600 via-pink-600 to-orange-600 hover:from-purple-700 hover:via-pink-700 hover:to-orange-700 disabled:from-gray-400 disabled:via-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed text-white font-bold text-[21px] py-4 px-8 rounded-xl shadow-2xl transition-all duration-300 transform hover:scale-105 disabled:hover:scale-100 flex items-center justify-center gap-3"
          >
            {isPlanning ? (
              <>
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white"></div>
                Planning Your Trip...
              </>
            ) : (
              <>🚀 Plan My Trip</>
            )}
          </button>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          INDIVIDUAL RECOMMENDATION STICKY NOTES — 3 per row
          ══════════════════════════════════════════════════════════════════ */}
      {recommendations && Object.keys(recommendations).length > 0 && (() => {
        const categoryConfig: Record<string, { icon: string; bg: string; tape: string; label: string }> = {
          flight:     { icon: '✈️',  bg: 'bg-yellow-100', tape: 'bg-yellow-300', label: 'Flight' },
          hotel:      { icon: '🏨', bg: 'bg-blue-100',   tape: 'bg-blue-300',   label: 'Hotel' },
          restaurant: { icon: '🍽️',  bg: 'bg-green-100',  tape: 'bg-green-300',  label: 'Restaurant' },
          activity:   { icon: '🎭', bg: 'bg-pink-100',   tape: 'bg-pink-300',   label: 'Activity' },
          weather:    { icon: '🌤️',  bg: 'bg-orange-100', tape: 'bg-orange-300', label: 'Weather' },
        };

        const allCategories = ['flight', 'hotel', 'restaurant', 'activity'];
        const cards = allCategories.map((cat) => ({
          category: cat,
          config: categoryConfig[cat] || { icon: '📋', bg: 'bg-gray-100', tape: 'bg-gray-300', label: cat },
          rec: recommendations[cat] || null,
        }));

        return (
          <div className="px-6 lg:px-[10%] pb-8">
            <div className="border-2 border-gray-800 rounded-2xl p-5 bg-white/50">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-7 h-7 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
                  <span className="text-white text-[15px]">✨</span>
                </div>
                <h3 className="text-[15px] font-bold text-purple-700 uppercase tracking-wide">
                  TravelQ Recommendations
                </h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {cards.map(({ category, config, rec }) => (
                  <div
                    key={category}
                    className={`${config.bg} rounded-lg shadow-md relative pt-4 pb-3 px-4 min-h-[130px] max-h-[200px] flex flex-col transform transition-transform hover:-rotate-1 hover:shadow-lg`}
                    style={{
                      transform: `rotate(${(category.charCodeAt(0) % 3 - 1) * 0.8}deg)`,
                    }}
                  >
                    <div className={`absolute -top-1.5 left-1/2 -translate-x-1/2 w-16 h-3 ${config.tape} rounded-sm opacity-70`} />

                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[19px]">{config.icon}</span>
                        <span className="text-[15px] font-bold uppercase tracking-wider text-gray-700">
                          {config.label}
                        </span>
                      </div>
                      {rec?.metadata?.price != null && (
                        <span className="text-[17px] font-bold text-green-700">
                          ${Number(rec.metadata.price).toFixed(2)}
                        </span>
                      )}
                    </div>

                    {rec && rec.recommended_id ? (
                      <div className="flex-1 overflow-y-auto pr-1">
                        <p className="text-[17px] font-semibold text-gray-800 mb-1 truncate">
                          {rec.metadata?.airline
                            || rec.metadata?.hotel_name
                            || rec.metadata?.name
                            || `Option #${rec.recommended_id}`}
                        </p>
                        <p className="text-[15px] text-gray-600 leading-relaxed"
                           style={{ fontFamily: "'Segoe UI', system-ui, sans-serif" }}>
                          {rec.reason || 'Best match for your preferences'}
                        </p>
                        <div className="flex items-center gap-2 mt-2 text-[13px] text-gray-500">
                          {rec.metadata?.is_direct !== undefined && (
                            <span>{rec.metadata.is_direct ? '✅ Direct' : '🔄 Connecting'}</span>
                          )}
                          {rec.metadata?.total_options_reviewed && (
                            <span>📊 {rec.metadata.total_options_reviewed} reviewed</span>
                          )}
                          {rec.metadata?.rating && (
                            <span>⭐ {rec.metadata.rating}</span>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="flex-1 flex items-center justify-center">
                        <p className="text-[15px] text-gray-400 italic">Pending...</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      })()}

      {/* ══════════════════════════════════════════════════════════════════
          MAIN CONTENT: Results (left) + Itinerary (right)
          ══════════════════════════════════════════════════════════════════ */}
      <div className="px-6 lg:px-[10%] pb-6">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

          <div className="lg:col-span-3">
            {hasResults ? (
              <div className="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">

                <div className="flex border-b bg-gradient-to-r from-purple-50 to-pink-50">
                  {resultsTabs.map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveResultsTab(tab.id)}
                      className={`flex-1 px-4 py-3 text-[15px] font-medium transition-all duration-300 relative ${
                        activeResultsTab === tab.id
                          ? 'text-purple-700 bg-white'
                          : 'text-gray-600 hover:text-purple-600 hover:bg-white/50'
                      }`}
                    >
                      <span className="flex items-center justify-center gap-2">
                        <span className="text-[19px]">{tab.icon}</span>
                        <span>{tab.label}</span>
                        {tab.count > 0 && (
                          <span className={`text-[13px] px-2 py-0.5 rounded-full ${
                            activeResultsTab === tab.id
                              ? 'bg-purple-100 text-purple-700'
                              : 'bg-gray-200 text-gray-600'
                          }`}>
                            {tab.count}
                          </span>
                        )}
                      </span>
                      {activeResultsTab === tab.id && (
                        <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-purple-600 to-pink-600" />
                      )}
                    </button>
                  ))}
                </div>

                <div className="p-6">

                  {activeResultsTab === 'flights' && (
                    <div>
                      <div className="flex items-center justify-between mb-4">
                        <h2 className="text-[19px] font-bold text-gray-800">
                          ✈️ Available Flights
                        </h2>
                        <div className="flex items-center gap-3">
                          {selectedFlight && (
                            <span className="text-[13px] bg-purple-100 text-purple-700 px-3 py-1 rounded-full font-medium">
                              Selected: {selectedFlight.airline_code} {selectedFlight.outbound?.flight_number} — ${selectedFlight.price}
                            </span>
                          )}
                          <span className="text-[15px] text-gray-500">
                            {flights.length} option{flights.length !== 1 ? 's' : ''}
                          </span>
                        </div>
                      </div>

                      <div className="space-y-4">
                        {flights.map((flight, index) => (
                          <FlightCard
                            key={flight.id || index}
                            flight={flight}
                            isSelected={selectedFlight?.id === flight.id}
                            isAiRecommended={flight.id === aiRecommendedFlightId}
                            onSelect={() => handleSelectFlight(flight)}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {activeResultsTab === 'hotels' && (
                    <div>
                      <div className="flex items-center justify-between mb-4">
                        <h2 className="text-[19px] font-bold text-gray-800">
                          🏨 Available Hotels
                        </h2>
                        <div className="flex items-center gap-3">
                          {selectedHotel && (
                            <span className="text-[13px] bg-purple-100 text-purple-700 px-3 py-1 rounded-full font-medium truncate max-w-[280px]">
                              Selected: {selectedHotel.name} — ${selectedHotel.total_price}
                            </span>
                          )}
                          <span className="text-[15px] text-gray-500">
                            {hotels.length} option{hotels.length !== 1 ? 's' : ''}
                          </span>
                        </div>
                      </div>

                      <div className="space-y-4">
                        {hotels.map((hotel, index) => (
                          <HotelCard
                            key={hotel.id || index}
                            hotel={hotel}
                            isSelected={selectedHotel?.id === hotel.id}
                            isAiRecommended={hotel.id === aiRecommendedHotelId}
                            onSelect={() => handleSelectHotel(hotel)}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {activeResultsTab === 'restaurants' && (
                    <div className="text-center py-12 text-gray-500">
                      <div className="text-4xl mb-3">🍽️</div>
                      <p className="font-semibold">Restaurant results — wiring up next</p>
                      <p className="text-[15px] mt-1">
                        {useTripData.getState().restaurants.length} restaurants found
                      </p>
                    </div>
                  )}

                  {activeResultsTab === 'activities' && (
                    <div className="text-center py-12 text-gray-500">
                      <div className="text-4xl mb-3">🎭</div>
                      <p className="font-semibold">Activity results — wiring up next</p>
                      <p className="text-[15px] mt-1">
                        {useTripData.getState().activities.length} activities found
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-200">
                <div className="text-center py-20">
                  <div className="text-6xl mb-4">🚀</div>
                  <h2 className="text-[25px] font-bold text-gray-800 mb-2">
                    Ready to Plan Your Trip?
                  </h2>
                  <p className="text-gray-600 mb-6">
                    Fill in your trip details above and click "Plan My Trip" to see options!
                  </p>
                  <div className="text-[15px] text-gray-500">
                    Flight, Hotel, Restaurant, and Activity options will appear here.
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="lg:col-span-2">
            <ItinerarySidebar />
          </div>
        </div>
      </div>
    </div>
  );
};
