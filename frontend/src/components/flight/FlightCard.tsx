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

  const formatTime = (dateStr: string) =>
    new Date(dateStr).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  const stopsLabel = (stops: number) =>
    stops === 0 ? 'Direct' : `${stops} stop${stops > 1 ? 's' : ''}`;

  return (
    <motion.div
      whileHover={{ scale: 1.01 }}
      transition={{ duration: 0.15 }}
      className={`rounded-lg overflow-hidden cursor-pointer transition-all duration-200 ${
        isSelected
          ? 'ring-2 ring-purple-500 shadow-lg bg-gradient-to-br from-purple-50 to-pink-50'
          : 'hover:shadow-md bg-white border border-gray-200'
      }`}
      onClick={onSelect}
    >
      {/* AI Recommendation Badge — slim */}
      {isAiRecommended && !isSelected && (
        <div className="bg-gradient-to-r from-yellow-400 to-yellow-500 px-3 py-0.5 flex items-center justify-center gap-2">
          <span className="text-[15px] font-bold text-yellow-900">🤖 AI Recommended</span>
        </div>
      )}

      <div className="px-4 py-3">
        {/* Header row: radio + airline + cabin/stops ... price */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <input
              type="radio"
              checked={isSelected}
              onChange={onSelect}
              className="w-4 h-4 text-purple-600 cursor-pointer"
            />
            <div className="flex items-center gap-2">
              <span className="font-bold text-[17px] text-gray-800">
                {flight.airline_code} {flight.outbound?.flight_number || ''}
              </span>
              {isAiRecommended && <span className="text-[17px]" title="AI Recommended">🌟</span>}
              <span className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-[15px] font-medium">
                {flight.cabin_class}
              </span>
              <span className="text-[15px] text-gray-500">
                • {stopsLabel(flight.outbound?.stops ?? 0)}
              </span>
            </div>
          </div>
          <div className="text-right">
            <span className="text-[21px] font-bold text-green-600">${flight.price}</span>
            <span className="text-[15px] text-gray-400 ml-1">pp</span>
          </div>
        </div>

        {/* Outbound row */}
        <div className="flex items-center gap-2 py-1.5 px-2 bg-blue-50/60 rounded text-[17px]">
          <span className="text-[15px] font-semibold text-blue-600 w-8 flex-shrink-0">OUT</span>
          <span className="font-semibold text-gray-800 w-10">{flight.outbound?.departure_airport}</span>
          <span className="text-[15px] text-gray-500">{formatTime(flight.outbound?.departure_time)}</span>
          <div className="flex-1 flex items-center px-1">
            <div className="flex-1 h-px bg-blue-300" />
            <span className="text-[15px] text-gray-400 px-1.5">
              {flight.outbound?.duration}
            </span>
            <div className="flex-1 h-px bg-blue-300" />
          </div>
          <span className="font-semibold text-gray-800 w-10 text-right">{flight.outbound?.arrival_airport}</span>
          <span className="text-[15px] text-gray-500 w-16 text-right">{formatTime(flight.outbound?.arrival_time)}</span>
          <span className="text-[15px] text-gray-400 w-14 text-right">{formatDate(flight.outbound?.departure_time)}</span>
          {(flight.outbound?.stops ?? 0) > 0 && flight.outbound?.layovers && flight.outbound.layovers.length > 0 && (
            <span className="text-[15px] text-gray-400 ml-1">via {flight.outbound.layovers.join(',')}</span>
          )}
        </div>

        {/* Return row */}
        {flight.return_flight && (
          <div className="flex items-center gap-2 py-1.5 px-2 bg-purple-50/60 rounded text-[17px] mt-1">
            <span className="text-[15px] font-semibold text-purple-600 w-8 flex-shrink-0">RET</span>
            <span className="font-semibold text-gray-800 w-10">{flight.return_flight.departure_airport}</span>
            <span className="text-[15px] text-gray-500">{formatTime(flight.return_flight.departure_time)}</span>
            <div className="flex-1 flex items-center px-1">
              <div className="flex-1 h-px bg-purple-300" />
              <span className="text-[15px] text-gray-400 px-1.5">
                {flight.return_flight.duration}
              </span>
              <div className="flex-1 h-px bg-purple-300" />
            </div>
            <span className="font-semibold text-gray-800 w-10 text-right">{flight.return_flight.arrival_airport}</span>
            <span className="text-[15px] text-gray-500 w-16 text-right">{formatTime(flight.return_flight.arrival_time)}</span>
            <span className="text-[15px] text-gray-400 w-14 text-right">{formatDate(flight.return_flight.departure_time)}</span>
            {flight.return_flight.stops > 0 && flight.return_flight.layovers && flight.return_flight.layovers.length > 0 && (
              <span className="text-[15px] text-gray-400 ml-1">via {flight.return_flight.layovers.join(',')}</span>
            )}
          </div>
        )}

        {/* Footer row: baggage + actions */}
        <div className="mt-2 flex items-center justify-between text-[15px] text-gray-500">
          <div className="flex items-center gap-3">
            {flight.cabin_bags && (
              <span>💼 {flight.cabin_bags.quantity} cabin bag ({flight.cabin_bags.weight}{flight.cabin_bags.weight_unit})</span>
            )}
            {flight.checked_bags && (
              <span>🧳 {flight.checked_bags.quantity} checked</span>
            )}
          </div>
          <div className="flex gap-3">
            <button
              onClick={(e) => { e.stopPropagation(); setShowDetails(!showDetails); }}
              className="text-purple-600 hover:text-purple-700 font-semibold hover:underline"
            >
              {showDetails ? 'Hide' : 'Details'}
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
          <div className="mt-2 pt-2 border-t border-gray-200 text-[15px] space-y-1">
            <div className="flex justify-between">
              <span className="text-gray-500">Total Duration:</span>
              <span className="font-semibold">{flight.total_duration}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Aircraft:</span>
              <span className="font-semibold">Boeing 787 (Estimated)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Cancellation:</span>
              <span className="font-semibold text-green-600">Flexible</span>
            </div>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
};
