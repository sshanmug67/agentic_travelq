/**
 * TripStatusBar — Animated Agent Progress Display
 * Location: frontend/src/components/common/TripStatusBar.tsx
 *
 * v6 Phase 1: Now displays granular status messages from agent_details.
 * Each agent row shows real-time messages like "Received 44 flight options"
 * instead of static descriptions.
 *
 * Pure display component — receives pollData from useTripSearch hook.
 * No internal polling or fetching.
 *
 * Behavior:
 *   EXPANDED  — During planning. Shows per-agent status with live messages.
 *   COLLAPSED — After completion. Single bar showing elapsed time. Click to re-expand.
 *   HIDDEN    — No active trip AND no previous result to show.
 */

import React, { useState, useEffect, useRef } from 'react';
import type { TripPollResponse, AgentDetail } from '../../services/api';

interface TripStatusBarProps {
  pollData: TripPollResponse | null;
  isActive: boolean;
}

// ── Agent display config ────────────────────────────────────────────
const AGENT_META: Record<string, { icon: string; label: string; fallbackDesc: string }> = {
  preprocessor: {
    icon: '🧠',
    label: 'Understanding Request',
    fallbackDesc: 'Analyzing your preferences and text input',
  },
  flight: {
    icon: '✈️',
    label: 'Searching Flights',
    fallbackDesc: 'Finding the best flights with your preferred airlines',
  },
  hotel: {
    icon: '🏨',
    label: 'Finding Hotels',
    fallbackDesc: 'Searching hotels matching your chain and location preferences',
  },
  weather: {
    icon: '🌤️',
    label: 'Checking Weather',
    fallbackDesc: 'Getting forecast for your travel dates',
  },
  places: {
    icon: '🎭',
    label: 'Discovering Activities',
    fallbackDesc: 'Finding attractions, tours, and experiences',
  },
  restaurant: {
    icon: '🍽️',
    label: 'Restaurant Picks',
    fallbackDesc: 'Curating restaurants matching your cuisine preferences',
  },
};

const AGENT_ORDER = ['preprocessor', 'flight', 'hotel', 'weather', 'places', 'restaurant'];

// ── Component ───────────────────────────────────────────────────────
const TripStatusBar: React.FC<TripStatusBarProps> = ({ pollData, isActive }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [isDismissed, setIsDismissed] = useState(false);
  const startTimeRef = useRef<number>(Date.now());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastPollDataRef = useRef<TripPollResponse | null>(null);

  // Track which agents just got a new message (for flash highlight)
  const [flashAgents, setFlashAgents] = useState<Set<string>>(new Set());
  const prevMessagesRef = useRef<Record<string, string | null>>({});

  // Keep a snapshot of the most recent pollData
  useEffect(() => {
    if (pollData) {
      lastPollDataRef.current = pollData;
    }
  }, [pollData]);

  // Detect message changes and trigger flash
  useEffect(() => {
    if (!pollData?.agent_details) return;

    const newFlashes = new Set<string>();
    for (const [agentKey, detail] of Object.entries(pollData.agent_details)) {
      const currentMsg = (detail as AgentDetail)?.status_message || null;
      const prevMsg = prevMessagesRef.current[agentKey] || null;
      if (currentMsg && currentMsg !== prevMsg) {
        newFlashes.add(agentKey);
      }
      prevMessagesRef.current[agentKey] = currentMsg;
    }

    if (newFlashes.size > 0) {
      setFlashAgents(newFlashes);
      // Clear flash after animation
      const timeout = setTimeout(() => setFlashAgents(new Set()), 600);
      return () => clearTimeout(timeout);
    }
  }, [pollData?.agent_details]);

  // Reset timer when a new trip starts
  useEffect(() => {
    if (isActive) {
      startTimeRef.current = Date.now();
      setIsExpanded(true);
      setElapsedTime(0);
      setIsDismissed(false);
      prevMessagesRef.current = {};
      setFlashAgents(new Set());

      timerRef.current = setInterval(() => {
        setElapsedTime(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isActive]);

  // Stop timer + auto-collapse on completion
  useEffect(() => {
    if (pollData?.status === 'completed' || pollData?.status === 'failed') {
      if (timerRef.current) clearInterval(timerRef.current);
      const timeout = setTimeout(() => setIsExpanded(false), 1800);
      return () => clearTimeout(timeout);
    }
  }, [pollData?.status]);

  // Use current pollData if available, otherwise fall back to last snapshot
  const displayData = pollData || lastPollDataRef.current;

  // Only truly hide if: (a) never had data, or (b) user explicitly dismissed the bar
  if (!displayData || isDismissed) return null;

  const agents = displayData.agents || {};
  const agentDetails: Record<string, AgentDetail> = displayData.agent_details || {};
  const completedCount = Object.values(agents).filter((s) => s === 'completed').length;
  const totalCount = Object.keys(agents).length || AGENT_ORDER.length;
  const progressPercent = totalCount > 0 ? (completedCount / totalCount) * 100 : 5;
  const isComplete = displayData.status === 'completed';
  const isFailed = displayData.status === 'failed';

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  };

  /**
   * Get the display message for an agent.
   * Priority: agent_details.status_message → fallback description → null
   */
  const getAgentMessage = (agentKey: string, status: string): string | null => {
    const detail: AgentDetail | undefined = agentDetails[agentKey];
    const meta = AGENT_META[agentKey];

    // If we have a granular message from the backend, always show it
    if (detail?.status_message) {
      return detail.status_message;
    }

    // Fallback: show static description only while in_progress
    if (status === 'in_progress' && meta?.fallbackDesc) {
      return meta.fallbackDesc;
    }

    return null;
  };

  return (
    <div className="w-full max-w-4xl mx-auto mt-4 mb-2">
      {/* ── PROGRESS BAR (always visible) ─────────────────────────── */}
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="relative h-12 overflow-hidden cursor-pointer shadow-lg transition-all duration-300"
        style={{
          borderRadius: isExpanded ? '12px 12px 0 0' : '12px',
          background: isComplete ? '#0d1f0d' : isFailed ? '#2e1a1a' : '#1a1a2e',
        }}
      >
        {/* Animated fill */}
        <div
          className="absolute top-0 left-0 h-full transition-all duration-700 ease-out"
          style={{
            width: `${progressPercent}%`,
            borderRadius: 'inherit',
            background: isComplete
              ? 'linear-gradient(90deg, #10b981, #34d399)'
              : isFailed
                ? 'linear-gradient(90deg, #ef4444, #f87171)'
                : 'linear-gradient(90deg, #6c5ce7 0%, #a855f7 50%, #ec4899 100%)',
          }}
        />

        {/* Bar content */}
        <div className="relative z-10 flex items-center justify-between h-full px-5">
          <div className="flex items-center gap-2.5">
            {!isComplete && !isFailed && (
              <div className="animate-spin w-4 h-4 border-2 border-white/20 border-t-white rounded-full" />
            )}
            {isComplete && <span className="text-emerald-400 font-bold text-base">✓</span>}
            {isFailed && <span className="text-red-400 font-bold text-base">✕</span>}

            <span className="text-white text-sm font-medium">
              {isComplete
                ? `Trip planned in ${formatTime(elapsedTime)}`
                : isFailed
                  ? 'Planning failed'
                  : `Planning your trip... ${completedCount}/${totalCount} agents`}
            </span>
          </div>

          <div className="flex items-center gap-3">
            {!isComplete && !isFailed && (
              <span className="text-white/50 text-xs font-mono tabular-nums">
                {formatTime(elapsedTime)}
              </span>
            )}
            {/* Dismiss button — only show when completed/failed and collapsed */}
            {(isComplete || isFailed) && !isExpanded && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setIsDismissed(true);
                }}
                className="text-white/30 hover:text-white/60 text-xs ml-1 transition-colors"
                title="Dismiss"
              >
                ✕
              </button>
            )}
            <span className="text-white/40 text-[10px]">
              {isExpanded ? '▲' : '▼'}
            </span>
          </div>
        </div>
      </div>

      {/* ── EXPANDED DETAIL CARD ──────────────────────────────────── */}
      <div
        className="bg-white shadow-lg overflow-hidden transition-all duration-400"
        style={{
          borderRadius: '0 0 12px 12px',
          maxHeight: isExpanded ? '500px' : '0px',
          opacity: isExpanded ? 1 : 0,
          padding: isExpanded ? '16px 20px' : '0px 20px',
          transition: 'max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease, padding 0.3s ease',
        }}
      >
        {AGENT_ORDER.map((agentKey) => {
          const status = agents[agentKey] || 'pending';
          const meta = AGENT_META[agentKey] || { icon: '🔧', label: agentKey, fallbackDesc: '' };
          const detail: AgentDetail | undefined = agentDetails[agentKey];
          const message = getAgentMessage(agentKey, status);
          const isFlashing = flashAgents.has(agentKey);

          return (
            <div
              key={agentKey}
              className={`flex items-center py-2.5 border-b border-gray-100 gap-3 transition-colors duration-300 ${
                isFlashing ? 'bg-purple-50/60' : ''
              }`}
            >
              <span className="text-xl w-7 text-center flex-shrink-0">{meta.icon}</span>

              <div className="flex-1 flex flex-col gap-0.5 min-w-0">
                {/* Agent label — dims when completed */}
                <div className="flex items-center gap-1.5">
                  <span className={`text-[13px] font-semibold transition-colors duration-300 ${
                    status === 'completed' ? 'text-gray-400' : 'text-gray-700'
                  }`}>
                    {meta.label}
                  </span>
                  {/* Result count badge */}
                  {detail?.result_count != null && status === 'completed' && (
                    <span className="text-[10px] font-normal text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded-full leading-none">
                      {detail.result_count}
                    </span>
                  )}
                </div>

                {/* Granular status message — the Phase 1 addition */}
                {message && (
                  <span
                    className={`text-[11px] truncate transition-all duration-300 ${
                      status === 'completed'
                        ? 'text-emerald-600/60'
                        : status === 'failed'
                          ? 'text-red-400'
                          : 'text-gray-500 italic'
                    }`}
                    title={message}
                  >
                    {message}
                  </span>
                )}
              </div>

              {/* Status indicator */}
              <span className="w-6 text-center flex-shrink-0">
                {status === 'pending' && <span className="text-sm opacity-40">⏳</span>}
                {status === 'in_progress' && (
                  <div className="animate-spin inline-block w-3.5 h-3.5 border-2 border-gray-200 border-t-purple-500 rounded-full" />
                )}
                {status === 'completed' && <span className="text-sm">✅</span>}
                {status === 'failed' && <span className="text-sm">❌</span>}
              </span>
            </div>
          );
        })}

        {/* Preference changes from preprocessor */}
        {displayData.preference_changes && displayData.preference_changes.length > 0 && (
          <div className="mt-3 p-3 bg-sky-50 rounded-lg border border-sky-200">
            <div className="text-[11px] font-semibold text-sky-700 uppercase tracking-wider mb-1.5">
              Applied from your text:
            </div>
            {displayData.preference_changes.map((change, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs text-slate-600 py-0.5">
                <span>{change.action === 'replace' ? '🔄' : change.action === 'add' ? '➕' : '➖'}</span>
                <span className="font-semibold text-sky-700">{change.field.split('.').pop()}:</span>
                <span className="text-slate-500">{change.old} → {change.new}</span>
              </div>
            ))}
          </div>
        )}

        {/* Error */}
        {isFailed && displayData.error && (
          <div className="mt-3 p-3 bg-red-50 rounded-lg border border-red-200 text-red-700 text-[13px]">
            {displayData.error}
          </div>
        )}
      </div>
    </div>
  );
};

export default TripStatusBar;
