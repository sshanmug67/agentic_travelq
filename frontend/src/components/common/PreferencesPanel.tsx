// frontend/src/components/common/PreferencesPanel.tsx
//
// v6 — Compact controls matching Agent Feed density
//   - Tab row: smaller text, tighter padding, reduced icon size
//   - Chips: smaller padding, smaller font, inline star/remove
//   - Input row: shorter height, smaller font
//   - Suggestions: tighter pills
//   - Activity/Restaurant settings: condensed spacing
//   - Overall: less vertical padding between sections

import React, { useState } from 'react';

interface Preference {
  name: string;
  preferred?: boolean;
}

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
  budget: {
    meals: string;
    accommodation: string;
    activities: string;
  };
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
  airlines: ['United Airlines', 'Delta', 'American Airlines', 'British Airways', 'Southwest', 'JetBlue', 'Emirates', 'Lufthansa'],
  hotels: ['Marriott', 'Hilton', 'Hyatt', 'IHG', 'Best Western', 'Radisson', 'Wyndham', 'Four Seasons'],
  activities: ['Museums', 'Historic Landmarks', 'Walking Tours', 'Theater', 'Parks & Gardens', 'Shopping', 'Nightlife', 'Food Tours', 'Art Galleries', 'Outdoor Adventures'],
  restaurant: ['British', 'Indian', 'Italian', 'Chinese', 'Japanese', 'Mexican', 'French', 'Thai', 'Mediterranean', 'American'],
};

export const PreferencesPanel: React.FC<PreferencesPanelProps> = ({
  preferences,
  onUpdate,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('airlines');
  const [newItem, setNewItem] = useState('');

  const tabs: { id: TabType; label: string; icon: string }[] = [
    { id: 'airlines', label: 'Airlines', icon: '✈️' },
    { id: 'hotels', label: 'Hotels', icon: '🏨' },
    { id: 'activities', label: 'Activities', icon: '🎭' },
    { id: 'restaurant', label: 'Restaurant', icon: '🍽️' },
  ];

  const storeKey = tabToKey(activeTab);
  const items = (preferences[storeKey] as Preference[]) || [];
  const itemNames = new Set(items.map((i) => i.name.toLowerCase()));

  const availableSuggestions = SUGGESTIONS[activeTab].filter(
    (s) => !itemNames.has(s.toLowerCase())
  );

  const addItem = (name: string, preferred = false) => {
    if (!name.trim()) return;
    if (itemNames.has(name.trim().toLowerCase())) return;
    onUpdate(storeKey, [...items, { name: name.trim(), preferred }]);
    setNewItem('');
  };

  const removeItem = (name: string) => {
    onUpdate(storeKey, items.filter((p) => p.name !== name));
  };

  const togglePreferred = (name: string) => {
    onUpdate(
      storeKey,
      items.map((p) =>
        p.name === name ? { ...p, preferred: !p.preferred } : p
      )
    );
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') addItem(newItem);
  };

  const getTabCount = (tab: TabType) => {
    const key = tabToKey(tab);
    return ((preferences[key] as Preference[]) || []).length;
  };

  // ── Shared compact pill button style ──────────────────────────
  const pillClass = (isSelected: boolean) =>
    `text-[10px] px-2 py-1 rounded-full font-medium transition-all border leading-none ${
      isSelected
        ? 'bg-purple-100 border-purple-300 text-purple-800'
        : 'bg-gray-50 border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-100'
    }`;

  return (
    <div className="bg-white rounded-xl shadow-lg border-2 border-gray-300 overflow-hidden flex flex-col h-full">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="px-4 py-2.5 border-b-2 border-gray-200 flex items-center gap-2 flex-shrink-0 bg-gradient-to-r from-gray-50 to-white">
        <span className="text-base">⚙️</span>
        <span className="text-[15px] font-bold text-gray-800">Preferences</span>
      </div>

      {/* ── Tab Headers (compact) ──────────────────────────────── */}
      <div className="flex border-b bg-gradient-to-r from-purple-50 to-pink-50 flex-shrink-0">
        {tabs.map((tab) => {
          const count = getTabCount(tab.id);
          return (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                setNewItem('');
              }}
              className={`flex-1 px-2 py-2 text-[11px] font-medium transition-all duration-300 relative ${
                activeTab === tab.id
                  ? 'text-purple-700 bg-white'
                  : 'text-gray-600 hover:text-purple-600 hover:bg-white/50'
              }`}
            >
              <span className="flex items-center justify-center gap-1">
                <span className="text-sm">{tab.icon}</span>
                <span className="hidden sm:inline">{tab.label}</span>
                {count > 0 && (
                  <span
                    className={`text-[9px] min-w-[15px] h-[15px] flex items-center justify-center rounded-full font-semibold ${
                      activeTab === tab.id
                        ? 'bg-purple-200 text-purple-800'
                        : 'bg-gray-200 text-gray-600'
                    }`}
                  >
                    {count}
                  </span>
                )}
              </span>
              {activeTab === tab.id && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-purple-600 to-pink-600" />
              )}
            </button>
          );
        })}
      </div>

      {/* ── Tab Content (scrollable) ─────────────────────────── */}
      <div
        className="flex-1 overflow-y-auto px-3 py-2.5"
        style={{ scrollbarWidth: 'thin', scrollbarColor: '#CBD5E1 transparent' }}
      >
        {/* ── Activity Settings (compact) ──────────────────────── */}
        {activeTab === 'activities' && (() => {
          const ap = preferences.activityPrefs || {
            pace: 'moderate',
            preferredTimes: ['morning', 'afternoon'],
            entertainmentHoursPerDay: 6,
          };

          const paceOptions = [
            { value: 'relaxed', label: '🐢 Relaxed' },
            { value: 'moderate', label: '🚶 Moderate' },
            { value: 'aggressive', label: '⚡ Aggressive' },
          ];

          const timeOptions = [
            { value: 'morning', label: '🌅 Morning' },
            { value: 'afternoon', label: '☀️ Afternoon' },
            { value: 'evening', label: '🌙 Evening' },
            { value: 'all_day', label: '📅 All Day' },
          ];

          const hoursOptions = [
            { value: 4, label: '4h' },
            { value: 6, label: '6h' },
            { value: 8, label: '8h' },
            { value: 10, label: '10h' },
          ];

          const updateActivityPrefs = (patch: Partial<ActivityPrefs>) => {
            onUpdate('activityPrefs' as keyof PreferencesData, { ...ap, ...patch });
          };

          const toggleTime = (time: string) => {
            const current = ap.preferredTimes || [];
            if (time === 'all_day') {
              updateActivityPrefs({
                preferredTimes: current.includes('all_day') ? [] : ['all_day'],
              });
              return;
            }
            const withoutAllDay = current.filter((t) => t !== 'all_day');
            const updated = withoutAllDay.includes(time)
              ? withoutAllDay.filter((t) => t !== time)
              : [...withoutAllDay, time];
            updateActivityPrefs({ preferredTimes: updated });
          };

          return (
            <div className="mb-2 border border-gray-200 rounded-lg p-2 space-y-2">
              <div className="text-[9px] font-semibold text-gray-400 uppercase tracking-wider">
                Activity Settings
              </div>

              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-[9px] text-gray-500 mb-1">Hours / Day</div>
                  <div className="flex flex-wrap gap-1">
                    {hoursOptions.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => updateActivityPrefs({ entertainmentHoursPerDay: opt.value })}
                        className={pillClass(ap.entertainmentHoursPerDay === opt.value)}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-[9px] text-gray-500 mb-1">Pace</div>
                  <div className="flex flex-wrap gap-1">
                    {paceOptions.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => updateActivityPrefs({ pace: opt.value })}
                        className={pillClass(ap.pace === opt.value)}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div>
                <div className="text-[9px] text-gray-500 mb-1">Preferred Time</div>
                <div className="flex flex-wrap gap-1">
                  {timeOptions.map((opt) => {
                    const isSelected = (ap.preferredTimes || []).includes(opt.value);
                    return (
                      <button
                        key={opt.value}
                        onClick={() => toggleTime(opt.value)}
                        className={pillClass(isSelected)}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          );
        })()}

        {/* ── Restaurant Settings (compact) ────────────────────── */}
        {activeTab === 'restaurant' && (() => {
          const rp = preferences.restaurantPrefs || {
            meals: ['lunch', 'dinner'],
            priceLevel: ['moderate'],
          };

          const mealOptions = [
            { value: 'breakfast', label: '🥐 Breakfast' },
            { value: 'brunch', label: '🍳 Brunch' },
            { value: 'lunch', label: '🥗 Lunch' },
            { value: 'dinner', label: '🍽️ Dinner' },
          ];

          const priceOptions = [
            { value: 'budget', label: '$ Budget' },
            { value: 'moderate', label: '$$ Mid' },
            { value: 'upscale', label: '$$$ Up' },
            { value: 'fine_dining', label: '$$$$ Fine' },
          ];

          const updateRestaurantPrefs = (patch: Partial<RestaurantPrefs>) => {
            onUpdate('restaurantPrefs' as keyof PreferencesData, { ...rp, ...patch });
          };

          const toggleMeal = (meal: string) => {
            const current = rp.meals || [];
            const updated = current.includes(meal)
              ? current.filter((m: string) => m !== meal)
              : [...current, meal];
            updateRestaurantPrefs({ meals: updated });
          };

          const togglePrice = (price: string) => {
            const current = rp.priceLevel || [];
            const updated = current.includes(price)
              ? current.filter((p: string) => p !== price)
              : [...current, price];
            updateRestaurantPrefs({ priceLevel: updated });
          };

          return (
            <div className="mb-2 border border-gray-200 rounded-lg p-2 space-y-2">
              <div className="text-[9px] font-semibold text-gray-400 uppercase tracking-wider">
                Dining Settings
              </div>

              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-[9px] text-gray-500 mb-1">Meals</div>
                  <div className="flex flex-wrap gap-1">
                    {mealOptions.map((opt) => {
                      const isSelected = (rp.meals || []).includes(opt.value);
                      return (
                        <button
                          key={opt.value}
                          onClick={() => toggleMeal(opt.value)}
                          className={pillClass(isSelected)}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div>
                  <div className="text-[9px] text-gray-500 mb-1">Price Level</div>
                  <div className="flex flex-wrap gap-1">
                    {priceOptions.map((opt) => {
                      const isSelected = (rp.priceLevel || []).includes(opt.value);
                      return (
                        <button
                          key={opt.value}
                          onClick={() => togglePrice(opt.value)}
                          className={pillClass(isSelected)}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          );
        })()}

        {/* ── Selected Items (compact chips) ───────────────────── */}
        {items.length > 0 ? (
          <div className="mb-2">
            <div className="text-[9px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
              Selected
            </div>
            <div className="flex flex-wrap gap-1.5 border border-gray-200 rounded-lg p-2">
              {items.map((item) => (
                <div
                  key={item.name}
                  className={`group inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-medium transition-all duration-200 border leading-none ${
                    item.preferred
                      ? 'bg-purple-100 border-purple-300 text-purple-800'
                      : 'bg-gray-100 border-gray-200 text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <button
                    onClick={() => togglePreferred(item.name)}
                    className="text-xs leading-none transition-transform hover:scale-125"
                    title={item.preferred ? 'Remove priority' : 'Mark as priority'}
                  >
                    {item.preferred ? '⭐' : '☆'}
                  </button>

                  <span>{item.name}</span>

                  {item.preferred && (
                    <span className="text-[8px] bg-yellow-200 text-yellow-800 px-1 py-0.5 rounded-full font-semibold leading-none">
                      Priority
                    </span>
                  )}

                  <button
                    onClick={() => removeItem(item.name)}
                    className="text-gray-400 hover:text-red-500 transition-colors text-xs leading-none"
                    title="Remove"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-4 text-gray-400 mb-2">
            <div className="text-2xl mb-1">
              {tabs.find((t) => t.id === activeTab)?.icon}
            </div>
            <p className="text-[11px]">
              No {activeTab === 'restaurant' ? 'cuisine' : activeTab} preferences yet
            </p>
          </div>
        )}

        {/* ── Add Input (compact) ──────────────────────────────── */}
        <div className="flex gap-1.5 items-center">
          <input
            type="text"
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={`Add ${activeTab === 'restaurant' ? 'cuisine' : activeTab === 'hotels' ? 'hotel chain' : activeTab}...`}
            className="flex-1 text-[11px] px-2.5 py-1.5 border border-gray-300 rounded-lg focus:border-purple-500 focus:ring-1 focus:ring-purple-200 outline-none transition-all"
          />
          <button
            onClick={() => addItem(newItem)}
            disabled={!newItem.trim()}
            className="bg-gradient-to-r from-purple-600 to-pink-600 disabled:from-gray-300 disabled:to-gray-300 text-white px-3 py-1.5 rounded-lg hover:from-purple-700 hover:to-pink-700 transition-all duration-300 font-semibold text-[11px] disabled:cursor-not-allowed leading-none"
          >
            Add
          </button>
        </div>

        {/* ── Quick-Add Suggestions (compact) ──────────────────── */}
        {availableSuggestions.length > 0 && (
          <div className="mt-2">
            <div className="text-[9px] font-semibold text-gray-400 uppercase tracking-wider mb-1">
              Suggestions
            </div>
            <div className="flex flex-wrap gap-1">
              {availableSuggestions.slice(0, 6).map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => addItem(suggestion)}
                  className="inline-flex items-center gap-0.5 text-[10px] px-2 py-0.5 rounded-full border border-dashed border-purple-300 text-purple-600 hover:bg-purple-50 hover:border-purple-400 transition-all duration-200 leading-snug"
                >
                  <span className="text-purple-400">+</span>
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
