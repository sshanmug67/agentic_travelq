// frontend/src/components/common/TripSummaryBar.tsx
//
// v5 — Glass header matching TravelQ v3 mockup:
//   - Replaces old header + gradient bar + PreferencesSummary
//   - Glass backdrop: rgba(255,255,255,0.75) + blur(24px)
//   - Gradient top line (purple → pink → orange)
//   - TravelQ logo left, trip pill center, icon buttons right
//   - Budget progress bar with gradient fill
//   - All inline-edit functionality preserved

import React, { useState } from 'react';
import { useTripData, getNextWeekDates } from '../../hooks/useTripData';
import { useItinerary } from '../../hooks/useItinerary';

export const TripSummaryBar: React.FC = () => {
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

  /* ── Inline edit mini-component ── */
  const InlineEdit = ({ field, children }: { field: 'origin' | 'destination' | 'dates' | 'travelers' | 'budget'; children: React.ReactNode }) => {
    if (editMode.field !== field) return <>{children}</>;

    if (field === 'dates') {
      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <input type="date" value={tempValues.startDate} onChange={(e) => setTempValues({ ...tempValues, startDate: e.target.value })}
            style={{ border: '1.5px solid #C4B5FD', borderRadius: 8, padding: '4px 6px', fontSize: 12, outline: 'none', width: 120 }} />
          <span style={{ color: '#94A3B8', fontSize: 12 }}>–</span>
          <input type="date" value={tempValues.endDate} onChange={(e) => setTempValues({ ...tempValues, endDate: e.target.value })}
            style={{ border: '1.5px solid #C4B5FD', borderRadius: 8, padding: '4px 6px', fontSize: 12, outline: 'none', width: 120 }} />
          <button onClick={() => handleSave('dates')} style={{ color: '#059669', fontWeight: 700, fontSize: 14, background: 'none', border: 'none', cursor: 'pointer' }}>✓</button>
          <button onClick={() => setEditMode({ field: null })} style={{ color: '#EF4444', fontSize: 13, background: 'none', border: 'none', cursor: 'pointer' }}>✕</button>
        </div>
      );
    }

    const cfg: Record<string, any> = {
      origin: { value: tempValues.origin, set: (v: string) => setTempValues({ ...tempValues, origin: v }), w: 110, ph: 'Origin city' },
      destination: { value: tempValues.destination, set: (v: string) => setTempValues({ ...tempValues, destination: v }), w: 130, ph: 'Destination' },
      travelers: { value: tempValues.travelers, set: (v: string) => setTempValues({ ...tempValues, travelers: parseInt(v) || 1 }), w: 50, type: 'number', min: 1 },
      budget: { value: tempValues.budget, set: (v: string) => setTempValues({ ...tempValues, budget: parseInt(v) || 0 }), w: 80, type: 'number', min: 0 },
    };
    const c = cfg[field];

    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        {field === 'budget' && <span style={{ fontSize: 12, color: '#64748B' }}>$</span>}
        <input value={c.value} onChange={(e) => c.set(e.target.value)} onKeyDown={(e: React.KeyboardEvent) => e.key === 'Enter' && handleSave(field)}
          type={c.type} min={c.min} placeholder={c.ph} autoFocus
          style={{ border: '1.5px solid #C4B5FD', borderRadius: 8, padding: '4px 8px', fontSize: 12, outline: 'none', width: c.w }} />
        <button onClick={() => handleSave(field)} style={{ color: '#059669', fontWeight: 700, fontSize: 14, background: 'none', border: 'none', cursor: 'pointer' }}>✓</button>
        <button onClick={() => setEditMode({ field: null })} style={{ color: '#EF4444', fontSize: 13, background: 'none', border: 'none', cursor: 'pointer' }}>✕</button>
      </div>
    );
  };

  const Divider = () => <div style={{ width: 1, height: 20, background: '#E2E8F0', flexShrink: 0 }} />;

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
              <InlineEdit field="origin">
                <span onClick={() => startEdit('origin')} style={{ fontSize: 14, fontWeight: 700, color: '#1E293B', cursor: 'pointer' }} title="Click to edit">
                  🗽 {tripData.origin || 'Origin'}
                </span>
              </InlineEdit>

              <span style={{ color: '#8B5CF6', fontWeight: 700, fontSize: 14 }}>→</span>

              <InlineEdit field="destination">
                <span onClick={() => startEdit('destination')} style={{ fontSize: 14, fontWeight: 700, color: '#1E293B', cursor: 'pointer' }} title="Click to edit">
                  🇬🇧 {tripData.destination || 'Destination'}
                </span>
              </InlineEdit>

              <Divider />

              <InlineEdit field="dates">
                <span onClick={() => startEdit('dates')} style={{ fontSize: 13, color: '#64748B', cursor: 'pointer' }} title="Click to edit">
                  📅 {tripData.startDate && tripData.endDate ? `${fmtDate(tripData.startDate)}–${fmtDate(tripData.endDate)}` : 'Set dates'}
                </span>
              </InlineEdit>

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

            {/* ── Right icons ── */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
              <button style={{ width: 36, height: 36, borderRadius: 12, background: 'rgba(139,92,246,0.08)', border: 'none', cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>🔔</button>
              <div style={{ position: 'relative' }}>
                <button onClick={() => setShowTripMenu(!showTripMenu)} style={{ width: 36, height: 36, borderRadius: 12, background: 'rgba(139,92,246,0.08)', border: 'none', cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="Settings">⚙️</button>
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
              <div style={{ width: 36, height: 36, borderRadius: 12, background: 'linear-gradient(135deg, #8B5CF6, #EC4899)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 700, fontSize: 14, cursor: 'pointer' }}>J</div>
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
    </>
  );
};
