// frontend/src/components/hotel/HotelCard.tsx

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

  // Handle photos being either string[] or {url: string}[]
  const rawPhotos = hotel.photos?.slice(0, 5) || [];
  const photoUrls: string[] = rawPhotos.map((p: any) => (typeof p === 'string' ? p : p?.url)).filter(Boolean);

  const renderStars = (rating: number) => {
    const full = Math.floor(rating);
    const half = rating - full >= 0.3;
    return (
      <span className="flex items-center gap-0.5">
        {[...Array(5)].map((_, i) => (
          <span key={i} className={i < full ? 'text-yellow-500' : (i === full && half) ? 'text-yellow-400' : 'text-gray-300'}>★</span>
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
      {/* AI Recommendation Badge — slim */}
      {isAiRecommended && !isSelected && (
        <div className="bg-gradient-to-r from-yellow-400 to-yellow-500 px-3 py-0.5 flex items-center justify-center gap-2">
          <span className="text-[15px] font-bold text-yellow-900">🤖 AI Recommended</span>
        </div>
      )}

      <div className="px-4 py-3">
        {/* Header row: radio + name + rating ... price */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <input
              type="radio"
              checked={isSelected}
              onChange={onSelect}
              className="w-4 h-4 text-purple-600 cursor-pointer"
            />
            <div className="flex items-center gap-2">
              <span className="font-bold text-[17px] text-gray-800 truncate max-w-[240px]">
                {hotel.name}
              </span>
              {isAiRecommended && <span className="text-[17px]" title="AI Recommended">🌟</span>}
              <span className="flex items-center gap-1 text-[15px]">
                {renderStars(hotel.google_rating)}
                <span className="font-semibold text-gray-700 ml-0.5">{hotel.google_rating}</span>
              </span>
              <span className="text-[15px] text-gray-400">
                ({hotel.user_ratings_total?.toLocaleString()})
              </span>
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            <span className="text-[21px] font-bold text-green-600">${hotel.total_price}</span>
            <span className="text-[15px] text-gray-400 ml-1">total</span>
          </div>
        </div>

        {/* Details row: photo thumbnail + address + dates + per-night */}
        <div className="flex items-center gap-3 py-1.5 px-2 bg-blue-50/60 rounded text-[17px]">
          {/* Small thumbnail */}
          {photoUrls.length > 0 ? (
            <img
              src={photoUrls[0]}
              alt={hotel.name}
              className="w-12 h-12 rounded object-cover flex-shrink-0"
            />
          ) : (
            <div className="w-12 h-12 rounded bg-gray-200 flex items-center justify-center flex-shrink-0">
              <span className="text-[21px]">🏨</span>
            </div>
          )}

          {/* Address */}
          <div className="flex items-center gap-1 flex-1 min-w-0">
            <span className="text-[15px] text-gray-500">📍</span>
            <span className="text-[15px] text-gray-700 truncate">{hotel.address}</span>
          </div>

          {/* Dates */}
          <div className="flex items-center gap-1 flex-shrink-0">
            <span className="text-[15px] text-gray-500">🗓️</span>
            <span className="text-[15px] text-gray-700">
              {formatDate(hotel.check_in_date)} – {formatDate(hotel.check_out_date)}
            </span>
          </div>

          {/* Per-night price */}
          <div className="flex-shrink-0 text-right">
            <span className="text-[15px] font-semibold text-gray-600">
              ${hotel.price_per_night}/night
            </span>
            <span className="text-[15px] text-gray-400 ml-1">
              • {hotel.num_nights}n
            </span>
          </div>
        </div>

        {/* Footer row: highlights + actions */}
        <div className="mt-2 flex items-center justify-between text-[15px] text-gray-500">
          <div className="flex items-center gap-2">
            {hotel.highlights && hotel.highlights.slice(0, 3).map((h, idx) => (
              <span key={idx} className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full text-[15px]">
                ✨ {h}
              </span>
            ))}
            {(!hotel.highlights || hotel.highlights.length === 0) && (
              <span className="text-[15px] text-gray-400">{hotel.num_nights} nights stay</span>
            )}
          </div>
          <div className="flex gap-3">
            <button
              onClick={(e) => { e.stopPropagation(); setShowDetails(!showDetails); }}
              className="text-purple-600 hover:text-purple-700 font-semibold hover:underline"
            >
              {showDetails ? 'Hide' : 'Details'}
            </button>
            {photoUrls.length > 0 && (
              <button
                onClick={(e) => { e.stopPropagation(); setShowPhotos(true); }}
                className="text-purple-600 hover:text-purple-700 font-semibold hover:underline"
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
                className="text-purple-600 hover:text-purple-700 font-semibold hover:underline"
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
          <div className="mt-2 pt-2 border-t border-gray-200 text-[15px] space-y-1">
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
              <span className="text-gray-500">Price per Night:</span>
              <span className="font-semibold text-green-600">${hotel.price_per_night}</span>
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
