// frontend/src/components/common/TripSummaryBar.tsx
//
// v4: Only spacing changes — all font sizes identical to original
//   - py-4 → py-2
//   - mb-2 → mb-1
//   - mt-3 → mt-1
//   - Budget bar h-2 → h-1.5
//   - Everything else: UNCHANGED from original

import React, { useState } from 'react';
import { useTripData } from '../../hooks/useTripData';
import { useItinerary } from '../../hooks/useItinerary';

export const TripSummaryBar: React.FC = () => {
  const { tripData, setTripData, resetTrip } = useTripData();
  const { clearItinerary, budget, setBudget } = useItinerary();
  
  const [showTripMenu, setShowTripMenu] = useState(false);
  const [showOrigin, setShowOrigin] = useState(true); // Always show origin
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
      setShowOrigin(true);
      setEditMode({ field: 'destination' });
    }
    setShowTripMenu(false);
  };

  const handleClearItinerary = () => {
    const confirmed = window.confirm(
      'Clear all selected items? Trip details will be kept.'
    );
    if (confirmed) {
      clearItinerary();
    }
    setShowTripMenu(false);
  };

  const toggleOriginField = () => {
    if (showOrigin && tripData.origin) {
      const confirmed = window.confirm('Remove origin location?');
      if (confirmed) {
        setTripData({ origin: '' });
        setShowOrigin(false);
      }
    } else {
      setShowOrigin(true);
      setEditMode({ field: 'origin' });
    }
  };

  return (
    <div className="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 text-white shadow-xl">
      <div className="px-6 py-2">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold opacity-90">
              {tripData.id ? 'Current Trip' : 'New Trip'}
            </h2>
            {/* Show trip ID badge only for existing trips */}
            {tripData.id && (
              <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full opacity-70">
                {tripData.id}
              </span>
            )}
          </div>
          
          {/* Trip Actions Menu */}
          <div className="relative">
            <button
              onClick={() => setShowTripMenu(!showTripMenu)}
              className="p-2 hover:bg-white/20 rounded-lg transition-all"
              title="Trip Actions"
            >
              ⋮
            </button>
            
            {showTripMenu && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-2xl border border-gray-200 py-1 z-50">
                <button
                  onClick={toggleOriginField}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-blue-50 flex items-center gap-2"
                >
                  {showOrigin ? '➖ Remove Origin' : '➕ Add Origin Location'}
                </button>
                <hr className="my-1" />
                <button
                  onClick={handleNewTrip}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-purple-50 flex items-center gap-2"
                >
                  ✨ New Trip
                </button>
                <button
                  onClick={handleClearItinerary}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-red-50 flex items-center gap-2"
                >
                  🗑️ Clear Itinerary
                </button>
                <hr className="my-1" />
                <button
                  onClick={() => {
                    alert('My Trips feature coming soon!');
                    setShowTripMenu(false);
                  }}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-blue-50 flex items-center gap-2"
                >
                  📋 My Trips
                </button>
                <button
                  onClick={() => {
                    if (!tripData.id) {
                      alert('Plan a trip first before saving!');
                    } else {
                      alert('Save Trip feature coming soon!');
                    }
                    setShowTripMenu(false);
                  }}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-green-50 flex items-center gap-2"
                >
                  💾 Save Trip
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4 text-sm">
          {/* Origin (Optional) */}
          {showOrigin && (
            <>
              <div className="flex items-center gap-2 font-semibold group relative">
                <span className="text-2xl">🏠</span>
                {editMode.field === 'origin' ? (
                  <div className="flex items-center gap-2 bg-white/20 rounded-lg px-3 py-1">
                    <input
                      type="text"
                      value={tempValues.origin}
                      onChange={(e) =>
                        setTempValues({ ...tempValues, origin: e.target.value })
                      }
                      onKeyPress={(e) => e.key === 'Enter' && handleSave('origin')}
                      className="bg-transparent border-none outline-none text-white placeholder-white/60 w-48"
                      placeholder="From (e.g., New York)"
                      autoFocus
                    />
                    <button
                      onClick={() => handleSave('origin')}
                      className="text-green-300 hover:text-green-100"
                    >
                      ✓
                    </button>
                    <button
                      onClick={() => {
                        setEditMode({ field: null });
                        if (!tripData.origin) setShowOrigin(false);
                      }}
                      className="text-red-300 hover:text-red-100"
                    >
                      ✕
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => {
                      setTempValues({ ...tempValues, origin: tripData.origin || '' });
                      setEditMode({ field: 'origin' });
                    }}
                    className="text-base hover:underline cursor-pointer opacity-90"
                  >
                    {tripData.origin || 'Click to set origin'}
                  </button>
                )}
              </div>
              <span className="text-white/80 text-xl">→</span>
            </>
          )}

          {/* Destination */}
          <div className="flex items-center gap-2 font-semibold group relative">
            <span className="text-2xl">📍</span>
            {editMode.field === 'destination' ? (
              <div className="flex items-center gap-2 bg-white/20 rounded-lg px-3 py-1">
                <input
                  type="text"
                  value={tempValues.destination}
                  onChange={(e) =>
                    setTempValues({ ...tempValues, destination: e.target.value })
                  }
                  onKeyPress={(e) => e.key === 'Enter' && handleSave('destination')}
                  className="bg-transparent border-none outline-none text-white placeholder-white/60 w-48"
                  placeholder="Enter destination"
                  autoFocus
                />
                <button
                  onClick={() => handleSave('destination')}
                  className="text-green-300 hover:text-green-100"
                >
                  ✓
                </button>
                <button
                  onClick={() => setEditMode({ field: null })}
                  className="text-red-300 hover:text-red-100"
                >
                  ✕
                </button>
              </div>
            ) : (
              <button
                onClick={() => {
                  setTempValues({ ...tempValues, destination: tripData.destination });
                  setEditMode({ field: 'destination' });
                }}
                className="text-lg hover:underline cursor-pointer"
              >
                {tripData.destination || 'Click to add destination'}
              </button>
            )}
          </div>

          <span className="text-white/60">•</span>

          {/* Dates */}
          <div className="flex items-center gap-2 group">
            <span className="text-xl">📅</span>
            {editMode.field === 'dates' ? (
              <div className="flex items-center gap-2 bg-white/20 rounded-lg px-3 py-1">
                <input
                  type="date"
                  value={tempValues.startDate}
                  onChange={(e) =>
                    setTempValues({ ...tempValues, startDate: e.target.value })
                  }
                  className="bg-transparent border-none outline-none text-white [color-scheme:dark]"
                />
                <span>-</span>
                <input
                  type="date"
                  value={tempValues.endDate}
                  onChange={(e) =>
                    setTempValues({ ...tempValues, endDate: e.target.value })
                  }
                  className="bg-transparent border-none outline-none text-white [color-scheme:dark]"
                />
                <button
                  onClick={() => handleSave('dates')}
                  className="text-green-300 hover:text-green-100 ml-2"
                >
                  ✓
                </button>
                <button
                  onClick={() => setEditMode({ field: null })}
                  className="text-red-300 hover:text-red-100"
                >
                  ✕
                </button>
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
                className="hover:underline cursor-pointer"
              >
                {tripData.startDate && tripData.endDate ? (
                  <>
                    {new Date(tripData.startDate).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                    })}{' '}
                    -{' '}
                    {new Date(tripData.endDate).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                  </>
                ) : (
                  'Click to add dates'
                )}
              </button>
            )}
          </div>

          <span className="text-white/60">•</span>

          {/* Travelers */}
          <div className="flex items-center gap-2 group">
            <span className="text-xl">👤</span>
            {editMode.field === 'travelers' ? (
              <div className="flex items-center gap-2 bg-white/20 rounded-lg px-3 py-1">
                <input
                  type="number"
                  min="1"
                  value={tempValues.travelers}
                  onChange={(e) =>
                    setTempValues({
                      ...tempValues,
                      travelers: parseInt(e.target.value) || 1,
                    })
                  }
                  onKeyPress={(e) => e.key === 'Enter' && handleSave('travelers')}
                  className="bg-transparent border-none outline-none text-white w-16"
                  autoFocus
                />
                <button
                  onClick={() => handleSave('travelers')}
                  className="text-green-300 hover:text-green-100"
                >
                  ✓
                </button>
                <button
                  onClick={() => setEditMode({ field: null })}
                  className="text-red-300 hover:text-red-100"
                >
                  ✕
                </button>
              </div>
            ) : (
              <button
                onClick={() => {
                  setTempValues({ ...tempValues, travelers: tripData.travelers });
                  setEditMode({ field: 'travelers' });
                }}
                className="hover:underline cursor-pointer"
              >
                {tripData.travelers} Traveler{tripData.travelers > 1 ? 's' : ''}
              </button>
            )}
          </div>

          <span className="text-white/60">•</span>

          {/* Budget */}
          <div className="flex items-center gap-2 group">
            <span className="text-xl">💰</span>
            {editMode.field === 'budget' ? (
              <div className="flex items-center gap-2 bg-white/20 rounded-lg px-3 py-1">
                <span>$</span>
                <input
                  type="number"
                  min="0"
                  value={tempValues.budget}
                  onChange={(e) =>
                    setTempValues({
                      ...tempValues,
                      budget: parseInt(e.target.value) || 0,
                    })
                  }
                  onKeyPress={(e) => e.key === 'Enter' && handleSave('budget')}
                  className="bg-transparent border-none outline-none text-white w-24"
                  autoFocus
                />
                <button
                  onClick={() => handleSave('budget')}
                  className="text-green-300 hover:text-green-100"
                >
                  ✓
                </button>
                <button
                  onClick={() => setEditMode({ field: null })}
                  className="text-red-300 hover:text-red-100"
                >
                  ✕
                </button>
              </div>
            ) : (
              <button
                onClick={() => {
                  setTempValues({ ...tempValues, budget: tripData.totalBudget });
                  setEditMode({ field: 'budget' });
                }}
                className="hover:underline cursor-pointer"
              >
                {tripData.totalBudget > 0
                  ? `Budget: $${tripData.totalBudget.toLocaleString()}`
                  : 'Set budget'}
              </button>
            )}
          </div>
        </div>

        {/* Budget Progress Bar */}
        {budget.total > 0 && (
          <div className="mt-1">
            <div className="flex justify-between text-xs mb-1">
              <span>Spent: ${budget.selected.toLocaleString()}</span>
              <span>Remaining: ${budget.remaining.toLocaleString()}</span>
            </div>
            <div className="h-1.5 bg-white/30 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${
                  budget.selected / budget.total >= 0.9
                    ? 'bg-red-400'
                    : budget.selected / budget.total >= 0.75
                    ? 'bg-orange-400'
                    : 'bg-green-400'
                }`}
                style={{ width: `${Math.min((budget.selected / budget.total) * 100, 100)}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Click outside to close menu */}
      {showTripMenu && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setShowTripMenu(false)}
        />
      )}
    </div>
  );
};
