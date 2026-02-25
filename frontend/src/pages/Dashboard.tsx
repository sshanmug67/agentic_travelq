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
interface DayWeatherData { day: number; date: string; icon: string; high: number; low: number; desc: string; precipProb?: number; }

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
      precipProb: d.weather!.precipitation_prob,
    }));
}

// ─── SVG Temperature Range Chart + Daily Cards ──────────────────────────
const WeatherChart: React.FC<{ days: DayWeatherData[]; globalMin: number; globalMax: number }> = ({ days, globalMin, globalMax }) => {
  if (days.length === 0) return null;
  const W = 280; const H = 80;
  const padX = 24; const padY = 12;
  const chartW = W - padX * 2; const chartH = H - padY * 2;
  const range = (globalMax - globalMin) || 1;

  const toY = (temp: number) => padY + chartH - ((temp - globalMin) / range) * chartH;
  const toX = (i: number) => padX + (days.length === 1 ? chartW / 2 : (i / (days.length - 1)) * chartW);

  // Build smooth curve paths
  const highPts = days.map((d, i) => ({ x: toX(i), y: toY(d.high) }));
  const lowPts = days.map((d, i) => ({ x: toX(i), y: toY(d.low) }));

  const smoothLine = (pts: { x: number; y: number }[]) => {
    if (pts.length === 1) return `M${pts[0].x},${pts[0].y}`;
    let d = `M${pts[0].x},${pts[0].y}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const cx = (pts[i].x + pts[i + 1].x) / 2;
      d += ` C${cx},${pts[i].y} ${cx},${pts[i + 1].y} ${pts[i + 1].x},${pts[i + 1].y}`;
    }
    return d;
  };

  const highPath = smoothLine(highPts);
  const lowPath = smoothLine(lowPts);
  // Area between curves
  const areaPath = highPath + ` L${lowPts[lowPts.length - 1].x},${lowPts[lowPts.length - 1].y}` +
    smoothLine([...lowPts].reverse()).replace('M', ' L') + ' Z';

  return (
    <div>
      {/* SVG Chart */}
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ overflow: 'visible' }}>
        <defs>
          <linearGradient id="tempBand" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#F59E0B" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.15" />
          </linearGradient>
          <linearGradient id="highLine" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#F59E0B" /><stop offset="100%" stopColor="#EF4444" />
          </linearGradient>
          <linearGradient id="lowLine" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#60A5FA" /><stop offset="100%" stopColor="#3B82F6" />
          </linearGradient>
        </defs>
        {/* Grid lines */}
        {[0, 0.5, 1].map((pct, i) => (
          <line key={i} x1={padX} x2={W - padX} y1={padY + chartH * (1 - pct)} y2={padY + chartH * (1 - pct)} stroke="#E2E8F0" strokeWidth="0.5" strokeDasharray="3,3" />
        ))}
        {/* Temperature band area */}
        <path d={areaPath} fill="url(#tempBand)" />
        {/* High temp line */}
        <path d={highPath} fill="none" stroke="url(#highLine)" strokeWidth="2.5" strokeLinecap="round" />
        {/* Low temp line */}
        <path d={lowPath} fill="none" stroke="url(#lowLine)" strokeWidth="2.5" strokeLinecap="round" />
        {/* Data points + labels */}
        {days.map((d, i) => {
          const x = toX(i); const yH = toY(d.high); const yL = toY(d.low);
          return (
            <g key={i}>
              <circle cx={x} cy={yH} r="4" fill="white" stroke="#F59E0B" strokeWidth="2" />
              <circle cx={x} cy={yL} r="4" fill="white" stroke="#3B82F6" strokeWidth="2" />
              <text x={x} y={yH - 8} textAnchor="middle" style={{ fontSize: 9, fontWeight: 700, fill: '#D97706' }}>{d.high}°</text>
              <text x={x} y={yL + 14} textAnchor="middle" style={{ fontSize: 9, fontWeight: 700, fill: '#2563EB' }}>{d.low}°</text>
            </g>
          );
        })}
      </svg>

      {/* Daily forecast cards */}
      <div style={{ display: 'flex', gap: 4, marginTop: 8 }}>
        {days.map((d, i) => {
          let dayName = ''; let dateName = '';
          try {
            const dt = new Date(d.date + 'T12:00:00');
            dayName = dt.toLocaleDateString('en-US', { weekday: 'short' });
            dateName = dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
          } catch {}
          const precipPct = d.precipProb != null ? d.precipProb : null;

          return (
            <div
              key={i}
              style={{
                flex: 1, borderRadius: 12, padding: '8px 4px', textAlign: 'center',
                background: i === 0 ? 'linear-gradient(135deg, rgba(139,92,246,0.08), rgba(236,72,153,0.06))' : 'rgba(241,245,249,0.6)',
                border: i === 0 ? '1.5px solid rgba(139,92,246,0.15)' : '1px solid rgba(226,232,240,0.5)',
              }}
            >
              <div style={{ fontSize: 10, fontWeight: 700, color: '#475569', textTransform: 'uppercase' }}>{dayName}</div>
              <div style={{ fontSize: 8, color: '#94A3B8', marginBottom: 2 }}>{dateName}</div>
              <div style={{ fontSize: 20 }}>{d.icon}</div>
              <div style={{ fontSize: 8, color: '#64748B', fontWeight: 600, marginTop: 2, lineHeight: 1.2, minHeight: 18 }}>{d.desc}</div>
              {precipPct != null && precipPct > 0 && (
                <div style={{ fontSize: 8, color: '#3B82F6', fontWeight: 700, marginTop: 2 }}>
                  💧 {Math.round(precipPct)}%
                </div>
              )}
            </div>
          );
        })}
      </div>
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
    // Clear itinerary RIGHT BEFORE adding new AI picks — avoids stale closure issues
    useItinerary.getState().clearItinerary();
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
    // Always create a fresh trip — don't send stale tripId from a previous search.
    // The new trip_id is returned by the backend and stored via processResults → setTripData({ id }).
    await submitTrip({ userRequest, tripDetails: { origin: tripData.origin, destination: tripData.destination, startDate: tripData.startDate, endDate: tripData.endDate, travelers: tripData.travelers, budget: tripData.totalBudget }, preferences, currentItinerary: { flight: selectedFlight, hotel: selectedHotel, restaurants: selectedRestaurants, activities: selectedActivities } });
  };

  const handleSelectFlight = (flight: any) => selectFlight(flight, flight.id === aiRecommendedFlightId ? 'ai' : 'user');
  const handleSelectHotel = (hotel: any) => selectHotel(hotel, hotel.id === aiRecommendedHotelId ? 'ai' : 'user');
  const handleToggleRestaurant = (restaurant: any) => toggleRestaurant(restaurant);
  const handleToggleActivity = (activity: any) => toggleActivity(activity);
  const handleItineraryItemClick = (tab: 'flights' | 'hotels' | 'restaurants' | 'activities', itemId?: string) => {
    setActiveResultsTab(tab);
    setFocusedItemId(itemId || null);
    if (itemId) {
      // Give React a tick to switch tabs, then scroll to the card
      requestAnimationFrame(() => {
        setTimeout(() => {
          const el = document.querySelector(`[data-item-id="${itemId}"]`);
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.classList.add('ring-2', 'ring-purple-400', 'ring-offset-2');
            setTimeout(() => el.classList.remove('ring-2', 'ring-purple-400', 'ring-offset-2'), 2000);
          }
        }, 100);
      });
      setTimeout(() => setFocusedItemId(null), 2500);
    }
  };

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
    <div style={{ minHeight: '100vh', background: 'linear-gradient(160deg, #FAF5FF 0%, #FDF4FF 25%, #FFF7ED 55%, #FFFBEB 100%)' }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@400;500;600;700&display=swap');
        .journal-text { font-family: 'Caveat', cursive; }
        @keyframes recCardFadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        .rec-card-enter { animation: recCardFadeIn 0.25s ease forwards; }
        @keyframes sparkleFloat { 0%, 100% { transform: translateY(0px); } 50% { transform: translateY(-3px); } }
        .line-clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
      `}</style>

      {/* ══════ Header (TripSummaryBar includes logo, trip pill, budget bar) ══════ */}
      <TripSummaryBar />

      {/* ══════ THREE-COLUMN PLANNING SECTION ══════ */}
      <div style={{ maxWidth: 1440, margin: '0 auto', padding: '20px 28px' }}>
        {showProgressBar && (
          <div className="overflow-hidden transition-all duration-500 ease-in-out" style={{ maxHeight: isPlanningCollapsed ? '44px' : '0px', opacity: isPlanningCollapsed ? 1 : 0, marginBottom: isPlanningCollapsed ? '12px' : '0px' }}>
            <div onClick={() => setIsPlanningCollapsed(false)} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '10px 20px', borderRadius: 14, cursor: 'pointer',
              background: isComplete ? 'linear-gradient(90deg, #059669, #10B981)' : isFailed ? 'linear-gradient(90deg, #DC2626, #EF4444)' : 'linear-gradient(90deg, #6c5ce7, #a855f7)',
              color: 'white', fontSize: 13, fontWeight: 600,
            }}>
              <span>{isComplete ? `✅ Trip planned in ${formatTime(elapsedTime)}` : isFailed ? '❌ Planning failed' : `Planning... ${completedCount}/${totalAgents}`}</span>
              <span style={{ fontSize: 12 }}>Click to expand ▼</span>
            </div>
          </div>
        )}
        <div className="transition-all duration-500 ease-in-out overflow-hidden" style={{ maxHeight: isPlanningCollapsed ? '0px' : '600px', opacity: isPlanningCollapsed ? 0 : 1 }}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-5">
            <div className="lg:h-[380px]"><NaturalLanguageInput value={naturalLanguageRequest} onChange={setNaturalLanguageRequest} onSubmit={handlePlanTrip} isProcessing={isPlanning} /></div>
            <div className="lg:h-[380px]"><PreferencesPanel preferences={preferences} onUpdate={useTripData.getState().updatePreferences} /></div>
            <div className="lg:h-[380px]"><AgentFeedColumn pollData={pollData} isActive={isPlanning} resetKey={feedResetKey} /></div>
          </div>
          <div className="max-w-full">
            <button onClick={() => handlePlanTrip(naturalLanguageRequest)} disabled={isPlanning || !tripData.destination || !tripData.startDate || !tripData.endDate}
              style={{
                width: '100%', padding: 15, borderRadius: 18, border: 'none',
                background: (isPlanning || !tripData.destination || !tripData.startDate || !tripData.endDate)
                  ? '#D1D5DB' : 'linear-gradient(135deg, #8B5CF6, #EC4899, #F97316)',
                backgroundSize: '200% 100%',
                color: 'white', fontSize: 16, fontWeight: 800, cursor: (isPlanning || !tripData.destination) ? 'not-allowed' : 'pointer',
                boxShadow: (isPlanning || !tripData.destination) ? 'none' : '0 8px 32px -4px rgba(139,92,246,0.4)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                transition: 'all 0.3s',
              }}>
              {isPlanning ? (<><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white"></div>Planning Your Trip...</>) : (<>🚀 Plan My Trip</>)}
            </button>
            {showProgressBar && !isPlanningCollapsed && (
              <div style={{
                marginTop: 10, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '10px 20px', borderRadius: 14, cursor: (isComplete || isFailed) ? 'pointer' : 'default',
                background: isComplete ? 'linear-gradient(90deg, #059669, #10B981)' : isFailed ? 'linear-gradient(90deg, #DC2626, #EF4444)' : 'linear-gradient(90deg, #6c5ce7, #a855f7)',
                color: 'white', fontSize: 13, fontWeight: 600,
              }} onClick={() => { if (isComplete || isFailed) setIsPlanningCollapsed(true); }}>
                <span>
                  {isPlanning && <span className="inline-block animate-spin mr-2" style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white', borderRadius: '50%', verticalAlign: 'middle' }} />}
                  {isComplete ? `✅ Trip planned in ${formatTime(elapsedTime)}` : isFailed ? '❌ Planning failed' : `${completedCount}/${totalAgents} agents complete`}
                </span>
                {(isComplete || isFailed) && <span style={{ cursor: 'pointer', fontSize: 12 }}>▲ Collapse</span>}
                {isPlanning && <span style={{ fontSize: 11, opacity: 0.6, fontFamily: 'monospace' }}>{formatTime(elapsedTime)}</span>}
              </div>
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
          <div style={{ maxWidth: 1440, margin: '0 auto', padding: '0 28px 32px' }}>
            <div style={{ background: 'rgba(255,255,255,0.85)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', borderRadius: 24, padding: 28, border: '1px solid rgba(139,92,246,0.1)' }}>

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
                        {/* Legend */}
                        <div className="flex items-center gap-3">
                          <div className="flex items-center gap-1"><div style={{ width: 12, height: 3, borderRadius: 2, background: 'linear-gradient(90deg, #F59E0B, #EF4444)' }} /><span style={{ fontSize: 9, color: '#94A3B8', fontWeight: 600 }}>High</span></div>
                          <div className="flex items-center gap-1"><div style={{ width: 12, height: 3, borderRadius: 2, background: 'linear-gradient(90deg, #60A5FA, #3B82F6)' }} /><span style={{ fontSize: 9, color: '#94A3B8', fontWeight: 600 }}>Low</span></div>
                        </div>
                      </div>

                      {/* Temperature range chart + daily cards */}
                      {dailyWeather.length > 0 && (
                        <div className="px-3 pb-2">
                          <WeatherChart days={dailyWeather} globalMin={globalMin} globalMax={globalMax} />
                        </div>
                      )}

                      {weatherRec.reason && (
                        <div className="px-4 pb-3 pt-1">
                          <p className="text-[12px] text-gray-500 leading-relaxed">{weatherRec.reason}</p>
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
              <div className="bg-white rounded-2xl shadow-lg border border-gray-200 overflow-hidden">
                {/* ── Pill tab bar (compact, matching day pills) ── */}
                <div style={{ display: 'flex', gap: 3, margin: '10px 12px 0', background: 'rgba(255,255,255,0.7)', borderRadius: 14, padding: 3, backdropFilter: 'blur(12px)', border: '1px solid rgba(139,92,246,0.08)' }}>
                  {resultsTabs.map((tab) => {
                    const tabColors: Record<string, string> = { flights: '#F59E0B', hotels: '#3B82F6', restaurants: '#EF4444', activities: '#10B981' };
                    const tc = tabColors[tab.id] || '#8B5CF6';
                    const isActive = activeResultsTab === tab.id;
                    return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveResultsTab(tab.id)}
                      style={{
                        flex: 1, padding: '7px 6px', cursor: 'pointer',
                        borderRadius: 11,
                        fontSize: 12, fontWeight: 700, fontFamily: "'DM Sans', 'Plus Jakarta Sans', sans-serif",
                        background: isActive ? 'linear-gradient(135deg, #8B5CF6, #7C3AED)' : `${tc}08`,
                        color: isActive ? 'white' : '#4B5563',
                        border: isActive ? 'none' : `1.5px solid ${tc}25`,
                        boxShadow: isActive ? '0 3px 12px rgba(139,92,246,0.3)' : `0 1px 3px ${tc}10`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
                        transition: 'all 0.25s ease',
                      }}
                    >
                      <span style={{ fontSize: 13 }}>{tab.icon}</span>
                      {tab.label}
                      {tab.count > 0 && (
                        <span style={{
                          fontSize: 9, fontWeight: 700,
                          background: isActive ? 'rgba(255,255,255,0.25)' : `${tc}15`,
                          color: isActive ? 'white' : `${tc}`,
                          padding: '1px 6px', borderRadius: 6,
                        }}>{tab.count}</span>
                      )}
                    </button>
                    );
                  })}
                </div>
                {/* ── Selection info bar (compact) ── */}
                <div style={{ margin: '6px 12px 0', padding: '6px 12px', borderRadius: 10, background: 'rgba(139,92,246,0.05)', border: '1px solid rgba(139,92,246,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#7C3AED' }}>
                    {activeResultsTab === 'flights' && selectedFlight && `✈️ Selected: ${selectedFlight.airline_code} ${selectedFlight.outbound?.flight_number || ''} — $${selectedFlight.price}`}
                    {activeResultsTab === 'hotels' && selectedHotel && `🏨 Selected: ${selectedHotel.name} — $${selectedHotel.total_price}`}
                    {activeResultsTab === 'restaurants' && selectedRestaurants.length > 0 && `🍽️ ${selectedRestaurants.length} added to itinerary`}
                    {activeResultsTab === 'activities' && selectedActivities.length > 0 && `🎭 ${selectedActivities.length} added to itinerary`}
                    {activeResultsTab === 'flights' && !selectedFlight && '✈️ No flight selected'}
                    {activeResultsTab === 'hotels' && !selectedHotel && '🏨 No hotel selected'}
                    {activeResultsTab === 'restaurants' && selectedRestaurants.length === 0 && '🍽️ No restaurants added'}
                    {activeResultsTab === 'activities' && selectedActivities.length === 0 && '🎭 No activities added'}
                  </span>
                  <span style={{ fontSize: 10, color: '#94A3B8' }}>
                    {activeResultsTab === 'flights' && `${flights.length} option${flights.length !== 1 ? 's' : ''}`}
                    {activeResultsTab === 'hotels' && `${hotels.length} option${hotels.length !== 1 ? 's' : ''}`}
                    {activeResultsTab === 'restaurants' && `${storeRestaurants.length} option${storeRestaurants.length !== 1 ? 's' : ''}`}
                    {activeResultsTab === 'activities' && `${storeActivities.length} option${storeActivities.length !== 1 ? 's' : ''}`}
                  </span>
                </div>
                <div className="p-4 pt-3">
                  {activeResultsTab === 'flights' && (<div><div className="flex items-center justify-between mb-4"><h2 className="text-[19px] font-bold text-gray-800">✈️ Available Flights</h2></div><div className="grid grid-cols-1 md:grid-cols-2 gap-4">{flights.map((flight, index) => (<div key={flight.id || index} data-item-id={flight.id}><FlightCard flight={flight} isSelected={selectedFlight?.id === flight.id} isAiRecommended={flight.id === aiRecommendedFlightId} onSelect={() => handleSelectFlight(flight)} focusedItemId={focusedItemId} /></div>))}</div></div>)}
                  {activeResultsTab === 'hotels' && (<div><div className="flex items-center justify-between mb-4"><h2 className="text-[19px] font-bold text-gray-800">🏨 Available Hotels</h2></div><div className="grid grid-cols-1 md:grid-cols-2 gap-4">{hotels.map((hotel, index) => (<div key={hotel.id || index} data-item-id={hotel.id}><HotelCard hotel={hotel} isSelected={selectedHotel?.id === hotel.id} isAiRecommended={hotel.id === aiRecommendedHotelId} onSelect={() => handleSelectHotel(hotel)} focusedItemId={focusedItemId} /></div>))}</div></div>)}
                  {activeResultsTab === 'restaurants' && (<div><div className="flex items-center justify-between mb-4"><h2 className="text-[19px] font-bold text-gray-800">🍽️ Recommended Restaurants</h2></div>{storeRestaurants.length > 0 ? (<div className="grid grid-cols-1 md:grid-cols-2 gap-4">{storeRestaurants.map((restaurant, index) => (<div key={`${restaurant.id}-${index}`} data-item-id={restaurant.id}><RestaurantCard restaurant={restaurant} isSelected={isRestaurantSelected(restaurant.id)} isAiRecommended={isRestaurantAiRecommended(restaurant.id)} onToggle={() => handleToggleRestaurant(restaurant)} focusedItemId={focusedItemId} /></div>))}</div>) : (<div className="text-center py-12 text-gray-500"><div className="text-4xl mb-3">🍽️</div><p className="font-semibold">No restaurant results yet</p></div>)}</div>)}
                  {activeResultsTab === 'activities' && (<div><div className="flex items-center justify-between mb-4"><h2 className="text-[19px] font-bold text-gray-800">🎭 Things To Do</h2></div>{storeActivities.length > 0 ? (<div className="grid grid-cols-1 md:grid-cols-2 gap-4">{storeActivities.map((activity, index) => (<div key={`${activity.id}-${index}`} data-item-id={activity.id}><ActivityCard activity={activity} isSelected={isActivitySelected(activity.id)} isAiRecommended={isActivityAiRecommended(activity.id)} onToggle={() => handleToggleActivity(activity)} focusedItemId={focusedItemId} /></div>))}</div>) : (<div className="text-center py-12 text-gray-500"><div className="text-4xl mb-3">🎭</div><p className="font-semibold">No activity results yet</p></div>)}</div>)}
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
