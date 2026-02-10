import React from 'react';
import { Calendar, MapPin, Tag } from 'lucide-react';
import type { Event } from '@/types/trip';
import { Card } from '@/components/common/Card';

interface EventCardProps {
  event: Event;
}

export const EventCard: React.FC<EventCardProps> = ({ event }) => {
  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Card className="hover:shadow-lg transition-shadow">
      {event.image_url && (
        <img
          src={event.image_url}
          alt={event.name}
          className="w-full h-48 object-cover rounded-t-lg -mt-6 -mx-6 mb-4"
        />
      )}

      <div className="space-y-3">
        <div>
          <h4 className="text-lg font-semibold text-gray-900">{event.name}</h4>
          <div className="flex items-center gap-2 mt-1">
            <Tag className="w-4 h-4 text-gray-500" />
            <span className="text-sm text-gray-600">{event.category}</span>
          </div>
        </div>

        {event.description && (
          <p className="text-sm text-gray-600 line-clamp-2">
            {event.description}
          </p>
        )}

        <div className="space-y-2 text-sm">
          <div className="flex items-start gap-2">
            <Calendar className="w-4 h-4 text-gray-500 mt-0.5" />
            <span className="text-gray-700">
              {formatDateTime(event.start_time)}
            </span>
          </div>

          <div className="flex items-start gap-2">
            <MapPin className="w-4 h-4 text-gray-500 mt-0.5" />
            <div>
              <p className="text-gray-700 font-medium">{event.venue}</p>
              <p className="text-gray-600 text-xs">{event.address}</p>
            </div>
          </div>
        </div>

        {event.price_range && (
          <div className="pt-3 border-t">
            <p className="text-sm">
              <span className="text-gray-600">Price: </span>
              <span className="font-semibold text-blue-600">
                {event.price_range}
              </span>
            </p>
          </div>
        )}

        {event.ticket_url && (
          <a
            href={event.ticket_url}
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full text-center bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            Get Tickets
          </a>
        )}
      </div>
    </Card>
  );
};
