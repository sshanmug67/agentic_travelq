// frontend/src/pages/Dashboard.tsx
//
// Changes (v6 — Structured Daily Schedule):
//   - Replaced inline daily schedule rendering with DailySchedulePanel component
//   - Removed dayBlocks parsing logic, renderBold helper, dayAccents array
//   - DailySchedulePanel handles both structured_v1 (JSON) and text_v8 (legacy)
//   - Added destination prop pass-through for dynamic journal title
//
// Changes (v5 — Three-Column Planning Layout):
//   - Replaced 2-col NL Input + Preferences grid with 3-col layout
//   - New right column: AgentFeedColumn (live streaming agent activity)
//   - Fixed 380px height on desktop with internal scrolling per column
//   - Auto-collapse to thin summary bar after trip completes (2s delay)
//   - Click summary bar to re-expand and review agent feed / adjust prefs
//   - Inline progress bar replaces TripStatusBar component
//   - "Plan My Trip" button sits below the three columns
//
// Changes (v4 — Async Pipeline):
//   - handlePlanTrip() returns instantly (HTTP 202) via useTripSearch hook
//   - Result processing in processResults() callback
//   - isPlanning = isSubmitting || isPolling
//
// Changes (v3):
//   - RestaurantCard, ActivityCard, toggleRestaurant/toggleActivity
//   - Auto-select AI-recommended restaurants/activities

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { ItinerarySidebar } from '../components/itinerary/ItinerarySidebar';
import { NaturalLanguageInput } from '../components/common/NaturalLanguageInput';
import { PreferencesPanel } from '../components/common/PreferencesPanel';
import { PreferencesSummary } from '../components/common/PreferencesSummary';
import { TripSummaryBar } from '../components/common/TripSummaryBar';
import AgentFeedColumn from '../components/common/AgentFeedColumn';
import { FlightCard } from '../components/flight/FlightCard';
import { HotelCard } from '../components/hotel/HotelCard';
import { RestaurantCard } from '../components/restaurant/RestaurantCard';
import { ActivityCard } from '../components/activity/ActivityCard';
import { DailySchedulePanel } from '../components/recommendation/DailySchedulePanel';
import { useTripData } from '../hooks/useTripData';
import { useItinerary } from '../hooks/useItinerary';
import { useTripSearch } from '../hooks/useTripSearch';

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
  const [activeResultsTab, setActiveResultsTab] = useState<ResultsTab>('flights');
  const [aiRecommendedFlightId, setAiRecommendedFlightId] = useState<string | null>(null);
  const [aiRecommendedHotelId, setAiRecommendedHotelId] = useState<string | null>(null);
  const [aiRecommendedRestaurantIds, setAiRecommendedRestaurantIds] = useState<string[]>([]);
  const [aiRecommendedActivityIds, setAiRecommendedActivityIds] = useState<string[]>([]);
  const [recommendations, setRecommendations] = useState<Record<string, any> | null>(null);
  const [feedResetKey, setFeedResetKey] = useState(0);
  const [focusedItemId, setFocusedItemId] = useState<string | null>(null);

  const [isPlanningCollapsed, setIsPlanningCollapsed] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const startTimeRef = useRef<number>(Date.now());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const processResults = useCallback((response: any) => {
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

    if (flightResults.length > 0) {
      const recFlightId = response.recommendations?.flight?.recommended_id;
      const aiPick = recFlightId
        ? flightResults.find((f: any) => String(f.id) === String(recFlightId))
        : null;
      const flightToSelect = aiPick || flightResults[0];
      setAiRecommendedFlightId(flightToSelect.id);
      selectFlight(flightToSelect, 'ai');
    }

    if (hotelResults.length > 0) {
      const recHotelId = response.recommendations?.hotel?.recommended_id;
      const aiHotelPick = recHotelId
        ? hotelResults.find((h: any) => String(h.id) === String(recHotelId))
        : null;
      const hotelToSelect = aiHotelPick || hotelResults[0];
      setAiRecommendedHotelId(hotelToSelect.id);
      selectHotel(hotelToSelect, 'ai');
    }

    if (restaurantResults.length > 0) {
      const recRestaurant = response.recommendations?.restaurant;
      const recIds: string[] = recRestaurant?.metadata?.all_recommended_ids || [];
      setAiRecommendedRestaurantIds(recIds);
      if (recIds.length > 0) {
        for (const recId of recIds) {
          const match = restaurantResults.find((r: any) => String(r.id) === String(recId));
          if (match) toggleRestaurant(match);
        }
      } else {
        const fallbackCount = Math.min(3, restaurantResults.length);
        const fallbackIds: string[] = [];
        for (let i = 0; i < fallbackCount; i++) {
          toggleRestaurant(restaurantResults[i]);
          fallbackIds.push(restaurantResults[i].id);
        }
        setAiRecommendedRestaurantIds(fallbackIds);
      }
    }

    if (activityResults.length > 0) {
      const recActivity = response.recommendations?.activity;
      const recIds: string[] = recActivity?.metadata?.all_recommended_ids || [];
      setAiRecommendedActivityIds(recIds);
      if (recIds.length > 0) {
        for (const recId of recIds) {
          const match = activityResults.find((a: any) => String(a.id) === String(recId));
          if (match) toggleActivity(match);
        }
      } else {
        const fallbackCount = Math.min(5, activityResults.length);
        const fallbackIds: string[] = [];
        for (let i = 0; i < fallbackCount; i++) {
          toggleActivity(activityResults[i]);
          fallbackIds.push(activityResults[i].id);
        }
        setAiRecommendedActivityIds(fallbackIds);
      }
    }

    if (flightResults.length > 0) setActiveResultsTab('flights');
    else if (hotelResults.length > 0) setActiveResultsTab('hotels');
    else if (restaurantResults.length > 0) setActiveResultsTab('restaurants');
    else if (activityResults.length > 0) setActiveResultsTab('activities');

    if (response.recommendations) {
      setRecommendations(response.recommendations);
    }

    setNaturalLanguageRequest('');
  }, [setTripData, setFlights, setHotels, setRestaurants, setActivities, setWeather,
      selectFlight, selectHotel, toggleRestaurant, toggleActivity]);

  const {
    submitTrip, pollData,
    isSubmitting, isPolling, clearTrip
  } = useTripSearch({
    onComplete: processResults,
    onError: (err) => {
      console.error('Trip planning failed:', err);
      alert('Failed to plan trip: ' + err);
    },
    pollInterval: 2500,
  });

  const isPlanning = isSubmitting || isPolling;

  const hasResults = flights.length > 0 || hotels.length > 0
    || storeRestaurants.length > 0 || storeActivities.length > 0;

  useEffect(() => {
    if (isPlanning) {
      startTimeRef.current = Date.now();
      setElapsedTime(0);
      setIsPlanningCollapsed(false);
      timerRef.current = setInterval(() => {
        setElapsedTime(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlanning]);

  useEffect(() => {
    if (pollData?.status === 'completed' || pollData?.status === 'failed') {
      if (timerRef.current) clearInterval(timerRef.current);
      const timeout = setTimeout(() => setIsPlanningCollapsed(true), 2000);
      return () => clearTimeout(timeout);
    }
  }, [pollData?.status]);

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

    clearTrip();
    setFeedResetKey((k) => k + 1);

    await submitTrip({
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
    });
  };

  const handleSelectFlight = (flight: any) => {
    const source = flight.id === aiRecommendedFlightId ? 'ai' : 'user';
    selectFlight(flight, source);
  };

  const handleSelectHotel = (hotel: any) => {
    const source = hotel.id === aiRecommendedHotelId ? 'ai' : 'user';
    selectHotel(hotel, source);
  };

  const handleToggleRestaurant = (restaurant: any) => toggleRestaurant(restaurant);
  const handleToggleActivity = (activity: any) => toggleActivity(activity);

  // v6: When user clicks an item on the itinerary sidebar, switch tab + focus that card
  const handleItineraryItemClick = (tab: 'flights' | 'hotels' | 'restaurants' | 'activities', itemId?: string) => {
    setActiveResultsTab(tab);
    setFocusedItemId(itemId || null);
    if (itemId) {
      setTimeout(() => setFocusedItemId(null), 1500);
    }
  };

  const resultsTabs: { id: ResultsTab; label: string; icon: string; count: number }[] = [
    { id: 'flights', label: 'Flights', icon: '✈️', count: flights.length },
    { id: 'hotels', label: 'Hotels', icon: '🏨', count: hotels.length },
    { id: 'restaurants', label: 'Restaurants', icon: '🍽️', count: storeRestaurants.length },
    { id: 'activities', label: 'Activities', icon: '🎭', count: storeActivities.length },
  ];

  const isRestaurantSelected = (id: string) => selectedRestaurants.some((r) => r.id === id);
  const isActivitySelected = (id: string) => selectedActivities.some((a) => a.id === id);
  const isRestaurantAiRecommended = (id: string) => aiRecommendedRestaurantIds.includes(id);
  const isActivityAiRecommended = (id: string) => aiRecommendedActivityIds.includes(id);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  };

  const agents = pollData?.agents || {};
  const completedCount = Object.values(agents).filter((s) => s === 'completed').length;
  const totalAgents = Object.keys(agents).length || 6;
  const progressPercent = totalAgents > 0 ? (completedCount / totalAgents) * 100 : 0;
  const isComplete = pollData?.status === 'completed';
  const isFailed = pollData?.status === 'failed';
  const showProgressBar = isPlanning || isComplete || isFailed;

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-pink-50 to-orange-50">
      {/* ══════ Header ══════ */}
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

      {/* ══════ THREE-COLUMN PLANNING SECTION (collapsible) ══════ */}
      <div className="px-6 lg:px-[10%] py-4">

        {/* ── Collapsed Summary Bar ──────────────────────────────────── */}
        {showProgressBar && (
          <div
            className="overflow-hidden transition-all duration-500 ease-in-out"
            style={{
              maxHeight: isPlanningCollapsed ? '36px' : '0px',
              opacity: isPlanningCollapsed ? 1 : 0,
              marginBottom: isPlanningCollapsed ? '12px' : '0px',
            }}
          >
            <div
              onClick={() => setIsPlanningCollapsed(false)}
              className="relative h-8 overflow-hidden cursor-pointer shadow-lg rounded-xl"
              style={{
                background: isComplete ? '#0d1f0d' : isFailed ? '#2e1a1a' : '#1a1a2e',
              }}
            >
              <div
                className="absolute top-0 left-0 h-full transition-all duration-700"
                style={{
                  width: `${progressPercent}%`,
                  background: isComplete
                    ? 'linear-gradient(90deg, #10b981, #34d399)'
                    : isFailed
                      ? 'linear-gradient(90deg, #ef4444, #f87171)'
                      : 'linear-gradient(90deg, #6c5ce7, #a855f7, #ec4899)',
                }}
              />
              <div className="relative z-10 flex items-center justify-between h-full px-4">
                <div className="flex items-center gap-2">
                  {isComplete && <span className="text-emerald-400 font-bold text-xs">✓</span>}
                  {isFailed && <span className="text-red-400 font-bold text-xs">✕</span>}
                  <span className="text-white text-xs font-medium">
                    {isComplete
                      ? `Trip planned in ${formatTime(elapsedTime)}`
                      : isFailed
                        ? 'Planning failed'
                        : `Planning... ${completedCount}/${totalAgents}`}
                  </span>
                  {isComplete && (
                    <div className="flex items-center gap-1 ml-2">
                      {['✈️', '🏨', '🌤️', '🎭', '🍽️'].map((icon, i) => (
                        <span key={i} className="text-[10px] opacity-70">{icon}</span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-white font-bold text-[11px] tracking-wide drop-shadow-sm">Click to expand ▼</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Expandable Three-Column Section ────────────────────────── */}
        <div
          className="transition-all duration-500 ease-in-out overflow-hidden"
          style={{
            maxHeight: isPlanningCollapsed ? '0px' : '600px',
            opacity: isPlanningCollapsed ? 0 : 1,
          }}
        >
          {/* ════ Three Columns — all fixed 380px with internal scroll ════ */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-5">

            {/* ── Column 1: Natural Language Input ─────────────────── */}
            <div className="lg:h-[380px]">
              <div className="bg-white rounded-xl shadow-lg border-2 border-gray-300 overflow-hidden h-full flex flex-col">
                <NaturalLanguageInput
                  value={naturalLanguageRequest}
                  onChange={setNaturalLanguageRequest}
                  onSubmit={handlePlanTrip}
                  isProcessing={isPlanning}
                />
              </div>
            </div>

            {/* ── Column 2: Preferences Panel ─────────────────────── */}
            <div className="lg:h-[380px]">
              <PreferencesPanel
                preferences={preferences}
                onUpdate={useTripData.getState().updatePreferences}
              />
            </div>

            {/* ── Column 3: Live Agent Feed ────────────────────────── */}
            <div className="lg:h-[380px]">
              <AgentFeedColumn
                pollData={pollData}
                isActive={isPlanning}
                resetKey={feedResetKey}
              />
            </div>
          </div>

          {/* ── Plan My Trip Button ──────────────────────────────────── */}
          <div className="max-w-full">
            <button
              onClick={() => handlePlanTrip(naturalLanguageRequest)}
              disabled={isPlanning || !tripData.destination || !tripData.startDate || !tripData.endDate}
              className="w-full bg-gradient-to-r from-purple-600 via-pink-600 to-orange-600 hover:from-purple-700 hover:via-pink-700 hover:to-orange-700 disabled:from-gray-400 disabled:via-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed text-white font-bold text-[17px] py-2.5 px-8 rounded-xl shadow-2xl transition-all duration-300 transform hover:scale-[1.02] disabled:hover:scale-100 flex items-center justify-center gap-3"
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

            {/* ── Inline Progress Bar (during/after planning) ────── */}
            {showProgressBar && !isPlanningCollapsed && (
              <div className="mt-2">
                <div
                  className="relative h-7 overflow-hidden shadow-lg rounded-xl cursor-pointer"
                  style={{
                    background: isComplete ? '#0d1f0d' : isFailed ? '#2e1a1a' : '#1a1a2e',
                  }}
                  onClick={() => {
                    if (isComplete || isFailed) setIsPlanningCollapsed(true);
                  }}
                >
                  <div
                    className="absolute top-0 left-0 h-full transition-all duration-700 ease-out"
                    style={{
                      width: `${isPlanning ? Math.max(progressPercent, 5) : progressPercent}%`,
                      background: isComplete
                        ? 'linear-gradient(90deg, #10b981, #34d399)'
                        : isFailed
                          ? 'linear-gradient(90deg, #ef4444, #f87171)'
                          : 'linear-gradient(90deg, #6c5ce7 0%, #a855f7 50%, #ec4899 100%)',
                    }}
                  />
                  <div className="relative z-10 flex items-center justify-between h-full px-4">
                    <div className="flex items-center gap-2">
                      {isPlanning && (
                        <div className="animate-spin w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full" />
                      )}
                      {isComplete && <span className="text-emerald-400 font-bold text-sm">✓</span>}
                      {isFailed && <span className="text-red-400 font-bold text-sm">✕</span>}
                      <span className="text-white text-xs font-medium">
                        {isComplete
                          ? `Trip planned in ${formatTime(elapsedTime)}`
                          : isFailed
                            ? 'Planning failed'
                            : `${completedCount}/${totalAgents} agents complete`}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      {isPlanning && (
                        <span className="text-white/50 text-[11px] font-mono tabular-nums">
                          {formatTime(elapsedTime)}
                        </span>
                      )}
                      {(isComplete || isFailed) && (
                        <span className="text-white font-bold text-[11px] tracking-wide drop-shadow-sm">▲ Collapse</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ══════ RECOMMENDATIONS ══════ */}
      {recommendations && Object.keys(recommendations).length > 0 && (() => {
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

        const dailyPlanRec = recommendations['daily_plan'];

        return (
          <div className="px-6 lg:px-[10%] pb-8">
            <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4">
              <div className="flex items-center gap-2.5 mb-4">
                <span className="text-[20px]">✨</span>
                <h3 className="handwritten-subtitle text-[20px] sketch-underline">
                  AI Recommendations
                </h3>
              </div>
              <hr className="border-gray-200 mb-4" />

              <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                {/* LEFT: Flight, Hotel & Weather */}
                <div className="lg:col-span-2 flex flex-col lg:border-r lg:border-gray-200 lg:pr-6">
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-[18px]">🎯</span>
                    <h4 className="handwritten text-[14px] font-semibold uppercase tracking-wide text-gray-500">Top Picks</h4>
                  </div>
                  <div className="space-y-4 max-h-[400px] overflow-y-auto pr-1">
                  {pickCards.map(({ category, config, rec }) => (
                    <div key={category} className={`${config.accentLight} rounded-lg border border-gray-200 border-l-4 ${config.accent} p-4 transition-shadow hover:shadow-md`}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-[18px]">{config.icon}</span>
                          <span className="text-[14px] font-semibold uppercase tracking-wide text-gray-500">{config.label}</span>
                        </div>
                        {rec?.metadata?.price != null && (
                          <span className="text-[17px] font-bold text-green-700">${Number(rec.metadata.price).toFixed(2)}</span>
                        )}
                      </div>
                      {rec && rec.recommended_id ? (
                        <div>
                          <p className="text-[16px] font-semibold text-gray-800 mb-1">
                            {rec.metadata?.airline || rec.metadata?.hotel_name || rec.metadata?.name || `Option #${rec.recommended_id}`}
                          </p>
                          <p className="text-[13px] text-gray-600 leading-relaxed mb-2">{rec.reason || 'Best match for your preferences'}</p>
                          <div className="flex items-center gap-3 text-[12px] text-gray-400">
                            {rec.metadata?.is_direct !== undefined && (
                              <span className="flex items-center gap-1">{rec.metadata.is_direct ? '✅ Direct' : '🔄 Connecting'}</span>
                            )}
                            {rec.metadata?.total_options_reviewed && <span>{rec.metadata.total_options_reviewed} reviewed</span>}
                            {rec.metadata?.rating && <span>⭐ {rec.metadata.rating}</span>}
                          </div>
                        </div>
                      ) : (
                        <p className="text-[14px] text-gray-400 italic py-4 text-center">Pending...</p>
                      )}
                    </div>
                  ))}

                  {(() => {
                    const weatherRec = recommendations['weather'];
                    if (!weatherRec) return null;
                    const tempMin = weatherRec.metadata?.temp_min;
                    const tempMax = weatherRec.metadata?.temp_max;
                    return (
                      <div className="bg-sky-50 rounded-lg border border-gray-200 border-l-4 border-l-sky-400 p-4 transition-shadow hover:shadow-md">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-[18px]">🌤️</span>
                            <span className="text-[14px] font-semibold uppercase tracking-wide text-gray-500">Weather</span>
                          </div>
                          {tempMin != null && tempMax != null && (
                            <span className="text-[13px] font-semibold text-sky-700">{tempMin}°F – {tempMax}°F</span>
                          )}
                        </div>
                        <p className="text-[13px] text-gray-600 leading-relaxed">{weatherRec.reason || 'Weather data available'}</p>
                        <div className="flex items-center gap-3 mt-2 text-[12px] text-gray-400">
                          {weatherRec.metadata?.num_days && <span>{weatherRec.metadata.num_days}-day forecast</span>}
                          {weatherRec.metadata?.rainy_days > 0 && (
                            <span>🌧️ {weatherRec.metadata.rainy_days} rainy day{weatherRec.metadata.rainy_days !== 1 ? 's' : ''}</span>
                          )}
                        </div>
                      </div>
                    );
                  })()}
                  </div>
                </div>

                {/* RIGHT: Daily Schedule — v6: DailySchedulePanel component */}
                <div className="lg:col-span-3">
                  <DailySchedulePanel
                    dailyPlanRec={dailyPlanRec || null}
                    destination={tripData.destination}
                  />
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* ══════ MAIN CONTENT: Results (left) + Itinerary (right) ══════ */}
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
                            activeResultsTab === tab.id ? 'bg-purple-100 text-purple-700' : 'bg-gray-200 text-gray-600'
                          }`}>{tab.count}</span>
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
                        <h2 className="text-[19px] font-bold text-gray-800">✈️ Available Flights</h2>
                        <div className="flex items-center gap-3">
                          {selectedFlight && (
                            <span className="text-[13px] bg-purple-100 text-purple-700 px-3 py-1 rounded-full font-medium">
                              Selected: {selectedFlight.airline_code} {selectedFlight.outbound?.flight_number} — ${selectedFlight.price}
                            </span>
                          )}
                          <span className="text-[15px] text-gray-500">{flights.length} option{flights.length !== 1 ? 's' : ''}</span>
                        </div>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {flights.map((flight, index) => (
                          <FlightCard
                            key={flight.id || index}
                            flight={flight}
                            isSelected={selectedFlight?.id === flight.id}
                            isAiRecommended={flight.id === aiRecommendedFlightId}
                            onSelect={() => handleSelectFlight(flight)}
                            focusedItemId={focusedItemId}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {activeResultsTab === 'hotels' && (
                    <div>
                      <div className="flex items-center justify-between mb-4">
                        <h2 className="text-[19px] font-bold text-gray-800">🏨 Available Hotels</h2>
                        <div className="flex items-center gap-3">
                          {selectedHotel && (
                            <span className="text-[13px] bg-purple-100 text-purple-700 px-3 py-1 rounded-full font-medium truncate max-w-[280px]">
                              Selected: {selectedHotel.name} — ${selectedHotel.total_price}
                            </span>
                          )}
                          <span className="text-[15px] text-gray-500">{hotels.length} option{hotels.length !== 1 ? 's' : ''}</span>
                        </div>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {hotels.map((hotel, index) => (
                          <HotelCard
                            key={hotel.id || index}
                            hotel={hotel}
                            isSelected={selectedHotel?.id === hotel.id}
                            isAiRecommended={hotel.id === aiRecommendedHotelId}
                            onSelect={() => handleSelectHotel(hotel)}
                            focusedItemId={focusedItemId}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {activeResultsTab === 'restaurants' && (
                    <div>
                      <div className="flex items-center justify-between mb-4">
                        <h2 className="text-[19px] font-bold text-gray-800">🍽️ Recommended Restaurants</h2>
                        <div className="flex items-center gap-3">
                          {selectedRestaurants.length > 0 && (
                            <span className="text-[13px] bg-orange-100 text-orange-700 px-3 py-1 rounded-full font-medium">
                              {selectedRestaurants.length} added to itinerary
                            </span>
                          )}
                          <span className="text-[15px] text-gray-500">{storeRestaurants.length} option{storeRestaurants.length !== 1 ? 's' : ''}</span>
                        </div>
                      </div>
                      {storeRestaurants.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {storeRestaurants.map((restaurant, index) => (
                            <RestaurantCard
                              key={`${restaurant.id}-${index}`}
                              restaurant={restaurant}
                              isSelected={isRestaurantSelected(restaurant.id)}
                              isAiRecommended={isRestaurantAiRecommended(restaurant.id)}
                              onToggle={() => handleToggleRestaurant(restaurant)}
                              focusedItemId={focusedItemId}
                            />
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-12 text-gray-500">
                          <div className="text-4xl mb-3">🍽️</div>
                          <p className="font-semibold">No restaurant results yet</p>
                          <p className="text-[15px] mt-1">Plan your trip to discover great dining options</p>
                        </div>
                      )}
                    </div>
                  )}

                  {activeResultsTab === 'activities' && (
                    <div>
                      <div className="flex items-center justify-between mb-4">
                        <h2 className="text-[19px] font-bold text-gray-800">🎭 Things To Do</h2>
                        <div className="flex items-center gap-3">
                          {selectedActivities.length > 0 && (
                            <span className="text-[13px] bg-blue-100 text-blue-700 px-3 py-1 rounded-full font-medium">
                              {selectedActivities.length} added to itinerary
                            </span>
                          )}
                          <span className="text-[15px] text-gray-500">{storeActivities.length} option{storeActivities.length !== 1 ? 's' : ''}</span>
                        </div>
                      </div>
                      {storeActivities.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {storeActivities.map((activity, index) => (
                            <ActivityCard
                              key={`${activity.id}-${index}`}
                              activity={activity}
                              isSelected={isActivitySelected(activity.id)}
                              isAiRecommended={isActivityAiRecommended(activity.id)}
                              onToggle={() => handleToggleActivity(activity)}
                              focusedItemId={focusedItemId}
                            />
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-12 text-gray-500">
                          <div className="text-4xl mb-3">🎭</div>
                          <p className="font-semibold">No activity results yet</p>
                          <p className="text-[15px] mt-1">Plan your trip to discover things to do</p>
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
                  <h2 className="text-[25px] font-bold text-gray-800 mb-2">Ready to Plan Your Trip?</h2>
                  <p className="text-gray-600 mb-6">Fill in your trip details above and click "Plan My Trip" to see options!</p>
                  <div className="text-[15px] text-gray-500">Flight, Hotel, Restaurant, and Activity options will appear here.</div>
                </div>
              </div>
            )}
          </div>

          <div className="lg:col-span-2">
            <ItinerarySidebar onSectionClick={handleItineraryItemClick} />
          </div>
        </div>
      </div>
    </div>
  );
};
