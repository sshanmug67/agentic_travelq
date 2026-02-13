// frontend/src/components/hotel/HotelCard.tsx
//
// Changes (v2 — Grid-friendly):
//   - Details row wraps for half-width cards
//   - Photo + address on one line, dates + price on next
//   - Compact header with name truncation
//   - Works in both single-col and 2-col grid

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Hotel } from '../../types/trip';

interface HotelCardProps {
  hotel: Hotel;
  isSelected: boolean;
  isAiRecommended: boolean;
  onSelect: () => void;
}

export const HotelCard: React.FC<HotelCardProps> = ({
  hotel,
  isSelected,
  isAiRecommended,
  onSelect,
}) => {
  const [showDetails, setShowDetails] = useState(false);
  const [showPhotos, setShowPhotos] = useState(false);
  const [currentPhotoIndex, setCurrentPhotoIndex] = useState(0);

  const rawPhotos = hotel.photos?.slice(0, 5) || [];
  const photoUrls: string[] = rawPhotos.map((p: any) => (typeof p === 'string' ? p : p?.url)).filter(Boolean);

  const renderStars = (rating: number) => {
    const full = Math.floor(rating);
    return (
      <span className="inline-flex gap-0.5">
        {[...Array(5)].map((_, i) => (
          <span key={i} className={i < full ? 'text-yellow-500' : 'text-gray-300'} style={{ fontSize: '11px' }}>★</span>
        ))}
      </span>
    );
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

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
        {/* Header: radio + name + stars ... price */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 min-w-0">
            <input
              type="radio"
              checked={isSelected}
              onChange={onSelect}
              className="w-3.5 h-3.5 text-purple-600 cursor-pointer flex-shrink-0"
            />
            <span className="font-bold text-[14px] text-gray-800 truncate">
              {hotel.name}
            </span>
            {isAiRecommended && <span className="text-[13px] flex-shrink-0" title="AI Recommended">🌟</span>}
          </div>
          <div className="text-right flex-shrink-0 ml-2">
            <span className="text-[17px] font-bold text-green-600">${hotel.total_price}</span>
          </div>
        </div>

        {/* Rating row */}
        <div className="flex items-center gap-1.5 mb-2">
          {renderStars(hotel.google_rating)}
          <span className="font-semibold text-[13px] text-gray-700">{hotel.google_rating}</span>
          <span className="text-[11px] text-gray-400">({hotel.user_ratings_total?.toLocaleString()})</span>
        </div>

        {/* Info block: photo + details stacked */}
        <div className="bg-blue-50/60 rounded p-2">
          <div className="flex items-start gap-2.5">
            {/* Photo thumbnail */}
            {photoUrls.length > 0 ? (
              <img
                src={photoUrls[0]}
                alt={hotel.name}
                className="w-12 h-12 rounded object-cover flex-shrink-0"
              />
            ) : (
              <div className="w-12 h-12 rounded bg-gray-200 flex items-center justify-center flex-shrink-0">
                <span className="text-[17px]">🏨</span>
              </div>
            )}

            {/* Address + dates */}
            <div className="flex-1 min-w-0 text-[12px] text-gray-600 space-y-0.5">
              <div className="flex items-start gap-1">
                <span className="flex-shrink-0">📍</span>
                <span className="truncate">{hotel.address}</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="flex-shrink-0">🗓️</span>
                <span>{formatDate(hotel.check_in_date)} – {formatDate(hotel.check_out_date)}</span>
                <span className="text-gray-400">· {hotel.num_nights}n</span>
              </div>
              <div className="text-[12px] font-semibold text-gray-600">
                ${hotel.price_per_night}/night
              </div>
            </div>
          </div>
        </div>

        {/* Footer: highlights + actions */}
        <div className="mt-2 flex items-center justify-between text-[11px] text-gray-500">
          <div className="flex items-center gap-1.5 flex-wrap">
            {hotel.highlights && hotel.highlights.slice(0, 2).map((h, idx) => (
              <span key={idx} className="bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded-full text-[11px]">
                ✨ {h}
              </span>
            ))}
            {(!hotel.highlights || hotel.highlights.length === 0) && (
              <span>{hotel.num_nights} nights stay</span>
            )}
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <button
              onClick={(e) => { e.stopPropagation(); setShowDetails(!showDetails); }}
              className="text-purple-600 hover:text-purple-700 font-semibold hover:underline text-[12px]"
            >
              {showDetails ? 'Hide' : 'Details'}
            </button>
            {photoUrls.length > 0 && (
              <button
                onClick={(e) => { e.stopPropagation(); setShowPhotos(true); }}
                className="text-purple-600 hover:text-purple-700 font-semibold hover:underline text-[12px]"
              >
                📷 {photoUrls.length}
              </button>
            )}
            {(hotel as any).booking_url && (
              <a
                href={(hotel as any).booking_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="text-purple-600 hover:text-purple-700 font-semibold hover:underline text-[12px]"
              >
                Book
              </a>
            )}
          </div>
        </div>

        {/* Expandable Details */}
        <motion.div
          initial={false}
          animate={{ height: showDetails ? 'auto' : 0 }}
          className="overflow-hidden"
        >
          <div className="mt-2 pt-2 border-t border-gray-200 text-[12px] space-y-1">
            <div className="flex justify-between">
              <span className="text-gray-500">Address:</span>
              <span className="font-semibold text-right max-w-[60%]">{hotel.address}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Check-in:</span>
              <span className="font-semibold">{hotel.check_in_date}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Check-out:</span>
              <span className="font-semibold">{hotel.check_out_date}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Total ({hotel.num_nights} nights):</span>
              <span className="font-semibold text-green-600">${hotel.total_price}</span>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Photo Gallery Modal */}
      <AnimatePresence>
        {showPhotos && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4"
            onClick={(e) => { e.stopPropagation(); setShowPhotos(false); }}
          >
            <div className="relative max-w-4xl w-full">
              <button
                className="absolute top-4 right-4 bg-white/90 hover:bg-white text-gray-800 rounded-full w-10 h-10 flex items-center justify-center text-xl z-10"
                onClick={(e) => { e.stopPropagation(); setShowPhotos(false); }}
              >×</button>
              <img
                src={photoUrls[currentPhotoIndex]}
                alt={hotel.name}
                className="w-full h-auto rounded-lg"
                onClick={(e) => e.stopPropagation()}
              />
              {photoUrls.length > 1 && (
                <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2">
                  {photoUrls.map((_, idx) => (
                    <button
                      key={idx}
                      onClick={(e) => { e.stopPropagation(); setCurrentPhotoIndex(idx); }}
                      className={`w-3 h-3 rounded-full transition-all ${
                        idx === currentPhotoIndex ? 'bg-white w-6' : 'bg-white/50'
                      }`}
                    />
                  ))}
                </div>
              )}
              {photoUrls.length > 1 && (
                <>
                  <button
                    onClick={(e) => { e.stopPropagation(); setCurrentPhotoIndex((p) => (p - 1 + photoUrls.length) % photoUrls.length); }}
                    className="absolute left-4 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white rounded-full w-10 h-10 flex items-center justify-center text-xl"
                  >‹</button>
                  <button
                    onClick={(e) => { e.stopPropagation(); setCurrentPhotoIndex((p) => (p + 1) % photoUrls.length); }}
                    className="absolute right-4 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white rounded-full w-10 h-10 flex items-center justify-center text-xl"
                  >›</button>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};
