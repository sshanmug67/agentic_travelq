/**
 * useTripSearch — Hook for async trip planning with polling
 * Location: frontend/src/hooks/useTripSearch.ts
 *
 * Manages the full async lifecycle:
 *   1. POST /search → get trip_id instantly (HTTP 202)
 *   2. Poll GET /{trip_id}/status every pollInterval ms
 *   3. Track per-agent progress (for TripStatusBar)
 *   4. Deliver final results when status = "completed"
 *
 * Usage in Dashboard:
 *   const { submitTrip, activeTripId, pollData, isPolling, ... } = useTripSearch({
 *     onComplete: (results) => processResults(results),
 *     onError: (err) => showError(err),
 *   });
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { tripApi } from '../services/api';
import type { TripPollResponse } from '../services/api';

interface UseTripSearchOptions {
  onComplete?: (results: any) => void;
  onError?: (error: string) => void;
  pollInterval?: number;
}

interface UseTripSearchReturn {
  submitTrip: (payload: any) => Promise<string | null>;
  activeTripId: string | null;
  pollData: TripPollResponse | null;
  isSubmitting: boolean;
  isPolling: boolean;
  error: string | null;
  clearTrip: () => void;
}

export function useTripSearch(options: UseTripSearchOptions = {}): UseTripSearchReturn {
  const { onComplete, onError, pollInterval = 2500 } = options;

  const [activeTripId, setActiveTripId] = useState<string | null>(null);
  const [pollData, setPollData] = useState<TripPollResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const completedRef = useRef(false);

  // Store latest callbacks in refs so polling doesn't get stale closures
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);
  onCompleteRef.current = onComplete;
  onErrorRef.current = onError;

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Poll function
  const poll = useCallback(async (tripId: string) => {
    if (completedRef.current) return;

    try {
      const data = await tripApi.pollTripStatus(tripId);
      setPollData(data);

      if (data.status === 'completed') {
        completedRef.current = true;
        setIsPolling(false);
        if (pollRef.current) clearInterval(pollRef.current);
        if (data.results) {
          onCompleteRef.current?.(data.results);
        }
      }

      if (data.status === 'failed') {
        completedRef.current = true;
        setIsPolling(false);
        if (pollRef.current) clearInterval(pollRef.current);
        const errMsg = data.error || 'Trip planning failed';
        setError(errMsg);
        onErrorRef.current?.(errMsg);
      }
    } catch (err: any) {
      console.error('Poll error:', err);
      // Don't stop polling on transient network errors
    }
  }, []);

  // Start polling when activeTripId changes
  useEffect(() => {
    if (!activeTripId) return;

    completedRef.current = false;
    setIsPolling(true);
    setPollData(null);

    // Immediate first poll
    poll(activeTripId);

    // Interval
    pollRef.current = setInterval(() => poll(activeTripId), pollInterval);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [activeTripId, poll, pollInterval]);

  // Submit
  const submitTrip = useCallback(async (payload: any): Promise<string | null> => {
    setIsSubmitting(true);
    setError(null);
    setActiveTripId(null);
    setPollData(null);

    try {
      const data = await tripApi.planTrip(payload);
      const tripId = data.trip_id;
      setActiveTripId(tripId);
      setIsSubmitting(false);
      return tripId;
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to start trip planning';
      setError(errMsg);
      setIsSubmitting(false);
      onErrorRef.current?.(errMsg);
      return null;
    }
  }, []);

  // Clear
  const clearTrip = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    setActiveTripId(null);
    setPollData(null);
    setError(null);
    setIsSubmitting(false);
    setIsPolling(false);
    completedRef.current = false;
  }, []);

  return {
    submitTrip,
    activeTripId,
    pollData,
    isSubmitting,
    isPolling,
    error,
    clearTrip,
  };
}