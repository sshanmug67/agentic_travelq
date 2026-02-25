// frontend/src/components/recommendation/DailySchedulePanel.tsx
//
// v7.2 — Compact day pills + bolder journal font + larger timeline
//   - Day pills: single-line horizontal layout (Day N / Date left, weather right)
//   - Unselected pills: subtle theme-color tint background + colored border
//   - Journal text (Caveat) font-weight 700 for stronger presence
//   - Timeline icons: 40×40 with themed border/shadow, time labels 10px bold
//   - Wider gap (20px) between icon column and content
//   - Journal title: 22px, summary strip: 12px
//
// v7.0 — Nuggets externalized (hideNuggets prop)
// v6.2 — Streaming support
// v6.0 — Initial structured daily schedule component

import React, { useState, useEffect } from 'react';

// ─── Types ───────────────────────────────────────────────────────────────

export interface TimeSlot {
  time: string;
  venue_name: string;
  type: string;
  category: string;
  narrative: string;
  icon?: string;
  rating?: number;
  place_id?: string;
  address?: string;
  google_url?: string;
  cuisine_tag?: string;
  interest_tag?: string;
  venue_type?: string;
  photos?: Array<{ url: string }>;
}

export interface DayWeather {
  icon: string;
  temp_high: number;
  temp_low: number;
  description: string;
  precipitation_prob: number;
}

export interface DaySchedule {
  day: number;
  date: string;
  title: string;
  intro: string;
  slots: TimeSlot[];
  weather?: DayWeather;
}

export interface Nugget {
  id: string;
  title: string;
  content: string;
  color: string;
}

export interface StructuredPlan {
  daily_schedule: DaySchedule[];
  nuggets: Nugget[];
}

export interface DailyPlanRec {
  recommended_id: string;
  reason: string;
  metadata?: Record<string, any>;
}

interface Props {
  dailyPlanRec: DailyPlanRec | null;
  destination?: string;
  hideNuggets?: boolean;
}

// ─── Day color themes ────────────────────────────────────────────────────

const DAY_THEMES = [
  { color: '#8B5CF6', gradient: 'linear-gradient(135deg, #8B5CF6, #A78BFA)' },
  { color: '#EC4899', gradient: 'linear-gradient(135deg, #EC4899, #F472B6)' },
  { color: '#10B981', gradient: 'linear-gradient(135deg, #10B981, #34D399)' },
  { color: '#0EA5E9', gradient: 'linear-gradient(135deg, #0EA5E9, #38BDF8)' },
  { color: '#F59E0B', gradient: 'linear-gradient(135deg, #F59E0B, #FBBF24)' },
  { color: '#EF4444', gradient: 'linear-gradient(135deg, #EF4444, #F87171)' },
  { color: '#6366F1', gradient: 'linear-gradient(135deg, #6366F1, #818CF8)' },
];

// ─── Nugget styling config (EXPORTED) ────────────────────────────────────

export const NUGGET_STYLES: Record<string, { bg: string; border: string; titleColor: string; textColor: string }> = {
  sky:     { bg: 'bg-sky-50',     border: 'border-sky-200',     titleColor: 'text-sky-700',     textColor: 'text-sky-600' },
  purple:  { bg: 'bg-purple-50',  border: 'border-purple-200',  titleColor: 'text-purple-700',  textColor: 'text-purple-600' },
  orange:  { bg: 'bg-orange-50',  border: 'border-orange-200',  titleColor: 'text-orange-700',  textColor: 'text-orange-600' },
  green:   { bg: 'bg-green-50',   border: 'border-green-200',   titleColor: 'text-green-700',   textColor: 'text-green-600' },
  emerald: { bg: 'bg-emerald-50', border: 'border-emerald-200', titleColor: 'text-emerald-700', textColor: 'text-emerald-600' },
};

export const NUGGET_ICONS: Record<string, string> = {
  packing_tips: '🧳',
  local_events: '🎪',
  cuisine_rationale: '🍽️',
  activity_rationale: '🎭',
  seasonal_tip: '📌',
};

const TIME_SLOT_DEFAULT_ICONS: Record<string, string> = {
  morning: '🌅',
  lunch: '🍽️',
  afternoon: '🌆',
  dinner: '🍷',
};

// ─── Helpers ─────────────────────────────────────────────────────────────

function formatDayDate(dateStr: string): string {
  if (!dateStr) return '';
  try { const d = new Date(dateStr + 'T12:00:00'); return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); }
  catch { return dateStr; }
}

function formatDayDateFull(dateStr: string): string {
  if (!dateStr) return '';
  try { const d = new Date(dateStr + 'T12:00:00'); return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }); }
  catch { return dateStr; }
}

function renderBoldMarkdown(text: string): React.ReactNode {
  const parts = text.split(/\*\*(.*?)\*\*/g);
  return parts.map((part, i) => i % 2 === 1 ? <strong key={i} className="font-semibold text-gray-800">{part}</strong> : <span key={i}>{part}</span>);
}

// ─── Exported helper: extract nuggets ────────────────────────────────────

export function extractNuggets(dailyPlanRec: DailyPlanRec | null): Nugget[] {
  if (!dailyPlanRec) return [];
  if (dailyPlanRec.metadata?.format !== 'structured_v1') return [];
  let structuredPlan: StructuredPlan | null = null;
  if (dailyPlanRec.metadata?.structured_data) { structuredPlan = dailyPlanRec.metadata.structured_data as StructuredPlan; }
  else if (dailyPlanRec.reason) { try { structuredPlan = JSON.parse(dailyPlanRec.reason) as StructuredPlan; } catch { return []; } }
  return structuredPlan?.nuggets || [];
}

// ─── Legacy parser ───────────────────────────────────────────────────────

function parseLegacyBlocks(planText: string): Array<{ title: string; body: string }> {
  const blocks: Array<{ title: string; body: string }> = [];
  if (!planText) return blocks;
  const hashSections = planText.split(/(?=###\s)/);
  const hasHash = hashSections.some(s => s.trim().startsWith('###'));
  if (hasHash) {
    for (const section of hashSections) {
      const trimmed = section.trim();
      if (!trimmed) continue;
      const nl = trimmed.indexOf('\n');
      if (nl === -1) { blocks.push({ title: trimmed.replace(/^#+\s*/, ''), body: '' }); }
      else { blocks.push({ title: trimmed.slice(0, nl).replace(/^#+\s*/, '').trim(), body: trimmed.slice(nl + 1).trim() }); }
    }
  } else {
    const boldSections = planText.split(/(?=\*\*Day\s+\d)/);
    for (const section of boldSections) {
      const trimmed = section.trim();
      if (!trimmed) continue;
      const match = trimmed.match(/^\*\*(.+?)\*\*:?\s*/);
      if (match) { blocks.push({ title: match[1].trim(), body: trimmed.slice(match[0].length).trim() }); }
      else { const colon = trimmed.indexOf(':'); if (colon > 0 && colon < 80) { blocks.push({ title: trimmed.slice(0, colon).replace(/\*\*/g, ''), body: trimmed.slice(colon + 1).trim() }); } else { blocks.push({ title: 'Schedule', body: trimmed }); } }
    }
  }
  return blocks;
}

// ═════════════════════════════════════════════════════════════════════════

export const DailySchedulePanel: React.FC<Props> = ({ dailyPlanRec, destination, hideNuggets = false }) => {
  const [expandedDay, setExpandedDay] = useState(0);

  const daysComplete = dailyPlanRec?.metadata?.days_complete || 0;
  const isStreaming = dailyPlanRec?.metadata?.streaming === true;

  useEffect(() => {
    if (isStreaming && daysComplete > 0) setExpandedDay(daysComplete - 1);
  }, [daysComplete, isStreaming]);

  if (!dailyPlanRec) {
    return (
      <div className="bg-gray-50 rounded-lg border border-dashed border-gray-300 p-8 text-center">
        <span className="text-3xl mb-2 block">📅</span>
        <p className="text-sm text-gray-400 italic">Daily schedule will appear after planning...</p>
      </div>
    );
  }

  const format = dailyPlanRec.metadata?.format;
  const isStructured = format === 'structured_v1';
  let structuredPlan: StructuredPlan | null = null;
  if (isStructured) {
    if (dailyPlanRec.metadata?.structured_data) { structuredPlan = dailyPlanRec.metadata.structured_data as StructuredPlan; }
    else if (dailyPlanRec.reason) { try { structuredPlan = JSON.parse(dailyPlanRec.reason) as StructuredPlan; } catch {} }
  }

  // ═══ LEGACY ═══
  if (!structuredPlan) {
    const planText = dailyPlanRec.reason || '';
    const dayBlocks = parseLegacyBlocks(planText);
    const accents = ['border-l-purple-400', 'border-l-pink-400', 'border-l-indigo-400', 'border-l-teal-400', 'border-l-orange-400', 'border-l-rose-400'];
    return (
      <div>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-base">📅</span>
          <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Daily Schedule</h4>
          {dailyPlanRec.metadata?.num_days && <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full font-medium">{dailyPlanRec.metadata.num_days} days</span>}
        </div>
        {dayBlocks.length > 0 ? (
          <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
            {dayBlocks.map((day, idx) => (
              <div key={idx} className={`bg-gray-50 rounded-lg border border-gray-200 border-l-4 ${accents[idx % accents.length]} px-4 py-3 transition-shadow hover:shadow-sm`}>
                <p className="text-[13px] font-bold text-gray-800 mb-1">{day.title}</p>
                <p className="text-[12.5px] text-gray-600 leading-relaxed">{renderBoldMarkdown(day.body)}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-gray-50 rounded-lg border border-dashed border-gray-300 p-8 text-center">
            <span className="text-3xl mb-2 block">📅</span>
            <p className="text-sm text-gray-400 italic">Daily schedule will appear after planning...</p>
          </div>
        )}
      </div>
    );
  }

  // ═══ STRUCTURED ═══
  const { daily_schedule, nuggets } = structuredPlan;
  const daysTotal = dailyPlanRec.metadata?.days_total || daily_schedule.length;
  const currentDay = daily_schedule[expandedDay];
  const theme = currentDay ? DAY_THEMES[expandedDay % DAY_THEMES.length] : DAY_THEMES[0];
  const displayDestination = destination || dailyPlanRec.metadata?.destination || 'Your Trip';
  const showNuggetsHere = !hideNuggets && nuggets && nuggets.length > 0 && !isStreaming;

  return (
    <div>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@400;500;600;700&display=swap');
        .journal-text { font-family: 'Caveat', cursive; }
        @keyframes dsp-fadeSlideUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes dsp-pillFadeIn { from { opacity: 0; transform: scale(0.85); } to { opacity: 1; transform: scale(1); } }
        @keyframes dsp-pulseGlow { 0%, 100% { opacity: 0.6; } 50% { opacity: 1; } }
      `}</style>

      {/* Section header */}
      <div className="flex items-center gap-1.5 mb-2.5">
        <span style={{ fontSize: 15 }}>📅</span>
        <h4 className="journal-text text-[20px] font-bold text-gray-800">
          Your {displayDestination} Journal
        </h4>
        <span className="text-[10px] font-bold text-purple-700 bg-purple-100 px-2 py-0.5 rounded-full">
          {daily_schedule.length}{isStreaming ? `/${daysTotal}` : ''} days
        </span>
        {isStreaming && (
          <div className="flex items-center gap-1 ml-1">
            <div className="w-2 h-2 bg-purple-500 rounded-full" style={{ animation: 'dsp-pulseGlow 1.2s ease-in-out infinite' }} />
            <span className="text-[9px] font-semibold text-purple-500">LIVE</span>
          </div>
        )}
      </div>

      {/* ── Day pills — COMPACT SINGLE-LINE with theme tint ──── */}
      <div className="flex gap-1.5 mb-3 overflow-x-auto pb-0.5">
        {daily_schedule.map((day, i) => {
          const t = DAY_THEMES[i % DAY_THEMES.length];
          const isActive = expandedDay === i;
          return (
            <button
              key={i}
              onClick={() => setExpandedDay(i)}
              className="flex-1 min-w-[90px] rounded-xl border-none cursor-pointer transition-all duration-300"
              style={{
                padding: '7px 10px',
                background: isActive ? t.gradient : `${t.color}08`,
                border: isActive ? 'none' : `1.5px solid ${t.color}25`,
                boxShadow: isActive ? '0 3px 12px rgba(0,0,0,0.15)' : `0 1px 3px ${t.color}10`,
                transform: isActive ? 'translateY(-1px)' : 'none',
                animation: 'dsp-pillFadeIn 0.4s ease forwards',
              }}
            >
              <div className="flex items-center justify-between gap-1.5">
                <div className="flex flex-col items-start leading-tight">
                  <span style={{
                    fontSize: 8, fontWeight: 700,
                    color: isActive ? 'rgba(255,255,255,0.7)' : `${t.color}90`,
                    textTransform: 'uppercase' as const, letterSpacing: '0.5px',
                  }}>Day {day.day}</span>
                  <span style={{
                    fontSize: 11, fontWeight: 700,
                    color: isActive ? 'white' : '#1E293B',
                  }}>{formatDayDate(day.date)}</span>
                </div>
                {day.weather && (
                  <div className="flex items-center gap-1">
                    <span style={{ fontSize: 14 }}>{day.weather.icon}</span>
                    <span style={{
                      fontSize: 9, fontWeight: 600,
                      color: isActive ? 'rgba(255,255,255,0.9)' : '#64748B',
                    }}>{Math.round(day.weather.temp_high)}°F</span>
                  </div>
                )}
              </div>
            </button>
          );
        })}

        {/* Placeholder pills for streaming */}
        {isStreaming && Array.from({ length: daysTotal - daily_schedule.length }, (_, i) => {
          const dayNum = daily_schedule.length + i + 1;
          return (
            <div
              key={`placeholder-${dayNum}`}
              className="flex-1 min-w-[90px] rounded-xl flex items-center justify-center"
              style={{ padding: '7px 10px', border: '1.5px dashed #E2E8F0', background: '#FAFBFC' }}
            >
              <div className="flex items-center gap-2">
                <span style={{ fontSize: 8, fontWeight: 700, color: '#CBD5E1', textTransform: 'uppercase' as const }}>Day {dayNum}</span>
                <div className="rounded-full" style={{
                  width: 8, height: 8, backgroundColor: '#CBD5E1',
                  animation: dayNum === daily_schedule.length + 1 ? 'dsp-pulseGlow 1.2s ease-in-out infinite' : 'none',
                }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Streaming indicator */}
      {isStreaming && (
        <div className="flex items-center gap-2 mb-3 px-1">
          <div className="animate-spin w-3.5 h-3.5 border-2 border-purple-200 border-t-purple-600 rounded-full flex-shrink-0" />
          <span className="journal-text text-purple-600" style={{ fontSize: 17, fontWeight: 700 }}>
            ✏️ Planning day {Math.min(daysComplete + 1, daysTotal)} of {daysTotal}...
          </span>
        </div>
      )}

      {/* ── Expanded day card ───────────────────────────────────────── */}
      {currentDay && (
        <div
          key={expandedDay}
          className="rounded-2xl overflow-hidden bg-white"
          style={{ border: `2px solid ${theme.color}20`, animation: 'dsp-fadeSlideUp 0.35s ease forwards' }}
        >
          {/* Day header */}
          <div className="px-4 py-2.5 flex justify-between items-center" style={{ background: theme.gradient }}>
            <div>
              <div style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'rgba(255,255,255,0.7)' }}>
                Day {currentDay.day} · {formatDayDateFull(currentDay.date)}
              </div>
              <h3 className="text-[15px] font-extrabold text-white mt-0.5" style={{ fontFamily: "'Plus Jakarta Sans', 'DM Sans', sans-serif" }}>
                {currentDay.title}
              </h3>
            </div>
            {currentDay.weather && (
              <div className="flex items-center gap-1.5 rounded-lg px-2.5 py-1" style={{ background: 'rgba(255,255,255,0.2)', backdropFilter: 'blur(8px)' }}>
                <span style={{ fontSize: 16 }}>{currentDay.weather.icon}</span>
                <div>
                  <div className="text-xs font-bold text-white">{Math.round(currentDay.weather.temp_high)}°F</div>
                  <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.8)' }}>{currentDay.weather.description}</div>
                </div>
              </div>
            )}
          </div>

          {/* Journal intro — BOLDER */}
          {currentDay.intro && (
            <div className="px-4 pt-3 pb-2" style={{ borderBottom: `1px dashed ${theme.color}15` }}>
              <p className="journal-text leading-relaxed" style={{ fontSize: '18px', fontWeight: 700, color: '#3D2E1E', lineHeight: 1.45 }}>
                ✏️ {currentDay.intro}
              </p>
            </div>
          )}

          {/* Timeline slots — revamped JSX style */}
          <div className="px-5 py-3">
            {currentDay.slots.map((slot, si) => {
              const slotIcon = slot.icon || TIME_SLOT_DEFAULT_ICONS[slot.time] || '📍';
              const tagText = slot.cuisine_tag || slot.interest_tag || slot.category || '';
              return (
                <div
                  key={si}
                  className="flex gap-5 py-3.5 rounded-xl transition-colors"
                  style={{ borderBottom: si < currentDay.slots.length - 1 ? '1px solid rgba(0,0,0,0.04)' : 'none' }}
                >
                  {/* Timeline column — wider, larger icon */}
                  <div className="flex flex-col items-center flex-shrink-0" style={{ width: 52 }}>
                    <span
                      className="text-center leading-tight font-extrabold"
                      style={{
                        fontSize: 10, letterSpacing: '0.6px',
                        textTransform: 'uppercase' as const,
                        color: theme.color,
                      }}
                    >
                      {slot.time}
                    </span>
                    <div
                      className="flex items-center justify-center mt-1.5 rounded-xl"
                      style={{
                        width: 40, height: 40, fontSize: 19,
                        background: `${theme.color}12`,
                        border: `2.5px solid ${theme.color}35`,
                        boxShadow: `0 2px 8px ${theme.color}15`,
                      }}
                    >
                      {slotIcon}
                    </div>
                    {si < currentDay.slots.length - 1 && (
                      <div className="flex-1 mt-1.5 rounded" style={{ width: 2.5, minHeight: 20, background: `linear-gradient(to bottom, ${theme.color}30, transparent)` }} />
                    )}
                  </div>

                  {/* Content — more breathing room */}
                  <div className="flex-1 min-w-0 pt-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4 className="text-[14px] font-bold text-gray-800" style={{ fontFamily: "'Plus Jakarta Sans', 'DM Sans', sans-serif" }}>
                        {slot.venue_name}
                      </h4>
                      {slot.rating != null && (
                        <span className="text-[10px] font-bold text-amber-600 bg-amber-50 px-2 py-0.5 rounded-md">
                          ⭐ {typeof slot.rating === 'number' ? slot.rating.toFixed(1) : slot.rating}
                        </span>
                      )}
                      {tagText && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md" style={{ color: theme.color, background: `${theme.color}10` }}>
                          {tagText}
                        </span>
                      )}
                    </div>
                    {slot.narrative && (
                      <p className="journal-text mt-1 leading-relaxed" style={{ fontSize: '18px', fontWeight: 700, color: '#4A3728', lineHeight: 1.4 }}>
                        {slot.narrative}
                      </p>
                    )}
                    {slot.google_url && (
                      <a href={slot.google_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 mt-1.5 text-[10px] font-medium text-gray-400 hover:text-purple-500 transition-colors">
                        📍 View on Google Maps
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Day summary strip */}
          <div className="flex items-center gap-3 px-4 py-2.5 text-[12px] font-semibold text-gray-500" style={{ background: `${theme.color}06`, borderTop: `1px solid ${theme.color}12` }}>
            <span>🏛️ {currentDay.slots.filter(s => s.type === 'activity').length} Activities</span>
            <span className="w-px h-3 bg-gray-200" />
            <span>🍽️ {currentDay.slots.filter(s => s.type === 'restaurant').length} Meals</span>
            {currentDay.weather && (<><span className="w-px h-3 bg-gray-200" /><span>{currentDay.weather.icon} {Math.round(currentDay.weather.temp_high)}°F · {currentDay.weather.description}</span></>)}
          </div>
        </div>
      )}

      {/* Nuggets (only if not hidden) */}
      {showNuggetsHere && (
        <div className="grid grid-cols-2 gap-2 mt-3" style={{ animation: 'dsp-fadeSlideUp 0.4s ease forwards' }}>
          {nuggets.map((nugget, i) => {
            const style = NUGGET_STYLES[nugget.color] || NUGGET_STYLES.emerald;
            const icon = NUGGET_ICONS[nugget.id] || '💡';
            const isWide = i === nuggets.length - 1 && nuggets.length % 2 === 1;
            return (
              <div key={nugget.id} className={`${style.bg} border ${style.border} rounded-xl p-2.5 transition-all hover:-translate-y-0.5 hover:shadow-md cursor-default ${isWide ? 'col-span-2' : ''}`}>
                <div className="flex items-start gap-1.5">
                  <span className="text-sm flex-shrink-0">{icon}</span>
                  <div className="min-w-0">
                    <h5 className={`text-[10px] font-bold ${style.titleColor}`} style={{ fontFamily: "'Plus Jakarta Sans', 'DM Sans', sans-serif" }}>{nugget.title}</h5>
                    <p className={`text-[9px] ${style.textColor} leading-snug mt-0.5`}>{nugget.content}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default DailySchedulePanel;
