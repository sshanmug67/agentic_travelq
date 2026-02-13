// frontend/src/pages/Dashboard.tsx
//
// Changes (v3):
//   - v2 changes (RestaurantCard, ActivityCard, toggleRestaurant/toggleActivity)
//   - Fix hasResults to include restaurants + activities (not just flights/hotels)
//   - Destructure restaurants/activities from useTripData for reactive rendering
//   - Auto-select AI-recommended restaurants into itinerary sidebar
//   - Auto-select AI-recommended activities into itinerary sidebar
//   - Auto-switch to first populated tab when agents return data
//   - Replace useTripData.getState() calls in JSX with reactive store variables

import React, { useState, useEffect } from 'react';
import { ItinerarySidebar } from '../components/itinerary/ItinerarySidebar';
import { NaturalLanguageInput } from '../components/common/NaturalLanguageInput';
import { PreferencesPanel } from '../components/common/PreferencesPanel';
import { PreferencesSummary } from '../components/common/PreferencesSummary';
import { TripSummaryBar } from '../components/common/TripSummaryBar';
import { FlightCard } from '../components/flight/FlightCard';
import { HotelCard } from '../components/hotel/HotelCard';
import { RestaurantCard } from '../components/restaurant/RestaurantCard';
import { ActivityCard } from '../components/activity/ActivityCard';
import { useTripData } from '../hooks/useTripData';
import { useItinerary } from '../hooks/useItinerary';
import { tripApi } from '../services/api';
import type { TripPlanResponse } from '../types/trip';

type ResultsTab = 'flights' | 'hotels' | 'restaurants' | 'activities';

export const Dashboard: React.FC = () => {
  const {
    tripData, preferences, flights, hotels,
    restaurants: storeRestaurants, activities: storeActivities,
    setTripData, setFlights, setHotels, setRestaurants, setActivities, setWeather
  } = useTripData();
  const {
    flight: selectedFlight, hotel: selectedHotel,
    restaurants: selectedRestaurants, activities: selectedActivities,
    selectFlight, selectHotel, toggleRestaurant, toggleActivity
  } = useItinerary();

  const [naturalLanguageRequest, setNaturalLanguageRequest] = useState('');
  const [isPlanning, setIsPlanning] = useState(false);
  const [activeResultsTab, setActiveResultsTab] = useState<ResultsTab>('flights');
  const [aiRecommendedFlightId, setAiRecommendedFlightId] = useState<string | null>(null);
  const [aiRecommendedHotelId, setAiRecommendedHotelId] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<Record<string, any> | null>(null);

  // v3: Include all four data types in hasResults check
  const hasResults = flights.length > 0 || hotels.length > 0
    || storeRestaurants.length > 0 || storeActivities.length > 0;

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
      const hotelResults = results.hotels || [];
      const restaurantResults = results.restaurants || [];
      const activityResults = results.activities || [];

      setFlights(flightResults);
      setHotels(hotelResults);
      setRestaurants(restaurantResults);
      setActivities(activityResults);
      setWeather(results.weather || []);

      // ── Auto-select AI-recommended flight ──────────────────────────
      if (flightResults.length > 0) {
        const recFlightId = response.recommendations?.flight?.recommended_id;
        const aiPick = recFlightId
          ? flightResults.find((f: any) => String(f.id) === String(recFlightId))
          : null;
        const flightToSelect = aiPick || flightResults[0];
        setAiRecommendedFlightId(flightToSelect.id);
        selectFlight(flightToSelect, 'ai');
      }

      // ── Auto-select AI-recommended hotel ───────────────────────────
      if (hotelResults.length > 0) {
        const recHotelId = response.recommendations?.hotel?.recommended_id;
        const aiHotelPick = recHotelId
          ? hotelResults.find((h: any) => String(h.id) === String(recHotelId))
          : null;
        const hotelToSelect = aiHotelPick || hotelResults[0];
        setAiRecommendedHotelId(hotelToSelect.id);
        selectHotel(hotelToSelect, 'ai');
      }

      // ── v3 NEW: Auto-select AI-recommended restaurants ─────────────
      if (restaurantResults.length > 0) {
        const recRestaurant = response.recommendations?.restaurant;
        const recIds: string[] =
          recRestaurant?.metadata?.all_recommended_ids || [];

        if (recIds.length > 0) {
          // Toggle each recommended restaurant into the itinerary
          for (const recId of recIds) {
            const match = restaurantResults.find(
              (r: any) => String(r.id) === String(recId)
            );
            if (match) {
              toggleRestaurant(match);
            }
          }
        }
      }

      // ── v3 NEW: Auto-select AI-recommended activities ──────────────
      if (activityResults.length > 0) {
        const recActivity = response.recommendations?.activity;
        const recIds: string[] =
          recActivity?.metadata?.all_recommended_ids || [];

        if (recIds.length > 0) {
          // Toggle each recommended activity into the itinerary
          for (const recId of recIds) {
            const match = activityResults.find(
              (a: any) => String(a.id) === String(recId)
            );
            if (match) {
              toggleActivity(match);
            }
          }
        }
      }

      // ── Auto-switch to first tab that has data ─────────────────────
      if (flightResults.length > 0) {
        setActiveResultsTab('flights');
      } else if (hotelResults.length > 0) {
        setActiveResultsTab('hotels');
      } else if (restaurantResults.length > 0) {
        setActiveResultsTab('restaurants');
      } else if (activityResults.length > 0) {
        setActiveResultsTab('activities');
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

  const handleToggleRestaurant = (restaurant: any) => {
    toggleRestaurant(restaurant);
  };

  const handleToggleActivity = (activity: any) => {
    toggleActivity(activity);
  };

  // v3: Use reactive store variables for tab counts
  const resultsTabs: { id: ResultsTab; label: string; icon: string; count: number }[] = [
    { id: 'flights', label: 'Flights', icon: '✈️', count: flights.length },
    { id: 'hotels', label: 'Hotels', icon: '🏨', count: hotels.length },
    { id: 'restaurants', label: 'Restaurants', icon: '🍽️', count: storeRestaurants.length },
    { id: 'activities', label: 'Activities', icon: '🎭', count: storeActivities.length },
  ];

  // Helper: check if a restaurant is selected in itinerary
  const isRestaurantSelected = (id: string) =>
    selectedRestaurants.some((r) => r.id === id);

  // Helper: check if an activity is selected in itinerary
  const isActivitySelected = (id: string) =>
    selectedActivities.some((a) => a.id === id);

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
          RECOMMENDATIONS: Left = Flight/Hotel picks | Right = Daily Schedule
          ══════════════════════════════════════════════════════════════════ */}
      {recommendations && Object.keys(recommendations).length > 0 && (() => {
        // ── Left side: Flight + Hotel cards ───────────────────────────
        const categoryConfig: Record<string, { icon: string; accent: string; accentLight: string; label: string }> = {
          flight: { icon: '✈️', accent: 'border-l-amber-400',  accentLight: 'bg-amber-50',  label: 'Flight' },
          hotel:  { icon: '🏨', accent: 'border-l-blue-400',   accentLight: 'bg-blue-50',   label: 'Hotel' },
        };
        const pickCategories = ['flight', 'hotel'];
        const pickCards = pickCategories.map((cat) => ({
          category: cat,
          config: categoryConfig[cat],
          rec: recommendations[cat] || null,
        }));

        // ── Right side: Daily plan from PlacesAgent ──────────────────
        const dailyPlanRec = recommendations['daily_plan'];
        const planText: string = dailyPlanRec?.reason || '';

        // Parse markdown plan into day blocks
        const dayBlocks: { title: string; body: string }[] = [];
        if (planText) {
          const sections = planText.split(/(?=###\s)/);
          for (const section of sections) {
            const trimmed = section.trim();
            if (!trimmed) continue;
            const newlineIdx = trimmed.indexOf('\n');
            if (newlineIdx === -1) {
              dayBlocks.push({ title: trimmed.replace(/^#+\s*/, ''), body: '' });
            } else {
              const heading = trimmed.slice(0, newlineIdx).replace(/^#+\s*/, '').trim();
              const body = trimmed.slice(newlineIdx + 1).trim();
              dayBlocks.push({ title: heading, body });
            }
          }
        }

        // Accent colors for day timeline
        const dayAccents = [
          'border-l-purple-400',
          'border-l-pink-400',
          'border-l-indigo-400',
          'border-l-teal-400',
          'border-l-orange-400',
          'border-l-rose-400',
        ];

        // Convert **text** to <strong> for display
        const renderBold = (text: string) => {
          const parts = text.split(/\*\*(.*?)\*\*/g);
          return parts.map((part, i) =>
            i % 2 === 1
              ? <strong key={i} className="font-semibold text-gray-800">{part}</strong>
              : <span key={i}>{part}</span>
          );
        };

        return (
          <div className="px-6 lg:px-[10%] pb-8">
            <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6">
              {/* Section header */}
              <div className="flex items-center gap-2.5 mb-5">
                <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center shadow-sm">
                  <span className="text-white text-[16px]">✨</span>
                </div>
                <h3 className="text-[16px] font-bold text-gray-800 tracking-wide">
                  AI Recommendations
                </h3>
              </div>
              <hr className="border-gray-200 mb-5" />

              <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

                {/* ─── LEFT: Flight & Hotel Picks ─────────────────────── */}
                <div className="lg:col-span-2 flex flex-col">
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-[18px]">🎯</span>
                    <h4 className="text-[14px] font-semibold uppercase tracking-wide text-gray-500">
                      Top Picks
                    </h4>
                  </div>
                  <div className="space-y-4">
                  {pickCards.map(({ category, config, rec }) => (
                    <div
                      key={category}
                      className={`${config.accentLight} rounded-lg border border-gray-200 border-l-4 ${config.accent} p-4 transition-shadow hover:shadow-md`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-[18px]">{config.icon}</span>
                          <span className="text-[14px] font-semibold uppercase tracking-wide text-gray-500">
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
                        <div>
                          <p className="text-[16px] font-semibold text-gray-800 mb-1">
                            {rec.metadata?.airline
                              || rec.metadata?.hotel_name
                              || rec.metadata?.name
                              || `Option #${rec.recommended_id}`}
                          </p>
                          <p className="text-[13px] text-gray-600 leading-relaxed mb-2">
                            {rec.reason || 'Best match for your preferences'}
                          </p>
                          <div className="flex items-center gap-3 text-[12px] text-gray-400">
                            {rec.metadata?.is_direct !== undefined && (
                              <span className="flex items-center gap-1">
                                {rec.metadata.is_direct ? '✅ Direct' : '🔄 Connecting'}
                              </span>
                            )}
                            {rec.metadata?.total_options_reviewed && (
                              <span>{rec.metadata.total_options_reviewed} reviewed</span>
                            )}
                            {rec.metadata?.rating && (
                              <span>⭐ {rec.metadata.rating}</span>
                            )}
                          </div>
                        </div>
                      ) : (
                        <p className="text-[14px] text-gray-400 italic py-4 text-center">
                          Pending...
                        </p>
                      )}
                    </div>
                  ))}
                  </div>
                </div>

                {/* ─── RIGHT: Daily Activity Schedule ─────────────────── */}
                <div className="lg:col-span-3">
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-[18px]">📅</span>
                    <h4 className="text-[14px] font-semibold uppercase tracking-wide text-gray-500">
                      Daily Schedule
                    </h4>
                    {dailyPlanRec?.metadata?.num_days && (
                      <span className="text-[12px] bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full font-medium">
                        {dailyPlanRec.metadata.num_days} days
                      </span>
                    )}
                  </div>

                  {dayBlocks.length > 0 ? (
                    <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
                      {dayBlocks.map((day, idx) => {
                        const accent = dayAccents[idx % dayAccents.length];
                        return (
                          <div
                            key={idx}
                            className={`bg-gray-50 rounded-lg border border-gray-200 border-l-4 ${accent} px-4 py-3 transition-shadow hover:shadow-sm`}
                          >
                            <p className="text-[13px] font-bold text-gray-800 mb-1">
                              {day.title}
                            </p>
                            <p className="text-[12.5px] text-gray-600 leading-relaxed">
                              {renderBold(day.body)}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="bg-gray-50 rounded-lg border border-dashed border-gray-300 p-8 text-center">
                      <span className="text-3xl mb-2 block">📅</span>
                      <p className="text-[14px] text-gray-400 italic">
                        Daily schedule will appear after planning...
                      </p>
                    </div>
                  )}
                </div>

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

                  {/* ────────── FLIGHTS TAB ────────── */}
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

                  {/* ────────── HOTELS TAB ────────── */}
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

                  {/* ────────── RESTAURANTS TAB ────────── */}
                  {activeResultsTab === 'restaurants' && (
                    <div>
                      <div className="flex items-center justify-between mb-4">
                        <h2 className="text-[19px] font-bold text-gray-800">
                          🍽️ Recommended Restaurants
                        </h2>
                        <div className="flex items-center gap-3">
                          {selectedRestaurants.length > 0 && (
                            <span className="text-[13px] bg-orange-100 text-orange-700 px-3 py-1 rounded-full font-medium">
                              {selectedRestaurants.length} added to itinerary
                            </span>
                          )}
                          <span className="text-[15px] text-gray-500">
                            {storeRestaurants.length} option{storeRestaurants.length !== 1 ? 's' : ''}
                          </span>
                        </div>
                      </div>

                      {storeRestaurants.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {storeRestaurants.map((restaurant, index) => (
                            <RestaurantCard
                              key={`${restaurant.id}-${index}`}
                              restaurant={restaurant}
                              isSelected={isRestaurantSelected(restaurant.id)}
                              onToggle={() => handleToggleRestaurant(restaurant)}
                            />
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-12 text-gray-500">
                          <div className="text-4xl mb-3">🍽️</div>
                          <p className="font-semibold">No restaurant results yet</p>
                          <p className="text-[15px] mt-1">
                            Plan your trip to discover great dining options
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ────────── ACTIVITIES TAB ────────── */}
                  {activeResultsTab === 'activities' && (
                    <div>
                      <div className="flex items-center justify-between mb-4">
                        <h2 className="text-[19px] font-bold text-gray-800">
                          🎭 Things To Do
                        </h2>
                        <div className="flex items-center gap-3">
                          {selectedActivities.length > 0 && (
                            <span className="text-[13px] bg-blue-100 text-blue-700 px-3 py-1 rounded-full font-medium">
                              {selectedActivities.length} added to itinerary
                            </span>
                          )}
                          <span className="text-[15px] text-gray-500">
                            {storeActivities.length} option{storeActivities.length !== 1 ? 's' : ''}
                          </span>
                        </div>
                      </div>

                      {storeActivities.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {storeActivities.map((activity, index) => (
                            <ActivityCard
                              key={`${activity.id}-${index}`}
                              activity={activity}
                              isSelected={isActivitySelected(activity.id)}
                              onToggle={() => handleToggleActivity(activity)}
                            />
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-12 text-gray-500">
                          <div className="text-4xl mb-3">🎭</div>
                          <p className="font-semibold">No activity results yet</p>
                          <p className="text-[15px] mt-1">
                            Plan your trip to discover things to do
                          </p>
                        </div>
                      )}
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
