// frontend/src/components/common/PreferencesSummary.tsx

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface PreferencesSummaryProps {
  preferences: {
    airlines: Array<{ name: string }>;
    hotelChains: Array<{ name: string }>;
    cuisines: Array<{ name: string }>;
    activities: Array<{ name: string }>;
    budget: {
      meals: string;
      accommodation: string;
      activities: string;
    };
  };
}

export const PreferencesSummary: React.FC<PreferencesSummaryProps> = ({
  preferences,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const formatList = (items: Array<{ name: string }>) => {
    if (items.length === 0) return 'None';
    if (items.length <= 2) return items.map((i) => i.name).join(', ');
    return `${items[0].name}, ${items[1].name} +${items.length - 2} more`;
  };

  return (
    <div className="bg-gradient-to-r from-purple-50 via-pink-50 to-orange-50 border-y border-gray-200 shadow-sm">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-6 py-3 flex items-center justify-between hover:bg-white/50 transition-all duration-300"
      >
        <div className="flex items-center gap-4 text-sm">
          <span className="font-semibold text-purple-700">Preferences:</span>
          <div className="flex items-center gap-3 text-gray-700">
            <span className="flex items-center gap-1">
              ✈️ <span className="hidden sm:inline">Airlines:</span>{' '}
              <span className="font-medium">{formatList(preferences.airlines)}</span>
            </span>
            <span className="hidden md:inline">•</span>
            <span className="hidden md:flex items-center gap-1">
              🏨 <span className="hidden sm:inline">Hotels:</span>{' '}
              <span className="font-medium">{formatList(preferences.hotelChains)}</span>
            </span>
            <span className="hidden lg:inline">•</span>
            <span className="hidden lg:flex items-center gap-1">
              🍽️ <span className="hidden sm:inline">Cuisines:</span>{' '}
              <span className="font-medium">{formatList(preferences.cuisines)}</span>
            </span>
            <span className="hidden lg:inline">•</span>
            <span className="hidden lg:flex items-center gap-1">
              💵 <span className="hidden sm:inline">Budget:</span>{' '}
              <span className="font-medium">{preferences.budget.meals}</span>
            </span>
          </div>
        </div>
        <motion.div
          animate={{ rotate: isExpanded ? 180 : 0 }}
          transition={{ duration: 0.3 }}
          className="text-purple-600 text-xl"
        >
          ▼
        </motion.div>
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden"
          >
            <div className="px-6 pb-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Airlines */}
              <div className="bg-white rounded-lg p-3 shadow-sm border border-purple-200">
                <h4 className="font-semibold text-sm text-purple-700 mb-2">✈️ Airlines</h4>
                {preferences.airlines.length > 0 ? (
                  <ul className="text-xs space-y-1">
                    {preferences.airlines.map((airline, idx) => (
                      <li key={idx} className="text-gray-700">
                        • {airline.name}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-gray-400">None set</p>
                )}
              </div>

              {/* Hotels */}
              <div className="bg-white rounded-lg p-3 shadow-sm border border-pink-200">
                <h4 className="font-semibold text-sm text-pink-700 mb-2">🏨 Hotels</h4>
                {preferences.hotelChains.length > 0 ? (
                  <ul className="text-xs space-y-1">
                    {preferences.hotelChains.map((hotel, idx) => (
                      <li key={idx} className="text-gray-700">
                        • {hotel.name}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-gray-400">None set</p>
                )}
              </div>

              {/* Cuisines */}
              <div className="bg-white rounded-lg p-3 shadow-sm border border-orange-200">
                <h4 className="font-semibold text-sm text-orange-700 mb-2">🍽️ Cuisines</h4>
                {preferences.cuisines.length > 0 ? (
                  <ul className="text-xs space-y-1">
                    {preferences.cuisines.map((cuisine, idx) => (
                      <li key={idx} className="text-gray-700">
                        • {cuisine.name}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-gray-400">None set</p>
                )}
              </div>

              {/* Budget */}
              <div className="bg-white rounded-lg p-3 shadow-sm border border-green-200">
                <h4 className="font-semibold text-sm text-green-700 mb-2">💵 Budget</h4>
                <div className="text-xs space-y-1">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Meals:</span>
                    <span className="font-medium">{preferences.budget.meals}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Activities:</span>
                    <span className="font-medium">{preferences.budget.activities}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Accommodation:</span>
                    <span className="font-medium">{preferences.budget.accommodation}</span>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};