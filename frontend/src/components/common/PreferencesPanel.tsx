// frontend/src/components/common/PreferencesPanel.tsx
//
// v7 — Glass card matching TravelQ v3 mockup:
//   - Glass card: rgba(255,255,255,0.85) + blur(20px), rounded-20
//   - Segmented tab control: #F8FAFC tray, white active pill with shadow
//   - Count badges: purple when active, gray inactive
//   - Selected chips: star + name + PRIORITY badge + × remove
//   - Add input + purple gradient button
//   - Suggestion chips: dashed border with + prefix
//   - Activity/Restaurant settings: preserved as compact pill groups

import React, { useState } from 'react';

interface Preference { name: string; preferred?: boolean; }

interface ActivityPrefs {
  pace: string;
  preferredTimes: string[];
  entertainmentHoursPerDay: number;
  accessibilityNeeds?: string;
}

interface RestaurantPrefs {
  meals: string[];
  priceLevel: string[];
}

interface PreferencesData {
  airlines: Preference[];
  hotelChains: Preference[];
  cuisines: Preference[];
  activities: Preference[];
  budget: { meals: string; accommodation: string; activities: string; };
  activityPrefs: ActivityPrefs;
  restaurantPrefs: RestaurantPrefs;
}

interface PreferencesPanelProps {
  preferences: PreferencesData;
  onUpdate: (category: keyof PreferencesData, value: any) => void;
}

type TabType = 'airlines' | 'hotels' | 'activities' | 'restaurant';

const tabToKey = (tab: TabType): keyof PreferencesData =>
  tab === 'restaurant' ? 'cuisines' : tab === 'hotels' ? 'hotelChains' : tab;

const SUGGESTIONS: Record<TabType, string[]> = {
  airlines: ['American Airlines', 'Southwest', 'JetBlue', 'Emirates', 'Lufthansa', 'Delta', 'British Airways'],
  hotels: ['Marriott', 'Hilton', 'Hyatt', 'IHG', 'Best Western', 'Four Seasons', 'Radisson'],
  activities: ['Museums', 'Historic Landmarks', 'Walking Tours', 'Theater', 'Parks & Gardens', 'Shopping', 'Nightlife', 'Food Tours'],
  restaurant: ['British', 'Indian', 'Italian', 'Chinese', 'Japanese', 'French', 'Thai', 'Mediterranean'],
};

export const PreferencesPanel: React.FC<PreferencesPanelProps> = ({ preferences, onUpdate }) => {
  const [activeTab, setActiveTab] = useState<TabType>('airlines');
  const [newItem, setNewItem] = useState('');

  const tabs: { id: TabType; label: string; icon: string }[] = [
    { id: 'airlines', label: 'Airlines', icon: '✈️' },
    { id: 'hotels', label: 'Hotels', icon: '🏨' },
    { id: 'activities', label: 'Activities', icon: '🎭' },
    { id: 'restaurant', label: 'Cuisine', icon: '🍽️' },
  ];

  const storeKey = tabToKey(activeTab);
  const items = (preferences[storeKey] as Preference[]) || [];
  const itemNames = new Set(items.map((i) => i.name.toLowerCase()));
  const availableSuggestions = SUGGESTIONS[activeTab].filter((s) => !itemNames.has(s.toLowerCase()));

  const addItem = (name: string, preferred = false) => {
    if (!name.trim() || itemNames.has(name.trim().toLowerCase())) return;
    onUpdate(storeKey, [...items, { name: name.trim(), preferred }]);
    setNewItem('');
  };
  const removeItem = (name: string) => onUpdate(storeKey, items.filter((p) => p.name !== name));
  const togglePreferred = (name: string) => onUpdate(storeKey, items.map((p) => p.name === name ? { ...p, preferred: !p.preferred } : p));
  const getTabCount = (tab: TabType) => ((preferences[tabToKey(tab)] as Preference[]) || []).length;

  /* ── Compact settings pill ── */
  const SettingsPill = ({ label, selected, onClick }: { label: string; selected: boolean; onClick: () => void }) => (
    <button onClick={onClick} style={{
      fontSize: 10, padding: '4px 8px', borderRadius: 20, fontWeight: 500, cursor: 'pointer', border: 'none',
      background: selected ? '#EDE9FE' : '#F8FAFC', color: selected ? '#7C3AED' : '#94A3B8',
      transition: 'all 0.2s',
    }}>{label}</button>
  );

  return (
    <div style={{
      background: 'rgba(255,255,255,0.85)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
      borderRadius: 20, padding: 22, height: '100%', display: 'flex', flexDirection: 'column',
      border: '1px solid rgba(139,92,246,0.08)',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      overflow: 'hidden',
    }}>
      {/* Title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, flexShrink: 0 }}>
        <span style={{ fontSize: 18 }}>⚙️</span>
        <h3 style={{ fontSize: 15, fontWeight: 700, color: '#1E293B', margin: 0 }}>Preferences</h3>
      </div>

      {/* ── Segmented tab control ── */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 14, background: '#F8FAFC', borderRadius: 14, padding: 3, flexShrink: 0 }}>
        {tabs.map((t) => {
          const count = getTabCount(t.id);
          const isActive = activeTab === t.id;
          return (
            <button key={t.id} onClick={() => { setActiveTab(t.id); setNewItem(''); }} style={{
              flex: 1, padding: '7px 4px', border: 'none', cursor: 'pointer', borderRadius: 12,
              fontSize: 11.5, fontWeight: 600,
              background: isActive ? 'white' : 'transparent',
              color: isActive ? '#7C3AED' : '#94A3B8',
              boxShadow: isActive ? '0 2px 8px rgba(0,0,0,0.06)' : 'none',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 3,
              transition: 'all 0.25s ease',
            }}>
              <span style={{ fontSize: 12 }}>{t.icon}</span>
              {t.label}
              {count > 0 && (
                <span style={{
                  background: isActive ? '#8B5CF6' : '#E2E8F0',
                  color: isActive ? 'white' : '#94A3B8',
                  fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 8,
                }}>{count}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── Scrollable content ── */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10, scrollbarWidth: 'thin' as any, scrollbarColor: '#C4B5FD transparent' }}>

        {/* Activity Settings */}
        {activeTab === 'activities' && (() => {
          const ap = preferences.activityPrefs || { pace: 'moderate', preferredTimes: ['morning', 'afternoon'], entertainmentHoursPerDay: 6 };
          const updateAP = (patch: Partial<ActivityPrefs>) => onUpdate('activityPrefs' as keyof PreferencesData, { ...ap, ...patch });
          const toggleTime = (t: string) => {
            const cur = ap.preferredTimes || [];
            if (t === 'all_day') { updateAP({ preferredTimes: cur.includes('all_day') ? [] : ['all_day'] }); return; }
            const wo = cur.filter((x) => x !== 'all_day');
            updateAP({ preferredTimes: wo.includes(t) ? wo.filter((x) => x !== t) : [...wo, t] });
          };
          return (
            <div style={{ padding: 8, border: '1px solid #F1F5F9', borderRadius: 12 }}>
              <div style={{ fontSize: 9, fontWeight: 700, color: '#94A3B8', letterSpacing: 1, textTransform: 'uppercase' as const, marginBottom: 6 }}>Activity Settings</div>
              <div style={{ display: 'flex', gap: 12, marginBottom: 6 }}>
                <div>
                  <div style={{ fontSize: 9, color: '#94A3B8', marginBottom: 3 }}>Hours / Day</div>
                  <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                    {[4, 6, 8, 10].map((h) => <SettingsPill key={h} label={`${h}h`} selected={ap.entertainmentHoursPerDay === h} onClick={() => updateAP({ entertainmentHoursPerDay: h })} />)}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 9, color: '#94A3B8', marginBottom: 3 }}>Pace</div>
                  <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                    {[{ v: 'relaxed', l: '🐢 Relaxed' }, { v: 'moderate', l: '🚶 Moderate' }, { v: 'aggressive', l: '⚡ Fast' }].map((o) => <SettingsPill key={o.v} label={o.l} selected={ap.pace === o.v} onClick={() => updateAP({ pace: o.v })} />)}
                  </div>
                </div>
              </div>
              <div style={{ fontSize: 9, color: '#94A3B8', marginBottom: 3 }}>Time</div>
              <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                {[{ v: 'morning', l: '🌅 AM' }, { v: 'afternoon', l: '☀️ PM' }, { v: 'evening', l: '🌙 Eve' }, { v: 'all_day', l: '📅 All' }].map((o) => (
                  <SettingsPill key={o.v} label={o.l} selected={(ap.preferredTimes || []).includes(o.v)} onClick={() => toggleTime(o.v)} />
                ))}
              </div>
            </div>
          );
        })()}

        {/* Restaurant Settings */}
        {activeTab === 'restaurant' && (() => {
          const rp = preferences.restaurantPrefs || { meals: ['lunch', 'dinner'], priceLevel: ['moderate'] };
          const updateRP = (patch: Partial<RestaurantPrefs>) => onUpdate('restaurantPrefs' as keyof PreferencesData, { ...rp, ...patch });
          const toggleMeal = (m: string) => { const c = rp.meals || []; updateRP({ meals: c.includes(m) ? c.filter((x: string) => x !== m) : [...c, m] }); };
          const togglePrice = (p: string) => { const c = rp.priceLevel || []; updateRP({ priceLevel: c.includes(p) ? c.filter((x: string) => x !== p) : [...c, p] }); };
          return (
            <div style={{ padding: 8, border: '1px solid #F1F5F9', borderRadius: 12 }}>
              <div style={{ fontSize: 9, fontWeight: 700, color: '#94A3B8', letterSpacing: 1, textTransform: 'uppercase' as const, marginBottom: 6 }}>Dining Settings</div>
              <div style={{ display: 'flex', gap: 12, marginBottom: 4 }}>
                <div>
                  <div style={{ fontSize: 9, color: '#94A3B8', marginBottom: 3 }}>Meals</div>
                  <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                    {[{ v: 'breakfast', l: '🥐 Brkfst' }, { v: 'brunch', l: '🍳 Brunch' }, { v: 'lunch', l: '🥗 Lunch' }, { v: 'dinner', l: '🍽️ Dinner' }].map((o) => (
                      <SettingsPill key={o.v} label={o.l} selected={(rp.meals || []).includes(o.v)} onClick={() => toggleMeal(o.v)} />
                    ))}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 9, color: '#94A3B8', marginBottom: 3 }}>Price</div>
                  <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                    {[{ v: 'budget', l: '$' }, { v: 'moderate', l: '$$' }, { v: 'upscale', l: '$$$' }, { v: 'fine_dining', l: '$$$$' }].map((o) => (
                      <SettingsPill key={o.v} label={o.l} selected={(rp.priceLevel || []).includes(o.v)} onClick={() => togglePrice(o.v)} />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          );
        })()}

        {/* ── Selected items ── */}
        <div>
          <span style={{ fontSize: 9, fontWeight: 700, color: '#94A3B8', letterSpacing: 1, textTransform: 'uppercase' as const }}>Selected</span>
          {items.length > 0 ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginTop: 6 }}>
              {items.map((item) => (
                <div key={item.name} style={{
                  display: 'flex', alignItems: 'center', gap: 5, padding: '5px 11px', borderRadius: 11,
                  background: item.preferred ? 'linear-gradient(135deg, #FEF3C7, #FDE68A)' : 'white',
                  border: item.preferred ? '1.5px solid #F59E0B' : '1.5px solid #E2E8F0',
                  fontSize: 12, fontWeight: 600, color: '#1E293B',
                  transition: 'all 0.2s ease',
                }}>
                  <button onClick={() => togglePreferred(item.name)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontSize: 11, lineHeight: 1 }} title={item.preferred ? 'Remove priority' : 'Set as priority'}>
                    {item.preferred ? '⭐' : '☆'}
                  </button>
                  {item.name}
                  {item.preferred && <span style={{ fontSize: 8, fontWeight: 700, color: '#92400E', background: 'rgba(245,158,11,0.2)', padding: '1px 5px', borderRadius: 5 }}>PRIORITY</span>}
                  <button onClick={() => removeItem(item.name)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontSize: 13, color: '#94A3B8', lineHeight: 1 }} title="Remove">×</button>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '12px 0', color: '#CBD5E1' }}>
              <span style={{ fontSize: 20 }}>{tabs.find(t => t.id === activeTab)?.icon}</span>
              <p style={{ fontSize: 11, margin: '4px 0 0' }}>No {activeTab === 'restaurant' ? 'cuisine' : activeTab} set</p>
            </div>
          )}
        </div>

        {/* ── Add input ── */}
        <div style={{ display: 'flex', gap: 7 }}>
          <input value={newItem} onChange={(e) => setNewItem(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addItem(newItem)}
            placeholder={`Add ${activeTab === 'restaurant' ? 'cuisine' : activeTab === 'hotels' ? 'hotel chain' : activeTab}...`}
            style={{ flex: 1, padding: '7px 12px', borderRadius: 11, border: '2px solid #F1F5F9', fontSize: 12, outline: 'none', transition: 'border-color 0.2s' }}
            onFocus={(e) => { e.currentTarget.style.borderColor = '#C4B5FD'; }}
            onBlur={(e) => { e.currentTarget.style.borderColor = '#F1F5F9'; }}
          />
          <button onClick={() => addItem(newItem)} disabled={!newItem.trim()} style={{
            padding: '7px 16px', borderRadius: 11, border: 'none',
            background: newItem.trim() ? 'linear-gradient(135deg, #8B5CF6, #7C3AED)' : '#E2E8F0',
            color: newItem.trim() ? 'white' : '#94A3B8', fontWeight: 700, fontSize: 11.5, cursor: newItem.trim() ? 'pointer' : 'default',
          }}>Add</button>
        </div>

        {/* ── Suggestions ── */}
        {availableSuggestions.length > 0 && (
          <div>
            <span style={{ fontSize: 9, fontWeight: 700, color: '#94A3B8', letterSpacing: 1, textTransform: 'uppercase' as const }}>Suggestions</span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 6 }}>
              {availableSuggestions.slice(0, 5).map((s) => (
                <button key={s} onClick={() => addItem(s)} style={{
                  padding: '4px 10px', borderRadius: 9, fontSize: 11, color: '#7C3AED',
                  background: 'rgba(139,92,246,0.06)', border: '1px dashed rgba(139,92,246,0.2)',
                  fontWeight: 500, cursor: 'pointer', transition: 'all 0.2s',
                }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = '#8B5CF6'; e.currentTarget.style.color = 'white'; e.currentTarget.style.borderStyle = 'solid'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(139,92,246,0.06)'; e.currentTarget.style.color = '#7C3AED'; e.currentTarget.style.borderStyle = 'dashed'; }}
                >+ {s}</button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
