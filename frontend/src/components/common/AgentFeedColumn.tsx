/**
 * AgentFeedColumn — Live Streaming Agent Activity Feed
 * Location: frontend/src/components/common/AgentFeedColumn.tsx
 *
 * Right column of the three-column planning layout.
 * Accumulates a chronological feed from pollData snapshots — each time
 * an agent's status_message changes, a new feed item is appended.
 *
 * Features:
 *   - Color-coded by agent (matches TravelQ agent palette)
 *   - Auto-scrolls to latest entry
 *   - Agent status pills at top for at-a-glance progress
 *   - START / DONE badges on lifecycle events
 *   - Resets automatically when a new trip starts
 */

import React, { useState, useEffect, useRef } from 'react';
import type { TripPollResponse, AgentDetail } from '../../services/api';

// ── Agent display config ────────────────────────────────────────────
const AGENTS: Record<string, { icon: string; label: string; color: string; bg: string }> = {
  preprocessor: { icon: '🧠', label: 'Analyzer',    color: '#8B5CF6', bg: '#F5F3FF' },
  flight:       { icon: '✈️', label: 'Flight',      color: '#EF4444', bg: '#FEF2F2' },
  hotel:        { icon: '🏨', label: 'Hotel',       color: '#3B82F6', bg: '#EFF6FF' },
  weather:      { icon: '🌤️', label: 'Weather',     color: '#F59E0B', bg: '#FFFBEB' },
  places:       { icon: '🎭', label: 'Activities',  color: '#10B981', bg: '#ECFDF5' },
  restaurant:   { icon: '🍽️', label: 'Restaurant',  color: '#EC4899', bg: '#FDF2F8' },
};

const AGENT_ORDER = ['preprocessor', 'flight', 'hotel', 'weather', 'places', 'restaurant'];

// ── Types ───────────────────────────────────────────────────────────
interface FeedItem {
  id: string;
  timestamp: Date;
  agentKey: string;
  message: string;
  type: 'start' | 'update' | 'done' | 'error';
}

interface AgentFeedColumnProps {
  pollData: TripPollResponse | null;
  isActive: boolean;
}

// ── Component ───────────────────────────────────────────────────────
const AgentFeedColumn: React.FC<AgentFeedColumnProps> = ({ pollData, isActive }) => {
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const feedRef = useRef<HTMLDivElement>(null);
  const prevStatesRef = useRef<Record<string, string>>({});
  const prevMessagesRef = useRef<Record<string, string | null>>({});
  const prevTripIdRef = useRef<string | null>(null);

  // ── Reset feed on new trip ──────────────────────────────────────
  useEffect(() => {
    const tripId = pollData?.trip_id || null;
    if (tripId && tripId !== prevTripIdRef.current) {
      setFeed([]);
      prevStatesRef.current = {};
      prevMessagesRef.current = {};
      prevTripIdRef.current = tripId;
    }
  }, [pollData?.trip_id]);

  // ── Accumulate feed items from pollData changes ─────────────────
  useEffect(() => {
    if (!pollData) return;

    const agents = pollData.agents || {};
    const details: Record<string, AgentDetail> = pollData.agent_details || {};
    const newItems: FeedItem[] = [];
    const now = new Date();

    for (const key of AGENT_ORDER) {
      const status = agents[key];
      const detail = details[key];
      const prevStatus = prevStatesRef.current[key];
      const prevMsg = prevMessagesRef.current[key];
      const currentMsg = detail?.status_message || null;

      // Agent started
      if (status === 'in_progress' && prevStatus !== 'in_progress') {
        newItems.push({
          id: `${key}-start-${now.getTime()}`,
          timestamp: now,
          agentKey: key,
          message: 'Started',
          type: 'start',
        });
      }

      // Status message changed (the granular v7 updates)
      if (currentMsg && currentMsg !== prevMsg) {
        // Skip if this would duplicate a start/done message
        const isDoneMsg = status === 'completed' && prevStatus !== 'completed';
        if (!isDoneMsg) {
          newItems.push({
            id: `${key}-${now.getTime()}-${Math.random().toString(36).slice(2, 6)}`,
            timestamp: now,
            agentKey: key,
            message: currentMsg,
            type: 'update',
          });
        }
      }

      // Agent completed
      if (status === 'completed' && prevStatus !== 'completed') {
        newItems.push({
          id: `${key}-done-${now.getTime()}`,
          timestamp: now,
          agentKey: key,
          message: currentMsg || 'Complete',
          type: 'done',
        });
      }

      // Agent failed
      if (status === 'failed' && prevStatus !== 'failed') {
        newItems.push({
          id: `${key}-error-${now.getTime()}`,
          timestamp: now,
          agentKey: key,
          message: detail?.error_message || 'Failed',
          type: 'error',
        });
      }

      // Update tracking refs
      prevStatesRef.current[key] = status || '';
      prevMessagesRef.current[key] = currentMsg;
    }

    if (newItems.length > 0) {
      setFeed((prev) => [...prev, ...newItems]);
    }
  }, [pollData]);

  // ── Auto-scroll to bottom ──────────────────────────────────────
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [feed]);

  // ── Derived state ─────────────────────────────────────────────
  const agents = pollData?.agents || {};
  const isComplete = pollData?.status === 'completed';
  const completedCount = Object.values(agents).filter((s) => s === 'completed').length;

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden flex flex-col h-full">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="px-4 py-2.5 border-b border-gray-100 flex items-center justify-between flex-shrink-0 bg-gradient-to-r from-gray-50 to-white">
        <div className="flex items-center gap-2">
          <span className="text-base">📡</span>
          <span className="text-sm font-bold text-gray-800">Agent Feed</span>
          {isActive && !isComplete && (
            <span
              className="w-2 h-2 rounded-full bg-red-500"
              style={{
                animation: 'pulse 1.2s ease-in-out infinite',
                boxShadow: '0 0 6px rgba(239,68,68,0.5)',
              }}
            />
          )}
          {isComplete && <span className="text-xs text-emerald-600 font-semibold">✓ Done</span>}
        </div>
        <span className="text-[10px] text-gray-400 font-mono tabular-nums">
          {feed.length > 0 ? `${feed.length} events` : ''}
        </span>
      </div>

      {/* ── Agent Status Pills ──────────────────────────────────── */}
      {(isActive || feed.length > 0) && (
        <div className="px-3 py-2 border-b border-gray-100 flex flex-wrap gap-1.5 flex-shrink-0">
          {AGENT_ORDER.map((key) => {
            const agent = AGENTS[key];
            const status = agents[key];
            const isRunning = status === 'in_progress';
            const isDone = status === 'completed';
            const isFailed = status === 'failed';

            return (
              <div
                key={key}
                className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[10px] font-semibold transition-all duration-300"
                style={{
                  background: isDone ? `${agent.color}15` : isFailed ? '#FEE2E2' : isRunning ? agent.bg : '#F8FAFC',
                  color: isDone ? agent.color : isFailed ? '#DC2626' : isRunning ? agent.color : '#94A3B8',
                  border: `1px solid ${isRunning ? agent.color + '40' : 'transparent'}`,
                  boxShadow: isRunning ? `0 0 8px ${agent.color}25` : 'none',
                }}
              >
                <span className="text-xs">{agent.icon}</span>
                {isDone && <span>✓</span>}
                {isFailed && <span>✕</span>}
                {isRunning && (
                  <span
                    className="inline-block w-1.5 h-1.5 rounded-full"
                    style={{
                      background: agent.color,
                      animation: 'pulse 1s ease-in-out infinite',
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Feed Items (scrollable) ─────────────────────────────── */}
      <div
        ref={feedRef}
        className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5"
        style={{ scrollbarWidth: 'thin', scrollbarColor: '#CBD5E1 transparent' }}
      >
        {feed.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-300">
            <span className="text-3xl mb-2">📡</span>
            <p className="text-xs font-medium">Waiting to start...</p>
            <p className="text-[10px] mt-1">Agent activity will stream here</p>
          </div>
        ) : (
          feed.map((item, idx) => {
            const agent = AGENTS[item.agentKey] || { icon: '🔧', label: item.agentKey, color: '#6B7280', bg: '#F9FAFB' };
            const isLatest = idx === feed.length - 1 && isActive;

            return (
              <div
                key={item.id}
                className={`flex items-start gap-2 py-1.5 px-2 rounded-md transition-colors duration-500 ${
                  isLatest ? 'bg-purple-50/60' : ''
                }`}
              >
                {/* Timestamp */}
                <span className="text-[9px] text-gray-400 font-mono tabular-nums flex-shrink-0 mt-0.5 w-[52px]">
                  {formatTime(item.timestamp)}
                </span>

                {/* Color dot */}
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0 mt-1"
                  style={{ background: agent.color }}
                />

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span
                      className="text-[10px] font-bold flex-shrink-0"
                      style={{ color: agent.color }}
                    >
                      {agent.label}
                    </span>

                    {/* Badges */}
                    {item.type === 'start' && (
                      <span className="text-[8px] font-bold bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full uppercase tracking-wider">
                        Start
                      </span>
                    )}
                    {item.type === 'done' && (
                      <span className="text-[8px] font-bold bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full uppercase tracking-wider">
                        Done
                      </span>
                    )}
                    {item.type === 'error' && (
                      <span className="text-[8px] font-bold bg-red-100 text-red-700 px-1.5 py-0.5 rounded-full uppercase tracking-wider">
                        Error
                      </span>
                    )}
                  </div>

                  {/* Message (skip for bare "Started" messages) */}
                  {!(item.type === 'start' && item.message === 'Started') && (
                    <p className={`text-[11px] leading-snug mt-0.5 ${
                      item.type === 'done'
                        ? 'text-emerald-700'
                        : item.type === 'error'
                          ? 'text-red-600'
                          : 'text-gray-600'
                    }`}>
                      {item.message}
                    </p>
                  )}
                </div>
              </div>
            );
          })
        )}

        {/* Completion banner */}
        {isComplete && feed.length > 0 && (
          <div className="mt-2 mb-1 py-2 px-3 rounded-lg bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 text-center">
            <span className="text-xs font-semibold text-emerald-700">
              ✓ All {completedCount} agents finished — {feed.length} events
            </span>
          </div>
        )}
      </div>

      {/* ── Keyframe for pulse animation ────────────────────────── */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
};

export default AgentFeedColumn;
