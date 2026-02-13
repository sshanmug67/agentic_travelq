// frontend/src/components/itinerary/ItineraryFlightCard.tsx
//
// Changes (v2 — Compact):
//   - Single-row route display instead of two-column leg panels
//   - Inline outbound + return on same line with arrow
//   - Smaller AI Pick badge as a pill
//   - Price and stops on one metadata line
//   - ~60% height reduction

import React from 'react';
import type { Flight } from '../../types/trip';

interface ItineraryFlightCardProps {
  flight: Flight & { selectedBy?: 'ai' | 'user'; priceDifference?: number };
  onDelete: () => void;
}

export const ItineraryFlightCard: React.FC<ItineraryFlightCardProps> = ({
  flight,
  onDelete,
}) => {
  const isAiSelected = flight.selectedBy === 'ai';

  const fmtDate = (d: string) =>
    new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  const fmtTime = (d: string) =>
    new Date(d).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });

  const ob = flight.outbound;
  const rt = flight.return_flight;

  return (
    <div className="itinerary-card !p-3">
      {/* Row 1: Badge + Airline + Delete */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          {isAiSelected ? (
            <span className="ai-sticker !text-[11px] !px-1.5 !py-0.5">🤖 AI</span>
          ) : (
            <span className="user-badge !text-[11px] !px-1.5 !py-0.5 text-white">👤</span>
          )}
          <span className="font-bold text-[15px] text-gray-800 handwritten-body">
            {flight.airline_code} {ob?.flight_number || ''}
          </span>
        </div>
        <button onClick={onDelete} className="paper-delete !w-5 !h-5 !text-sm" aria-label="Delete flight">
          ×
        </button>
      </div>

      {/* Row 2: Route — Outbound */}
      {ob && (
        <div className="flex items-center gap-2 text-[13px] handwritten-body text-gray-700">
          <span className="font-semibold text-purple-700">{ob.departure_airport}</span>
          <span className="text-gray-400">→</span>
          <span className="font-semibold text-purple-700">{ob.arrival_airport}</span>
          <span className="text-gray-400">·</span>
          <span>{fmtDate(ob.departure_time)} {fmtTime(ob.departure_time)}–{fmtTime(ob.arrival_time)}</span>
          {ob.stops > 0 && (
            <span className="text-gray-400 text-[12px]">
              · {ob.stops} stop{ob.stops > 1 ? 's' : ''}{ob.layovers?.length ? ` (${ob.layovers.join(',')})` : ''}
            </span>
          )}
        </div>
      )}

      {/* Row 3: Route — Return */}
      {rt && (
        <div className="flex items-center gap-2 text-[13px] handwritten-body text-gray-700 mt-0.5">
          <span className="font-semibold text-pink-700">{rt.departure_airport}</span>
          <span className="text-gray-400">→</span>
          <span className="font-semibold text-pink-700">{rt.arrival_airport}</span>
          <span className="text-gray-400">·</span>
          <span>{fmtDate(rt.departure_time)} {fmtTime(rt.departure_time)}–{fmtTime(rt.arrival_time)}</span>
          {rt.stops > 0 && (
            <span className="text-gray-400 text-[12px]">
              · {rt.stops} stop{rt.stops > 1 ? 's' : ''}{rt.layovers?.length ? ` (${rt.layovers.join(',')})` : ''}
            </span>
          )}
        </div>
      )}

      {/* Row 4: Price */}
      <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-dashed border-gray-300">
        <span className="font-bold text-[15px] text-green-700 handwritten-body">
          💰 ${flight.price}
        </span>
        {!isAiSelected && flight.priceDifference !== undefined && flight.priceDifference !== 0 && (
          <span className="text-[12px] text-gray-500 handwritten-body">
            {flight.priceDifference > 0 ? '+' : ''}${flight.priceDifference.toFixed(2)} vs AI
          </span>
        )}
      </div>
    </div>
  );
};
