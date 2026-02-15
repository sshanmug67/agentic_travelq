// frontend/src/components/flight/FlightCard.tsx
//
// v6 — focusedItemId prop: when matched, auto-expand + scroll into view
//   - New optional `focusedItemId` prop
//   - useEffect watches for match → setIsExpanded(true) + scrollIntoView
//   - Brief highlight pulse on focus

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Flight, FlightLeg, FlightAmenity } from '../../types/trip';

interface FlightCardProps {
  flight: Flight;
  isSelected: boolean;
  isAiRecommended: boolean;
  onSelect: () => void;
  focusedItemId?: string | null;
}

export const FlightCard: React.FC<FlightCardProps> = ({
  flight,
  isSelected,
  isAiRecommended,
  onSelect,
  focusedItemId,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isFocusHighlight, setIsFocusHighlight] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  // ── Focus: auto-expand + scroll when focusedItemId matches ──────
  useEffect(() => {
    if (focusedItemId && String(flight.id) === String(focusedItemId)) {
      setIsExpanded(true);
      setIsFocusHighlight(true);
      // Small delay to let React render the tab switch first
      requestAnimationFrame(() => {
        cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
      const timer = setTimeout(() => setIsFocusHighlight(false), 1200);
      return () => clearTimeout(timer);
    }
  }, [focusedItemId, flight.id]);

  // ── Helpers ──────────────────────────────────────────────────────────

  const formatTime = (dateStr: string) =>
    new Date(dateStr).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  const stopsLabel = (stops: number) =>
    stops === 0 ? 'Direct' : `${stops} stop${stops > 1 ? 's' : ''}`;

  const stopsColor = (stops: number) =>
    stops === 0 ? 'text-green-600' : stops === 1 ? 'text-amber-600' : 'text-red-500';

  const isMixedCarrier =
    flight.return_flight?.airline_code &&
    flight.return_flight.airline_code !== flight.outbound?.airline_code;

  const seatsColor = (seats: number) =>
    seats < 3 ? 'text-red-600' : seats <= 5 ? 'text-orange-500' : 'text-gray-600';

  const seatsIcon = (seats: number) =>
    seats < 3 ? '🔥 ' : seats <= 5 ? '⚠️ ' : '';

  const toggleExpand = () => {
    setIsExpanded((prev) => !prev);
  };

  const handleAddToItinerary = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSelect();
  };

  // ── Summary Leg Row (collapsed) ─────────────────────────────────────

  const SummaryLeg: React.FC<{
    tag: string; tagColor: string; bgColor: string; leg: FlightLeg;
  }> = ({ tag, tagColor, bgColor, leg }) => (
    <div className={`${bgColor} rounded px-2.5 py-1.5`}>
      <div className="flex items-center justify-between mb-0.5">
        <span className={`text-[10px] font-bold ${tagColor} uppercase tracking-wide`}>{tag}</span>
        <span className="text-[10px] text-gray-400">{formatDate(leg.departure_time)}</span>
      </div>
      <div className="flex items-center gap-1">
        <span className="font-bold text-[13px] text-gray-800">{leg.departure_airport}</span>
        <span className="text-[10px] text-gray-400">{formatTime(leg.departure_time)}</span>
        <div className="flex-1 flex items-center gap-1 px-0.5">
          <div className="flex-1 h-px bg-gray-300" />
          <span className="text-[9px] text-gray-400 whitespace-nowrap">{leg.duration}</span>
          <div className="flex-1 h-px bg-gray-300" />
        </div>
        <span className="text-[10px] text-gray-400">{formatTime(leg.arrival_time)}</span>
        <span className="font-bold text-[13px] text-gray-800">{leg.arrival_airport}</span>
      </div>
      <div className="flex items-center gap-2 mt-0.5">
        <span className={`text-[10px] font-medium ${stopsColor(leg.stops)}`}>
          {stopsLabel(leg.stops)}
        </span>
        {isMixedCarrier && tag === 'Ret' && leg.airline_code && (
          <span className="text-[10px] text-gray-400">· {leg.airline_code} {leg.flight_number}</span>
        )}
      </div>
    </div>
  );

  // ── Expanded: Per-Segment Timeline ──────────────────────────────────

  const SegmentTimeline: React.FC<{
    tag: string; tagColor: string; tagBg: string; leg: FlightLeg;
  }> = ({ tag, tagColor, tagBg, leg }) => {
    const segments = leg.segments || [];
    const layoverDurations = leg.layover_durations || [];

    if (segments.length === 0) {
      return (
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            <span className={`text-[10px] font-bold ${tagColor} ${tagBg} uppercase tracking-wide px-1.5 py-0.5 rounded`}>
              {tag}
            </span>
            <span className="text-[12px] font-semibold text-gray-700">
              {leg.airline_code} {leg.flight_number}
            </span>
          </div>
          <div className="text-[12px] text-gray-600">
            {leg.departure_airport} → {leg.arrival_airport} · {leg.duration} · {stopsLabel(leg.stops)}
          </div>
        </div>
      );
    }

    return (
      <div className="bg-gray-50 rounded-lg p-3 space-y-0">
        <div className="flex items-center justify-between mb-2">
          <span className={`text-[10px] font-bold ${tagColor} ${tagBg} uppercase tracking-wide px-1.5 py-0.5 rounded`}>
            {tag}
          </span>
          <span className="text-[11px] text-gray-400">Total: {leg.duration}</span>
        </div>

        {segments.map((seg, idx) => (
          <React.Fragment key={seg.segment_id || idx}>
            <div className="flex gap-2.5 py-1.5">
              <div className="flex flex-col items-center w-3 pt-0.5">
                <div className="w-2 h-2 rounded-full bg-purple-500 flex-shrink-0" />
                <div className="flex-1 w-px bg-gray-300 my-0.5" />
                <div className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-1.5 mb-1">
                  <span className="font-bold text-[12px] text-gray-800">{seg.departure_airport}</span>
                  {seg.departure_terminal && (
                    <span className="text-[10px] text-gray-400">T{seg.departure_terminal}</span>
                  )}
                  <span className="text-[11px] text-gray-600">{formatTime(seg.departure_time)}</span>
                </div>
                <div className="flex items-center gap-1.5 flex-wrap mb-1 ml-0.5">
                  <span className="text-[11px] font-medium text-gray-700">
                    {seg.marketing_flight_number}
                  </span>
                  {seg.operating_carrier && seg.operating_carrier !== seg.marketing_carrier && (
                    <span className="text-[10px] text-gray-400 italic">
                      op. {seg.operating_carrier_name || seg.operating_carrier}
                    </span>
                  )}
                  <span className="text-[10px] text-gray-300">|</span>
                  <span className="text-[10px] text-gray-500">{seg.duration}</span>
                  {seg.aircraft_name && (
                    <>
                      <span className="text-[10px] text-gray-300">|</span>
                      <span className="text-[10px] text-gray-500">✈ {seg.aircraft_name}</span>
                    </>
                  )}
                  {!seg.aircraft_name && seg.aircraft_code && (
                    <>
                      <span className="text-[10px] text-gray-300">|</span>
                      <span className="text-[10px] text-gray-500">✈ {seg.aircraft_code}</span>
                    </>
                  )}
                </div>
                <div className="flex items-baseline gap-1.5">
                  <span className="font-bold text-[12px] text-gray-800">{seg.arrival_airport}</span>
                  {seg.arrival_terminal && (
                    <span className="text-[10px] text-gray-400">T{seg.arrival_terminal}</span>
                  )}
                  <span className="text-[11px] text-gray-600">{formatTime(seg.arrival_time)}</span>
                </div>
              </div>
            </div>

            {idx < segments.length - 1 && (
              <div className="flex items-center gap-2.5 py-1">
                <div className="w-3 flex justify-center">
                  <div className="w-px h-4 bg-amber-300" />
                </div>
                <div className="flex-1 flex items-center gap-1.5 bg-amber-50 rounded px-2 py-1 border border-amber-200">
                  <span className="text-[10px] font-semibold text-amber-700">
                    ⏱ {layoverDurations[idx] || '—'} layover
                  </span>
                  <span className="text-[10px] text-amber-600">
                    at {seg.arrival_airport}
                    {seg.arrival_terminal ? ` (T${seg.arrival_terminal})` : ''}
                  </span>
                </div>
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    );
  };

  // ── Amenities Grid ──────────────────────────────────────────────────

  const AmenitiesGrid: React.FC<{ amenities: FlightAmenity[] }> = ({ amenities }) => {
    if (!amenities || amenities.length === 0) return null;
    const included = amenities.filter((a) => !a.is_chargeable);
    const paid = amenities.filter((a) => a.is_chargeable);
    const formatLabel = (desc: string) =>
      desc.charAt(0) + desc.slice(1).toLowerCase().replace(/_/g, ' ');

    return (
      <div className="bg-gray-50 rounded-lg p-3">
        <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">
          What's Included
        </p>
        <div className="flex flex-wrap gap-1.5">
          {included.map((a, i) => (
            <span key={i} className="text-[10px] bg-green-50 text-green-700 border border-green-200 px-1.5 py-0.5 rounded-full">
              ✅ {formatLabel(a.description)}
            </span>
          ))}
          {paid.map((a, i) => (
            <span key={i} className="text-[10px] bg-gray-100 text-gray-500 border border-gray-200 px-1.5 py-0.5 rounded-full">
              💰 {formatLabel(a.description)}
            </span>
          ))}
        </div>
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
          <span className="text-[12px] font-bold text-amber-900 tracking-wide">✨ AI Recommended</span>
        </div>
      )}

      <div className="p-3">
        {/* HEADER */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="font-bold text-[14px] text-gray-800">
              {flight.airline} {flight.outbound?.flight_number || ''}
            </span>
            {isAiRecommended && <span className="text-[11px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full font-semibold">AI Pick</span>}
            <span className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-[10px] font-medium">
              {flight.branded_fare || flight.cabin_class}
            </span>
            {isMixedCarrier && (
              <span className="bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded text-[10px] font-medium">Mixed</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[17px] font-bold text-green-600">
              ${flight.price}
              {flight.currency && flight.currency !== 'USD' && (
                <span className="text-[10px] text-gray-400 ml-0.5 font-normal">{flight.currency}</span>
              )}
            </span>
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

        {/* SUMMARY */}
        {flight.outbound && (
          <SummaryLeg tag="Out" tagColor="text-blue-600" bgColor="bg-blue-50/60" leg={flight.outbound} />
        )}
        {flight.return_flight && (
          <div className="mt-1">
            <SummaryLeg tag="Ret" tagColor="text-purple-600" bgColor="bg-purple-50/60" leg={flight.return_flight} />
          </div>
        )}

        {/* FOOTER */}
        <div className="mt-2 flex items-center justify-between text-[11px] text-gray-500">
          <div className="flex items-center gap-2">
            {flight.cabin_bags && <span>💼 {flight.cabin_bags.quantity} cabin</span>}
            {flight.checked_bags && flight.checked_bags.quantity > 0 && (
              <span>🧳 {flight.checked_bags.quantity} checked</span>
            )}
            {flight.checked_bags && flight.checked_bags.quantity === 0 && (
              <span className="text-amber-500">🧳 No checked bag</span>
            )}
            {!flight.cabin_bags && !flight.checked_bags && (
              <span>{stopsLabel(flight.outbound?.stops ?? 0)}</span>
            )}
            {flight.seats_remaining != null && (
              <span className={`font-semibold ${seatsColor(flight.seats_remaining)}`}>
                {seatsIcon(flight.seats_remaining)}{flight.seats_remaining} seat{flight.seats_remaining !== 1 ? 's' : ''} left
              </span>
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
                {flight.outbound && (
                  <SegmentTimeline tag="Outbound" tagColor="text-blue-700" tagBg="bg-blue-100" leg={flight.outbound} />
                )}
                {flight.return_flight && (
                  <SegmentTimeline tag="Return" tagColor="text-purple-700" tagBg="bg-purple-100" leg={flight.return_flight} />
                )}
                {flight.amenities && flight.amenities.length > 0 && (
                  <AmenitiesGrid amenities={flight.amenities} />
                )}

                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12px]">
                    {flight.branded_fare && (
                      <div className="flex justify-between col-span-2">
                        <span className="text-gray-500">Fare</span>
                        <span className="font-semibold text-gray-700">{flight.branded_fare}</span>
                      </div>
                    )}
                    {flight.validating_carrier && (
                      <div className="flex justify-between col-span-2">
                        <span className="text-gray-500">Ticketed by</span>
                        <span className="font-semibold text-gray-700">{flight.validating_carrier}</span>
                      </div>
                    )}
                    {isMixedCarrier && (
                      <div className="flex justify-between col-span-2">
                        <span className="text-gray-500">Carriers</span>
                        <span className="font-semibold text-gray-700">
                          {flight.outbound?.airline_code || flight.airline_code} → {flight.return_flight?.airline_code}
                        </span>
                      </div>
                    )}
                    {flight.cabin_bags && (
                      <div className="flex justify-between col-span-2">
                        <span className="text-gray-500">💼 Cabin bag</span>
                        <span className="font-semibold text-gray-700">
                          {flight.cabin_bags.quantity} × {flight.cabin_bags.weight}{flight.cabin_bags.weight_unit}
                        </span>
                      </div>
                    )}
                    {flight.checked_bags && (
                      <div className="flex justify-between col-span-2">
                        <span className="text-gray-500">🧳 Checked bag</span>
                        <span className={`font-semibold ${flight.checked_bags.quantity === 0 ? 'text-amber-600' : 'text-gray-700'}`}>
                          {flight.checked_bags.quantity === 0
                            ? 'Not included (paid add-on)'
                            : `${flight.checked_bags.quantity} × ${flight.checked_bags.weight}${flight.checked_bags.weight_unit}`
                          }
                        </span>
                      </div>
                    )}
                    {flight.last_ticketing_date && (
                      <div className="flex justify-between col-span-2">
                        <span className="text-gray-500">Book by</span>
                        <span className="font-semibold text-amber-600">
                          {new Date(flight.last_ticketing_date + 'T00:00:00').toLocaleDateString('en-US', {
                            month: 'short', day: 'numeric', year: 'numeric'
                          })}
                        </span>
                      </div>
                    )}
                    {flight.seats_remaining != null && (
                      <div className="flex justify-between col-span-2">
                        <span className="text-gray-500">Seats left</span>
                        <span className={`font-semibold ${seatsColor(flight.seats_remaining)}`}>
                          {seatsIcon(flight.seats_remaining)}{flight.seats_remaining}
                        </span>
                      </div>
                    )}
                    {(flight.price_base != null || flight.price_taxes != null) && (
                      <>
                        <div className="col-span-2 border-t border-gray-200 mt-1 pt-1.5">
                          <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
                            Price Breakdown
                          </p>
                        </div>
                        {flight.price_base != null && (
                          <div className="flex justify-between col-span-2">
                            <span className="text-gray-500">Base fare</span>
                            <span className="font-semibold text-gray-700">${flight.price_base.toFixed(2)}</span>
                          </div>
                        )}
                        {flight.price_taxes != null && (
                          <div className="flex justify-between col-span-2">
                            <span className="text-gray-500">Taxes & fees</span>
                            <span className="font-semibold text-gray-700">${flight.price_taxes.toFixed(2)}</span>
                          </div>
                        )}
                        <div className="flex justify-between col-span-2 pt-1 border-t border-gray-200">
                          <span className="text-gray-600 font-medium">Total</span>
                          <span className="font-bold text-green-600 text-[14px]">
                            ${flight.price.toFixed(2)}
                            {flight.currency && (
                              <span className="text-[10px] text-gray-400 ml-1 font-normal">{flight.currency}</span>
                            )}
                          </span>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-gray-400">
                  <span>ID: {flight.id}</span>
                  {(flight as any).booking_url && (
                    <a
                      href={(flight as any).booking_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-purple-600 hover:text-purple-700 font-semibold hover:underline text-[12px]"
                    >
                      Book Now ↗
                    </a>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
};
