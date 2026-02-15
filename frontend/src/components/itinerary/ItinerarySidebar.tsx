// frontend/src/components/itinerary/ItinerarySidebar.tsx
//
// v4 — Clickable items: sends (tab, itemId) so the left panel
//       switches tab AND expands the specific card.
//   - Section headers send tab only → switches tab
//   - Clicking a specific card sends tab + itemId → switches + focuses
//   - "Add more" buttons also trigger section switch
//   - Hover highlights on clickable items

import React from 'react';
import { ItineraryFlightCard } from './ItineraryFlightCard';
import { ItineraryHotelCard } from './ItineraryHotelCard';
import { ItineraryRestaurantCard } from './ItineraryRestaurantCard';
import { ItineraryActivityCard } from './ItineraryActivityCard';
import { useItinerary } from '../../hooks/useItinerary';
import '../../styles/itinerary.css';

type ResultsTab = 'flights' | 'hotels' | 'restaurants' | 'activities';

interface ItinerarySidebarProps {
  onSectionClick?: (tab: ResultsTab, itemId?: string) => void;
}

export const ItinerarySidebar: React.FC<ItinerarySidebarProps> = ({ onSectionClick }) => {
  const { flight, hotel, restaurants, activities, removeItem, budget } = useItinerary();

  const handleSectionClick = (tab: ResultsTab) => {
    onSectionClick?.(tab);
  };

  const handleItemClick = (tab: ResultsTab, itemId: string) => {
    onSectionClick?.(tab, itemId);
  };

  const clickable = !!onSectionClick;

  return (
    <div className="itinerary-paper h-full overflow-y-auto sticky top-0">

      {/* ── "Your Itinerary" Header ────────────────────── */}
      <div className="px-4 pt-3 pb-1">
        <h2 className="handwritten-subtitle text-[22px] mb-0.5 sketch-underline">
          🧭 Your Itinerary
        </h2>
        <p className="handwritten text-[11px] text-gray-500 ml-8 mb-1">
          {[flight && '✈️', hotel && '🏨', restaurants.length > 0 && `🍽️×${restaurants.length}`, activities.length > 0 && `🎭×${activities.length}`].filter(Boolean).join('  ') || 'Start adding items to your trip'}
        </p>
      </div>

      <div className="pt-2 px-4 pb-4">

        {/* ── Flight ─────────────────────────────────── */}
        <div className="mb-3">
          <h3
            className={`handwritten-subtitle text-lg mb-1.5 sketch-underline${clickable ? ' cursor-pointer hover:text-purple-700 transition-colors' : ''}`}
            onClick={() => handleSectionClick('flights')}
          >
            ✈️ Flight
          </h3>
          {flight ? (
            <div
              className={clickable ? 'cursor-pointer rounded-lg transition-all hover:ring-2 hover:ring-purple-200' : ''}
              onClick={() => flight.id && handleItemClick('flights', String(flight.id))}
            >
              <ItineraryFlightCard flight={flight} onDelete={() => removeItem('flight')} />
            </div>
          ) : (
            <div
              className={`empty-doodle !py-3 !text-[13px]${clickable ? ' cursor-pointer hover:border-purple-300' : ''}`}
              onClick={() => handleSectionClick('flights')}
            >
              <div className="text-base mb-1">✈️</div>
              <div>No flight selected</div>
            </div>
          )}
        </div>

        {/* ── Hotel ──────────────────────────────────── */}
        <div className="mb-3">
          <h3
            className={`handwritten-subtitle text-lg mb-1.5 sketch-underline${clickable ? ' cursor-pointer hover:text-purple-700 transition-colors' : ''}`}
            onClick={() => handleSectionClick('hotels')}
          >
            🏨 Hotel
          </h3>
          {hotel ? (
            <div
              className={clickable ? 'cursor-pointer rounded-lg transition-all hover:ring-2 hover:ring-purple-200' : ''}
              onClick={() => hotel.id && handleItemClick('hotels', String(hotel.id))}
            >
              <ItineraryHotelCard hotel={hotel} onDelete={() => removeItem('hotel')} />
            </div>
          ) : (
            <div
              className={`empty-doodle !py-3 !text-[13px]${clickable ? ' cursor-pointer hover:border-purple-300' : ''}`}
              onClick={() => handleSectionClick('hotels')}
            >
              <div className="text-base mb-1">🏨</div>
              <div>No hotel selected</div>
            </div>
          )}
        </div>

        {/* ── Restaurants — 2-col grid ───────────────── */}
        <div className="mb-6">
          <h3
            className={`handwritten-subtitle text-lg mb-1 sketch-underline${clickable ? ' cursor-pointer hover:text-purple-700 transition-colors' : ''}`}
            onClick={() => handleSectionClick('restaurants')}
          >
            🍽️ Restaurants {restaurants.length > 0 && (
              <span className="text-[13px] text-gray-500 ml-1">({restaurants.length})</span>
            )}
          </h3>
          {restaurants.length > 0 ? (
            <>
              <div className="grid grid-cols-2 gap-4">
                {restaurants.map((restaurant) => (
                  <div
                    key={restaurant.id}
                    className={clickable ? 'cursor-pointer rounded-lg transition-all hover:ring-2 hover:ring-purple-200' : ''}
                    onClick={() => handleItemClick('restaurants', String(restaurant.id))}
                  >
                    <ItineraryRestaurantCard
                      restaurant={restaurant}
                      onDelete={() => removeItem('restaurant', restaurant.id)}
                    />
                  </div>
                ))}
              </div>
              {restaurants.length < 10 && (
                <button
                  className="w-full mt-1.5 text-[12px] text-purple-600 hover:text-purple-700 handwritten"
                  onClick={() => handleSectionClick('restaurants')}
                >
                  + Add more
                </button>
              )}
            </>
          ) : (
            <div
              className={`empty-doodle !py-3 !text-[13px]${clickable ? ' cursor-pointer hover:border-purple-300' : ''}`}
              onClick={() => handleSectionClick('restaurants')}
            >
              <div className="text-base mb-1">🍽️</div>
              <div>Add restaurants to your trip</div>
            </div>
          )}
        </div>

        {/* ── Activities — 2-col grid ────────────────── */}
        <div className="mb-6">
          <h3
            className={`handwritten-subtitle text-lg mb-1 sketch-underline${clickable ? ' cursor-pointer hover:text-purple-700 transition-colors' : ''}`}
            onClick={() => handleSectionClick('activities')}
          >
            🎭 Activities {activities.length > 0 && (
              <span className="text-[13px] text-gray-500 ml-1">({activities.length})</span>
            )}
          </h3>
          {activities.length > 0 ? (
            <>
              <div className="grid grid-cols-2 gap-4">
                {activities.map((activity) => (
                  <div
                    key={activity.id}
                    className={clickable ? 'cursor-pointer rounded-lg transition-all hover:ring-2 hover:ring-purple-200' : ''}
                    onClick={() => handleItemClick('activities', String(activity.id))}
                  >
                    <ItineraryActivityCard
                      activity={activity}
                      onDelete={() => removeItem('activity', activity.id)}
                    />
                  </div>
                ))}
              </div>
              {activities.length < 10 && (
                <button
                  className="w-full mt-1.5 text-[12px] text-purple-600 hover:text-purple-700 handwritten"
                  onClick={() => handleSectionClick('activities')}
                >
                  + Add more
                </button>
              )}
            </>
          ) : (
            <div
              className={`empty-doodle !py-3 !text-[13px]${clickable ? ' cursor-pointer hover:border-purple-300' : ''}`}
              onClick={() => handleSectionClick('activities')}
            >
              <div className="text-base mb-1">🎭</div>
              <div>Add activities to your trip</div>
            </div>
          )}
        </div>

        {/* ── Budget Summary ─────────────────────────── */}
        <div className="budget-receipt !p-3">
          <div className="handwritten-subtitle text-base mb-2 text-center">
            💰 Budget Summary
          </div>
          <div className="space-y-1 text-[13px]">
            {flight && (
              <div className="flex justify-between handwritten-body">
                <span>Flight:</span>
                <span className="font-mono">${flight.price}</span>
              </div>
            )}
            {hotel && (
              <div className="flex justify-between handwritten-body">
                <span>Hotel:</span>
                <span className="font-mono">${hotel.total_price}</span>
              </div>
            )}
            {restaurants.length > 0 && (
              <div className="flex justify-between handwritten-body">
                <span>Restaurants:</span>
                <span className="font-mono">
                  ${restaurants.reduce((sum, r) => sum + (r.estimatedCost || 0), 0)}
                </span>
              </div>
            )}
            {activities.length > 0 && (
              <div className="flex justify-between handwritten-body">
                <span>Activities:</span>
                <span className="font-mono">
                  ${activities.reduce((sum, a) => sum + (a.estimatedCost || 0), 0)}
                </span>
              </div>
            )}
            <div className="border-t-2 border-dashed border-gray-400 my-1.5"></div>
            <div className="flex justify-between handwritten-body font-semibold text-[14px]">
              <span>Total:</span>
              <span className="font-mono">${budget.selected}</span>
            </div>
            <div className="flex justify-between handwritten-body text-gray-600">
              <span>Budget:</span>
              <span className="font-mono">${budget.total}</span>
            </div>
            <div className="flex justify-between handwritten-body font-semibold text-green-700">
              <span>Remaining:</span>
              <span className="font-mono">${budget.remaining}</span>
            </div>
          </div>

          <div className="mt-2">
            <div className="h-2.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-green-400 to-green-600 transition-all duration-500"
                style={{ width: `${Math.min((budget.selected / budget.total) * 100, 100)}%` }}
              ></div>
            </div>
            <div className="text-[11px] text-center mt-0.5 handwritten text-gray-500">
              {((budget.selected / budget.total) * 100).toFixed(0)}% used
            </div>
          </div>
        </div>

        <div className="mt-4 space-y-2">
          <button className="sticky-button w-full !py-2 !text-[13px]">📧 Email Itinerary</button>
          <button className="sticky-button w-full !py-2 !text-[13px]">💾 Save Trip</button>
          <button className="sticky-button w-full !py-2 !text-[13px]">📤 Share with Friends</button>
        </div>

        <div className="mt-4 text-center opacity-30">
          <div className="handwritten text-xl">✈️ 🌍 🗺️ 📸 ⭐</div>
        </div>
      </div>
    </div>
  );
};
