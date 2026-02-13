// frontend/src/components/itinerary/ItineraryHotelCard.tsx
//
// Changes (v2 — Compact):
//   - Smaller thumbnail (12x12 → w-12 h-12)
//   - Name + stars on same row as thumbnail
//   - Address, dates, price all tighter
//   - ~40% height reduction

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

  const rawPhotos = hotel.photos || [];
  const firstPhoto = rawPhotos.length > 0
    ? (typeof rawPhotos[0] === 'string' ? rawPhotos[0] : (rawPhotos[0] as any)?.url)
    : null;

  const fmtDate = (d: string) => {
    const dt = new Date(d + 'T00:00:00');
    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <div className="itinerary-card !p-3">
      {/* Row 1: Badge + Delete */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          {isAiSelected ? (
            <span className="ai-sticker !text-[11px] !px-1.5 !py-0.5">🤖 AI</span>
          ) : (
            <span className="user-badge !text-[11px] !px-1.5 !py-0.5 text-white">👤</span>
          )}
        </div>
        <button onClick={onDelete} className="paper-delete !w-5 !h-5 !text-sm" aria-label="Delete hotel">
          ×
        </button>
      </div>

      {/* Row 2: Photo + Name + Rating */}
      <div className="flex gap-2.5 handwritten-body">
        {firstPhoto ? (
          <img
            src={firstPhoto}
            alt={hotel.name}
            className="w-12 h-12 rounded-lg object-cover flex-shrink-0"
          />
        ) : (
          <div className="w-12 h-12 rounded-lg bg-gray-200 flex items-center justify-center flex-shrink-0">
            <span className="text-[20px]">🏨</span>
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="font-bold text-[15px] text-gray-800 truncate">{hotel.name}</div>
          <div className="flex items-center gap-1 text-[12px]">
            <span className="text-yellow-500">{'★'.repeat(Math.floor(hotel.google_rating))}</span>
            <span className="font-semibold text-gray-700">{hotel.google_rating}</span>
            <span className="text-gray-400">({hotel.user_ratings_total?.toLocaleString()})</span>
          </div>
        </div>
      </div>

      {/* Row 3: Address + Dates inline */}
      <div className="mt-1.5 text-[12px] text-gray-500 handwritten-body space-y-0.5">
        <div className="truncate">📍 {hotel.address}</div>
        <div>
          🗓️ {fmtDate(hotel.check_in_date)} – {fmtDate(hotel.check_out_date)} · {hotel.num_nights}n
        </div>
      </div>

      {/* Row 4: Price */}
      <div className="flex items-center justify-between mt-1.5 pt-1.5 border-t border-dashed border-gray-300">
        <span className="font-bold text-[15px] text-green-700 handwritten-body">
          💰 ${hotel.total_price}
        </span>
        <span className="text-[12px] text-gray-500 handwritten-body">
          ${hotel.price_per_night}/night
        </span>
      </div>
      {!isAiSelected && hotel.priceDifference !== undefined && hotel.priceDifference !== 0 && (
        <div className="text-[11px] text-gray-500 text-right handwritten-body">
          {hotel.priceDifference > 0 ? '+' : ''}${hotel.priceDifference.toFixed(2)} vs AI
        </div>
      )}
    </div>
  );
};
