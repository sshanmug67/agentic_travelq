// frontend/src/components/flight/FlightCard.tsx

import React from 'react';
import { motion } from 'framer-motion';
import { Flight } from '../../types/trip';

interface FlightCardProps {
  flight: Flight;
  isSelected: boolean;
  isAiRecommended: boolean;
  onSelect: () => void;
}

export const FlightCard: React.FC<FlightCardProps> = ({
  flight,
  isSelected,
  isAiRecommended,
  onSelect,
}) => {
  const [showDetails, setShowDetails] = React.useState(false);

  return (
    <motion.div
      whileHover={{ scale: 1.02, y: -4 }}
      transition={{ duration: 0.2 }}
      className={`rounded-xl overflow-hidden cursor-pointer transition-all duration-300 ${
        isSelected
          ? 'ring-4 ring-purple-500 shadow-2xl bg-gradient-to-br from-purple-50 to-pink-50'
          : 'hover:shadow-xl bg-white border-2 border-gray-200'
      }`}
      onClick={onSelect}
    >
      {/* AI Recommendation Badge */}
      {isAiRecommended && !isSelected && (
        <div className="bg-gradient-to-r from-yellow-400 to-yellow-500 px-4 py-1 flex items-center justify-center gap-2">
          <span className="text-sm font-bold text-yellow-900">🤖 AI Recommended</span>
          <span className="text-xs bg-yellow-600 text-white px-2 py-0.5 rounded-full">
            Best Value
          </span>
        </div>
      )}

      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-start gap-3">
            <input
              type="radio"
              checked={isSelected}
              onChange={onSelect}
              className="mt-1 w-5 h-5 text-purple-600 cursor-pointer"
            />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg text-gray-800">
                  {flight.airline} {flight.outbound.flight_number}
                </span>
                {isAiRecommended && (
                  <span className="text-xl" title="AI Recommended">
                    🌟
                  </span>
                )}
              </div>
              <div className="text-sm text-gray-600 mt-1 flex items-center gap-2">
                <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full text-xs font-medium">
                  {flight.cabin_class}
                </span>
                <span>•</span>
                <span>
                  {flight.outbound.stops === 0
                    ? 'Direct'
                    : `${flight.outbound.stops} stop${flight.outbound.stops > 1 ? 's' : ''}`}
                </span>
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-green-600">${flight.price}</div>
            <div className="text-xs text-gray-500">per person</div>
          </div>
        </div>

        {/* Flight Route Visualization */}
        <div className="space-y-3">
          {/* Outbound */}
          <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-blue-700 uppercase tracking-wide">
                ✈️ Outbound
              </span>
              <span className="text-xs text-gray-600">
                {new Date(flight.outbound.departure_time).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                })}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-center">
                <div className="font-bold text-lg">{flight.outbound.departure_airport}</div>
                <div className="text-sm text-gray-600">
                  {new Date(flight.outbound.departure_time).toLocaleTimeString('en-US', {
                    hour: 'numeric',
                    minute: '2-digit',
                  })}
                </div>
              </div>
              <div className="flex-1 flex items-center">
                <div className="flex-1 h-0.5 bg-gradient-to-r from-blue-400 to-purple-400 relative">
                  <motion.div
                    animate={{ x: ['0%', '100%'] }}
                    transition={{ duration: 2, repeat: Infinity }}
                    className="absolute top-1/2 -translate-y-1/2 text-blue-600"
                  >
                    ✈
                  </motion.div>
                </div>
              </div>
              <div className="text-center">
                <div className="font-bold text-lg">{flight.outbound.arrival_airport}</div>
                <div className="text-sm text-gray-600">
                  {new Date(flight.outbound.arrival_time).toLocaleTimeString('en-US', {
                    hour: 'numeric',
                    minute: '2-digit',
                  })}
                </div>
              </div>
            </div>
            <div className="text-xs text-gray-600 mt-2 flex items-center justify-center gap-2">
              <span>⏱️ {flight.outbound.duration}</span>
              {flight.outbound.stops > 0 && flight.outbound.layovers && (
                <>
                  <span>•</span>
                  <span>🔄 via {flight.outbound.layovers.join(', ')}</span>
                </>
              )}
            </div>
          </div>

          {/* Return */}
          {flight.return_flight && (
            <div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-purple-700 uppercase tracking-wide">
                  ✈️ Return
                </span>
                <span className="text-xs text-gray-600">
                  {new Date(flight.return_flight.departure_time).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                  })}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-center">
                  <div className="font-bold text-lg">{flight.return_flight.departure_airport}</div>
                  <div className="text-sm text-gray-600">
                    {new Date(flight.return_flight.departure_time).toLocaleTimeString('en-US', {
                      hour: 'numeric',
                      minute: '2-digit',
                    })}
                  </div>
                </div>
                <div className="flex-1 flex items-center">
                  <div className="flex-1 h-0.5 bg-gradient-to-r from-purple-400 to-pink-400 relative">
                    <motion.div
                      animate={{ x: ['0%', '100%'] }}
                      transition={{ duration: 2, repeat: Infinity }}
                      className="absolute top-1/2 -translate-y-1/2 text-purple-600 transform rotate-180"
                    >
                      ✈
                    </motion.div>
                  </div>
                </div>
                <div className="text-center">
                  <div className="font-bold text-lg">{flight.return_flight.arrival_airport}</div>
                  <div className="text-sm text-gray-600">
                    {new Date(flight.return_flight.arrival_time).toLocaleTimeString('en-US', {
                      hour: 'numeric',
                      minute: '2-digit',
                    })}
                  </div>
                </div>
              </div>
              <div className="text-xs text-gray-600 mt-2 flex items-center justify-center gap-2">
                <span>⏱️ {flight.return_flight.duration}</span>
                {flight.return_flight.stops > 0 && flight.return_flight.layovers && (
                  <>
                    <span>•</span>
                    <span>🔄 via {flight.return_flight.layovers.join(', ')}</span>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Additional Info */}
        <div className="mt-4 flex items-center justify-between text-xs text-gray-600">
          <div className="flex items-center gap-3">
            {flight.cabin_bags && (
              <span className="flex items-center gap-1">
                💼 {flight.cabin_bags.quantity} cabin bag ({flight.cabin_bags.weight}
                {flight.cabin_bags.weight_unit})
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowDetails(!showDetails);
              }}
              className="text-purple-600 hover:text-purple-700 font-semibold hover:underline"
            >
              {showDetails ? 'Hide' : 'View'} Details
            </button>
            <button
              onClick={(e) => e.stopPropagation()}
              className="text-purple-600 hover:text-purple-700 font-semibold hover:underline"
            >
              Compare
            </button>
          </div>
        </div>

        {/* Expandable Details */}
        <motion.div
          initial={false}
          animate={{ height: showDetails ? 'auto' : 0 }}
          className="overflow-hidden"
        >
          <div className="mt-4 pt-4 border-t border-gray-200 text-sm space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-600">Total Duration:</span>
              <span className="font-semibold">{flight.total_duration}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Aircraft:</span>
              <span className="font-semibold">Boeing 787 (Estimated)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Cancellation:</span>
              <span className="font-semibold text-green-600">Flexible</span>
            </div>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
};