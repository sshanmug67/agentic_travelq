// frontend/src/components/itinerary/ItineraryHotelCard.tsx

import React from 'react';
import type { Hotel } from '../../types/trip';

interface ItineraryHotelCardProps {
  hotel: Hotel & { selectedBy?: 'ai' | 'user'; priceDifference?: number };
  onDelete: () => void;
}

export const ItineraryHotelCard: React.FC<ItineraryHotelCardProps> = ({
  hotel,
  onDelete,
}) => {
  const isAiSelected = hotel.selectedBy === 'ai';

  // Handle photos being either string[] or {url: string}[]
  const rawPhotos = hotel.photos || [];
  const firstPhoto = rawPhotos.length > 0
    ? (typeof rawPhotos[0] === 'string' ? rawPhotos[0] : (rawPhotos[0] as any)?.url)
    : null;

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const renderStars = (rating: number) => {
    const full = Math.floor(rating);
    return (
      <span className="inline-flex gap-0.5">
        {[...Array(5)].map((_, i) => (
          <span key={i} className={i < full ? 'text-yellow-500' : 'text-gray-300'}>★</span>
        ))}
      </span>
    );
  };

  return (
    <div className="itinerary-card">
      {/* Header: badge + delete */}
      <div className="flex justify-between items-start mb-3">
        {isAiSelected ? (
          <span className="ai-sticker text-[15px]">🤖 AI Pick</span>
        ) : (
          <span className="user-badge text-[15px] text-white">👤 You Chose</span>
        )}
        <button onClick={onDelete} className="paper-delete" aria-label="Delete hotel">
          ×
        </button>
      </div>

      <div className="handwritten-body">
        {/* Side-by-side: thumbnail + details */}
        <div className="flex gap-3">
          {/* Photo thumbnail */}
          {firstPhoto ? (
            <img
              src={firstPhoto}
              alt={hotel.name}
              className="w-16 h-16 rounded-lg object-cover flex-shrink-0"
            />
          ) : (
            <div className="w-16 h-16 rounded-lg bg-gray-200 flex items-center justify-center flex-shrink-0">
              <span className="text-[25px]">🏨</span>
            </div>
          )}

          {/* Hotel info */}
          <div className="flex-1 min-w-0">
            <div className="font-bold text-[19px] text-gray-800 truncate">
              {hotel.name}
            </div>
            <div className="flex items-center gap-1 mt-0.5">
              <span className="text-[13px]">{renderStars(hotel.google_rating)}</span>
              <span className="text-[15px] font-semibold text-gray-700">{hotel.google_rating}</span>
              <span className="text-[13px] text-gray-400">
                ({hotel.user_ratings_total?.toLocaleString()})
              </span>
            </div>
          </div>
        </div>

        {/* Address */}
        <div className="mt-2 flex items-start gap-1">
          <span className="text-[13px] mt-0.5">📍</span>
          <span className="text-[15px] text-gray-600 leading-tight">{hotel.address}</span>
        </div>

        {/* Dates */}
        <div className="mt-1 flex items-center gap-1">
          <span className="text-[13px]">🗓️</span>
          <span className="text-[15px] text-gray-600">
            {formatDate(hotel.check_in_date)} – {formatDate(hotel.check_out_date)}
          </span>
          <span className="text-[13px] text-gray-400 ml-1">
            • {hotel.num_nights} nights
          </span>
        </div>

        {/* Price */}
        <div className="mt-3 pt-2 border-t border-dashed border-gray-300">
          <div className="flex justify-between items-center">
            <span className="font-bold text-[19px] text-green-700">
              💰 ${hotel.total_price}
            </span>
            <span className="text-[15px] text-gray-500">
              ${hotel.price_per_night}/night
            </span>
          </div>
          {!isAiSelected && hotel.priceDifference !== undefined && hotel.priceDifference !== 0 && (
            <div className="text-[15px] text-gray-600 mt-1 text-right">
              {hotel.priceDifference > 0 ? '+' : ''}${hotel.priceDifference.toFixed(2)} vs AI
            </div>
          )}
        </div>

        {/* Booking link */}
        {(hotel as any).booking_url && (
          <div className="mt-2">
            <a
              href={(hotel as any).booking_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[13px] text-purple-600 hover:text-purple-700 font-semibold hover:underline"
            >
              🔗 View on Booking.com →
            </a>
          </div>
        )}
      </div>
    </div>
  );
};
