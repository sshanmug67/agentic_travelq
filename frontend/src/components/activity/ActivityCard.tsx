// frontend/src/components/activity/ActivityCard.tsx
//
// v3 — focusedItemId prop: when matched, auto-expand + scroll into view

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Activity, HotelReview } from '../../types/trip';

interface ActivityCardProps {
  activity: Activity;
  isSelected: boolean;
  isAiRecommended?: boolean;
  onToggle: () => void;
  focusedItemId?: string | null;
}

export const ActivityCard: React.FC<ActivityCardProps> = ({
  activity,
  isSelected,
  isAiRecommended = false,
  onToggle,
  focusedItemId,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isFocusHighlight, setIsFocusHighlight] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  // ── Focus: auto-expand + scroll when focusedItemId matches ──────
  useEffect(() => {
    if (focusedItemId && String(activity.id) === String(focusedItemId)) {
      setIsExpanded(true);
      setIsFocusHighlight(true);
      requestAnimationFrame(() => {
        cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
      const timer = setTimeout(() => setIsFocusHighlight(false), 1200);
      return () => clearTimeout(timer);
    }
  }, [focusedItemId, activity.id]);

  const toggleExpand = () => setIsExpanded((prev) => !prev);

  const handleAddToItinerary = (e: React.MouseEvent) => {
    e.stopPropagation();
    onToggle();
  };

  // ── Helpers ──────────────────────────────────────────────────────────

  const getCategoryIcon = (category: string) => {
    const icons: Record<string, string> = {
      museum: '🏛️', park: '🌳', landmark: '🗿', shopping: '🛍️',
      entertainment: '🎭', cultural: '🎨', historic: '🏰', religious: '⛪',
      nature: '🏞️', tourist_attraction: '📸', art_gallery: '🎨',
      performing_arts_theater: '🎭', movie_theater: '🎬', amusement_park: '🎢',
      zoo: '🦁', aquarium: '🐠', botanical_garden: '🌺', beach: '🏖️',
      hiking_area: '🥾', stadium: '🏟️',
    };
    return icons[category.toLowerCase()] || '📍';
  };

  const getVenueTypeBadge = (venueType?: string) => {
    if (!venueType || venueType === 'either') return null;
    if (venueType === 'indoor') return { label: 'Indoor', color: 'bg-blue-100 text-blue-700' };
    if (venueType === 'outdoor') return { label: 'Outdoor', color: 'bg-green-100 text-green-700' };
    return null;
  };

  const renderMiniStars = (rating: number) => (
    <span className="inline-flex gap-px">
      {[...Array(5)].map((_, i) => (
        <span key={i} className={i < Math.floor(rating) ? 'text-yellow-500' : 'text-gray-200'} style={{ fontSize: '9px' }}>★</span>
      ))}
    </span>
  );

  const ReviewSnippet: React.FC<{ review: HotelReview }> = ({ review }) => {
    const maxLen = 140;
    const text = review.text.length > maxLen
      ? review.text.slice(0, maxLen).trim() + '…'
      : review.text;
    return (
      <div className="bg-white rounded p-2 border border-gray-100">
        <div className="flex items-center gap-1.5 mb-1">
          {renderMiniStars(review.rating)}
          <span className="text-[11px] font-semibold text-gray-700">{review.author_name}</span>
          {review.relative_time_description && (
            <span className="text-[10px] text-gray-400">· {review.relative_time_description}</span>
          )}
        </div>
        <p className="text-[11px] text-gray-600 leading-relaxed">{text}</p>
      </div>
    );
  };

  const venueTypeBadge = getVenueTypeBadge(activity.venue_type);

  // ── Render ───────────────────────────────────────────────────────────

  return (
    <motion.div
      ref={cardRef}
      layout
      transition={{ duration: 0.2 }}
      className={`rounded-lg overflow-hidden cursor-pointer transition-all duration-200 ${
        isFocusHighlight
          ? 'ring-2 ring-purple-500 shadow-xl bg-purple-50/40'
          : isAiRecommended
            ? 'ring-2 ring-amber-400 shadow-lg ' + (isSelected ? 'bg-gradient-to-br from-amber-50 to-yellow-50' : 'bg-white')
            : isSelected
              ? 'ring-2 ring-blue-500 shadow-lg bg-gradient-to-br from-blue-50 to-indigo-50'
              : 'hover:shadow-md bg-white border border-gray-200'
      }`}
      onClick={toggleExpand}
    >
      {isAiRecommended && (
        <div className="bg-gradient-to-r from-amber-400 via-yellow-400 to-amber-400 px-3 py-1 flex items-center justify-center gap-1.5">
          <span className="text-[12px] font-bold text-amber-900 tracking-wide">✨ AI Recommended</span>
        </div>
      )}
      <div className="flex gap-3 p-4">
        {/* Photo */}
        <div className="w-20 h-20 rounded-lg overflow-hidden bg-gray-200 flex-shrink-0 relative">
          {activity.photos && activity.photos.length > 0 ? (
            <img src={activity.photos[0].url} alt={activity.name} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-2xl">
              {getCategoryIcon(activity.category)}
            </div>
          )}
          <div className="absolute top-1 right-1 bg-white/90 backdrop-blur-sm rounded-full px-1.5 py-0.5 text-[10px]">
            {getCategoryIcon(activity.category)}
          </div>
        </div>

        {/* Details */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1.5">
            <div className="flex items-center gap-1.5 min-w-0">
              <h3 className="font-bold text-[14px] text-gray-800 truncate">{activity.name}</h3>
              {isAiRecommended && (
                <span className="flex-shrink-0 bg-amber-100 text-amber-700 text-[11px] font-semibold px-1.5 py-0.5 rounded-full">AI Pick</span>
              )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {activity.price && (
                <span className="text-[13px] font-semibold text-green-700">
                  {activity.price === 'Free' ? '🎁 Free' : activity.price}
                </span>
              )}
              <button
                onClick={handleAddToItinerary}
                className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all duration-200 ${
                  isSelected
                    ? 'bg-orange-500 text-white shadow-sm'
                    : 'bg-orange-50 text-orange-700 border border-orange-300 hover:bg-orange-100'
                }`}
              >
                {isSelected ? '✓ Added' : '+ Add'}
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <div className="flex items-center gap-1">
              <span className="text-yellow-500 text-[12px]">⭐</span>
              <span className="font-semibold text-[13px]">{activity.rating}</span>
            </div>
            <span className="text-[11px] text-gray-400">({activity.user_ratings_total?.toLocaleString()})</span>
            {activity.interest_tag && (
              <>
                <span className="text-gray-300">·</span>
                <span className="bg-blue-100 text-blue-700 text-[10px] px-1.5 py-0.5 rounded-full font-medium capitalize">
                  {activity.interest_tag.replace('_', ' ')}
                </span>
              </>
            )}
            {!activity.interest_tag && activity.category && (
              <>
                <span className="text-gray-300">·</span>
                <span className="bg-blue-100 text-blue-700 text-[10px] px-1.5 py-0.5 rounded-full font-medium capitalize">
                  {activity.category.replace('_', ' ')}
                </span>
              </>
            )}
            {venueTypeBadge && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${venueTypeBadge.color}`}>
                {venueTypeBadge.label}
              </span>
            )}
          </div>

          <div className="flex items-center justify-between">
            <div className="text-[11px] text-gray-500 truncate">📍 {activity.address}</div>
            <span className="text-purple-500 text-[10px] flex items-center gap-0.5 flex-shrink-0 ml-2">
              {isExpanded ? 'Less' : 'Details'}
              <motion.span
                animate={{ rotate: isExpanded ? 180 : 0 }}
                transition={{ duration: 0.2 }}
                className="inline-block text-[8px]"
              >▼</motion.span>
            </span>
          </div>
        </div>
      </div>

      {/* EXPANDED */}
      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-3">
              <div className="border-t border-gray-200 pt-3"></div>

              {activity.reviews && activity.reviews.length > 0 && (
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">Visitor Reviews</p>
                  <div className="space-y-2">
                    {activity.reviews.slice(0, 3).map((review, idx) => (
                      <ReviewSnippet key={idx} review={review} />
                    ))}
                  </div>
                </div>
              )}

              {(activity.google_url || activity.website || activity.phone_number || activity.opening_hours) && (
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">Details & Contact</p>
                  <div className="space-y-1.5 text-[12px]">
                    {activity.opening_hours && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">Hours</span>
                        <span className="font-semibold text-gray-700">🕐 {activity.opening_hours}</span>
                      </div>
                    )}
                    {activity.phone_number && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">Phone</span>
                        <a href={`tel:${activity.phone_number}`} onClick={(e) => e.stopPropagation()} className="font-semibold text-purple-600 hover:underline">
                          {activity.phone_number}
                        </a>
                      </div>
                    )}
                    <div className="flex items-center gap-2 mt-1">
                      {activity.google_url && (
                        <a href={activity.google_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-[11px] bg-blue-50 text-blue-700 border border-blue-200 px-2 py-1 rounded hover:bg-blue-100 font-medium">
                          📍 Google Maps
                        </a>
                      )}
                      {activity.website && (
                        <a href={activity.website} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-[11px] bg-gray-100 text-gray-700 border border-gray-200 px-2 py-1 rounded hover:bg-gray-200 font-medium">
                          🌐 Website
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};
