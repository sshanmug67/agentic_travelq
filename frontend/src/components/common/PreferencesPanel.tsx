// frontend/src/components/common/PreferencesPanel.tsx

import React, { useState } from 'react';

interface Preference {
  name: string;
  preferred?: boolean;
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
}

interface PreferencesPanelProps {
  preferences: PreferencesData;
  onUpdate: (category: keyof PreferencesData, value: any) => void;
}

type TabType = 'airlines' | 'hotels' | 'activities' | 'restaurant';

export const PreferencesPanel: React.FC<PreferencesPanelProps> = ({
  preferences,
  onUpdate,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('airlines');
  const [isAdding, setIsAdding] = useState(false);
  const [newItem, setNewItem] = useState('');

  const tabs: { id: TabType; label: string; icon: string }[] = [
    { id: 'airlines', label: 'Airlines', icon: '✈️' },
    { id: 'hotels', label: 'Hotels', icon: '🏨' },
    { id: 'activities', label: 'Activities', icon: '🎭' },
    { id: 'restaurant', label: 'Restaurant', icon: '🍽️' },
  ];

  const handleAdd = () => {
    if (!newItem.trim()) return;

    const category = activeTab === 'restaurant' ? 'cuisines' : 
                     activeTab === 'hotels' ? 'hotelChains' : activeTab;
    
    const newPref = { name: newItem, preferred: false };
    const currentItems = preferences[category as keyof PreferencesData] as Preference[];
    onUpdate(category as keyof PreferencesData, [...currentItems, newPref]);
    
    setNewItem('');
    setIsAdding(false);
  };

  const handleRemove = (category: string, item: Preference) => {
    const key = category === 'restaurant' ? 'cuisines' : 
                category === 'hotels' ? 'hotelChains' : category;
    const currentItems = preferences[key as keyof PreferencesData] as Preference[];
    onUpdate(
      key as keyof PreferencesData,
      currentItems.filter((p) => p.name !== item.name)
    );
  };

  const togglePreferred = (category: string, itemName: string) => {
    const key = category === 'restaurant' ? 'cuisines' : 
                category === 'hotels' ? 'hotelChains' : category;
    const items = preferences[key as keyof PreferencesData] as Preference[];
    
    onUpdate(
      key as keyof PreferencesData,
      items.map((p) =>
        p.name === itemName ? { ...p, preferred: !p.preferred } : p
      )
    );
  };

  const renderContent = () => {
    const category = activeTab === 'restaurant' ? 'cuisines' : 
                     activeTab === 'hotels' ? 'hotelChains' : activeTab;
    const items = preferences[category as keyof PreferencesData] as Preference[];

    return (
      <div className="min-h-[200px]">
        {items && items.length > 0 ? (
          <div className="space-y-2 mb-3">
            {items.map((item) => (
              <div
                key={item.name}
                className="group flex items-center justify-between bg-gradient-to-r from-purple-50 to-pink-50 hover:from-purple-100 hover:to-pink-100 px-3 py-2 rounded-lg border border-purple-200 transition-all duration-300"
              >
                <div className="flex items-center gap-2 flex-1">
                  <button
                    onClick={() => togglePreferred(activeTab, item.name)}
                    className="text-lg transition-transform hover:scale-125"
                  >
                    {item.preferred ? '⭐' : '☆'}
                  </button>
                  <span className="font-medium text-gray-800">{item.name}</span>
                  {item.preferred && (
                    <span className="text-xs bg-yellow-200 text-yellow-800 px-2 py-0.5 rounded-full">
                      Preferred
                    </span>
                  )}
                </div>
                <button
                  onClick={() => handleRemove(activeTab, item)}
                  className="text-red-500 hover:text-red-700 opacity-0 group-hover:opacity-100 transition-all duration-200"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-gray-400">
            <div className="text-4xl mb-2">
              {tabs.find((t) => t.id === activeTab)?.icon}
            </div>
            <p className="text-sm">No {activeTab} preference set</p>
          </div>
        )}

        {isAdding ? (
          <div className="flex gap-2 items-center bg-white p-2 rounded-lg border-2 border-purple-300">
            <input
              type="text"
              value={newItem}
              onChange={(e) => setNewItem(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleAdd()}
              placeholder={`Add ${activeTab}...`}
              className="flex-1 text-sm px-3 py-2 border border-gray-300 rounded-md focus:border-purple-500 focus:ring-2 focus:ring-purple-200 outline-none"
              autoFocus
            />
            <button
              onClick={handleAdd}
              className="bg-gradient-to-r from-purple-600 to-pink-600 text-white px-4 py-2 rounded-md hover:from-purple-700 hover:to-pink-700 transition-all duration-300 font-semibold"
            >
              Add
            </button>
            <button
              onClick={() => {
                setIsAdding(false);
                setNewItem('');
              }}
              className="text-gray-600 hover:text-gray-800 px-2"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setIsAdding(true)}
            className="w-full text-sm text-purple-600 hover:text-purple-700 font-semibold py-2 px-3 border-2 border-dashed border-purple-300 rounded-lg hover:border-purple-500 hover:bg-purple-50 transition-all duration-300"
          >
            + Add {activeTab}
          </button>
        )}
      </div>
    );
  };

  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
      <div className="bg-gradient-to-r from-purple-600 to-pink-600 px-4 py-3">
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          ⚙️ Preferences
        </h3>
      </div>

      {/* Tab Headers */}
      <div className="flex border-b bg-gradient-to-r from-purple-50 to-pink-50">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 px-3 py-3 text-sm font-medium transition-all duration-300 relative ${
              activeTab === tab.id
                ? 'text-purple-700 bg-white'
                : 'text-gray-600 hover:text-purple-600 hover:bg-white/50'
            }`}
          >
            <span className="flex items-center justify-center gap-1">
              <span className="text-lg">{tab.icon}</span>
              <span className="hidden sm:inline">{tab.label}</span>
            </span>
            {activeTab === tab.id && (
              <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-purple-600 to-pink-600" />
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="p-4">
        {renderContent()}
      </div>
    </div>
  );
};