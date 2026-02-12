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

  const formatDate = (dateString: string) =>
    new Date(dateString).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  const formatTime = (dateString: string) =>
    new Date(dateString).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });

  const FlightLeg: React.FC<{
    label: string;
    color: string;
    departure_airport: string;
    arrival_airport: string;
    departure_time: string;
    arrival_time: string;
    stops: number;
    layovers?: string[];
  }> = ({ label, color, departure_airport, arrival_airport, departure_time, arrival_time, stops, layovers }) => (
    <div className="flex-1 min-w-0">
      <div className={`font-semibold text-[19px] ${color} mb-1`}>📅 {label}</div>
      <div className="text-[19px] font-bold text-gray-800">
        {departure_airport} → {arrival_airport}
      </div>
      <div className="text-[17px] text-gray-600 mt-0.5">
        {formatDate(departure_time)} {formatTime(departure_time)} – {formatTime(arrival_time)}
      </div>
      {stops > 0 && (
        <div className="text-[17px] text-gray-500 mt-0.5">
          🔄 {stops} stop{stops > 1 ? 's' : ''}
          {layovers && layovers.length > 0 && ` (${layovers.join(', ')})`}
        </div>
      )}
    </div>
  );

  return (
    <div className="itinerary-card">
      {/* Header: badge + delete */}
      <div className="flex justify-between items-start mb-3">
        {isAiSelected ? (
          <span className="ai-sticker text-[17px]">🤖 AI Pick</span>
        ) : (
          <span className="user-badge text-[17px] text-white">👤 You Chose</span>
        )}
        <button onClick={onDelete} className="paper-delete" aria-label="Delete flight">
          ×
        </button>
      </div>

      <div className="handwritten-body">
        {/* Airline name */}
        <div className="font-bold text-[21px] mb-3">
          {flight.airline_code} {flight.outbound?.flight_number || ''}
        </div>

        {/* Side-by-side legs */}
        <div className="flex gap-4">
          {flight.outbound && (
            <FlightLeg
              label="Outbound"
              color="text-purple-700"
              departure_airport={flight.outbound.departure_airport}
              arrival_airport={flight.outbound.arrival_airport}
              departure_time={flight.outbound.departure_time}
              arrival_time={flight.outbound.arrival_time}
              stops={flight.outbound.stops}
              layovers={flight.outbound.layovers}
            />
          )}

          {flight.return_flight && (
            <>
              {/* Divider */}
              <div className="w-px bg-gray-300 self-stretch" />

              <FlightLeg
                label="Return"
                color="text-pink-700"
                departure_airport={flight.return_flight.departure_airport}
                arrival_airport={flight.return_flight.arrival_airport}
                departure_time={flight.return_flight.departure_time}
                arrival_time={flight.return_flight.arrival_time}
                stops={flight.return_flight.stops}
                layovers={flight.return_flight.layovers}
              />
            </>
          )}
        </div>

        {/* Price */}
        <div className="mt-3 pt-2 border-t border-dashed border-gray-300">
          <div className="flex justify-between items-center">
            <span className="font-bold text-[21px] text-green-700">
              💰 ${flight.price}
            </span>
            {!isAiSelected && flight.priceDifference !== undefined && flight.priceDifference !== 0 && (
              <span className="text-[17px] text-gray-600">
                {flight.priceDifference > 0 ? '+' : ''}${flight.priceDifference.toFixed(2)} vs AI
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
