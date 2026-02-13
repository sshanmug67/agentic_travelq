// frontend/src/components/common/PreferencesPanel.tsx
//
// Revamped v4 — Chip-based compact layout + Activity Settings
//
// Design:
//   ┌─────────────────────────────────────────────────┐
//   │ ⚙️ Preferences                                  │
//   │ [ Airlines | Hotels | Activities | Restaurant ]  │
//   │                                                  │
//   │  (Activities tab only:)                          │
//   │  ┌ Activity Settings ─────────────────────────┐  │
//   │  │ Pace:  [Relaxed] [Moderate] [Aggressive]   │  │
//   │  │ Time:  [Morning] [Afternoon] [Evening]     │  │
//   │  │ Hours: [4 hrs] [6 hrs] [8 hrs] [10 hrs]   │  │
//   │  └────────────────────────────────────────────┘  │
//   │                                                  │
//   │  Selected:                                       │
//   │  ┌────────────────────────────────────────────┐  │
//   │  │ ⭐ Museums × ☆ Walking Tours ×             │  │
//   │  └────────────────────────────────────────────┘  │
//   │                                                  │
//   │  [ Add activity...          ] [Add]              │
//   │  Suggestions: + Theater  + Food Tours            │
//   └─────────────────────────────────────────────────┘
//
// Semantics:
//   - Items in the list = user is interested
//   - ⭐ starred items  = user wants priority
//   - Items NOT in list = user doesn't care
//
// Only items in the list get sent to the backend.
// The backend receives both `preferred` and non-preferred items
// and can prioritize accordingly.

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
  [key: string]: any;  // allow other prefs keys
}

interface PreferencesPanelProps {
  preferences: PreferencesData;
  onUpdate: (category: keyof PreferencesData, value: any) => void;
}

type TabType = 'airlines' | 'hotels' | 'activities' | 'restaurant';

// ── Tab → store key mapping ────────────────────────────────────────────────
const tabToKey = (tab: TabType): keyof PreferencesData =>
  tab === 'restaurant' ? 'cuisines' : tab === 'hotels' ? 'hotelChains' : tab;

// ── Suggested quick-adds per category ──────────────────────────────────────
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

  // Suggestions that haven't been added yet
  const availableSuggestions = SUGGESTIONS[activeTab].filter(
    (s) => !itemNames.has(s.toLowerCase())
  );

  // ── Actions ────────────────────────────────────────────────────────────

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

  // ── Count badges for tabs ──────────────────────────────────────────────
  const getTabCount = (tab: TabType) => {
    const key = tabToKey(tab);
    return ((preferences[key] as Preference[]) || []).length;
  };

  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-600 to-pink-600 px-4 py-3">
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          ⚙️ Preferences
        </h3>
      </div>

      {/* Tab Headers */}
      <div className="flex border-b bg-gradient-to-r from-purple-50 to-pink-50">
        {tabs.map((tab) => {
          const count = getTabCount(tab.id);
          return (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                setNewItem('');
              }}
              className={`flex-1 px-3 py-3 text-sm font-medium transition-all duration-300 relative ${
                activeTab === tab.id
                  ? 'text-purple-700 bg-white'
                  : 'text-gray-600 hover:text-purple-600 hover:bg-white/50'
              }`}
            >
              <span className="flex items-center justify-center gap-1">
                <span className="text-lg">{tab.icon}</span>
                <span className="hidden sm:inline">{tab.label}</span>
                {count > 0 && (
                  <span
                    className={`text-[11px] min-w-[18px] h-[18px] flex items-center justify-center rounded-full font-semibold ${
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
                <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-purple-600 to-pink-600" />
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="p-4">
        {/* ── Activity Settings (only on Activities tab) ───────────────── */}
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
            { value: 4, label: '4 hrs' },
            { value: 6, label: '6 hrs' },
            { value: 8, label: '8 hrs' },
            { value: 10, label: '10 hrs' },
          ];

          const updateActivityPrefs = (patch: Partial<ActivityPrefs>) => {
            onUpdate('activityPrefs' as keyof PreferencesData, { ...ap, ...patch });
          };

          const toggleTime = (time: string) => {
            const current = ap.preferredTimes || [];
            // If "all_day" is clicked, toggle it exclusively
            if (time === 'all_day') {
              updateActivityPrefs({
                preferredTimes: current.includes('all_day') ? [] : ['all_day'],
              });
              return;
            }
            // If selecting a specific time, remove "all_day"
            const withoutAllDay = current.filter((t) => t !== 'all_day');
            const updated = withoutAllDay.includes(time)
              ? withoutAllDay.filter((t) => t !== time)
              : [...withoutAllDay, time];
            updateActivityPrefs({ preferredTimes: updated });
          };

          return (
            <div className="mb-3 border border-gray-200 rounded-xl p-3 space-y-3">
              <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                Activity Settings
              </div>

              {/* Row 1: Hours/Day (left) + Pace (right) */}
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[11px] text-gray-500 mb-1.5">Hours / Day</div>
                  <div className="flex flex-wrap gap-1.5">
                    {hoursOptions.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => updateActivityPrefs({ entertainmentHoursPerDay: opt.value })}
                        className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all border ${
                          ap.entertainmentHoursPerDay === opt.value
                            ? 'bg-purple-100 border-purple-300 text-purple-800'
                            : 'bg-gray-50 border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-100'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-gray-500 mb-1.5">Pace</div>
                  <div className="flex flex-wrap gap-1.5">
                    {paceOptions.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => updateActivityPrefs({ pace: opt.value })}
                        className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all border ${
                          ap.pace === opt.value
                            ? 'bg-purple-100 border-purple-300 text-purple-800'
                            : 'bg-gray-50 border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-100'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Row 2: Preferred Times */}
              <div>
                <div className="text-[11px] text-gray-500 mb-1.5">Preferred Time</div>
                <div className="flex flex-wrap gap-1.5">
                  {timeOptions.map((opt) => {
                    const isSelected = (ap.preferredTimes || []).includes(opt.value);
                    return (
                      <button
                        key={opt.value}
                        onClick={() => toggleTime(opt.value)}
                        className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all border ${
                          isSelected
                            ? 'bg-purple-100 border-purple-300 text-purple-800'
                            : 'bg-gray-50 border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-100'
                        }`}
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

        {/* ── Restaurant Settings (only on Restaurant tab) ─────────────── */}
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
            { value: 'moderate', label: '$$ Mid-range' },
            { value: 'upscale', label: '$$$ Upscale' },
            { value: 'fine_dining', label: '$$$$ Fine Dining' },
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
            <div className="mb-3 border border-gray-200 rounded-xl p-3 space-y-3">
              <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                Dining Settings
              </div>

              {/* Row 1: Meals (left) + Price Level (right) */}
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[11px] text-gray-500 mb-1.5">Meals</div>
                  <div className="flex flex-wrap gap-1.5">
                    {mealOptions.map((opt) => {
                      const isSelected = (rp.meals || []).includes(opt.value);
                      return (
                        <button
                          key={opt.value}
                          onClick={() => toggleMeal(opt.value)}
                          className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all border ${
                            isSelected
                              ? 'bg-purple-100 border-purple-300 text-purple-800'
                              : 'bg-gray-50 border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-100'
                          }`}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-gray-500 mb-1.5">Price Level</div>
                  <div className="flex flex-wrap gap-1.5">
                    {priceOptions.map((opt) => {
                      const isSelected = (rp.priceLevel || []).includes(opt.value);
                      return (
                        <button
                          key={opt.value}
                          onClick={() => togglePrice(opt.value)}
                          className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all border ${
                            isSelected
                              ? 'bg-purple-100 border-purple-300 text-purple-800'
                              : 'bg-gray-50 border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-100'
                          }`}
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

        {/* ── Selected Items (Chip Cloud) ──────────────────────────────── */}
        {items.length > 0 ? (
          <div className="mb-3">
            <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Selected
            </div>
            <div className="flex flex-wrap gap-2 border border-gray-200 rounded-xl p-3">
              {items.map((item) => (
                <div
                  key={item.name}
                  className={`group inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-200 border ${
                    item.preferred
                      ? 'bg-purple-100 border-purple-300 text-purple-800'
                      : 'bg-gray-100 border-gray-200 text-gray-700 hover:border-gray-300'
                  }`}
                >
                  {/* Star toggle */}
                  <button
                    onClick={() => togglePreferred(item.name)}
                    className="text-base leading-none transition-transform hover:scale-125"
                    title={item.preferred ? 'Remove priority' : 'Mark as priority'}
                  >
                    {item.preferred ? '⭐' : '☆'}
                  </button>

                  <span>{item.name}</span>

                  {item.preferred && (
                    <span className="text-[10px] bg-yellow-200 text-yellow-800 px-1.5 py-0.5 rounded-full font-semibold">
                      Priority
                    </span>
                  )}

                  {/* Remove button */}
                  <button
                    onClick={() => removeItem(item.name)}
                    className="text-gray-400 hover:text-red-500 transition-colors ml-0.5 text-base leading-none"
                    title="Remove"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-6 text-gray-400 mb-3">
            <div className="text-3xl mb-1">
              {tabs.find((t) => t.id === activeTab)?.icon}
            </div>
            <p className="text-sm">
              No {activeTab === 'restaurant' ? 'cuisine' : activeTab} preferences yet
            </p>
          </div>
        )}

        {/* ── Add Input ───────────────────────────────────────────────── */}
        <div className="flex gap-2 items-center">
          <input
            type="text"
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={`Add ${activeTab === 'restaurant' ? 'cuisine' : activeTab === 'hotels' ? 'hotel chain' : activeTab}...`}
            className="flex-1 text-sm px-3 py-2 border border-gray-300 rounded-lg focus:border-purple-500 focus:ring-2 focus:ring-purple-200 outline-none transition-all"
          />
          <button
            onClick={() => addItem(newItem)}
            disabled={!newItem.trim()}
            className="bg-gradient-to-r from-purple-600 to-pink-600 disabled:from-gray-300 disabled:to-gray-300 text-white px-4 py-2 rounded-lg hover:from-purple-700 hover:to-pink-700 transition-all duration-300 font-semibold text-sm disabled:cursor-not-allowed"
          >
            Add
          </button>
        </div>

        {/* ── Quick-Add Suggestions ───────────────────────────────────── */}
        {availableSuggestions.length > 0 && (
          <div className="mt-3">
            <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
              Suggestions
            </div>
            <div className="flex flex-wrap gap-1.5">
              {availableSuggestions.slice(0, 6).map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => addItem(suggestion)}
                  className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full border border-dashed border-purple-300 text-purple-600 hover:bg-purple-50 hover:border-purple-400 transition-all duration-200"
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
