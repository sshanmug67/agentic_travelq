// frontend/src/components/common/AgentFeedColumn.tsx
//
// v4 — Glass card matching TravelQ v3 mockup:
//   - Glass card: rgba(255,255,255,0.85) + blur(20px), rounded-20
//   - ProgressRing SVG top-right
//   - Agent status icons in tinted row with green checkmarks
//   - Timeline with colored dots, connecting lines, DONE badges
//   - "All X agents finished" summary at bottom
//   - View toggle: Timeline vs By Agent preserved

import React, { useState, useEffect, useRef } from 'react';
import type { TripPollResponse, AgentDetail } from '../../services/api';

const AGENTS: Record<string, { icon: string; label: string; color: string }> = {
  preprocessor: { icon: '🧠', label: 'Analyzer',   color: '#8B5CF6' },
  flight:       { icon: '✈️', label: 'Flight',     color: '#F59E0B' },
  hotel:        { icon: '🏨', label: 'Hotel',      color: '#3B82F6' },
  weather:      { icon: '🌤️', label: 'Weather',    color: '#0EA5E9' },
  places:       { icon: '🎭', label: 'Activities',  color: '#10B981' },
  restaurant:   { icon: '🍽️', label: 'Restaurant', color: '#EF4444' },
};
const AGENT_ORDER = ['preprocessor', 'flight', 'hotel', 'weather', 'places', 'restaurant'];

type ViewMode = 'timeline' | 'byAgent';

interface FeedItem {
  id: string; timestamp: Date; agentKey: string; message: string;
  type: 'start' | 'update' | 'done' | 'error';
}

interface AgentFeedColumnProps {
  pollData: TripPollResponse | null;
  isActive: boolean;
  resetKey?: number;
}

/* ── Progress Ring ── */
const ProgressRing = ({ progress, size = 36, stroke = 3 }: { progress: number; size?: number; stroke?: number }) => {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (progress / 100) * circ;
  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#E5E7EB" strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#8B5CF6" strokeWidth={stroke}
        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
        style={{ transition: 'stroke-dashoffset 1s ease' }} />
    </svg>
  );
};

const AgentFeedColumn: React.FC<AgentFeedColumnProps> = ({ pollData, isActive, resetKey }) => {
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('timeline');
  const [elapsedTime, setElapsedTime] = useState(0);
  const feedRef = useRef<HTMLDivElement>(null);
  const prevStatesRef = useRef<Record<string, string>>({});
  const prevMessagesRef = useRef<Record<string, string | null>>({});
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startRef = useRef<number>(Date.now());

  // Elapsed time tracker
  useEffect(() => {
    if (isActive) {
      startRef.current = Date.now();
      setElapsedTime(0);
      timerRef.current = setInterval(() => setElapsedTime(Math.floor((Date.now() - startRef.current) / 1000)), 1000);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isActive]);

  // Stop timer on completion
  useEffect(() => {
    if (pollData?.status === 'completed' || pollData?.status === 'failed') {
      if (timerRef.current) clearInterval(timerRef.current);
    }
  }, [pollData?.status]);

  const fmtElapsed = (s: number) => { const m = Math.floor(s / 60); const sec = s % 60; return m > 0 ? `${m}m ${sec} secs` : `${sec} secs`; };

  // Reset
  useEffect(() => {
    if (resetKey === undefined || resetKey === 0) return;
    setFeed([]); prevStatesRef.current = {}; prevMessagesRef.current = {};
    setViewMode('timeline');
  }, [resetKey]);

  // Accumulate feed items
  useEffect(() => {
    if (!pollData) return;
    const agents = pollData.agents || {};
    const details: Record<string, AgentDetail> = pollData.agent_details || {};
    const newItems: FeedItem[] = [];
    const now = new Date();

    for (const key of AGENT_ORDER) {
      const status = agents[key]; const detail = details[key];
      const prevStatus = prevStatesRef.current[key];
      const prevMsg = prevMessagesRef.current[key];
      const curMsg = detail?.status_message || null;

      if (status === 'in_progress' && prevStatus !== 'in_progress')
        newItems.push({ id: `${key}-start-${now.getTime()}`, timestamp: now, agentKey: key, message: 'Started', type: 'start' });

      if (curMsg && curMsg !== prevMsg) {
        const isDoneMsg = status === 'completed' && prevStatus !== 'completed';
        if (!isDoneMsg)
          newItems.push({ id: `${key}-${now.getTime()}-${Math.random().toString(36).slice(2, 6)}`, timestamp: now, agentKey: key, message: curMsg, type: 'update' });
      }

      if (status === 'completed' && prevStatus !== 'completed')
        newItems.push({ id: `${key}-done-${now.getTime()}`, timestamp: now, agentKey: key, message: curMsg || 'Complete', type: 'done' });

      if (status === 'failed' && prevStatus !== 'failed')
        newItems.push({ id: `${key}-error-${now.getTime()}`, timestamp: now, agentKey: key, message: detail?.error_message || 'Failed', type: 'error' });

      prevStatesRef.current[key] = status || '';
      prevMessagesRef.current[key] = curMsg;
    }

    if (newItems.length > 0) setFeed((prev) => [...prev, ...newItems]);
  }, [pollData]);

  // Auto-scroll
  useEffect(() => {
    if (feedRef.current && viewMode === 'timeline') feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [feed, viewMode]);

  const agents = pollData?.agents || {};
  const isComplete = pollData?.status === 'completed';
  const completedCount = Object.values(agents).filter((s) => s === 'completed').length;
  const totalAgents = Math.max(Object.keys(agents).length, 6);
  const progressPct = totalAgents > 0 ? (completedCount / totalAgents) * 100 : 0;

  const fmtTime = (d: Date) => d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

  const feedByAgent: Record<string, FeedItem[]> = {};
  for (const key of AGENT_ORDER) feedByAgent[key] = feed.filter((i) => i.agentKey === key);

  /* ── Single feed row ── */
  const FeedRow = ({ item, isLast, showLabel }: { item: FeedItem; isLast: boolean; showLabel: boolean }) => {
    const a = AGENTS[item.agentKey] || { icon: '🔧', label: item.agentKey, color: '#6B7280' };
    return (
      <div style={{ display: 'flex', gap: 10, marginBottom: isLast ? 0 : 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <span style={{ fontSize: 9, color: '#94A3B8', fontFamily: "'Space Mono', monospace", whiteSpace: 'nowrap' }}>{fmtTime(item.timestamp)}</span>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: a.color, marginTop: 3, boxShadow: `0 0 0 3px ${a.color}30`, flexShrink: 0 }} />
          {!isLast && <div style={{ width: 2, flex: 1, background: `${a.color}20`, marginTop: 2 }} />}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap' }}>
            {showLabel && <span style={{ fontSize: 11, fontWeight: 700, color: a.color }}>{a.label} Agent</span>}
            {item.type === 'done' && <span style={{ fontSize: 8, fontWeight: 700, color: '#059669', background: '#ECFDF5', padding: '1px 5px', borderRadius: 5 }}>DONE</span>}
            {item.type === 'error' && <span style={{ fontSize: 8, fontWeight: 700, color: '#DC2626', background: '#FEF2F2', padding: '1px 5px', borderRadius: 5 }}>ERROR</span>}
          </div>
          {!(item.type === 'start' && item.message === 'Started') && (
            <p style={{ fontSize: 11, color: item.type === 'done' ? '#059669' : item.type === 'error' ? '#DC2626' : '#64748B', margin: '2px 0 0', lineHeight: 1.4 }}>{item.message}</p>
          )}
        </div>
      </div>
    );
  };

  return (
    <div style={{
      background: 'rgba(255,255,255,0.85)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
      borderRadius: 20, padding: 22, height: '100%', display: 'flex', flexDirection: 'column',
      border: '1px solid rgba(139,92,246,0.08)',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      overflow: 'hidden', maxHeight: 380,
    }}>

      {/* ── Header with progress ring ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14, flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 18 }}>🤖</span>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: '#1E293B', margin: 0 }}>Agent Feed</h3>
          {isComplete && <span style={{ fontSize: 12, fontWeight: 700, color: '#059669', background: '#ECFDF5', padding: '3px 9px', borderRadius: 8 }}>✓ Done · {fmtElapsed(elapsedTime)}</span>}
          {isActive && !isComplete && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10B981', display: 'inline-block', animation: 'agentPulse 1.2s ease-in-out infinite', boxShadow: '0 0 6px rgba(16,185,129,0.5)' }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: '#8B5CF6' }}>Completed {completedCount}/{totalAgents} · {fmtElapsed(elapsedTime)}</span>
            </span>
          )}
        </div>
        <ProgressRing progress={progressPct} />
      </div>

      {/* ── Agent status icons ── */}
      {(isActive || feed.length > 0) && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 14, padding: '10px 12px', background: 'rgba(139,92,246,0.04)', borderRadius: 12, flexShrink: 0 }}>
          {AGENT_ORDER.map((key) => {
            const a = AGENTS[key]; const s = agents[key];
            const isDone = s === 'completed'; const isRunning = s === 'in_progress'; const isFailed = s === 'failed';
            return (
              <div key={key} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }} title={a.label}>
                <div style={{
                  width: 36, height: 36, borderRadius: 11, position: 'relative',
                  background: `${a.color}15`, border: `2px solid ${isRunning ? a.color : isDone ? a.color + '40' : '#E2E8F0'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18,
                  boxShadow: isRunning ? `0 0 10px ${a.color}25` : 'none',
                  transition: 'all 0.3s',
                }}>
                  {a.icon}
                  {isDone && <div style={{ position: 'absolute', bottom: -3, right: -3, width: 14, height: 14, borderRadius: '50%', background: '#059669', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, color: 'white', border: '2px solid white' }}>✓</div>}
                  {isFailed && <div style={{ position: 'absolute', bottom: -3, right: -3, width: 14, height: 14, borderRadius: '50%', background: '#DC2626', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, color: 'white', border: '2px solid white' }}>✕</div>}
                </div>
              </div>
            );
          })}

          {/* View toggle — shown when there are feed items */}
          {feed.length > 0 && (
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 0, border: '1px solid #F97316', background: '#FFF7ED', borderRadius: 20, padding: 2 }}>
              {(['timeline', 'byAgent'] as ViewMode[]).map((m) => (
                <button key={m} onClick={() => setViewMode(m)} style={{
                  fontSize: 9, fontWeight: 600, padding: '3px 8px', borderRadius: 16, border: 'none', cursor: 'pointer',
                  background: viewMode === m ? 'white' : 'transparent',
                  color: viewMode === m ? '#C2410C' : '#94A3B8',
                  boxShadow: viewMode === m ? '0 0 0 1.5px #F97316' : 'none',
                  transition: 'all 0.2s',
                }}>{m === 'timeline' ? '🕐' : '🤖'}</button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Feed (scrollable) ── */}
      <div ref={feedRef} style={{ flex: 1, overflowY: 'auto', scrollbarWidth: 'thin' as any, scrollbarColor: '#C4B5FD transparent' }}>
        {feed.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#CBD5E1' }}>
            <span style={{ fontSize: 28, marginBottom: 6 }}>📡</span>
            <p style={{ fontSize: 13, fontWeight: 500, margin: 0 }}>Waiting to start...</p>
            <p style={{ fontSize: 11, margin: '4px 0 0', color: '#94A3B8' }}>Agent activity will stream here</p>
          </div>
        ) : viewMode === 'timeline' ? (
          <div>
            {feed.map((item, idx) => <FeedRow key={item.id} item={item} isLast={idx === feed.length - 1} showLabel={true} />)}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {AGENT_ORDER.map((key) => {
              const a = AGENTS[key]; const items = feedByAgent[key];
              if (!items || items.length === 0) return null;
              const s = agents[key];
              return (
                <div key={key} style={{ borderRadius: 12, border: `1px solid ${a.color}30`, overflow: 'hidden' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', background: `${a.color}08` }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                      <span style={{ fontSize: 13 }}>{a.icon}</span>
                      <span style={{ fontSize: 11, fontWeight: 700, color: a.color }}>{a.label}</span>
                      {s === 'completed' && <span style={{ fontSize: 8, fontWeight: 700, color: '#059669', background: '#ECFDF5', padding: '1px 5px', borderRadius: 5 }}>DONE</span>}
                    </div>
                    <span style={{ fontSize: 9, color: '#94A3B8' }}>{items.length}</span>
                  </div>
                  <div style={{ padding: '6px 8px', background: 'white' }}>
                    {items.map((item, idx) => <FeedRow key={item.id} item={item} isLast={idx === items.length - 1} showLabel={false} />)}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Completion summary */}
        {isComplete && feed.length > 0 && (
          <div style={{ marginTop: 10, padding: '8px 14px', borderRadius: 12, background: 'linear-gradient(90deg, #ECFDF5, #F0FDFA)', border: '1px solid #A7F3D0', textAlign: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#059669' }}>✓ All {completedCount} agents finished in {fmtElapsed(elapsedTime)} — {feed.length} events</span>
          </div>
        )}
      </div>

      <style>{`@keyframes agentPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }`}</style>
    </div>
  );
};

export default AgentFeedColumn;
