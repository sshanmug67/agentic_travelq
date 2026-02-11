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
  const [showPhotos, setShowPhotos] = useState(false);
  const [currentPhotoIndex, setCurrentPhotoIndex] = useState(0);

  const photos = hotel.photos?.slice(0, 5) || [];

  return (
    <motion.div
      whileHover={{ scale: 1.01, y: -4 }}
      transition={{ duration: 0.2 }}
      className={`rounded-xl overflow-hidden cursor-pointer transition-all duration-300 ${
        isSelected
          ? 'ring-4 ring-purple-500 shadow-2xl bg-gradient-to-br from-purple-50 to-pink-50'
          : 'hover:shadow-xl bg-white border-2 border-gray-200'
      }`}
      onClick={onSelect}
    >
      {/* AI Recommendation Badge */}
      {isAiRecommended && !isSelected && (
        <div className="bg-gradient-to-r from-yellow-400 to-yellow-500 px-4 py-1 flex items-center justify-center gap-2">
          <span className="text-sm font-bold text-yellow-900">🤖 AI Recommended</span>
          <span className="text-xs bg-yellow-600 text-white px-2 py-0.5 rounded-full">
            Best Value
          </span>
        </div>
      )}

      <div className="flex flex-col md:flex-row">
        {/* Photo Gallery */}
        <div className="relative md:w-1/3 bg-gray-200 group">
          {photos.length > 0 ? (
            <>
              <img
                src={photos[currentPhotoIndex]?.url || photos[0]?.url}
                alt={hotel.name}
                className="w-full h-48 md:h-full object-cover"
              />
              {/* Photo Navigation Overlay */}
              <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                {photos.length > 1 && (
                  <>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setCurrentPhotoIndex((prev) => (prev - 1 + photos.length) % photos.length);
                      }}
                      className="bg-white/90 hover:bg-white text-gray-800 rounded-full w-8 h-8 flex items-center justify-center transition-all hover:scale-110"
                    >
                      ‹
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowPhotos(true);
                      }}
                      className="bg-white/90 hover:bg-white text-gray-800 px-3 py-1 rounded-full text-sm font-semibold transition-all hover:scale-110"
                    >
                      📷 View All
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setCurrentPhotoIndex((prev) => (prev + 1) % photos.length);
                      }}
                      className="bg-white/90 hover:bg-white text-gray-800 rounded-full w-8 h-8 flex items-center justify-center transition-all hover:scale-110"
                    >
                      ›
                    </button>
                  </>
                )}
              </div>
              {/* Photo Indicators */}
              {photos.length > 1 && (
                <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1">
                  {photos.map((_, idx) => (
                    <div
                      key={idx}
                      className={`w-2 h-2 rounded-full transition-all ${
                        idx === currentPhotoIndex ? 'bg-white w-4' : 'bg-white/50'
                      }`}
                    />
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="w-full h-48 md:h-full flex items-center justify-center text-gray-400">
              <span className="text-4xl">🏨</span>
            </div>
          )}
        </div>

        {/* Hotel Details */}
        <div className="flex-1 p-5">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-start gap-3 flex-1">
              <input
                type="radio"
                checked={isSelected}
                onChange={onSelect}
                className="mt-1 w-5 h-5 text-purple-600 cursor-pointer"
              />
              <div className="flex-1">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-bold text-lg text-gray-800">{hotel.name}</h3>
                      {isAiRecommended && <span className="text-xl">🌟</span>}
                    </div>
                    {/* Rating */}
                    <div className="flex items-center gap-2 mt-1">
                      <div className="flex items-center gap-1">
                        {[...Array(5)].map((_, i) => (
                          <span
                            key={i}
                            className={
                              i < Math.floor(hotel.google_rating)
                                ? 'text-yellow-500'
                                : 'text-gray-300'
                            }
                          >
                            ★
                          </span>
                        ))}
                        <span className="font-semibold text-gray-700 ml-1">
                          {hotel.google_rating}
                        </span>
                      </div>
                      <span className="text-sm text-gray-500">
                        ({hotel.user_ratings_total?.toLocaleString()} reviews)
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-green-600">
                      ${hotel.total_price}
                    </div>
                    <div className="text-sm text-gray-600">
                      ${hotel.price_per_night}/night
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {hotel.num_nights} nights
                    </div>
                  </div>
                </div>

                {/* Location */}
                <div className="mt-3 space-y-2">
                  <div className="flex items-start gap-2 text-sm">
                    <span className="text-gray-600 mt-0.5">📍</span>
                    <span className="text-gray-700">{hotel.address}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-gray-600">🗓️</span>
                    <span className="text-gray-700">
                      {hotel.check_in_date} - {hotel.check_out_date}
                    </span>
                  </div>
                </div>

                {/* Highlights */}
                {hotel.highlights && hotel.highlights.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {hotel.highlights.slice(0, 3).map((highlight, idx) => (
                      <span
                        key={idx}
                        className="bg-gradient-to-r from-blue-50 to-purple-50 text-blue-700 text-xs px-3 py-1 rounded-full border border-blue-200"
                      >
                        ✨ {highlight}
                      </span>
                    ))}
                  </div>
                )}

                {/* Actions */}
                <div className="mt-4 flex gap-3">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      // Open map
                    }}
                    className="text-sm text-purple-600 hover:text-purple-700 font-semibold hover:underline flex items-center gap-1"
                  >
                    🗺️ View on Map
                  </button>
                  {photos.length > 0 && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowPhotos(true);
                      }}
                      className="text-sm text-purple-600 hover:text-purple-700 font-semibold hover:underline flex items-center gap-1"
                    >
                      📷 Photos ({photos.length})
                    </button>
                  )}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      // Show reviews
                    }}
                    className="text-sm text-purple-600 hover:text-purple-700 font-semibold hover:underline flex items-center gap-1"
                  >
                    ⭐ Reviews
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Photo Gallery Modal */}
      <AnimatePresence>
        {showPhotos && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4"
            onClick={(e) => {
              e.stopPropagation();
              setShowPhotos(false);
            }}
          >
            <div className="relative max-w-4xl w-full">
              <button
                className="absolute top-4 right-4 bg-white/90 hover:bg-white text-gray-800 rounded-full w-10 h-10 flex items-center justify-center text-xl z-10"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowPhotos(false);
                }}
              >
                ×
              </button>
              <img
                src={photos[currentPhotoIndex]?.url}
                alt={hotel.name}
                className="w-full h-auto rounded-lg"
                onClick={(e) => e.stopPropagation()}
              />
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2">
                {photos.map((_, idx) => (
                  <button
                    key={idx}
                    onClick={(e) => {
                      e.stopPropagation();
                      setCurrentPhotoIndex(idx);
                    }}
                    className={`w-3 h-3 rounded-full transition-all ${
                      idx === currentPhotoIndex ? 'bg-white w-6' : 'bg-white/50'
                    }`}
                  />
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};