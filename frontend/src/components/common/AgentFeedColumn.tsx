/**
 * AgentFeedColumn — Live Streaming Agent Activity Feed
 * Location: frontend/src/components/common/AgentFeedColumn.tsx
 *
 * v3 Refinements:
 *   - Toggle buttons now have 2px orange border to stand out
 *
 * v2 Refinements:
 *   - Font sizes increased ~3-4px to match NL Input column readability
 *   - Agent labels include "Agent" suffix (e.g., "Flight Agent")
 *   - View toggle: Timeline (chronological) vs By Agent (grouped)
 */

import React, { useState, useEffect, useRef } from 'react';
import type { TripPollResponse, AgentDetail } from '../../services/api';

// ── Agent display config ────────────────────────────────────────────
const AGENTS: Record<string, { icon: string; label: string; color: string; bg: string }> = {
  preprocessor: { icon: '🧠', label: 'Analyzer Agent',    color: '#8B5CF6', bg: '#F5F3FF' },
  flight:       { icon: '✈️', label: 'Flight Agent',      color: '#EF4444', bg: '#FEF2F2' },
  hotel:        { icon: '🏨', label: 'Hotel Agent',       color: '#3B82F6', bg: '#EFF6FF' },
  weather:      { icon: '🌤️', label: 'Weather Agent',     color: '#F59E0B', bg: '#FFFBEB' },
  places:       { icon: '🎭', label: 'Activities Agent',  color: '#10B981', bg: '#ECFDF5' },
  restaurant:   { icon: '🍽️', label: 'Restaurant Agent',  color: '#EC4899', bg: '#FDF2F8' },
};

const AGENT_ORDER = ['preprocessor', 'flight', 'hotel', 'weather', 'places', 'restaurant'];

type ViewMode = 'timeline' | 'byAgent';

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
  resetKey?: number;
}

const AgentFeedColumn: React.FC<AgentFeedColumnProps> = ({ pollData, isActive, resetKey }) => {
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('timeline');
  const feedRef = useRef<HTMLDivElement>(null);
  const prevStatesRef = useRef<Record<string, string>>({});
  const prevMessagesRef = useRef<Record<string, string | null>>({});
  const prevTripIdRef = useRef<string | null>(null);

  // Reset feed whenever Dashboard signals a new planning request
  useEffect(() => {
    if (resetKey === undefined || resetKey === 0) return;
    setFeed([]);
    prevStatesRef.current = {};
    prevMessagesRef.current = {};
    prevTripIdRef.current = null;
    setViewMode('timeline');
  }, [resetKey]);

  // Accumulate feed items from pollData changes
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

      if (status === 'in_progress' && prevStatus !== 'in_progress') {
        newItems.push({ id: `${key}-start-${now.getTime()}`, timestamp: now, agentKey: key, message: 'Started', type: 'start' });
      }

      if (currentMsg && currentMsg !== prevMsg) {
        const isDoneMsg = status === 'completed' && prevStatus !== 'completed';
        if (!isDoneMsg) {
          newItems.push({ id: `${key}-${now.getTime()}-${Math.random().toString(36).slice(2, 6)}`, timestamp: now, agentKey: key, message: currentMsg, type: 'update' });
        }
      }

      if (status === 'completed' && prevStatus !== 'completed') {
        newItems.push({ id: `${key}-done-${now.getTime()}`, timestamp: now, agentKey: key, message: currentMsg || 'Complete', type: 'done' });
      }

      if (status === 'failed' && prevStatus !== 'failed') {
        newItems.push({ id: `${key}-error-${now.getTime()}`, timestamp: now, agentKey: key, message: detail?.error_message || 'Failed', type: 'error' });
      }

      prevStatesRef.current[key] = status || '';
      prevMessagesRef.current[key] = currentMsg;
    }

    if (newItems.length > 0) {
      setFeed((prev) => [...prev, ...newItems]);
    }
  }, [pollData]);

  // Auto-scroll (timeline mode)
  useEffect(() => {
    if (feedRef.current && viewMode === 'timeline') {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [feed, viewMode]);

  const agents = pollData?.agents || {};
  const isComplete = pollData?.status === 'completed';
  const completedCount = Object.values(agents).filter((s) => s === 'completed').length;

  const formatTime = (date: Date) =>
    date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

  const feedByAgent: Record<string, FeedItem[]> = {};
  for (const key of AGENT_ORDER) {
    feedByAgent[key] = feed.filter((item) => item.agentKey === key);
  }

  // ── Render a single feed item ─────────────────────────────────
  const renderFeedItem = (item: FeedItem, isLatest: boolean, showAgentLabel: boolean) => {
    const agent = AGENTS[item.agentKey] || { icon: '🔧', label: item.agentKey, color: '#6B7280', bg: '#F9FAFB' };

    return (
      <div
        key={item.id}
        className={`flex items-start gap-2 py-1.5 px-2 rounded-md transition-colors duration-500 ${
          isLatest && isActive ? 'bg-purple-50/60' : ''
        }`}
      >
        <span className="text-[12px] text-gray-400 font-mono tabular-nums flex-shrink-0 mt-0.5 w-[56px]">
          {formatTime(item.timestamp)}
        </span>

        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0 mt-1" style={{ background: agent.color }} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            {showAgentLabel && (
              <span className="handwritten text-[16px] font-semibold flex-shrink-0" style={{ color: agent.color }}>
                {agent.label}
              </span>
            )}
            {item.type === 'start' && (
              <span className="text-[9px] font-bold bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full uppercase tracking-wider">Start</span>
            )}
            {item.type === 'done' && (
              <span className="text-[9px] font-bold bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full uppercase tracking-wider">Done</span>
            )}
            {item.type === 'error' && (
              <span className="text-[9px] font-bold bg-red-100 text-red-700 px-1.5 py-0.5 rounded-full uppercase tracking-wider">Error</span>
            )}
          </div>

          {!(item.type === 'start' && item.message === 'Started') && (
            <p className={`text-[14px] leading-snug mt-0.5 ${
              item.type === 'done' ? 'text-emerald-700' : item.type === 'error' ? 'text-red-600' : 'text-gray-600'
            }`}>
              {item.message}
            </p>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="bg-white rounded-xl shadow-lg border-2 border-gray-300 overflow-hidden flex flex-col h-full">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="px-4 py-2.5 border-b-2 border-gray-200 flex items-center justify-between flex-shrink-0 bg-gradient-to-r from-gray-50 to-white">
        <div className="flex items-center gap-2">
          <span className="text-base">📡</span>
          <span className="text-[15px] font-bold text-gray-800">Agent Feed</span>
          {isActive && !isComplete && (
            <span
              className="w-2 h-2 rounded-full bg-red-500"
              style={{ animation: 'agentPulse 1.2s ease-in-out infinite', boxShadow: '0 0 6px rgba(239,68,68,0.5)' }}
            />
          )}
          {isComplete && <span className="text-xs text-emerald-600 font-semibold">✓ Done</span>}
        </div>

        <div className="flex items-center gap-2">
          {/* v3: Toggle with orange border */}
          {feed.length > 0 && (
            <div
              className="flex items-center rounded-full p-0.5"
              style={{ border: '1px solid #F97316', background: '#FFF7ED' }}
            >
              <button
                onClick={() => setViewMode('timeline')}
                className="text-[10px] font-semibold px-2.5 py-1 rounded-full transition-all duration-200"
                style={{
                  background: viewMode === 'timeline' ? 'white' : 'transparent',
                  color: viewMode === 'timeline' ? '#C2410C' : '#6B7280',
                  boxShadow: viewMode === 'timeline' ? '0 0 0 1.5px #F97316, 0 1px 3px rgba(249,115,22,0.25)' : 'none',
                }}
                title="Chronological timeline"
              >
                🕐 Timeline
              </button>
              <button
                onClick={() => setViewMode('byAgent')}
                className="text-[10px] font-semibold px-2.5 py-1 rounded-full transition-all duration-200"
                style={{
                  background: viewMode === 'byAgent' ? 'white' : 'transparent',
                  color: viewMode === 'byAgent' ? '#C2410C' : '#6B7280',
                  boxShadow: viewMode === 'byAgent' ? '0 0 0 1.5px #F97316, 0 1px 3px rgba(249,115,22,0.25)' : 'none',
                }}
                title="Grouped by agent"
              >
                🤖 By Agent
              </button>
            </div>
          )}

          <span className="text-[11px] text-gray-400 font-mono tabular-nums">
            {feed.length > 0 ? `${feed.length} events` : ''}
          </span>
        </div>
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
                className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[10px] font-semibold transition-all duration-300 cursor-default"
                style={{
                  background: isDone ? `${agent.color}15` : isFailed ? '#FEE2E2' : isRunning ? agent.bg : '#F8FAFC',
                  color: isDone ? agent.color : isFailed ? '#DC2626' : isRunning ? agent.color : '#94A3B8',
                  border: `1px solid ${isRunning ? agent.color + '40' : 'transparent'}`,
                  boxShadow: isRunning ? `0 0 8px ${agent.color}25` : 'none',
                }}
                title={agent.label}
              >
                <span className="text-xs">{agent.icon}</span>
                {isDone && <span>✓</span>}
                {isFailed && <span>✕</span>}
                {isRunning && (
                  <span
                    className="inline-block w-1.5 h-1.5 rounded-full"
                    style={{ background: agent.color, animation: 'agentPulse 1s ease-in-out infinite' }}
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
        className="flex-1 overflow-y-auto px-3 py-2"
        style={{ scrollbarWidth: 'thin', scrollbarColor: '#CBD5E1 transparent' }}
      >
        {feed.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-300">
            <span className="text-3xl mb-2">📡</span>
            <p className="text-sm font-medium">Waiting to start...</p>
            <p className="text-[12px] mt-1">Agent activity will stream here</p>
          </div>
        ) : viewMode === 'timeline' ? (
          <div className="space-y-0.5">
            {feed.map((item, idx) => renderFeedItem(item, idx === feed.length - 1, true))}
          </div>
        ) : (
          <div className="space-y-3">
            {AGENT_ORDER.map((key) => {
              const agent = AGENTS[key];
              const items = feedByAgent[key];
              if (!items || items.length === 0) return null;

              const status = agents[key];
              const isDone = status === 'completed';
              const isFailed = status === 'failed';
              const isRunning = status === 'in_progress';

              return (
                <div key={key} className="rounded-lg border overflow-hidden" style={{ borderColor: `${agent.color}30` }}>
                  <div className="flex items-center justify-between px-3 py-2" style={{ background: agent.bg }}>
                    <div className="flex items-center gap-2">
                      <span className="text-sm">{agent.icon}</span>
                      <span className="handwritten text-[16px] font-semibold" style={{ color: agent.color }}>{agent.label}</span>
                      {isDone && <span className="text-[9px] font-bold bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full uppercase">Done</span>}
                      {isFailed && <span className="text-[9px] font-bold bg-red-100 text-red-700 px-1.5 py-0.5 rounded-full uppercase">Error</span>}
                      {isRunning && (
                        <span className="inline-block w-2 h-2 rounded-full" style={{ background: agent.color, animation: 'agentPulse 1s ease-in-out infinite' }} />
                      )}
                    </div>
                    <span className="text-[10px] text-gray-400 font-mono">{items.length} event{items.length !== 1 ? 's' : ''}</span>
                  </div>
                  <div className="px-2 py-1 bg-white space-y-0.5">
                    {items.map((item, idx) => renderFeedItem(item, idx === items.length - 1, false))}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {isComplete && feed.length > 0 && (
          <div className="mt-2 mb-1 py-2 px-3 rounded-lg bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 text-center">
            <span className="text-[13px] font-semibold text-emerald-700">
              ✓ All {completedCount} agents finished — {feed.length} events
            </span>
          </div>
        )}
      </div>

      <style>{`
        @keyframes agentPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
};

export default AgentFeedColumn;
