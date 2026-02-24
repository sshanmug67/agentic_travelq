// frontend/src/pages/Dashboard.tsx
//
// v7.3 — Refined AI Rec left column:
//   - Flight & Hotel: 2-line preview always visible, click to expand full
//   - Weather: always expanded with per-day thermometer bars (low→high range)
//   - Packing Tips, Local Events, Seasonal Tip: always expanded in left col
//   - Cuisine Rationale & Activity Rationale: moved to bottom below daily schedule
//   - Thermometer uses gradient bar showing temperature range per day

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
import {
  DailySchedulePanel,
  extractNuggets,
  NUGGET_STYLES,
  NUGGET_ICONS,
} from '../components/recommendation/DailySchedulePanel';
import type { Nugget, DaySchedule, StructuredPlan } from '../components/recommendation/DailySchedulePanel';
import { useTripData } from '../hooks/useTripData';
import { useItinerary } from '../hooks/useItinerary';
import { useTripSearch } from '../hooks/useTripSearch';

type ResultsTab = 'flights' | 'hotels' | 'restaurants' | 'activities';
type PanelId = 'flight' | 'hotel' | string;

// ─── Nugget category split ───────────────────────────────────────────────
const LEFT_NUGGET_IDS = new Set(['packing_tips', 'local_events', 'seasonal_tip', 'cuisine_rationale', 'activity_rationale']);
const BOTTOM_NUGGET_IDS = new Set<string>();

// ─── Weather helpers ─────────────────────────────────────────────────────
interface DayWeatherData { day: number; date: string; icon: string; high: number; low: number; desc: string; }

function extractWeatherFromDailyPlan(dailyPlanRec: Record<string, any> | null): DayWeatherData[] {
  if (!dailyPlanRec) return [];
  const structured = dailyPlanRec.metadata?.structured_data as StructuredPlan | undefined;
  if (!structured?.daily_schedule) return [];
  return structured.daily_schedule
    .filter((d: DaySchedule) => d.weather)
    .map((d: DaySchedule) => ({
      day: d.day, date: d.date, icon: d.weather!.icon,
      high: Math.round(d.weather!.temp_high), low: Math.round(d.weather!.temp_low),
      desc: d.weather!.description,
    }));
}

// ─── Vertical Mercury Thermometer Component ─────────────────────────────
const THERMO_HEIGHT = 80; // px height of the tube
const VerticalThermometer: React.FC<{ low: number; high: number; globalMin: number; globalMax: number; icon: string; dayLabel: string }> = ({ low, high, globalMin, globalMax, icon, dayLabel }) => {
  const range = globalMax - globalMin || 1;
  // Mercury fills from bottom (globalMin) to "high" temp
  const mercuryPct = Math.max(12, ((high - globalMin) / range) * 100);
  // Mark where "low" sits on the scale
  const lowMarkPct = ((low - globalMin) / range) * 100;

  return (
    <div className="flex flex-col items-center gap-1" style={{ minWidth: 48 }}>
      {/* Day label */}
      <span className="text-[11px] font-extrabold text-gray-500 uppercase tracking-wide">{dayLabel}</span>
      {/* Weather icon */}
      <span style={{ fontSize: 20 }}>{icon}</span>
      {/* High temp */}
      <span className="text-[11px] font-bold text-red-500">{high}°</span>
      {/* Thermometer tube */}
      <div className="relative rounded-full overflow-hidden" style={{ width: 14, height: THERMO_HEIGHT, background: '#F1F5F9', border: '1.5px solid #E2E8F0' }}>
        {/* Mercury fill from bottom */}
        <div
          className="absolute bottom-0 left-0 right-0 rounded-full"
          style={{
            height: `${mercuryPct}%`,
            background: 'linear-gradient(to top, #DC2626, #EF4444, #F87171)',
            transition: 'height 0.6s ease',
          }}
        />
        {/* Low temp marker line */}
        <div
          className="absolute left-0 right-0"
          style={{
            bottom: `${lowMarkPct}%`,
            height: 2,
            background: '#1E40AF',
            opacity: 0.5,
          }}
        />
      </div>
      {/* Bulb */}
      <div className="rounded-full" style={{ width: 20, height: 20, background: 'linear-gradient(135deg, #DC2626, #B91C1C)', border: '1.5px solid #E2E8F0', marginTop: -6, boxShadow: '0 1px 4px rgba(220,38,38,0.3)' }} />
      {/* Low temp */}
      <span className="text-[11px] font-bold text-blue-500" style={{ marginTop: -2 }}>{low}°</span>
    </div>
  );
};

// ─── Chevron ─────────────────────────────────────────────────────────────
const Chevron: React.FC<{ open: boolean; color?: string }> = ({ open, color = '#94A3B8' }) => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"
    style={{ transition: 'transform 0.3s cubic-bezier(0.4,0,0.2,1)', transform: open ? 'rotate(180deg)' : 'rotate(0deg)', flexShrink: 0 }}>
    <path d="M4 6L8 10L12 6" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

// ═════════════════════════════════════════════════════════════════════════

export const Dashboard: React.FC = () => {
  const { tripData, preferences, flights, hotels, restaurants: storeRestaurants, activities: storeActivities, setTripData, setFlights, setHotels, setRestaurants, setActivities, setWeather } = useTripData();
  const { flight: selectedFlight, hotel: selectedHotel, restaurants: selectedRestaurants, activities: selectedActivities, selectFlight, selectHotel, toggleRestaurant, toggleActivity } = useItinerary();

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

  // Only Flight & Hotel are expandable now
  const [expandedPanel, setExpandedPanel] = useState<PanelId | null>(null);
  const togglePanel = (id: PanelId) => setExpandedPanel(prev => prev === id ? null : id);

  const processResults = useCallback((response: any) => {
    const resolvedTripId = response.tripId || response.trip_id;
    if (resolvedTripId) setTripData({ id: resolvedTripId });
    const results: Record<string, any> = response.results || response.options || {};
    const flightResults = results.flights || []; const hotelResults = results.hotels || []; const restaurantResults = results.restaurants || []; const activityResults = results.activities || [];
    setFlights(flightResults); setHotels(hotelResults); setRestaurants(restaurantResults); setActivities(activityResults); setWeather(results.weather || []);
    if (flightResults.length > 0) { const recFlightId = response.recommendations?.flight?.recommended_id; const aiPick = recFlightId ? flightResults.find((f: any) => String(f.id) === String(recFlightId)) : null; const s = aiPick || flightResults[0]; setAiRecommendedFlightId(s.id); selectFlight(s, 'ai'); }
    if (hotelResults.length > 0) { const recHotelId = response.recommendations?.hotel?.recommended_id; const aiPick = recHotelId ? hotelResults.find((h: any) => String(h.id) === String(recHotelId)) : null; const s = aiPick || hotelResults[0]; setAiRecommendedHotelId(s.id); selectHotel(s, 'ai'); }
    if (restaurantResults.length > 0) { const rec = response.recommendations?.restaurant; const ids: string[] = rec?.metadata?.all_recommended_ids || []; setAiRecommendedRestaurantIds(ids); if (ids.length > 0) { for (const id of ids) { const m = restaurantResults.find((r: any) => String(r.id) === String(id)); if (m) toggleRestaurant(m); } } else { const n = Math.min(3, restaurantResults.length); const fb: string[] = []; for (let i = 0; i < n; i++) { toggleRestaurant(restaurantResults[i]); fb.push(restaurantResults[i].id); } setAiRecommendedRestaurantIds(fb); } }
    if (activityResults.length > 0) { const rec = response.recommendations?.activity; const ids: string[] = rec?.metadata?.all_recommended_ids || []; setAiRecommendedActivityIds(ids); if (ids.length > 0) { for (const id of ids) { const m = activityResults.find((a: any) => String(a.id) === String(id)); if (m) toggleActivity(m); } } else { const n = Math.min(5, activityResults.length); const fb: string[] = []; for (let i = 0; i < n; i++) { toggleActivity(activityResults[i]); fb.push(activityResults[i].id); } setAiRecommendedActivityIds(fb); } }
    if (flightResults.length > 0) setActiveResultsTab('flights'); else if (hotelResults.length > 0) setActiveResultsTab('hotels'); else if (restaurantResults.length > 0) setActiveResultsTab('restaurants'); else if (activityResults.length > 0) setActiveResultsTab('activities');
    if (response.recommendations) setRecommendations(response.recommendations);
    setNaturalLanguageRequest('');
  }, [setTripData, setFlights, setHotels, setRestaurants, setActivities, setWeather, selectFlight, selectHotel, toggleRestaurant, toggleActivity]);

  const { submitTrip, pollData, isSubmitting, isPolling, clearTrip } = useTripSearch({ onComplete: processResults, onError: (err) => { console.error('Trip planning failed:', err); alert('Failed to plan trip: ' + err); }, pollInterval: 2500 });
  const isPlanning = isSubmitting || isPolling;
  const hasResults = flights.length > 0 || hotels.length > 0 || storeRestaurants.length > 0 || storeActivities.length > 0;

  useEffect(() => { if (isPlanning) { startTimeRef.current = Date.now(); setElapsedTime(0); setIsPlanningCollapsed(false); timerRef.current = setInterval(() => { setElapsedTime(Math.floor((Date.now() - startTimeRef.current) / 1000)); }, 1000); } return () => { if (timerRef.current) clearInterval(timerRef.current); }; }, [isPlanning]);
  useEffect(() => { if (pollData?.status === 'completed' || pollData?.status === 'failed') { if (timerRef.current) clearInterval(timerRef.current); const t = setTimeout(() => setIsPlanningCollapsed(true), 2000); return () => clearTimeout(t); } }, [pollData?.status]);
  useEffect(() => { const { flights, hotels, restaurants, activities } = useTripData.getState(); if (!(flights.length > 0 || hotels.length > 0 || restaurants.length > 0 || activities.length > 0)) { try { localStorage.removeItem('itinerary-storage'); } catch (e) {} useItinerary.getState().clearItinerary(); } }, []);

  const handlePlanTrip = async (userRequest: string) => {
    if (!tripData.destination) { alert('Please enter a destination'); return; }
    if (!tripData.startDate || !tripData.endDate) { alert('Please enter travel dates'); return; }
    clearTrip(); setFeedResetKey((k) => k + 1);
    await submitTrip({ tripId: tripData.id, userRequest, tripDetails: { origin: tripData.origin, destination: tripData.destination, startDate: tripData.startDate, endDate: tripData.endDate, travelers: tripData.travelers, budget: tripData.totalBudget }, preferences, currentItinerary: { flight: selectedFlight, hotel: selectedHotel, restaurants: selectedRestaurants, activities: selectedActivities } });
  };

  const handleSelectFlight = (flight: any) => selectFlight(flight, flight.id === aiRecommendedFlightId ? 'ai' : 'user');
  const handleSelectHotel = (hotel: any) => selectHotel(hotel, hotel.id === aiRecommendedHotelId ? 'ai' : 'user');
  const handleToggleRestaurant = (restaurant: any) => toggleRestaurant(restaurant);
  const handleToggleActivity = (activity: any) => toggleActivity(activity);
  const handleItineraryItemClick = (tab: 'flights' | 'hotels' | 'restaurants' | 'activities', itemId?: string) => { setActiveResultsTab(tab); setFocusedItemId(itemId || null); if (itemId) setTimeout(() => setFocusedItemId(null), 1500); };

  const resultsTabs: { id: ResultsTab; label: string; icon: string; count: number }[] = [
    { id: 'flights', label: 'Flights', icon: '✈️', count: flights.length }, { id: 'hotels', label: 'Hotels', icon: '🏨', count: hotels.length },
    { id: 'restaurants', label: 'Restaurants', icon: '🍽️', count: storeRestaurants.length }, { id: 'activities', label: 'Activities', icon: '🎭', count: storeActivities.length },
  ];
  const isRestaurantSelected = (id: string) => selectedRestaurants.some((r) => r.id === id);
  const isActivitySelected = (id: string) => selectedActivities.some((a) => a.id === id);
  const isRestaurantAiRecommended = (id: string) => aiRecommendedRestaurantIds.includes(id);
  const isActivityAiRecommended = (id: string) => aiRecommendedActivityIds.includes(id);
  const formatTime = (s: number) => { const m = Math.floor(s / 60); const sec = s % 60; return m > 0 ? `${m}m ${sec}s` : `${sec}s`; };

  const agents = pollData?.agents || {};
  const completedCount = Object.values(agents).filter((s) => s === 'completed').length;
  const totalAgents = Object.keys(agents).length || 6;
  const progressPercent = totalAgents > 0 ? (completedCount / totalAgents) * 100 : 0;
  const isComplete = pollData?.status === 'completed';
  const isFailed = pollData?.status === 'failed';
  const showProgressBar = isPlanning || isComplete || isFailed;

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-pink-50 to-orange-50">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@400;500;600;700&display=swap');
        .journal-text { font-family: 'Caveat', cursive; }
        @keyframes recCardFadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        .rec-card-enter { animation: recCardFadeIn 0.25s ease forwards; }
        @keyframes sparkleFloat { 0%, 100% { transform: translateY(0px); } 50% { transform: translateY(-3px); } }
        .line-clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
      `}</style>

      {/* ══════ Header ══════ */}
      <div className="bg-white shadow-md sticky top-0 z-40">
        <div className="px-6 lg:px-[10%] py-3 flex items-center justify-between">
          <h1 className="text-[25px] font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">TravelQ</h1>
          <div className="flex items-center gap-4"><button className="text-gray-600 hover:text-gray-800">🔍</button><button className="text-gray-600 hover:text-gray-800">🔔</button><button className="text-gray-600 hover:text-gray-800">👤 Profile</button><button className="text-gray-600 hover:text-gray-800">⚙️</button></div>
        </div>
      </div>
      <TripSummaryBar />
      <PreferencesSummary preferences={preferences} />

      {/* ══════ THREE-COLUMN PLANNING SECTION ══════ */}
      <div className="px-6 lg:px-[10%] py-4">
        {showProgressBar && (
          <div className="overflow-hidden transition-all duration-500 ease-in-out" style={{ maxHeight: isPlanningCollapsed ? '36px' : '0px', opacity: isPlanningCollapsed ? 1 : 0, marginBottom: isPlanningCollapsed ? '12px' : '0px' }}>
            <div onClick={() => setIsPlanningCollapsed(false)} className="relative h-8 overflow-hidden cursor-pointer shadow-lg rounded-xl" style={{ background: isComplete ? '#0d1f0d' : isFailed ? '#2e1a1a' : '#1a1a2e' }}>
              <div className="absolute top-0 left-0 h-full transition-all duration-700" style={{ width: `${progressPercent}%`, background: isComplete ? 'linear-gradient(90deg, #10b981, #34d399)' : isFailed ? 'linear-gradient(90deg, #ef4444, #f87171)' : 'linear-gradient(90deg, #6c5ce7, #a855f7, #ec4899)' }} />
              <div className="relative z-10 flex items-center justify-between h-full px-4"><div className="flex items-center gap-2">{isComplete && <span className="text-emerald-400 font-bold text-xs">✓</span>}{isFailed && <span className="text-red-400 font-bold text-xs">✕</span>}<span className="text-white text-xs font-medium">{isComplete ? `Trip planned in ${formatTime(elapsedTime)}` : isFailed ? 'Planning failed' : `Planning... ${completedCount}/${totalAgents}`}</span></div><span className="text-white font-bold text-[11px] tracking-wide drop-shadow-sm">Click to expand ▼</span></div>
            </div>
          </div>
        )}
        <div className="transition-all duration-500 ease-in-out overflow-hidden" style={{ maxHeight: isPlanningCollapsed ? '0px' : '600px', opacity: isPlanningCollapsed ? 0 : 1 }}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-5">
            <div className="lg:h-[380px]"><div className="bg-white rounded-xl shadow-lg border-2 border-gray-300 overflow-hidden h-full flex flex-col"><NaturalLanguageInput value={naturalLanguageRequest} onChange={setNaturalLanguageRequest} onSubmit={handlePlanTrip} isProcessing={isPlanning} /></div></div>
            <div className="lg:h-[380px]"><PreferencesPanel preferences={preferences} onUpdate={useTripData.getState().updatePreferences} /></div>
            <div className="lg:h-[380px]"><AgentFeedColumn pollData={pollData} isActive={isPlanning} resetKey={feedResetKey} /></div>
          </div>
          <div className="max-w-full">
            <button onClick={() => handlePlanTrip(naturalLanguageRequest)} disabled={isPlanning || !tripData.destination || !tripData.startDate || !tripData.endDate} className="w-full bg-gradient-to-r from-purple-600 via-pink-600 to-orange-600 hover:from-purple-700 hover:via-pink-700 hover:to-orange-700 disabled:from-gray-400 disabled:via-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed text-white font-bold text-[17px] py-2.5 px-8 rounded-xl shadow-2xl transition-all duration-300 transform hover:scale-[1.02] disabled:hover:scale-100 flex items-center justify-center gap-3">
              {isPlanning ? (<><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white"></div>Planning Your Trip...</>) : (<>🚀 Plan My Trip</>)}
            </button>
            {showProgressBar && !isPlanningCollapsed && (
              <div className="mt-2"><div className="relative h-7 overflow-hidden shadow-lg rounded-xl cursor-pointer" style={{ background: isComplete ? '#0d1f0d' : isFailed ? '#2e1a1a' : '#1a1a2e' }} onClick={() => { if (isComplete || isFailed) setIsPlanningCollapsed(true); }}><div className="absolute top-0 left-0 h-full transition-all duration-700 ease-out" style={{ width: `${isPlanning ? Math.max(progressPercent, 5) : progressPercent}%`, background: isComplete ? 'linear-gradient(90deg, #10b981, #34d399)' : isFailed ? 'linear-gradient(90deg, #ef4444, #f87171)' : 'linear-gradient(90deg, #6c5ce7 0%, #a855f7 50%, #ec4899 100%)' }} /><div className="relative z-10 flex items-center justify-between h-full px-4"><div className="flex items-center gap-2">{isPlanning && <div className="animate-spin w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full" />}{isComplete && <span className="text-emerald-400 font-bold text-sm">✓</span>}{isFailed && <span className="text-red-400 font-bold text-sm">✕</span>}<span className="text-white text-xs font-medium">{isComplete ? `Trip planned in ${formatTime(elapsedTime)}` : isFailed ? 'Planning failed' : `${completedCount}/${totalAgents} agents complete`}</span></div><div className="flex items-center gap-3">{isPlanning && <span className="text-white/50 text-[11px] font-mono tabular-nums">{formatTime(elapsedTime)}</span>}{(isComplete || isFailed) && <span className="text-white font-bold text-[11px] tracking-wide drop-shadow-sm">▲ Collapse</span>}</div></div></div></div>
            )}
          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          ✨ AI RECOMMENDATIONS — v7.3
          ══════════════════════════════════════════════════════════════════ */}
      {recommendations && Object.keys(recommendations).length > 0 && (() => {
        const flightRec = recommendations['flight'] || null;
        const hotelRec = recommendations['hotel'] || null;
        const weatherRec = recommendations['weather'] || null;
        const dailyPlanRec = recommendations['daily_plan'] || null;
        const allNuggets: Nugget[] = extractNuggets(dailyPlanRec);
        const leftNuggets = allNuggets.filter(n => LEFT_NUGGET_IDS.has(n.id));
        const bottomNuggets = allNuggets.filter(n => BOTTOM_NUGGET_IDS.has(n.id));
        const dailyWeather = extractWeatherFromDailyPlan(dailyPlanRec);
        const tempMin = weatherRec?.metadata?.temp_min;
        const tempMax = weatherRec?.metadata?.temp_max;
        const globalMin = dailyWeather.length > 0 ? Math.min(...dailyWeather.map(d => d.low)) : (tempMin || 30);
        const globalMax = dailyWeather.length > 0 ? Math.max(...dailyWeather.map(d => d.high)) : (tempMax || 70);
        const displayDest = tripData.destination || 'your trip';

        const bgGradients: Record<string, string> = { sky: 'linear-gradient(135deg, #F0F9FF, #E0F2FE)', purple: 'linear-gradient(135deg, #FDF4FF, #FAE8FF)', orange: 'linear-gradient(135deg, #FFF7ED, #FFEDD5)', green: 'linear-gradient(135deg, #F0FDF4, #DCFCE7)', emerald: 'linear-gradient(135deg, #ECFDF5, #D1FAE5)' };
        const borderClrs: Record<string, string> = { sky: 'rgba(56,189,248,0.25)', purple: 'rgba(167,139,250,0.25)', orange: 'rgba(251,146,60,0.25)', green: 'rgba(74,222,128,0.25)', emerald: 'rgba(52,211,153,0.25)' };

        return (
          <div className="px-6 lg:px-[10%] pb-8">
            <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4">

              {/* Header */}
              <div className="flex items-center gap-3 mb-4">
                <div className="flex items-center justify-center flex-shrink-0" style={{ width: 42, height: 42, borderRadius: 14, background: 'linear-gradient(135deg, #8B5CF6, #EC4899)', fontSize: 21, animation: 'sparkleFloat 3s ease-in-out infinite', boxShadow: '0 4px 14px rgba(139,92,246,0.3)' }}>✨</div>
                <div>
                  <h3 className="journal-text" style={{ fontSize: 26, fontWeight: 700, color: '#1E293B', lineHeight: 1.1, margin: 0 }}>AI Recommendations</h3>
                  <p style={{ fontSize: 14, color: '#94A3B8', margin: 0 }}>Your personalized {displayDest} adventure, day by day</p>
                </div>
              </div>
              <hr className="border-gray-200 mb-4" />

              <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

                {/* ═══ LEFT COLUMN ═══ */}
                <div className="lg:col-span-2 lg:border-r lg:border-gray-200 lg:pr-6">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-[20px]">🎯</span>
                    <h4 className="text-[16px] font-semibold uppercase tracking-wide text-gray-500">Top Picks</h4>
                  </div>

                  {/* ── FLIGHT: 2-line preview, click to expand ────── */}
                  <div
                    className="rounded-2xl overflow-hidden mb-3 cursor-pointer transition-all duration-200 hover:shadow-lg"
                    style={{ background: 'linear-gradient(135deg, #FFFBEB, #FEF3C7)', border: '1.5px solid rgba(245,158,11,0.25)' }}
                    onClick={() => togglePanel('flight')}
                  >
                    <div className="flex items-center justify-between px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <span className="text-[22px]">✈️</span>
                        <div>
                          <div className="text-[12px] font-bold uppercase tracking-wider text-amber-600/70">Flight</div>
                          <div className="text-[17px] font-bold text-gray-800">{flightRec?.metadata?.airline || 'Pending...'}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {flightRec?.metadata?.price != null && <span className="text-[20px] font-extrabold text-amber-800">${Number(flightRec.metadata.price).toFixed(2)}</span>}
                        <Chevron open={expandedPanel === 'flight'} color="#D97706" />
                      </div>
                    </div>
                    {/* 2-line preview always visible */}
                    {flightRec?.reason && (
                      <div className="px-4 pb-2.5" style={{ marginTop: -4 }}>
                        <p className={`text-[14px] text-gray-600 leading-relaxed ${expandedPanel === 'flight' ? '' : 'line-clamp-2'}`}>
                          {flightRec.reason}
                        </p>
                        {expandedPanel === 'flight' && (
                          <div className="flex items-center gap-2 flex-wrap mt-2 rec-card-enter">
                            {flightRec.metadata?.is_direct !== undefined && <span className="text-[12px] font-semibold bg-amber-200/60 text-amber-800 px-2 py-0.5 rounded-lg">{flightRec.metadata.is_direct ? '✅ Direct' : '🔗 Connecting'}</span>}
                            {flightRec.metadata?.total_options_reviewed && <span className="text-[12px] text-amber-700/60">{flightRec.metadata.total_options_reviewed} reviewed</span>}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* ── HOTEL: 2-line preview, click to expand ─────── */}
                  <div
                    className="rounded-2xl overflow-hidden mb-3 cursor-pointer transition-all duration-200 hover:shadow-lg"
                    style={{ background: 'linear-gradient(135deg, #EFF6FF, #DBEAFE)', border: '1.5px solid rgba(59,130,246,0.2)' }}
                    onClick={() => togglePanel('hotel')}
                  >
                    <div className="flex items-center justify-between px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <span className="text-[22px]">🏨</span>
                        <div>
                          <div className="text-[12px] font-bold uppercase tracking-wider text-blue-600/70">Hotel</div>
                          <div className="text-[17px] font-bold text-gray-800 truncate max-w-[200px]">{hotelRec?.metadata?.hotel_name || hotelRec?.metadata?.name || 'Pending...'}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {hotelRec?.metadata?.price != null && <span className="text-[20px] font-extrabold text-blue-800">${Number(hotelRec.metadata.price).toFixed(2)}</span>}
                        <Chevron open={expandedPanel === 'hotel'} color="#2563EB" />
                      </div>
                    </div>
                    {hotelRec?.reason && (
                      <div className="px-4 pb-2.5" style={{ marginTop: -4 }}>
                        <p className={`text-[14px] text-gray-600 leading-relaxed ${expandedPanel === 'hotel' ? '' : 'line-clamp-2'}`}>
                          {hotelRec.reason}
                        </p>
                        {expandedPanel === 'hotel' && (
                          <div className="flex items-center gap-2 flex-wrap mt-2 rec-card-enter">
                            {hotelRec.metadata?.rating && <span className="text-[12px] font-semibold bg-blue-200/50 text-blue-800 px-2 py-0.5 rounded-lg">⭐ {hotelRec.metadata.rating}</span>}
                            {hotelRec.metadata?.price_per_night && <span className="text-[12px] font-semibold bg-blue-200/50 text-blue-800 px-2 py-0.5 rounded-lg">${hotelRec.metadata.price_per_night}/night</span>}
                            {hotelRec.metadata?.total_options_reviewed && <span className="text-[12px] text-blue-700/60">{hotelRec.metadata.total_options_reviewed} reviewed</span>}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* ── WEATHER: Always expanded + thermometer bars ── */}
                  {weatherRec && (
                    <div className="rounded-2xl overflow-hidden mb-3" style={{ background: 'linear-gradient(135deg, #F0F9FF, #E0F2FE)', border: '1.5px solid rgba(14,165,233,0.15)' }}>
                      <div className="flex items-center justify-between px-4 py-3">
                        <div className="flex items-center gap-2.5">
                          <span className="text-[22px]">🌤️</span>
                          <div>
                            <div className="text-[12px] font-bold uppercase tracking-wider text-sky-600/70">Weather</div>
                            <div className="text-[17px] font-bold text-gray-800">{tempMin != null && tempMax != null ? `${tempMin}°F – ${tempMax}°F` : 'Forecast available'}</div>
                          </div>
                        </div>
                      </div>

                      {/* Vertical thermometers per day */}
                      {dailyWeather.length > 0 && (
                        <div className="px-4 pb-2 pt-1">
                          <div className="flex items-end justify-around gap-2">
                            {dailyWeather.map((dw, i) => {
                              let shortDay = `D${dw.day}`;
                              try { const d = new Date(dw.date + 'T12:00:00'); shortDay = d.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase(); } catch {}
                              return (
                                <VerticalThermometer key={i} low={dw.low} high={dw.high} globalMin={globalMin} globalMax={globalMax} icon={dw.icon} dayLabel={shortDay} />
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {weatherRec.reason && (
                        <div className="px-4 pb-3 pt-1.5">
                          <p className="text-[13px] text-gray-500 leading-relaxed">{weatherRec.reason}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ── LEFT NUGGETS: Always expanded ────────────── */}
                  {leftNuggets.length > 0 && (
                    <>
                      <div className="text-[12px] font-bold uppercase tracking-widest text-gray-400 mb-2 mt-1 px-0.5">💡 Travel Tips</div>
                      <div className="grid grid-cols-2 gap-2.5">
                        {leftNuggets.map((nugget, i) => {
                          const nStyle = NUGGET_STYLES[nugget.color] || NUGGET_STYLES.emerald;
                          const icon = NUGGET_ICONS[nugget.id] || '💡';
                          const isLastOdd = i === leftNuggets.length - 1 && leftNuggets.length % 2 === 1;
                          return (
                            <div
                              key={nugget.id}
                              className={`rounded-2xl overflow-hidden ${isLastOdd ? 'col-span-2' : ''}`}
                              style={{ background: bgGradients[nugget.color] || bgGradients.emerald, border: `1.5px solid ${borderClrs[nugget.color] || borderClrs.emerald}` }}
                            >
                              <div className="px-3 py-2.5">
                                <div className="flex items-center gap-2 mb-1.5">
                                  <span className="text-[18px] flex-shrink-0">{icon}</span>
                                  <span className={`text-[15px] font-bold ${nStyle.titleColor}`}>{nugget.title}</span>
                                </div>
                                <p className={`text-[13px] ${nStyle.textColor} leading-relaxed`}>{nugget.content}</p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>

                {/* ═══ RIGHT COLUMN: Daily Schedule + Bottom Nuggets ═══ */}
                <div className="lg:col-span-3">
                  <DailySchedulePanel dailyPlanRec={dailyPlanRec || null} destination={tripData.destination} hideNuggets={true} />

                  {/* Cuisine & Activity Rationale at the bottom */}
                  {bottomNuggets.length > 0 && (
                    <div className="grid grid-cols-2 gap-2.5 mt-3">
                      {bottomNuggets.map((nugget) => {
                        const nStyle = NUGGET_STYLES[nugget.color] || NUGGET_STYLES.emerald;
                        const icon = NUGGET_ICONS[nugget.id] || '💡';
                        return (
                          <div
                            key={nugget.id}
                            className="rounded-2xl overflow-hidden"
                            style={{ background: bgGradients[nugget.color] || bgGradients.emerald, border: `1.5px solid ${borderClrs[nugget.color] || borderClrs.emerald}` }}
                          >
                            <div className="px-3.5 py-3">
                              <div className="flex items-center gap-2 mb-1.5">
                                <span className="text-[18px] flex-shrink-0">{icon}</span>
                                <span className={`text-[15px] font-bold ${nStyle.titleColor}`}>{nugget.title}</span>
                              </div>
                              <p className={`text-[13px] ${nStyle.textColor} leading-relaxed`}>{nugget.content}</p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* ══════ Results + Itinerary ══════ */}
      <div className="px-6 lg:px-[10%] pb-6">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3">
            {hasResults ? (
              <div className="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
                <div className="flex border-b bg-gradient-to-r from-purple-50 to-pink-50">
                  {resultsTabs.map((tab) => (
                    <button key={tab.id} onClick={() => setActiveResultsTab(tab.id)} className={`flex-1 px-4 py-3 text-[15px] font-medium transition-all duration-300 relative ${activeResultsTab === tab.id ? 'text-purple-700 bg-white' : 'text-gray-600 hover:text-purple-600 hover:bg-white/50'}`}>
                      <span className="flex items-center justify-center gap-2"><span className="text-[19px]">{tab.icon}</span><span>{tab.label}</span>{tab.count > 0 && <span className={`text-[13px] px-2 py-0.5 rounded-full ${activeResultsTab === tab.id ? 'bg-purple-100 text-purple-700' : 'bg-gray-200 text-gray-600'}`}>{tab.count}</span>}</span>
                      {activeResultsTab === tab.id && <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-purple-600 to-pink-600" />}
                    </button>
                  ))}
                </div>
                <div className="p-6">
                  {activeResultsTab === 'flights' && (<div><div className="flex items-center justify-between mb-4"><h2 className="text-[19px] font-bold text-gray-800">✈️ Available Flights</h2><div className="flex items-center gap-3">{selectedFlight && <span className="text-[13px] bg-purple-100 text-purple-700 px-3 py-1 rounded-full font-medium">Selected: {selectedFlight.airline_code} {selectedFlight.outbound?.flight_number} — ${selectedFlight.price}</span>}<span className="text-[15px] text-gray-500">{flights.length} option{flights.length !== 1 ? 's' : ''}</span></div></div><div className="grid grid-cols-1 md:grid-cols-2 gap-4">{flights.map((flight, index) => (<FlightCard key={flight.id || index} flight={flight} isSelected={selectedFlight?.id === flight.id} isAiRecommended={flight.id === aiRecommendedFlightId} onSelect={() => handleSelectFlight(flight)} focusedItemId={focusedItemId} />))}</div></div>)}
                  {activeResultsTab === 'hotels' && (<div><div className="flex items-center justify-between mb-4"><h2 className="text-[19px] font-bold text-gray-800">🏨 Available Hotels</h2><div className="flex items-center gap-3">{selectedHotel && <span className="text-[13px] bg-purple-100 text-purple-700 px-3 py-1 rounded-full font-medium truncate max-w-[280px]">Selected: {selectedHotel.name} — ${selectedHotel.total_price}</span>}<span className="text-[15px] text-gray-500">{hotels.length} option{hotels.length !== 1 ? 's' : ''}</span></div></div><div className="grid grid-cols-1 md:grid-cols-2 gap-4">{hotels.map((hotel, index) => (<HotelCard key={hotel.id || index} hotel={hotel} isSelected={selectedHotel?.id === hotel.id} isAiRecommended={hotel.id === aiRecommendedHotelId} onSelect={() => handleSelectHotel(hotel)} focusedItemId={focusedItemId} />))}</div></div>)}
                  {activeResultsTab === 'restaurants' && (<div><div className="flex items-center justify-between mb-4"><h2 className="text-[19px] font-bold text-gray-800">🍽️ Recommended Restaurants</h2><div className="flex items-center gap-3">{selectedRestaurants.length > 0 && <span className="text-[13px] bg-orange-100 text-orange-700 px-3 py-1 rounded-full font-medium">{selectedRestaurants.length} added to itinerary</span>}<span className="text-[15px] text-gray-500">{storeRestaurants.length} option{storeRestaurants.length !== 1 ? 's' : ''}</span></div></div>{storeRestaurants.length > 0 ? (<div className="grid grid-cols-1 md:grid-cols-2 gap-4">{storeRestaurants.map((restaurant, index) => (<RestaurantCard key={`${restaurant.id}-${index}`} restaurant={restaurant} isSelected={isRestaurantSelected(restaurant.id)} isAiRecommended={isRestaurantAiRecommended(restaurant.id)} onToggle={() => handleToggleRestaurant(restaurant)} focusedItemId={focusedItemId} />))}</div>) : (<div className="text-center py-12 text-gray-500"><div className="text-4xl mb-3">🍽️</div><p className="font-semibold">No restaurant results yet</p></div>)}</div>)}
                  {activeResultsTab === 'activities' && (<div><div className="flex items-center justify-between mb-4"><h2 className="text-[19px] font-bold text-gray-800">🎭 Things To Do</h2><div className="flex items-center gap-3">{selectedActivities.length > 0 && <span className="text-[13px] bg-blue-100 text-blue-700 px-3 py-1 rounded-full font-medium">{selectedActivities.length} added to itinerary</span>}<span className="text-[15px] text-gray-500">{storeActivities.length} option{storeActivities.length !== 1 ? 's' : ''}</span></div></div>{storeActivities.length > 0 ? (<div className="grid grid-cols-1 md:grid-cols-2 gap-4">{storeActivities.map((activity, index) => (<ActivityCard key={`${activity.id}-${index}`} activity={activity} isSelected={isActivitySelected(activity.id)} isAiRecommended={isActivityAiRecommended(activity.id)} onToggle={() => handleToggleActivity(activity)} focusedItemId={focusedItemId} />))}</div>) : (<div className="text-center py-12 text-gray-500"><div className="text-4xl mb-3">🎭</div><p className="font-semibold">No activity results yet</p></div>)}</div>)}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-200"><div className="text-center py-20"><div className="text-6xl mb-4">🚀</div><h2 className="text-[25px] font-bold text-gray-800 mb-2">Ready to Plan Your Trip?</h2><p className="text-gray-600 mb-6">Fill in your trip details above and click "Plan My Trip" to see options!</p></div></div>
            )}
          </div>
          <div className="lg:col-span-2"><ItinerarySidebar onSectionClick={handleItineraryItemClick} /></div>
        </div>
      </div>
    </div>
  );
};
