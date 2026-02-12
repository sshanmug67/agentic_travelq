// frontend/src/pages/Dashboard.tsx

import React, { useState, useEffect } from 'react';
import { ItinerarySidebar } from '../components/itinerary/ItinerarySidebar';
import { NaturalLanguageInput } from '../components/common/NaturalLanguageInput';
import { PreferencesPanel } from '../components/common/PreferencesPanel';
import { PreferencesSummary } from '../components/common/PreferencesSummary';
import { TripSummaryBar } from '../components/common/TripSummaryBar';
import { FlightCard } from '../components/flight/FlightCard';
import { useTripData } from '../hooks/useTripData';
import { useItinerary } from '../hooks/useItinerary';
import { tripApi } from '../services/api';
import type { TripPlanResponse } from '../types/trip';

type ResultsTab = 'flights' | 'hotels' | 'restaurants' | 'activities';

export const Dashboard: React.FC = () => {
  const { 
    tripData, preferences, flights,
    setTripData, setFlights, setHotels, setRestaurants, setActivities, setWeather
  } = useTripData();
  const { 
    flight: selectedFlight, hotel: selectedHotel, 
    restaurants: selectedRestaurants, activities: selectedActivities,
    selectFlight 
  } = useItinerary();
  
  const [naturalLanguageRequest, setNaturalLanguageRequest] = useState('');
  const [isPlanning, setIsPlanning] = useState(false);
  const [lastSearchMessage, setLastSearchMessage] = useState('');
  const [activeResultsTab, setActiveResultsTab] = useState<ResultsTab>('flights');
  const [aiRecommendedFlightId, setAiRecommendedFlightId] = useState<string | null>(null);

  // Check if we have any results to show
  const hasResults = flights.length > 0;

  // Clear stale itinerary on mount if no results are loaded
  // (persisted state from a previous session with no matching options)
  useEffect(() => {
    if (!hasResults) {
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
    setLastSearchMessage('');
    
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

      // Store the tripId from backend response
      const resolvedTripId = response.tripId || response.trip_id;
      if (resolvedTripId) {
        setTripData({ id: resolvedTripId });
      }

      // Update all options with results
      const results = response.results || response.options || {};
      const flightResults = results.flights || [];
      setFlights(flightResults);
      setHotels(results.hotels || []);
      setRestaurants(results.restaurants || []);
      setActivities(results.activities || []);
      setWeather(results.weather || []);

      // ✅ Auto-select the AI recommended flight using structured recommendations
      if (flightResults.length > 0) {
        const recFlightId = response.recommendations?.flight?.recommended_id;
        const aiPick = recFlightId
          ? flightResults.find((f) => String(f.id) === String(recFlightId))
          : null;
        
        const flightToSelect = aiPick || flightResults[0];
        
        setAiRecommendedFlightId(flightToSelect.id);
        selectFlight(flightToSelect, 'ai');
        setActiveResultsTab('flights');
      }

      // Show success message
      setLastSearchMessage(
        response.message || response.final_recommendation || 'Trip planning complete!'
      );
      
      setNaturalLanguageRequest('');

    } catch (error: any) {
      console.error('Failed to plan trip:', error);
      alert('Failed to plan trip: ' + (error.message || 'Unknown error'));
    } finally {
      setIsPlanning(false);
    }
  };

  const handleSelectFlight = (flight: any) => {
    // If the user picks the AI-recommended flight, keep it tagged as 'ai'
    const source = flight.id === aiRecommendedFlightId ? 'ai' : 'user';
    selectFlight(flight, source);
  };

  // Results tabs config
  const resultsTabs: { id: ResultsTab; label: string; icon: string; count: number }[] = [
    { id: 'flights', label: 'Flights', icon: '✈️', count: flights.length },
    { id: 'hotels', label: 'Hotels', icon: '🏨', count: useTripData.getState().hotels.length },
    { id: 'restaurants', label: 'Restaurants', icon: '🍽️', count: useTripData.getState().restaurants.length },
    { id: 'activities', label: 'Activities', icon: '🎭', count: useTripData.getState().activities.length },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-pink-50 to-orange-50">
      {/* Header */}
      <div className="bg-white shadow-md sticky top-0 z-40">
        <div className="px-6 lg:px-[10%] py-3 flex items-center justify-between">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
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

      {/* Trip Summary Bar */}
      <TripSummaryBar />

      {/* Preferences Summary (collapsed bar below TripSummaryBar) */}
      <PreferencesSummary preferences={preferences} />

      {/* Natural Language Input & Preferences */}
      <div className="px-6 lg:px-[10%] py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Left: Natural Language Input */}
          <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
            <NaturalLanguageInput 
              value={naturalLanguageRequest}
              onChange={setNaturalLanguageRequest}
              onSubmit={handlePlanTrip}
              isProcessing={isPlanning}
            />
          </div>

          {/* Right: Preferences Panel */}
          <PreferencesPanel 
            preferences={preferences} 
            onUpdate={useTripData.getState().updatePreferences} 
          />
        </div>

        {/* Big "Plan My Trip" Button */}
        <div className="max-w-4xl mx-auto">
          <button
            onClick={() => handlePlanTrip(naturalLanguageRequest)}
            disabled={isPlanning || !tripData.destination || !tripData.startDate || !tripData.endDate}
            className="w-full bg-gradient-to-r from-purple-600 via-pink-600 to-orange-600 hover:from-purple-700 hover:via-pink-700 hover:to-orange-700 disabled:from-gray-400 disabled:via-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed text-white font-bold text-xl py-4 px-8 rounded-xl shadow-2xl transition-all duration-300 transform hover:scale-105 disabled:hover:scale-100 flex items-center justify-center gap-3"
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
          AI RECOMMENDATION SUMMARY — full width across both panels
          ══════════════════════════════════════════════════════════════════ */}
      {lastSearchMessage && (
        <div className="px-6 lg:px-[10%] pb-4">
          <div className="bg-gradient-to-r from-purple-600 via-pink-600 to-orange-500 rounded-xl p-[1px]">
            <div className="bg-white rounded-xl p-5">
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
                  <span className="text-white text-lg">✨</span>
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-bold text-purple-700 uppercase tracking-wide mb-2">
                    TravelQ Recommendation
                  </h3>
                  <div className="max-h-40 overflow-y-auto pr-2 text-sm text-gray-700 leading-relaxed scrollbar-thin">
                    {lastSearchMessage.split('\n').map((line, i) => {
                      const trimmed = line.trim();
                      
                      // Horizontal rule
                      if (trimmed === '---' || trimmed === '***') {
                        return <hr key={i} className="my-2 border-gray-200" />;
                      }
                      
                      // Empty line → spacing
                      if (!trimmed) {
                        return <div key={i} className="h-2" />;
                      }
                      
                      // H1: # Heading
                      if (trimmed.startsWith('# ')) {
                        return (
                          <h4 key={i} className="text-base font-bold text-gray-800 mt-2 mb-1">
                            {trimmed.replace(/^# /, '')}
                          </h4>
                        );
                      }
                      
                      // H2: ## Heading
                      if (trimmed.startsWith('## ')) {
                        return (
                          <h5 key={i} className="text-sm font-bold text-purple-700 mt-3 mb-1">
                            {trimmed.replace(/^## /, '')}
                          </h5>
                        );
                      }
                      
                      // List item: - text
                      if (trimmed.startsWith('- ')) {
                        const content = trimmed.replace(/^- /, '');
                        return (
                          <div key={i} className="flex items-start gap-2 ml-2 my-0.5">
                            <span className="text-purple-400 mt-0.5">•</span>
                            <span
                              dangerouslySetInnerHTML={{
                                __html: content
                                  .replace(/\*\*(.+?)\*\*/g, '<strong class="text-gray-800">$1</strong>')
                              }}
                            />
                          </div>
                        );
                      }
                      
                      // Regular paragraph with bold support
                      return (
                        <p
                          key={i}
                          className="my-0.5"
                          dangerouslySetInnerHTML={{
                            __html: trimmed
                              .replace(/\*\*(.+?)\*\*/g, '<strong class="text-gray-800">$1</strong>')
                          }}
                        />
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          MAIN CONTENT: Results (left) + Itinerary (right)
          ══════════════════════════════════════════════════════════════════ */}
      <div className="px-6 lg:px-[10%] pb-6">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          
          {/* ── LEFT: Results Panel (60% width) ───────────────────────── */}
          <div className="lg:col-span-3">
            {hasResults ? (
              <div className="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
                
                {/* Results Tab Bar */}
                <div className="flex border-b bg-gradient-to-r from-purple-50 to-pink-50">
                  {resultsTabs.map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveResultsTab(tab.id)}
                      className={`flex-1 px-4 py-3 text-sm font-medium transition-all duration-300 relative ${
                        activeResultsTab === tab.id
                          ? 'text-purple-700 bg-white'
                          : 'text-gray-600 hover:text-purple-600 hover:bg-white/50'
                      }`}
                    >
                      <span className="flex items-center justify-center gap-2">
                        <span className="text-lg">{tab.icon}</span>
                        <span>{tab.label}</span>
                        {tab.count > 0 && (
                          <span className={`text-xs px-2 py-0.5 rounded-full ${
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

                {/* Results Content */}
                <div className="p-6">

                  {/* ── FLIGHTS TAB ──────────────────────────────────── */}
                  {activeResultsTab === 'flights' && (
                    <div>
                      <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-bold text-gray-800">
                          ✈️ Available Flights
                        </h2>
                        <div className="flex items-center gap-3">
                          {selectedFlight && (
                            <span className="text-xs bg-purple-100 text-purple-700 px-3 py-1 rounded-full font-medium">
                              Selected: {selectedFlight.airline} {selectedFlight.outbound?.flight_number} — ${selectedFlight.price}
                            </span>
                          )}
                          <span className="text-sm text-gray-500">
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

                  {/* ── HOTELS TAB (placeholder — wire up next) ──────── */}
                  {activeResultsTab === 'hotels' && (
                    <div className="text-center py-12 text-gray-500">
                      <div className="text-4xl mb-3">🏨</div>
                      <p className="font-semibold">Hotel results — wiring up next</p>
                      <p className="text-sm mt-1">
                        {useTripData.getState().hotels.length} hotels found
                      </p>
                    </div>
                  )}

                  {/* ── RESTAURANTS TAB (placeholder) ─────────────────── */}
                  {activeResultsTab === 'restaurants' && (
                    <div className="text-center py-12 text-gray-500">
                      <div className="text-4xl mb-3">🍽️</div>
                      <p className="font-semibold">Restaurant results — wiring up next</p>
                      <p className="text-sm mt-1">
                        {useTripData.getState().restaurants.length} restaurants found
                      </p>
                    </div>
                  )}

                  {/* ── ACTIVITIES TAB (placeholder) ──────────────────── */}
                  {activeResultsTab === 'activities' && (
                    <div className="text-center py-12 text-gray-500">
                      <div className="text-4xl mb-3">🎭</div>
                      <p className="font-semibold">Activity results — wiring up next</p>
                      <p className="text-sm mt-1">
                        {useTripData.getState().activities.length} activities found
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              /* Empty State — before any search */
              <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-200">
                <div className="text-center py-20">
                  <div className="text-6xl mb-4">🚀</div>
                  <h2 className="text-2xl font-bold text-gray-800 mb-2">
                    Ready to Plan Your Trip?
                  </h2>
                  <p className="text-gray-600 mb-6">
                    Fill in your trip details above and click "Plan My Trip" to see options!
                  </p>
                  <div className="text-sm text-gray-500">
                    Flight, Hotel, Restaurant, and Activity options will appear here.
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* ── RIGHT: Itinerary Sidebar (40% width) ─────────────────── */}
          <div className="lg:col-span-2">
            <ItinerarySidebar />
          </div>
        </div>
      </div>
    </div>
  );
};
