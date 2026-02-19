// frontend/src/components/hotel/HotelCard.tsx
//
// v7 — provider_prices: "Compare Prices" section in expanded view
//       Shows all OTA prices from Xotelo with per-night rate, total, and Book links
// v6 — focusedItemId prop: when matched, auto-expand + scroll into view

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Hotel, HotelReview } from '../../types/trip';

interface HotelCardProps {
  hotel: Hotel;
  isSelected: boolean;
  isAiRecommended: boolean;
  onSelect: () => void;
  focusedItemId?: string | null;
}

export const HotelCard: React.FC<HotelCardProps> = ({
  hotel,
  isSelected,
  isAiRecommended,
  onSelect,
  focusedItemId,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showPhotos, setShowPhotos] = useState(false);
  const [currentPhotoIndex, setCurrentPhotoIndex] = useState(0);
  const [isFocusHighlight, setIsFocusHighlight] = useState(false);
  const [showAllProviders, setShowAllProviders] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  const rawPhotos = hotel.photos?.slice(0, 5) || [];
  const photoUrls: string[] = rawPhotos.map((p: any) => (typeof p === 'string' ? p : p?.url)).filter(Boolean);

  // ── Focus: auto-expand + scroll when focusedItemId matches ──────
  useEffect(() => {
    if (focusedItemId && String(hotel.id) === String(focusedItemId)) {
      setIsExpanded(true);
      setIsFocusHighlight(true);
      requestAnimationFrame(() => {
        cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
      const timer = setTimeout(() => setIsFocusHighlight(false), 1200);
      return () => clearTimeout(timer);
    }
  }, [focusedItemId, hotel.id]);

  // ── Helpers ──────────────────────────────────────────────────────────

  const toggleExpand = () => setIsExpanded((prev) => !prev);

  const handleAddToItinerary = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSelect();
  };

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

  const renderMiniStars = (rating: number) => {
    const full = Math.floor(rating);
    return (
      <span className="inline-flex gap-px">
        {[...Array(5)].map((_, i) => (
          <span key={i} className={i < full ? 'text-yellow-500' : 'text-gray-200'} style={{ fontSize: '9px' }}>★</span>
        ))}
      </span>
    );
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const priceLevelLabel = (level?: number) => {
    if (level == null) return null;
    const labels: Record<number, string> = {
      0: 'Free', 1: 'Budget', 2: 'Moderate', 3: 'Expensive', 4: 'Very Expensive'
    };
    return labels[level] || null;
  };

  /**
   * Find a booking URL for a provider by matching against hotel.booking_links.
   * Xotelo rates don't include URLs, but BookingLinkGenerator creates search
   * URLs for major OTAs. We fuzzy-match provider names (e.g. "Booking.com"
   * matches "Booking.com" key, "Expedia.com" matches "Expedia").
   */
  const findBookingUrl = (providerName: string): string | undefined => {
    if (!hotel.booking_links) return undefined;
    const pLower = providerName.toLowerCase().replace(/\.com$/, '');
    for (const [key, url] of Object.entries(hotel.booking_links)) {
      const kLower = key.toLowerCase().replace(/\.com$/, '');
      if (kLower.includes(pLower) || pLower.includes(kLower)) {
        return url;
      }
    }
    return undefined;
  };

  const ReviewSnippet: React.FC<{ review: HotelReview }> = ({ review }) => {
    const maxLen = 150;
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

  // ── Main Render ─────────────────────────────────────────────────────

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
              ? 'ring-2 ring-purple-500 shadow-lg bg-gradient-to-br from-purple-50 to-pink-50'
              : 'hover:shadow-md bg-white border border-gray-200'
      }`}
      onClick={toggleExpand}
    >
      {isAiRecommended && (
        <div className="bg-gradient-to-r from-amber-400 via-yellow-400 to-amber-400 px-3 py-1 flex items-center justify-center gap-1.5">
          <span className="text-[15px] font-bold text-amber-900 tracking-wide handwritten-subtitle">✨ AI Recommended</span>
        </div>
      )}

      <div className="p-3">
        {/* HEADER */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-bold text-[14px] text-gray-800 truncate">{hotel.name}</span>
            {isAiRecommended && <span className="text-[11px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full font-semibold flex-shrink-0">AI Pick</span>}
            {hotel.property_type && hotel.property_type !== 'Hotel' && (
              <span className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-[10px] font-medium flex-shrink-0">
                {hotel.property_type}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0 ml-2">
            <span className="text-[17px] font-bold text-green-600">${hotel.total_price}</span>
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

        {/* RATING */}
        <div className="flex items-center gap-1.5 mb-2">
          {renderStars(hotel.google_rating)}
          <span className="font-semibold text-[13px] text-gray-700">{hotel.google_rating}</span>
          <span className="text-[11px] text-gray-400">({hotel.user_ratings_total?.toLocaleString()})</span>
          {hotel.is_estimated_price === false && hotel.cheapest_provider && (
            <span className="text-[10px] bg-green-50 text-green-700 px-1.5 py-0.5 rounded-full ml-1">
              via {hotel.cheapest_provider}
            </span>
          )}
          {hotel.provider_prices && hotel.provider_prices.length > 1 && (
            <span className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded-full ml-1">
              {hotel.provider_prices.length} sites compared
            </span>
          )}
        </div>

        {/* INFO BLOCK */}
        <div className="bg-blue-50/60 rounded p-2">
          <div className="flex items-start gap-2.5">
            {photoUrls.length > 0 ? (
              <img src={photoUrls[0]} alt={hotel.name} className="w-12 h-12 rounded object-cover flex-shrink-0" />
            ) : (
              <div className="w-12 h-12 rounded bg-gray-200 flex items-center justify-center flex-shrink-0">
                <span className="text-[17px]">🏨</span>
              </div>
            )}
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
                {hotel.is_estimated_price && (
                  <span className="text-[10px] text-amber-500 font-normal ml-1">(est.)</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* FOOTER */}
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
          <span className="text-purple-500 text-[11px] flex items-center gap-1">
            {isExpanded ? 'Less' : 'Details'}
            <motion.span
              animate={{ rotate: isExpanded ? 180 : 0 }}
              transition={{ duration: 0.2 }}
              className="inline-block text-[9px]"
            >▼</motion.span>
          </span>
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
              <div className="mt-3 pt-3 border-t border-gray-200 space-y-3">
                {hotel.reviews && hotel.reviews.length > 0 && (
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">Guest Reviews</p>
                    <div className="space-y-2">
                      {hotel.reviews.slice(0, 3).map((review, idx) => (
                        <ReviewSnippet key={idx} review={review} />
                      ))}
                    </div>
                  </div>
                )}

                {(hotel.google_url || hotel.website || hotel.phone_number || hotel.property_type) && (
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">Location & Contact</p>
                    <div className="grid grid-cols-1 gap-1.5 text-[12px]">
                      {hotel.property_type && (
                        <div className="flex justify-between">
                          <span className="text-gray-500">Type</span>
                          <span className="font-semibold text-gray-700">{hotel.property_type}</span>
                        </div>
                      )}
                      {priceLevelLabel(hotel.price_level) && (
                        <div className="flex justify-between">
                          <span className="text-gray-500">Price tier</span>
                          <span className="font-semibold text-gray-700">{priceLevelLabel(hotel.price_level)}</span>
                        </div>
                      )}
                      {hotel.phone_number && (
                        <div className="flex justify-between">
                          <span className="text-gray-500">Phone</span>
                          <a href={`tel:${hotel.phone_number}`} onClick={(e) => e.stopPropagation()} className="font-semibold text-purple-600 hover:underline">
                            {hotel.phone_number}
                          </a>
                        </div>
                      )}
                      <div className="flex items-center gap-2 mt-1">
                        {hotel.google_url && (
                          <a href={hotel.google_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-[11px] bg-blue-50 text-blue-700 border border-blue-200 px-2 py-1 rounded hover:bg-blue-100 font-medium">
                            📍 Google Maps
                          </a>
                        )}
                        {hotel.website && (
                          <a href={hotel.website} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-[11px] bg-gray-100 text-gray-700 border border-gray-200 px-2 py-1 rounded hover:bg-gray-200 font-medium">
                            🌐 Website
                          </a>
                        )}
                        {photoUrls.length > 0 && (
                          <button onClick={(e) => { e.stopPropagation(); setShowPhotos(true); }} className="text-[11px] bg-gray-100 text-gray-700 border border-gray-200 px-2 py-1 rounded hover:bg-gray-200 font-medium">
                            📷 {photoUrls.length} photos
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* ── v9: PROVIDER PRICE COMPARISON (tax breakdown + expandable + URL fallback) ── */}
                {hotel.provider_prices && hotel.provider_prices.length > 1 && (
                  <div className="bg-gray-50 rounded-lg p-3">
                    <div className="flex items-baseline justify-between mb-2">
                      <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                        Compare Prices ({hotel.provider_prices.length} sites)
                      </p>
                      <span className="text-[10px] text-gray-400 italic">incl. taxes & fees</span>
                    </div>
                    <div className="space-y-1.5">
                      {(showAllProviders ? hotel.provider_prices : hotel.provider_prices.slice(0, 5)).map((pp, idx) => {
                        const bookUrl = pp.url || findBookingUrl(pp.provider);
                        return (
                          <div key={idx}>
                            <div className="flex items-center justify-between text-[12px]">
                              <span className="text-gray-600 flex items-center gap-1.5">
                                {idx === 0 && (
                                  <span className="text-[9px] bg-green-100 text-green-700 px-1 py-0.5 rounded font-semibold">
                                    BEST
                                  </span>
                                )}
                                {pp.provider}
                              </span>
                              <div className="flex items-center gap-2">
                                <span className={`font-semibold ${idx === 0 ? 'text-green-600' : 'text-gray-700'}`}>
                                  ${pp.price_per_night.toLocaleString()}<span className="text-[10px] font-normal text-gray-400">/night</span>
                                </span>
                                <span className="text-[10px] text-gray-400 w-[70px] text-right">
                                  ${pp.total_price.toLocaleString()}
                                </span>
                                {bookUrl ? (
                                  <a
                                    href={bookUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    onClick={(e) => e.stopPropagation()}
                                    className="text-[10px] bg-purple-50 text-purple-600 border border-purple-200 px-1.5 py-0.5 rounded hover:bg-purple-100 font-medium min-w-[48px] text-center"
                                  >
                                    Book ↗
                                  </a>
                                ) : (
                                  <span className="min-w-[48px]" />
                                )}
                              </div>
                            </div>
                            {pp.rate_base != null && pp.rate_tax != null && pp.rate_tax > 0 && (
                              <p className="text-[10px] text-gray-400 ml-[42px] mt-0.5">
                                base ${pp.rate_base.toLocaleString()} + ${pp.rate_tax.toLocaleString()} tax/night
                              </p>
                            )}
                          </div>
                        );
                      })}
                      {!showAllProviders && hotel.provider_prices.length > 5 && (
                        <button
                          onClick={(e) => { e.stopPropagation(); setShowAllProviders(true); }}
                          className="text-[11px] text-purple-600 hover:text-purple-800 font-medium pt-1 w-full text-center hover:underline cursor-pointer"
                        >
                          +{hotel.provider_prices.length - 5} more booking sites ▼
                        </button>
                      )}
                      {showAllProviders && hotel.provider_prices.length > 5 && (
                        <button
                          onClick={(e) => { e.stopPropagation(); setShowAllProviders(false); }}
                          className="text-[11px] text-purple-600 hover:text-purple-800 font-medium pt-1 w-full text-center hover:underline cursor-pointer"
                        >
                          Show fewer ▲
                        </button>
                      )}
                    </div>
                    <p className="text-[10px] text-gray-400 mt-2 pt-2 border-t border-gray-200">
                      💡 Most booking sites show the base rate on their search page and add taxes at checkout.
                      Our prices include taxes so you see the true total.
                    </p>
                  </div>
                )}

                {/* PRICE DETAILS */}
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">Price Details</p>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12px]">
                    <div className="flex justify-between col-span-2">
                      <span className="text-gray-500">Per night</span>
                      <span className="font-semibold text-gray-700">${hotel.price_per_night}/night</span>
                    </div>
                    <div className="flex justify-between col-span-2">
                      <span className="text-gray-500">Total ({hotel.num_nights} nights)</span>
                      <span className="font-bold text-green-600 text-[14px]">
                        ${hotel.total_price}
                        {hotel.currency && hotel.currency !== 'USD' && (
                          <span className="text-[10px] text-gray-400 ml-1 font-normal">{hotel.currency}</span>
                        )}
                      </span>
                    </div>
                    <div className="flex justify-between col-span-2">
                      <span className="text-gray-500">Price source</span>
                      {hotel.is_estimated_price ? (
                        <span className="text-[11px] bg-amber-50 text-amber-700 border border-amber-200 px-1.5 py-0.5 rounded font-medium">Estimated</span>
                      ) : (
                        <span className="text-[11px] bg-green-50 text-green-700 border border-green-200 px-1.5 py-0.5 rounded font-medium">
                          ✓ Real price{hotel.cheapest_provider ? ` via ${hotel.cheapest_provider}` : ''}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {hotel.booking_links && Object.keys(hotel.booking_links).length > 0 && (
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">Book on</p>
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(hotel.booking_links).map(([provider, url]) => (
                        <a key={provider} href={url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-[11px] bg-purple-50 text-purple-700 border border-purple-200 px-2 py-1 rounded-full hover:bg-purple-100 font-medium transition-colors">
                          {provider} ↗
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between text-[11px] text-gray-400">
                  <span>ID: {hotel.id?.slice(0, 20)}{hotel.id?.length > 20 ? '…' : ''}</span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* PHOTO GALLERY MODAL */}
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
              <button className="absolute top-4 right-4 bg-white/90 hover:bg-white text-gray-800 rounded-full w-10 h-10 flex items-center justify-center text-xl z-10" onClick={(e) => { e.stopPropagation(); setShowPhotos(false); }}>×</button>
              <img src={photoUrls[currentPhotoIndex]} alt={hotel.name} className="w-full h-auto rounded-lg" onClick={(e) => e.stopPropagation()} />
              {photoUrls.length > 1 && (
                <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2">
                  {photoUrls.map((_, idx) => (
                    <button key={idx} onClick={(e) => { e.stopPropagation(); setCurrentPhotoIndex(idx); }} className={`w-3 h-3 rounded-full transition-all ${idx === currentPhotoIndex ? 'bg-white w-6' : 'bg-white/50'}`} />
                  ))}
                </div>
              )}
              {photoUrls.length > 1 && (
                <>
                  <button onClick={(e) => { e.stopPropagation(); setCurrentPhotoIndex((p) => (p - 1 + photoUrls.length) % photoUrls.length); }} className="absolute left-4 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white rounded-full w-10 h-10 flex items-center justify-center text-xl">‹</button>
                  <button onClick={(e) => { e.stopPropagation(); setCurrentPhotoIndex((p) => (p + 1) % photoUrls.length); }} className="absolute right-4 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white rounded-full w-10 h-10 flex items-center justify-center text-xl">›</button>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};
