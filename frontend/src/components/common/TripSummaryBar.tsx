// frontend/src/components/common/TripSummaryBar.tsx
//
// v7 — Glass header + AirportAutocomplete auto-confirm + smart date picker:
//   - Airport: selecting from dropdown auto-saves (no ✓ click needed)
//   - Dates: picking start date clears end date if it's earlier; picking end
//     date auto-saves both and closes edit. End date min = start date.
//   - All other behaviour (budget, travelers, menu, etc.) unchanged.

import React, { useState, useRef } from 'react';
import { useTripData, getNextWeekDates } from '../../hooks/useTripData';
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

  // Ref for the end-date input so we can programmatically focus it
  const endDateRef = useRef<HTMLInputElement>(null);

  // ── Generic save helper ──
  const handleSave = (field: string) => {
    switch (field) {
      case 'origin': setTripData({ origin: tempValues.origin }); break;
      case 'destination': setTripData({ destination: tempValues.destination }); break;
      case 'dates': setTripData({ startDate: tempValues.startDate, endDate: tempValues.endDate }); break;
      case 'travelers': setTripData({ travelers: tempValues.travelers }); break;
      case 'budget': setTripData({ totalBudget: tempValues.budget }); setBudget(tempValues.budget); break;
    }
    setEditMode({ field: null });
  };

  // ── Airport auto-confirm: called when user picks from dropdown ──
  const handleAirportSelect = (field: 'origin' | 'destination', display: string) => {
    setTripData({ [field]: display });
    setTempValues(prev => ({ ...prev, [field]: display }));
    setEditMode({ field: null });
  };

  // ── Smart date: start date changed ──
  const handleStartDateChange = (newStart: string) => {
    const updated = { ...tempValues, startDate: newStart };

    // If end date is before new start date, clear it
    if (updated.endDate && updated.endDate < newStart) {
      updated.endDate = '';
    }

    setTempValues(updated);

    // Move focus to end-date picker so user can pick it next
    if (newStart) {
      setTimeout(() => {
        endDateRef.current?.focus();
        // showPicker() opens the native calendar — supported in modern browsers
        endDateRef.current?.showPicker?.();
      }, 50);
    }
  };

  // ── Smart date: end date changed → auto-save both ──
  const handleEndDateChange = (newEnd: string) => {
    const updated = { ...tempValues, endDate: newEnd };
    setTempValues(updated);

    // Both dates are set → save and close
    if (updated.startDate && newEnd) {
      setTripData({ startDate: updated.startDate, endDate: newEnd });
      setEditMode({ field: null });
    }
  };

  // ── Trip actions ──
  const handleNewTrip = () => {
    if (window.confirm('Start a new trip? This will clear your current itinerary.')) {
      const { startDate, endDate } = getNextWeekDates();
      resetTrip(); clearItinerary();
      setTempValues({ origin: 'New York', destination: 'London, UK', startDate, endDate, travelers: 1, budget: 4000 });
      setEditMode({ field: 'destination' });
    }
    setShowTripMenu(false);
  };

  const handleClearItinerary = () => {
    if (window.confirm('Clear all selected items? Trip details will be kept.')) clearItinerary();
    setShowTripMenu(false);
  };

  // ── Helpers ──
  const fmtDate = (d: string) => {
    try { return new Date(d + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); }
    catch { return d; }
  };

  const startEdit = (field: typeof editMode.field) => {
    setTempValues({
      origin: tripData.origin || '', destination: tripData.destination,
      startDate: tripData.startDate, endDate: tripData.endDate,
      travelers: tripData.travelers, budget: tripData.totalBudget,
    });
    setEditMode({ field });
  };

  const budgetPct = budget.total > 0 ? Math.min((budget.selected / budget.total) * 100, 100) : 0;

  // ── Inline edit for travelers & budget (unchanged) ──
  const InlineEdit = ({ field, children }: { field: 'travelers' | 'budget'; children: React.ReactNode }) => {
    if (editMode.field !== field) return <>{children}</>;

    const cfg: Record<string, any> = {
      travelers: { value: tempValues.travelers, set: (v: string) => setTempValues({ ...tempValues, travelers: parseInt(v) || 1 }), w: 50, type: 'number', min: 1 },
      budget: { value: tempValues.budget, set: (v: string) => setTempValues({ ...tempValues, budget: parseInt(v) || 0 }), w: 80, type: 'number', min: 0 },
    };
    const c = cfg[field];

    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        {field === 'budget' && <span style={{ fontSize: 12, color: '#64748B' }}>$</span>}
        <input value={c.value} onChange={(e) => c.set(e.target.value)} onKeyDown={(e: React.KeyboardEvent) => e.key === 'Enter' && handleSave(field)}
          type={c.type} min={c.min} autoFocus
          style={{ border: '1.5px solid #C4B5FD', borderRadius: 8, padding: '4px 8px', fontSize: 12, outline: 'none', width: c.w }} />
        <button onClick={() => handleSave(field)} style={{ color: '#059669', fontWeight: 700, fontSize: 14, background: 'none', border: 'none', cursor: 'pointer' }}>✓</button>
        <button onClick={() => setEditMode({ field: null })} style={{ color: '#EF4444', fontSize: 13, background: 'none', border: 'none', cursor: 'pointer' }}>✕</button>
      </div>
    );
  };

  const Divider = () => <div style={{ width: 1, height: 20, background: '#E2E8F0', flexShrink: 0 }} />;

  // Today's date string for min attributes
  const todayStr = new Date().toISOString().split('T')[0];

  return (
    <>
      <header style={{
        position: 'sticky', top: 0, zIndex: 50,
        background: 'rgba(255,255,255,0.75)', backdropFilter: 'blur(24px)', WebkitBackdropFilter: 'blur(24px)',
        borderBottom: '1px solid rgba(139,92,246,0.1)',
      }}>
        {/* Gradient top accent */}
        <div style={{ height: 3, background: 'linear-gradient(90deg, #8B5CF6, #EC4899, #F97316, #8B5CF6)', backgroundSize: '200% 100%' }} />

        <div style={{ maxWidth: 1440, margin: '0 auto', padding: '12px 28px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>

            {/* ── Logo ── */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
              <span style={{ fontSize: 26, fontWeight: 800, background: 'linear-gradient(135deg, #7C3AED, #DB2777)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>TravelQ</span>
              <span style={{ fontSize: 10, fontWeight: 700, color: '#8B5CF6', background: '#F3E8FF', padding: '2px 8px', borderRadius: 20 }}>BETA</span>
            </div>

            {/* ── Trip details pill ── */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
              background: 'rgba(139,92,246,0.04)', border: '1px solid rgba(139,92,246,0.1)',
              borderRadius: 16, padding: '8px 20px',
            }}>

              {/* ── Origin (AirportAutocomplete, auto-confirm on select) ── */}
              {editMode.field === 'origin' ? (
                <AirportAutocomplete
                  value={tempValues.origin}
                  onChange={(display) => setTempValues({ ...tempValues, origin: display })}
                  onSelect={(display) => handleAirportSelect('origin', display)}
                  onConfirm={() => handleSave('origin')}
                  onCancel={() => setEditMode({ field: null })}
                  placeholder="From (e.g., New York)"
                  autoFocus
                  className="trip-pill-autocomplete"
                />
              ) : (
                <span onClick={() => startEdit('origin')} style={{ fontSize: 14, fontWeight: 700, color: '#1E293B', cursor: 'pointer' }} title="Click to edit">
                  🗽 {tripData.origin || 'Origin'}
                </span>
              )}

              <span style={{ color: '#8B5CF6', fontWeight: 700, fontSize: 14 }}>→</span>

              {/* ── Destination (AirportAutocomplete, auto-confirm on select) ── */}
              {editMode.field === 'destination' ? (
                <AirportAutocomplete
                  value={tempValues.destination}
                  onChange={(display) => setTempValues({ ...tempValues, destination: display })}
                  onSelect={(display) => handleAirportSelect('destination', display)}
                  onConfirm={() => handleSave('destination')}
                  onCancel={() => setEditMode({ field: null })}
                  placeholder="To (e.g., London)"
                  autoFocus
                  className="trip-pill-autocomplete"
                />
              ) : (
                <span onClick={() => startEdit('destination')} style={{ fontSize: 14, fontWeight: 700, color: '#1E293B', cursor: 'pointer' }} title="Click to edit">
                  🇬🇧 {tripData.destination || 'Destination'}
                </span>
              )}

              <Divider />

              {/* ── Dates (smart auto-save, no ✓ needed) ── */}
              {editMode.field === 'dates' ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 14 }}>📅</span>
                  <input
                    type="date"
                    value={tempValues.startDate}
                    min={todayStr}
                    onChange={(e) => handleStartDateChange(e.target.value)}
                    style={{ border: '1.5px solid #C4B5FD', borderRadius: 8, padding: '4px 6px', fontSize: 12, outline: 'none', width: 130 }}
                    autoFocus
                  />
                  <span style={{ color: '#94A3B8', fontSize: 12 }}>–</span>
                  <input
                    ref={endDateRef}
                    type="date"
                    value={tempValues.endDate}
                    min={tempValues.startDate || todayStr}
                    onChange={(e) => handleEndDateChange(e.target.value)}
                    style={{ border: '1.5px solid #C4B5FD', borderRadius: 8, padding: '4px 6px', fontSize: 12, outline: 'none', width: 130 }}
                  />
                  <button onClick={() => setEditMode({ field: null })} style={{ color: '#EF4444', fontSize: 13, background: 'none', border: 'none', cursor: 'pointer' }} title="Cancel">✕</button>
                </div>
              ) : (
                <span onClick={() => startEdit('dates')} style={{ fontSize: 13, color: '#64748B', cursor: 'pointer' }} title="Click to edit">
                  📅 {tripData.startDate && tripData.endDate ? `${fmtDate(tripData.startDate)}–${fmtDate(tripData.endDate)}` : 'Set dates'}
                </span>
              )}

              <Divider />

              <InlineEdit field="travelers">
                <span onClick={() => startEdit('travelers')} style={{ fontSize: 13, color: '#64748B', cursor: 'pointer' }} title="Click to edit">
                  👤 {tripData.travelers}
                </span>
              </InlineEdit>

              <Divider />

              <InlineEdit field="budget">
                <span onClick={() => startEdit('budget')} style={{ fontSize: 13, fontWeight: 600, color: '#059669', cursor: 'pointer' }} title="Click to edit">
                  💰 ${tripData.totalBudget > 0 ? tripData.totalBudget.toLocaleString() : '0'}
                </span>
              </InlineEdit>
            </div>

            {/* ── Plan My Trip + Preferences toggle ── */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
              {onPlanTrip && (
                <button onClick={onPlanTrip} disabled={planningStatus === 'planning' || !tripData.destination || !tripData.startDate || !tripData.endDate}
                  style={{
                    padding: '9px 22px', borderRadius: 14, border: 'none',
                    background: (planningStatus === 'planning')
                      ? 'linear-gradient(135deg, #6c5ce7, #a855f7)'
                      : (!tripData.destination || !tripData.startDate || !tripData.endDate)
                        ? '#D1D5DB'
                        : 'linear-gradient(135deg, #8B5CF6, #EC4899, #F97316)',
                    backgroundSize: '200% 100%',
                    color: 'white', fontSize: 13, fontWeight: 700,
                    cursor: (planningStatus === 'planning' || !tripData.destination || !tripData.startDate || !tripData.endDate) ? 'not-allowed' : 'pointer',
                    boxShadow: (planningStatus === 'planning' || !tripData.destination || !tripData.startDate || !tripData.endDate) ? 'none' : '0 4px 16px -2px rgba(139,92,246,0.35)',
                    display: 'flex', alignItems: 'center', gap: 7, transition: 'all 0.3s',
                  }}>
                  {planningStatus === 'planning' ? (
                    <>
                      <span style={{ display: 'inline-block', width: 14, height: 14, border: '2.5px solid rgba(255,255,255,0.3)', borderTopColor: 'white', borderRadius: '50%', animation: 'planSpin 0.8s linear infinite' }} />
                      Planning…
                    </>
                  ) : (
                    <>🚀 Plan My Trip</>
                  )}
                </button>
              )}

              {onToggleCollapse && hasResults && (
                <button onClick={onToggleCollapse} style={{
                  padding: '6px 8px', borderRadius: 10, border: '2px solid #e30079',
                  background: isPlanningCollapsed ? 'rgba(139,92,246,0.08)' : 'rgba(139,92,246,0.04)',
                  cursor: 'pointer', fontSize: 11, fontWeight: 600,
                  display: 'flex', alignItems: 'center', gap: 4,
                  color: '#7C3AED', transition: 'all 0.2s',
                }} title={isPlanningCollapsed ? 'Show preferences & agent feed' : 'Hide preferences & agent feed'}>
                  <span style={{ fontSize: 13 }}>⚙️</span>
                  <span style={{ fontSize: 9, transition: 'transform 0.2s', transform: isPlanningCollapsed ? 'rotate(0deg)' : 'rotate(180deg)' }}>▼</span>
                </button>
              )}
            </div>

            {/* ── Right icons ── */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
              <button style={{ width: 36, height: 36, borderRadius: 12, background: 'rgba(139,92,246,0.08)', border: 'none', cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="Notifications">🔔</button>
              <button style={{ width: 36, height: 36, borderRadius: 12, background: 'rgba(139,92,246,0.08)', border: 'none', cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="Settings" onClick={() => alert('Settings coming soon!')}>⚙️</button>
              <div style={{ position: 'relative' }}>
                <button onClick={() => setShowTripMenu(!showTripMenu)} style={{
                  width: 36, height: 36, borderRadius: 12, border: 'none', cursor: 'pointer', fontSize: 18,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: showTripMenu ? 'rgba(139,92,246,0.15)' : 'rgba(139,92,246,0.08)',
                  color: '#6B7280', fontWeight: 700, transition: 'background 0.2s',
                }} title="Menu">☰</button>
                {showTripMenu && (
                  <div style={{ position: 'absolute', right: 0, top: 42, width: 200, background: 'white', borderRadius: 14, boxShadow: '0 8px 32px rgba(0,0,0,0.12)', border: '1px solid #E2E8F0', padding: 6, zIndex: 100 }}>
                    {[
                      { label: '✨ New Trip', action: handleNewTrip },
                      { label: '🗑️ Clear Itinerary', action: handleClearItinerary },
                      { label: '📋 My Trips', action: () => { alert('My Trips coming soon!'); setShowTripMenu(false); } },
                      { label: '💾 Save Trip', action: () => { alert(tripData.id ? 'Save coming soon!' : 'Plan first!'); setShowTripMenu(false); } },
                    ].map((item, i) => (
                      <button key={i} onClick={item.action} style={{ width: '100%', textAlign: 'left' as const, padding: '10px 14px', border: 'none', background: 'transparent', borderRadius: 10, fontSize: 13, fontWeight: 500, color: '#374151', cursor: 'pointer' }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = '#F5F3FF')}
                        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                      >{item.label}</button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ── Budget bar ── */}
          {budget.total > 0 && (
            <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: '#64748B', minWidth: 90, whiteSpace: 'nowrap' }}>
                Spent: <span style={{ color: '#8B5CF6' }}>${budget.selected.toLocaleString()}</span>
              </span>
              <div style={{ flex: 1, height: 6, background: '#F1F5F9', borderRadius: 10, overflow: 'hidden' }}>
                <div style={{ width: `${budgetPct}%`, height: '100%', borderRadius: 10, background: 'linear-gradient(90deg, #8B5CF6, #EC4899, #F97316)', transition: 'width 0.5s ease' }} />
              </div>
              <span style={{ fontSize: 11, fontWeight: 600, color: '#059669', minWidth: 100, textAlign: 'right' as const, whiteSpace: 'nowrap' }}>
                Remaining: ${budget.remaining.toLocaleString()}
              </span>
            </div>
          )}
        </div>
      </header>

      {showTripMenu && <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={() => setShowTripMenu(false)} />}

      <style>{`
        @keyframes planSpin { to { transform: rotate(360deg); } }
        .trip-pill-autocomplete .flex.items-center.gap-2 {
          background: rgba(139,92,246,0.08) !important;
          border: 1.5px solid #C4B5FD !important;
          border-radius: 8px !important;
          padding: 2px 8px !important;
        }
        .trip-pill-autocomplete input {
          color: #1E293B !important;
          font-size: 13px !important;
          font-weight: 600 !important;
        }
        .trip-pill-autocomplete input::placeholder {
          color: #94A3B8 !important;
        }
        .trip-pill-autocomplete .text-green-300 {
          color: #059669 !important;
        }
        .trip-pill-autocomplete .text-red-300 {
          color: #EF4444 !important;
        }
      `}</style>
    </>
  );
};
