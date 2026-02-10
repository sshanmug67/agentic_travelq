import React from 'react';
import { Plane } from 'lucide-react';
import type { Flight } from '@/types/trip';
import { Card } from '@/components/common/Card';

interface FlightCardProps {
  flight: Flight;
}

export const FlightCard: React.FC<FlightCardProps> = ({ flight }) => {
  const formatTime = (dateString: string) => {
    return new Date(dateString).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <Card className="hover:shadow-lg transition-shadow">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Plane className="w-6 h-6 text-blue-600" />
          <div>
            <p className="font-semibold text-lg">
              {flight.airline} {flight.flight_number}
            </p>
            <p className="text-sm text-gray-600">{flight.duration}</p>
          </div>
        </div>
        
        <div className="text-right">
          {flight.price && (
            <p className="text-2xl font-bold text-blue-600">
              ${flight.price.toFixed(2)}
            </p>
          )}
          {flight.currency && (
            <p className="text-sm text-gray-500">{flight.currency}</p>
          )}
        </div>
      </div>

      <div className="mt-4 flex justify-between items-center">
        <div>
          <p className="text-sm text-gray-500">Departure</p>
          <p className="font-semibold">{flight.origin}</p>
          <p className="text-sm">{formatTime(flight.departure_time)}</p>
          <p className="text-xs text-gray-500">
            {formatDate(flight.departure_time)}
          </p>
        </div>

        <div className="flex-1 mx-4">
          <div className="border-t-2 border-dashed border-gray-300 relative">
            <Plane className="w-4 h-4 absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-gray-400 rotate-90" />
          </div>
        </div>

        <div className="text-right">
          <p className="text-sm text-gray-500">Arrival</p>
          <p className="font-semibold">{flight.destination}</p>
          <p className="text-sm">{formatTime(flight.arrival_time)}</p>
          <p className="text-xs text-gray-500">
            {formatDate(flight.arrival_time)}
          </p>
        </div>
      </div>
    </Card>
  );
};
