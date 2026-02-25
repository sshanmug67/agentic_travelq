// frontend/src/components/common/TripSummaryBar.tsx
//
// v5: Wired up all Dashboard props:
//     - onPlanTrip        → "Plan My Trip" button
//     - planningStatus    → spinner / checkmark / error badge
//     - isPlanningCollapsed + onToggleCollapse → chevron toggle (when hasResults)
//     - hasResults        → controls visibility of collapse toggle
//     Fixed budget.used → budget.selected to match useItinerary store shape.

import React, { useState } from 'react';
import { useTripData } from '../../hooks/useTripData';
import { useItinerary } from '../../hooks/useItinerary';
import AirportAutocomplete from './AirportAutocomplete';

interface TripSummaryBarProps {
  onPlanTrip?: () => void;
  planningStatus?: 'idle' | 'planning' | 'completed' | 'failed';
  isPlanningCollapsed?: boolean;
  onToggleCollapse?: () => void;
  hasResults?: boolean;
}

export const TripSummaryBar: React.FC<TripSummaryBarProps> = ({
  onPlanTrip,
  planningStatus = 'idle',
  isPlanningCollapsed = false,
  onToggleCollapse,
  hasResults = false,
}) => {
  const { tripData, setTripData, resetTrip } = useTripData();
  const { clearItinerary, budget, setBudget } = useItinerary();
  
  const [showTripMenu, setShowTripMenu] = useState(false);
  const [showOrigin, setShowOrigin] = useState(true);
  const [editMode, setEditMode] = useState<{
    field: 'origin' | 'destination' | 'dates' | 'travelers' | 'budget' | null;
  }>({ field: null });
  const [tempValues, setTempValues] = useState({
    origin: tripData.origin || '',
    destination: tripData.destination,
    startDate: tripData.startDate,
    endDate: tripData.endDate,
    travelers: tripData.travelers,
    budget: tripData.totalBudget,
  });

  const handleSave = (field: string) => {
    switch (field) {
      case 'origin':
        setTripData({ origin: tempValues.origin });
        if (!tempValues.origin) {
          setShowOrigin(false);
        }
        break;
      case 'destination':
        setTripData({ destination: tempValues.destination });
        break;
      case 'dates':
        setTripData({ 
          startDate: tempValues.startDate, 
          endDate: tempValues.endDate 
        });
        break;
      case 'travelers':
        setTripData({ travelers: tempValues.travelers });
        break;
      case 'budget':
        setTripData({ totalBudget: tempValues.budget });
        setBudget(tempValues.budget);
        break;
    }
    setEditMode({ field: null });
  };

  const handleNewTrip = () => {
    const confirmed = window.confirm(
      'Start a new trip? This will clear your current itinerary.'
    );
    if (confirmed) {
      resetTrip();
      clearItinerary();
      setTempValues({
        origin: 'New York',
        destination: 'London, UK',
        startDate: '2026-02-20',
        endDate: '2026-02-25',
        travelers: 1,
        budget: 4000,
      });
      setShowTripMenu(false);
    }
  };

  // Calculate budget usage
  const totalBudget = tripData.totalBudget || 0;
  const usedBudget = budget?.selected || 0;
  const budgetPercent = totalBudget > 0 ? Math.min((usedBudget / totalBudget) * 100, 100) : 0;

  const isPlanning = planningStatus === 'planning';

  // Format date for display
  const formatDate = (dateStr: string) => {
    if (!dateStr) return '—';
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <div className="bg-gradient-to-r from-blue-600 to-indigo-700 text-white rounded-xl shadow-md px-4 py-2">
      <div className="flex items-center justify-between flex-wrap gap-2">
        {/* ── Left: Trip details ── */}
        <div className="flex items-center gap-3 flex-wrap">

          {/* ── Origin ── */}
          {showOrigin && (
            <>
              <div className="flex items-center gap-1.5 group relative">
                <span className="text-base">✈️</span>
                {editMode.field === 'origin' ? (
                  <AirportAutocomplete
                    value={tempValues.origin}
                    onChange={(display) =>
                      setTempValues({ ...tempValues, origin: display })
                    }
                    onConfirm={() => handleSave('origin')}
                    onCancel={() => {
                      setEditMode({ field: null });
                      if (!tripData.origin) setShowOrigin(false);
                    }}
                    placeholder="From (e.g., New York)"
                    autoFocus
                  />
                ) : (
                  <button
                    onClick={() => {
                      setTempValues({ ...tempValues, origin: tripData.origin || '' });
                      setEditMode({ field: 'origin' });
                    }}
                    className="text-sm hover:underline cursor-pointer opacity-90"
                  >
                    {tripData.origin || 'Click to set origin'}
                  </button>
                )}
              </div>
              <span className="text-white/80 text-base">→</span>
            </>
          )}

          {/* ── Destination ── */}
          <div className="flex items-center gap-1.5 font-semibold group relative">
            <span className="text-base">📍</span>
            {editMode.field === 'destination' ? (
              <AirportAutocomplete
                value={tempValues.destination}
                onChange={(display) =>
                  setTempValues({ ...tempValues, destination: display })
                }
                onConfirm={() => handleSave('destination')}
                onCancel={() => setEditMode({ field: null })}
                placeholder="To (e.g., London)"
                autoFocus
              />
            ) : (
              <button
                onClick={() => {
                  setTempValues({ ...tempValues, destination: tripData.destination });
                  setEditMode({ field: 'destination' });
                }}
                className="text-sm hover:underline cursor-pointer"
              >
                {tripData.destination || 'Set destination'}
              </button>
            )}
          </div>

          {/* ── Divider ── */}
          <span className="text-white/30">|</span>

          {/* ── Dates ── */}
          <div className="flex items-center gap-1.5 group relative">
            <span className="text-base">📅</span>
            {editMode.field === 'dates' ? (
              <div className="flex items-center gap-2 bg-white/20 rounded-lg px-2 py-0.5">
                <input
                  type="date"
                  value={tempValues.startDate}
                  onChange={(e) =>
                    setTempValues({ ...tempValues, startDate: e.target.value })
                  }
                  className="bg-transparent border-none outline-none text-white text-sm w-32
                             [color-scheme:dark]"
                  autoFocus
                />
                <span className="text-white/60 text-xs">to</span>
                <input
                  type="date"
                  value={tempValues.endDate}
                  onChange={(e) =>
                    setTempValues({ ...tempValues, endDate: e.target.value })
                  }
                  className="bg-transparent border-none outline-none text-white text-sm w-32
                             [color-scheme:dark]"
                />
                <button onClick={() => handleSave('dates')} className="text-green-300 hover:text-green-100">✓</button>
                <button onClick={() => setEditMode({ field: null })} className="text-red-300 hover:text-red-100">✕</button>
              </div>
            ) : (
              <button
                onClick={() => {
                  setTempValues({
                    ...tempValues,
                    startDate: tripData.startDate,
                    endDate: tripData.endDate,
                  });
                  setEditMode({ field: 'dates' });
                }}
                className="text-sm hover:underline cursor-pointer"
              >
                {formatDate(tripData.startDate)} – {formatDate(tripData.endDate)}
              </button>
            )}
          </div>

          {/* ── Divider ── */}
          <span className="text-white/30">|</span>

          {/* ── Travelers ── */}
          <div className="flex items-center gap-1.5 group relative">
            <span className="text-base">👤</span>
            {editMode.field === 'travelers' ? (
              <div className="flex items-center gap-2 bg-white/20 rounded-lg px-2 py-0.5">
                <input
                  type="number"
                  min={1}
                  max={9}
                  value={tempValues.travelers}
                  onChange={(e) =>
                    setTempValues({ ...tempValues, travelers: parseInt(e.target.value) || 1 })
                  }
                  onKeyPress={(e) => e.key === 'Enter' && handleSave('travelers')}
                  className="bg-transparent border-none outline-none text-white text-sm w-12 text-center"
                  autoFocus
                />
                <button onClick={() => handleSave('travelers')} className="text-green-300 hover:text-green-100">✓</button>
                <button onClick={() => setEditMode({ field: null })} className="text-red-300 hover:text-red-100">✕</button>
              </div>
            ) : (
              <button
                onClick={() => {
                  setTempValues({ ...tempValues, travelers: tripData.travelers });
                  setEditMode({ field: 'travelers' });
                }}
                className="text-sm hover:underline cursor-pointer"
              >
                {tripData.travelers} traveler{tripData.travelers !== 1 ? 's' : ''}
              </button>
            )}
          </div>
        </div>

        {/* ── Right: Plan button + Status + Budget + Collapse + Menu ── */}
        <div className="flex items-center gap-3">

          {/* ── Plan My Trip button ── */}
          {onPlanTrip && (
            <button
              onClick={onPlanTrip}
              disabled={isPlanning}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-sm font-semibold transition-all ${
                isPlanning
                  ? 'bg-white/20 text-white/60 cursor-not-allowed'
                  : 'bg-white text-indigo-700 hover:bg-white/90 shadow-sm hover:shadow-md'
              }`}
            >
              {planningStatus === 'planning' && (
                <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              )}
              {planningStatus === 'completed' && <span>✅</span>}
              {planningStatus === 'failed' && <span>⚠️</span>}
              {planningStatus === 'idle' && <span>🚀</span>}
              {isPlanning ? 'Planning…' : 'Plan My Trip'}
            </button>
          )}

          {/* ── Collapse / Expand toggle (only when results exist) ── */}
          {hasResults && onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              className="text-white/70 hover:text-white transition-transform"
              title={isPlanningCollapsed ? 'Expand planning panel' : 'Collapse planning panel'}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 16 16"
                fill="none"
                className="transition-transform duration-300"
                style={{ transform: isPlanningCollapsed ? 'rotate(180deg)' : 'rotate(0deg)' }}
              >
                <path d="M4 10L8 6L12 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          )}

          {/* ── Budget bar ── */}
          {totalBudget > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-base">💰</span>
              {editMode.field === 'budget' ? (
                <div className="flex items-center gap-2 bg-white/20 rounded-lg px-2 py-0.5">
                  <span className="text-white/60 text-sm">$</span>
                  <input
                    type="number"
                    min={0}
                    step={100}
                    value={tempValues.budget}
                    onChange={(e) =>
                      setTempValues({ ...tempValues, budget: parseInt(e.target.value) || 0 })
                    }
                    onKeyPress={(e) => e.key === 'Enter' && handleSave('budget')}
                    className="bg-transparent border-none outline-none text-white text-sm w-20"
                    autoFocus
                  />
                  <button onClick={() => handleSave('budget')} className="text-green-300 hover:text-green-100">✓</button>
                  <button onClick={() => setEditMode({ field: null })} className="text-red-300 hover:text-red-100">✕</button>
                </div>
              ) : (
                <button
                  onClick={() => {
                    setTempValues({ ...tempValues, budget: tripData.totalBudget });
                    setEditMode({ field: 'budget' });
                  }}
                  className="flex items-center gap-1.5 hover:opacity-80 cursor-pointer"
                >
                  <div className="w-20 h-1.5 bg-white/20 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        budgetPercent > 90 ? 'bg-red-400' :
                        budgetPercent > 70 ? 'bg-yellow-400' : 'bg-green-400'
                      }`}
                      style={{ width: `${budgetPercent}%` }}
                    />
                  </div>
                  <span className="text-xs opacity-80">
                    ${usedBudget.toLocaleString()} / ${totalBudget.toLocaleString()}
                  </span>
                </button>
              )}
            </div>
          )}

          {/* ── Trip menu ── */}
          <div className="relative">
            <button
              onClick={() => setShowTripMenu(!showTripMenu)}
              className="text-white/70 hover:text-white text-lg"
              title="Trip options"
            >
              ⋯
            </button>
            {showTripMenu && (
              <div className="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-lg py-1 z-50 min-w-[140px]">
                {!showOrigin && (
                  <button
                    onClick={() => {
                      setShowOrigin(true);
                      setShowTripMenu(false);
                    }}
                    className="w-full text-left px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
                  >
                    ➕ Add Origin
                  </button>
                )}
                <button
                  onClick={handleNewTrip}
                  className="w-full text-left px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
                >
                  🔄 New Trip
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
