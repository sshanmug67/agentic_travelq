// frontend/src/components/itinerary/ItineraryFlightCard.tsx

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

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  };

  const formatTime = (dateString: string) => {
    return new Date(dateString).toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  return (
    <div className="itinerary-card">
      <div className="flex justify-between items-start mb-3">
        {isAiSelected ? (
          <span className="ai-sticker text-sm">
            🤖 AI Pick
          </span>
        ) : (
          <span className="user-badge text-sm text-white">
            👤 You Chose
          </span>
        )}
        <button
          onClick={onDelete}
          className="paper-delete"
          aria-label="Delete flight"
        >
          ×
        </button>
      </div>

      <div className="handwritten-body">
        <div className="font-bold text-lg mb-2">
          {flight.airline} {flight.outbound.flight_number}
        </div>

        <div className="mb-3">
          <div className="font-semibold text-purple-700">📅 Outbound</div>
          <div className="ml-2">
            <div>
              {flight.outbound.departure_airport} → {flight.outbound.arrival_airport}
            </div>
            <div className="text-sm text-gray-600">
              {formatDate(flight.outbound.departure_time)}{' '}
              {formatTime(flight.outbound.departure_time)} -{' '}
              {formatTime(flight.outbound.arrival_time)}
            </div>
            {flight.outbound.stops > 0 && (
              <div className="text-sm text-gray-600">
                🔄 {flight.outbound.stops} stop{flight.outbound.stops > 1 ? 's' : ''}
                {flight.outbound.layovers && flight.outbound.layovers.length > 0 && 
                  ` (${flight.outbound.layovers.join(', ')})`
                }
              </div>
            )}
          </div>
        </div>

        {flight.return_flight && (
          <div className="mb-3">
            <div className="font-semibold text-purple-700">📅 Return</div>
            <div className="ml-2">
              <div>
                {flight.return_flight.departure_airport} → {flight.return_flight.arrival_airport}
              </div>
              <div className="text-sm text-gray-600">
                {formatDate(flight.return_flight.departure_time)}{' '}
                {formatTime(flight.return_flight.departure_time)} -{' '}
                {formatTime(flight.return_flight.arrival_time)}
              </div>
              {flight.return_flight.stops > 0 && (
                <div className="text-sm text-gray-600">
                  🔄 {flight.return_flight.stops} stop{flight.return_flight.stops > 1 ? 's' : ''}
                  {flight.return_flight.layovers && flight.return_flight.layovers.length > 0 && 
                    ` (${flight.return_flight.layovers.join(', ')})`
                  }
                </div>
              )}
            </div>
          </div>
        )}

        <div className="mt-4 pt-3 border-t border-dashed border-gray-300">
          <div className="flex justify-between items-center">
            <span className="font-bold text-lg text-green-700">
              💰 ${flight.price}
            </span>
            {!isAiSelected && flight.priceDifference !== undefined && flight.priceDifference !== 0 && (
              <span className="text-sm text-gray-600">
                {flight.priceDifference > 0 ? '+' : ''}${flight.priceDifference} vs AI
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};