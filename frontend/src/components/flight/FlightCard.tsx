// frontend/src/components/flight/FlightCard.tsx
//
// Changes (v2 — Grid-friendly):
//   - Route rows stack vertically for half-width cards
//   - Compact airport → airport with time below
//   - Duration shown inline, not on a stretched line
//   - Works in both single-col and 2-col grid

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

  const LegRow: React.FC<{
    tag: string;
    tagColor: string;
    bgColor: string;
    leg: any;
  }> = ({ tag, tagColor, bgColor, leg }) => (
    <div className={`${bgColor} rounded px-2.5 py-2`}>
      <div className="flex items-center justify-between mb-0.5">
        <span className={`text-[11px] font-bold ${tagColor} uppercase tracking-wide`}>{tag}</span>
        <span className="text-[11px] text-gray-400">{formatDate(leg.departure_time)}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="font-bold text-[14px] text-gray-800">{leg.departure_airport}</span>
        <span className="text-[11px] text-gray-400">{formatTime(leg.departure_time)}</span>
        <div className="flex-1 flex items-center gap-1 px-1">
          <div className="flex-1 h-px bg-gray-300" />
          <span className="text-[10px] text-gray-400 whitespace-nowrap">{leg.duration}</span>
          <div className="flex-1 h-px bg-gray-300" />
        </div>
        <span className="text-[11px] text-gray-400">{formatTime(leg.arrival_time)}</span>
        <span className="font-bold text-[14px] text-gray-800">{leg.arrival_airport}</span>
      </div>
      {leg.stops > 0 && (
        <div className="text-[11px] text-gray-400 mt-0.5">
          🔄 {stopsLabel(leg.stops)}{leg.layovers?.length ? ` via ${leg.layovers.join(', ')}` : ''}
        </div>
      )}
    </div>
  );

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
      {/* AI Badge */}
      {isAiRecommended && !isSelected && (
        <div className="bg-gradient-to-r from-yellow-400 to-yellow-500 px-3 py-0.5 flex items-center justify-center">
          <span className="text-[12px] font-bold text-yellow-900">🤖 AI Recommended</span>
        </div>
      )}

      <div className="p-3">
        {/* Header: radio + airline + price */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <input
              type="radio"
              checked={isSelected}
              onChange={onSelect}
              className="w-3.5 h-3.5 text-purple-600 cursor-pointer"
            />
            <span className="font-bold text-[14px] text-gray-800">
              {flight.airline_code} {flight.outbound?.flight_number || ''}
            </span>
            {isAiRecommended && <span className="text-[13px]" title="AI Recommended">🌟</span>}
            <span className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-[11px] font-medium">
              {flight.cabin_class}
            </span>
          </div>
          <span className="text-[17px] font-bold text-green-600">${flight.price}</span>
        </div>

        {/* Outbound leg */}
        {flight.outbound && (
          <LegRow tag="Out" tagColor="text-blue-600" bgColor="bg-blue-50/60" leg={flight.outbound} />
        )}

        {/* Return leg */}
        {flight.return_flight && (
          <div className="mt-1">
            <LegRow tag="Ret" tagColor="text-purple-600" bgColor="bg-purple-50/60" leg={flight.return_flight} />
          </div>
        )}

        {/* Footer: baggage + actions */}
        <div className="mt-2 flex items-center justify-between text-[11px] text-gray-500">
          <div className="flex items-center gap-2">
            {flight.cabin_bags && (
              <span>💼 {flight.cabin_bags.quantity} cabin</span>
            )}
            {flight.checked_bags && (
              <span>🧳 {flight.checked_bags.quantity} checked</span>
            )}
            {!flight.cabin_bags && !flight.checked_bags && (
              <span>{stopsLabel(flight.outbound?.stops ?? 0)}</span>
            )}
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); setShowDetails(!showDetails); }}
            className="text-purple-600 hover:text-purple-700 font-semibold hover:underline text-[12px]"
          >
            {showDetails ? 'Hide' : 'Details'}
          </button>
        </div>

        {/* Expandable Details */}
        <motion.div
          initial={false}
          animate={{ height: showDetails ? 'auto' : 0 }}
          className="overflow-hidden"
        >
          <div className="mt-2 pt-2 border-t border-gray-200 text-[12px] space-y-1">
            <div className="flex justify-between">
              <span className="text-gray-500">Total Duration:</span>
              <span className="font-semibold">{flight.total_duration}</span>
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
