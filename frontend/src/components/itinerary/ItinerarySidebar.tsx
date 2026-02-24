// frontend/src/components/itinerary/ItinerarySidebar.tsx
//
// v5 — Revamped modern design matching the TravelQ v3 mockup:
//   - Clean white card with gradient border
//   - Vertical gradient timeline line connecting sections
//   - Colored circle icons (amber=flight, blue=hotel, red=restaurants, green=activities)
//   - Compact flight/hotel cards with colored backgrounds
//   - Restaurant/activity mini-cards in 2-col grid with emoji + name + rating
//   - Modern budget summary with purple gradient background
//   - No more paper/handwritten styling

import React from 'react';
import { useItinerary } from '../../hooks/useItinerary';

type ResultsTab = 'flights' | 'hotels' | 'restaurants' | 'activities';

interface ItinerarySidebarProps {
  onSectionClick?: (tab: ResultsTab, itemId?: string) => void;
}

// ─── Category emoji lookup ───────────────────────────────────────────────
const RESTAURANT_EMOJIS: Record<string, string> = {
  italian: '🍝', japanese: '🍣', chinese: '🥡', indian: '🍛', thai: '🍜',
  mexican: '🌮', french: '🥐', korean: '🍱', american: '🍔', british: '🫖',
  mediterranean: '🫒', seafood: '🦞', pizza: '🍕', sushi: '🍣', steakhouse: '🥩',
  cafe: '☕', bakery: '🥖', default: '🍽️',
};

const ACTIVITY_EMOJIS: Record<string, string> = {
  museum: '🏛️', museums: '🏛️', park: '🌳', tour: '🚶', walking: '🚶',
  shopping: '🛍️', landmark: '🏰', entertainment: '🎭', nightlife: '🌙',
  sport: '⚽', beach: '🏖️', art: '🎨', history: '📜', nature: '🌿',
  explore: '🧭', market: '🏪', garden: '🌺', default: '🎯',
};

function getRestaurantEmoji(restaurant: any): string {
  const cats = [restaurant.cuisine_type, restaurant.category, restaurant.type, ...(restaurant.types || [])].filter(Boolean).map(s => s.toLowerCase());
  for (const cat of cats) { for (const [key, emoji] of Object.entries(RESTAURANT_EMOJIS)) { if (cat.includes(key)) return emoji; } }
  return RESTAURANT_EMOJIS.default;
}

function getActivityEmoji(activity: any): string {
  const cats = [activity.category, activity.type, activity.interest_type, ...(activity.types || [])].filter(Boolean).map(s => s.toLowerCase());
  for (const cat of cats) { for (const [key, emoji] of Object.entries(ACTIVITY_EMOJIS)) { if (cat.includes(key)) return emoji; } }
  return ACTIVITY_EMOJIS.default;
}

// ─── Photo extraction helper ─────────────────────────────────────────────
function getPhoto(item: any): string | null {
  if (item.photo_url) return item.photo_url;
  const photos = item.photos || [];
  if (photos.length === 0) return null;
  const first = photos[0];
  return typeof first === 'string' ? first : first?.url || null;
}

// ─── Shared styles ───────────────────────────────────────────────────────
const FONT = "'Plus Jakarta Sans', 'DM Sans', sans-serif";

export const ItinerarySidebar: React.FC<ItinerarySidebarProps> = ({ onSectionClick }) => {
  const { flight, hotel, restaurants, activities, removeItem, budget } = useItinerary();
  const clickable = !!onSectionClick;

  const handleSectionClick = (tab: ResultsTab) => onSectionClick?.(tab);
  const handleItemClick = (tab: ResultsTab, itemId: string) => onSectionClick?.(tab, itemId);

  const fmtDate = (d: string) => { try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); } catch { return d; } };
  const fmtTime = (d: string) => { try { return new Date(d).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }); } catch { return ''; } };

  return (
    <div
      className="h-full overflow-y-auto sticky top-0"
      style={{
        borderRadius: 24,
        padding: 22,
        background: 'rgba(255,255,255,0.85)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(139,92,246,0.1)',
        boxShadow: '0 8px 32px rgba(139,92,246,0.08)',
      }}
    >
      {/* ── Header ──────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
        <span style={{
          width: 36, height: 36, borderRadius: 12,
          background: 'linear-gradient(135deg, #8B5CF6, #EC4899)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 17, flexShrink: 0,
        }}>📋</span>
        <h3 style={{ fontFamily: FONT, fontSize: 17, fontWeight: 800, color: '#1E293B', margin: 0 }}>
          Your Itinerary
        </h3>
      </div>

      {/* ── Timeline container ──────────────────────── */}
      <div style={{ position: 'relative' }}>
        {/* Vertical gradient line */}
        <div style={{
          position: 'absolute', left: 17, top: 20, bottom: 20, width: 2,
          background: 'linear-gradient(to bottom, #C4B5FD, #FBCFE8, #FDE68A, #A7F3D0)',
          borderRadius: 2,
        }} />

        {/* ══ FLIGHT ══════════════════════════════════ */}
        <div
          style={{ display: 'flex', gap: 12, marginBottom: 16, position: 'relative' }}
          className={clickable ? 'cursor-pointer' : ''}
          onClick={() => flight ? handleItemClick('flights', String(flight.id)) : handleSectionClick('flights')}
        >
          <div style={{
            width: 34, height: 34, borderRadius: 11, flexShrink: 0,
            background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 15, zIndex: 1,
            boxShadow: '0 4px 12px rgba(245,158,11,0.3)',
          }}>✈️</div>

          {flight ? (
            <div
              style={{
                flex: 1, borderRadius: 14, padding: 13,
                background: 'linear-gradient(135deg, #FFFBEB, #FEF3C7)',
                border: '1.5px solid #FDE68A',
                transition: 'box-shadow 0.2s, transform 0.2s',
              }}
              className="hover:shadow-lg hover:-translate-y-0.5"
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontFamily: FONT, fontSize: 13, fontWeight: 700, color: '#92400E' }}>
                  {flight.airline_code} {flight.outbound?.flight_number || ''}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {flight.selectedBy === 'ai' && (
                    <span style={{ fontSize: 9, fontWeight: 700, color: '#B45309', background: '#FDE68A', padding: '2px 6px', borderRadius: 5 }}>AI PICK</span>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); removeItem('flight'); }}
                    style={{
                      width: 20, height: 20, borderRadius: '50%', border: 'none',
                      background: '#FCA5A5', color: 'white', fontSize: 13,
                      cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                      lineHeight: 1,
                    }}
                  >×</button>
                </div>
              </div>
              {flight.outbound && (
                <p style={{ fontSize: 11, color: '#92400E', margin: '3px 0 0', opacity: 0.8 }}>
                  {flight.outbound.departure_airport} → {flight.outbound.arrival_airport} · {fmtDate(flight.outbound.departure_time)} · {fmtTime(flight.outbound.departure_time)}
                  {flight.outbound.stops > 0 && ` · ${flight.outbound.stops} stop`}
                </p>
              )}
              {flight.return_flight && (
                <p style={{ fontSize: 11, color: '#92400E', margin: '2px 0 0', opacity: 0.7 }}>
                  {flight.return_flight.departure_airport} → {flight.return_flight.arrival_airport} · {fmtDate(flight.return_flight.departure_time)} · {fmtTime(flight.return_flight.departure_time)}
                  {flight.return_flight.stops > 0 && ` · ${flight.return_flight.stops} stop`}
                </p>
              )}
              <div style={{ fontFamily: FONT, fontSize: 16, fontWeight: 800, color: '#92400E', marginTop: 5 }}>
                ${flight.price}
              </div>
            </div>
          ) : (
            <div
              style={{
                flex: 1, borderRadius: 14, padding: 14,
                background: '#FAFAFA', border: '1.5px dashed #E2E8F0',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
              className={clickable ? 'hover:border-amber-300 hover:bg-amber-50/30' : ''}
            >
              <span style={{ fontSize: 12, color: '#94A3B8' }}>No flight selected</span>
            </div>
          )}
        </div>

        {/* ══ HOTEL ═══════════════════════════════════ */}
        <div
          style={{ display: 'flex', gap: 12, marginBottom: 16, position: 'relative' }}
          className={clickable ? 'cursor-pointer' : ''}
          onClick={() => hotel ? handleItemClick('hotels', String(hotel.id)) : handleSectionClick('hotels')}
        >
          <div style={{
            width: 34, height: 34, borderRadius: 11, flexShrink: 0,
            background: 'linear-gradient(135deg, #3B82F6, #60A5FA)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 15, zIndex: 1,
            boxShadow: '0 4px 12px rgba(59,130,246,0.3)',
          }}>🏨</div>

          {hotel ? (
            <div
              style={{
                flex: 1, borderRadius: 14, padding: 13,
                background: 'linear-gradient(135deg, #EFF6FF, #DBEAFE)',
                border: '1.5px solid #BFDBFE',
                transition: 'box-shadow 0.2s, transform 0.2s',
              }}
              className="hover:shadow-lg hover:-translate-y-0.5"
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <span style={{ fontFamily: FONT, fontSize: 13, fontWeight: 700, color: '#1E40AF' }}>
                  {hotel.name}
                </span>
                <button
                  onClick={(e) => { e.stopPropagation(); removeItem('hotel'); }}
                  style={{
                    width: 20, height: 20, borderRadius: '50%', border: 'none',
                    background: '#FCA5A5', color: 'white', fontSize: 13,
                    cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    lineHeight: 1, flexShrink: 0, marginLeft: 6,
                  }}
                >×</button>
              </div>
              <p style={{ fontSize: 11, color: '#1E40AF', margin: '3px 0 0', opacity: 0.8 }}>
                {(hotel as any).chain && `${(hotel as any).chain} · `}⭐ {hotel.google_rating} · {hotel.num_nights} night{hotel.num_nights !== 1 ? 's' : ''}
              </p>
              <div style={{ fontFamily: FONT, fontSize: 16, fontWeight: 800, color: '#1E40AF', marginTop: 5, display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span>${hotel.total_price}</span>
                <span style={{ fontSize: 11, fontWeight: 500, color: '#3B82F6' }}>${hotel.price_per_night}/night</span>
              </div>
            </div>
          ) : (
            <div
              style={{
                flex: 1, borderRadius: 14, padding: 14,
                background: '#FAFAFA', border: '1.5px dashed #E2E8F0',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
              className={clickable ? 'hover:border-blue-300 hover:bg-blue-50/30' : ''}
            >
              <span style={{ fontSize: 12, color: '#94A3B8' }}>No hotel selected</span>
            </div>
          )}
        </div>

        {/* ══ RESTAURANTS ═════════════════════════════ */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, position: 'relative' }}>
          <div style={{
            width: 34, height: 34, borderRadius: 11, flexShrink: 0,
            background: 'linear-gradient(135deg, #EF4444, #F87171)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 15, zIndex: 1,
            boxShadow: '0 4px 12px rgba(239,68,68,0.3)',
          }}>🍽️</div>

          <div style={{ flex: 1 }}>
            <span
              style={{ fontFamily: FONT, fontSize: 13, fontWeight: 700, color: '#991B1B', marginBottom: 6, display: 'block' }}
              className={clickable ? 'cursor-pointer hover:text-red-700' : ''}
              onClick={() => handleSectionClick('restaurants')}
            >
              Restaurants {restaurants.length > 0 && <span style={{ color: '#94A3B8', fontWeight: 500 }}>({restaurants.length})</span>}
            </span>

            {restaurants.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                {restaurants.map((r) => {
                  const photo = getPhoto(r);
                  return (
                  <div
                    key={r.id}
                    className={`hover:shadow-md hover:-translate-y-0.5 transition-all group relative ${clickable ? 'cursor-pointer' : ''}`}
                    style={{ borderRadius: 11, padding: 8, background: 'white', border: '1.5px solid #FEE2E2', display: 'flex', alignItems: 'center', gap: 8 }}
                    onClick={() => handleItemClick('restaurants', String(r.id))}
                  >
                    {/* Delete button */}
                    <button
                      onClick={(e) => { e.stopPropagation(); removeItem('restaurant', r.id); }}
                      className="absolute top-1 right-1 w-4 h-4 rounded-full bg-red-400 text-white text-[10px] items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10 hidden group-hover:flex"
                      style={{ right: photo ? 4 : 4, top: 4 }}
                    >×</button>
                    {/* Info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 20, marginBottom: 1 }}>{getRestaurantEmoji(r)}</div>
                      <div style={{ fontSize: 10.5, fontWeight: 700, color: '#1E293B', lineHeight: 1.2 }} className="truncate">{r.name}</div>
                      <div style={{ fontSize: 9.5, color: '#94A3B8' }}>⭐ {r.rating || (r as any).google_rating}</div>
                    </div>
                    {/* Photo thumbnail */}
                    {photo ? (
                      <img src={photo} alt="" style={{ width: 40, height: 40, borderRadius: 10, objectFit: 'cover', flexShrink: 0 }} />
                    ) : (
                      <div style={{ width: 40, height: 40, borderRadius: 10, background: 'linear-gradient(135deg, #FEE2E2, #FECACA)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, flexShrink: 0 }}>
                        {getRestaurantEmoji(r)}
                      </div>
                    )}
                  </div>
                  );
                })}
              </div>
            ) : (
              <div
                style={{ borderRadius: 11, padding: 12, background: '#FAFAFA', border: '1.5px dashed #E2E8F0', textAlign: 'center' }}
                className={clickable ? 'cursor-pointer hover:border-red-300 hover:bg-red-50/30' : ''}
                onClick={() => handleSectionClick('restaurants')}
              >
                <span style={{ fontSize: 12, color: '#94A3B8' }}>Add restaurants to your trip</span>
              </div>
            )}
            {restaurants.length > 0 && restaurants.length < 10 && (
              <button
                className="w-full mt-1.5 text-[11px] text-red-500 hover:text-red-700 font-medium transition-colors"
                onClick={() => handleSectionClick('restaurants')}
              >+ Add more</button>
            )}
          </div>
        </div>

        {/* ══ ACTIVITIES ══════════════════════════════ */}
        <div style={{ display: 'flex', gap: 12, position: 'relative' }}>
          <div style={{
            width: 34, height: 34, borderRadius: 11, flexShrink: 0,
            background: 'linear-gradient(135deg, #10B981, #34D399)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 15, zIndex: 1,
            boxShadow: '0 4px 12px rgba(16,185,129,0.3)',
          }}>🎭</div>

          <div style={{ flex: 1 }}>
            <span
              style={{ fontFamily: FONT, fontSize: 13, fontWeight: 700, color: '#065F46', marginBottom: 6, display: 'block' }}
              className={clickable ? 'cursor-pointer hover:text-emerald-700' : ''}
              onClick={() => handleSectionClick('activities')}
            >
              Activities {activities.length > 0 && <span style={{ color: '#94A3B8', fontWeight: 500 }}>({activities.length})</span>}
            </span>

            {activities.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                {activities.map((a) => {
                  const photo = getPhoto(a);
                  return (
                  <div
                    key={a.id}
                    className={`hover:shadow-md hover:-translate-y-0.5 transition-all group relative ${clickable ? 'cursor-pointer' : ''}`}
                    style={{ borderRadius: 11, padding: 8, background: 'white', border: '1.5px solid #D1FAE5', display: 'flex', alignItems: 'center', gap: 8 }}
                    onClick={() => handleItemClick('activities', String(a.id))}
                  >
                    {/* Delete button */}
                    <button
                      onClick={(e) => { e.stopPropagation(); removeItem('activity', a.id); }}
                      className="absolute top-1 right-1 w-4 h-4 rounded-full bg-red-400 text-white text-[10px] items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10 hidden group-hover:flex"
                      style={{ right: photo ? 4 : 4, top: 4 }}
                    >×</button>
                    {/* Info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 20, marginBottom: 1 }}>{getActivityEmoji(a)}</div>
                      <div style={{ fontSize: 10.5, fontWeight: 700, color: '#1E293B', lineHeight: 1.2 }} className="truncate">{a.name}</div>
                      <div style={{ fontSize: 9.5, color: '#94A3B8' }}>⭐ {a.rating || (a as any).google_rating}</div>
                    </div>
                    {/* Photo thumbnail */}
                    {photo ? (
                      <img src={photo} alt="" style={{ width: 40, height: 40, borderRadius: 10, objectFit: 'cover', flexShrink: 0 }} />
                    ) : (
                      <div style={{ width: 40, height: 40, borderRadius: 10, background: 'linear-gradient(135deg, #D1FAE5, #A7F3D0)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, flexShrink: 0 }}>
                        {getActivityEmoji(a)}
                      </div>
                    )}
                  </div>
                  );
                })}
              </div>
            ) : (
              <div
                style={{ borderRadius: 11, padding: 12, background: '#FAFAFA', border: '1.5px dashed #E2E8F0', textAlign: 'center' }}
                className={clickable ? 'cursor-pointer hover:border-emerald-300 hover:bg-emerald-50/30' : ''}
                onClick={() => handleSectionClick('activities')}
              >
                <span style={{ fontSize: 12, color: '#94A3B8' }}>Add activities to your trip</span>
              </div>
            )}
            {activities.length > 0 && activities.length < 10 && (
              <button
                className="w-full mt-1.5 text-[11px] text-emerald-500 hover:text-emerald-700 font-medium transition-colors"
                onClick={() => handleSectionClick('activities')}
              >+ Add more</button>
            )}
          </div>
        </div>
      </div>

      {/* ── Budget Summary ─────────────────────────── */}
      <div style={{
        marginTop: 20, padding: 16, borderRadius: 16,
        background: 'linear-gradient(135deg, #F5F3FF, #FDF4FF)',
        border: '1.5px dashed #C4B5FD',
      }}>
        <h4 style={{ fontFamily: FONT, fontSize: 13, fontWeight: 800, color: '#5B21B6', margin: '0 0 10px' }}>
          💰 Budget Summary
        </h4>
        {[
          flight && { label: 'Flight', amount: `$${flight.price}`, color: '#F59E0B' },
          hotel && { label: 'Hotel', amount: `$${hotel.total_price}`, color: '#3B82F6' },
          restaurants.length > 0 && { label: 'Restaurants', amount: `$${restaurants.reduce((s, r) => s + (r.estimatedCost || 0), 0)}`, color: '#EF4444' },
          activities.length > 0 && { label: 'Activities', amount: `$${activities.reduce((s, a) => s + (a.estimatedCost || 0), 0)}`, color: '#10B981' },
        ].filter(Boolean).map((b: any, i) => (
          <div key={i} style={{
            display: 'flex', justifyContent: 'space-between', padding: '5px 0',
            borderTop: i > 0 ? '1px solid rgba(139,92,246,0.1)' : 'none',
          }}>
            <span style={{ fontSize: 12, color: '#64748B' }}>{b.label}</span>
            <span style={{ fontFamily: FONT, fontSize: 13, fontWeight: 700, color: b.color }}>{b.amount}</span>
          </div>
        ))}

        {/* Total + Remaining */}
        <div style={{ borderTop: '1.5px solid rgba(139,92,246,0.15)', marginTop: 4, paddingTop: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
            <span style={{ fontSize: 12, color: '#64748B' }}>Total Spent</span>
            <span style={{ fontFamily: FONT, fontSize: 14, fontWeight: 800, color: '#7C3AED' }}>${budget.selected}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
            <span style={{ fontSize: 12, color: '#64748B' }}>Remaining</span>
            <span style={{ fontFamily: FONT, fontSize: 15, fontWeight: 800, color: '#059669' }}>${budget.remaining}</span>
          </div>
        </div>

        {/* Progress bar */}
        <div style={{ marginTop: 8 }}>
          <div style={{ height: 6, background: '#E9D5FF', borderRadius: 100, overflow: 'hidden' }}>
            <div
              style={{
                height: '100%', borderRadius: 100,
                background: 'linear-gradient(90deg, #8B5CF6, #EC4899)',
                width: `${Math.min((budget.selected / budget.total) * 100, 100)}%`,
                transition: 'width 0.5s ease',
              }}
            />
          </div>
          <div style={{ fontSize: 10, textAlign: 'center', marginTop: 3, color: '#94A3B8' }}>
            {((budget.selected / budget.total) * 100).toFixed(0)}% of ${budget.total} budget
          </div>
        </div>
      </div>

      {/* ── Action buttons ─────────────────────────── */}
      <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {['📧 Email Itinerary', '💾 Save Trip', '📤 Share with Friends'].map((label, i) => (
          <button
            key={i}
            style={{
              width: '100%', padding: '10px 0', borderRadius: 12, border: '1.5px solid #E2E8F0',
              background: 'white', fontFamily: FONT, fontSize: 12, fontWeight: 600,
              color: '#64748B', cursor: 'pointer', transition: 'all 0.2s',
            }}
            className="hover:border-purple-300 hover:text-purple-600 hover:shadow-sm"
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
};
