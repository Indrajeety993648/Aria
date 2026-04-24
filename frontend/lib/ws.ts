"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AriaObservation,
  GwAgentEvent,
  RewardBreakdown,
} from "@/lib/contracts";
import {
  MOCK_SESSION_ID,
  mockEvents,
  mockObservation,
  mockRewardBreakdown,
} from "@/lib/mockData";

export interface UseSessionResult {
  connected: boolean;
  observation: AriaObservation | null;
  rewardBreakdown: RewardBreakdown | null;
  events: GwAgentEvent[];
  transcript: string;
  startRecording: () => void;
  stopRecording: () => void;
  send: (payload: Record<string, unknown>) => void;
}

const WS_URL: string =
  process.env.NEXT_PUBLIC_GATEWAY_WS_URL ??
  "ws://localhost:8000/ws/session/demo";

const CONNECT_TIMEOUT_MS = 2000;
const MOCK_REPLAY_INTERVAL_MS = 500;

function coerceReward(p: Record<string, unknown>): RewardBreakdown | null {
  const b = p["breakdown"] ?? p;
  if (typeof b !== "object" || b === null) return null;
  const r = b as Partial<RewardBreakdown>;
  if (
    typeof r.task_completion === "number" &&
    typeof r.total === "number"
  ) {
    return r as RewardBreakdown;
  }
  return null;
}

function coerceTranscript(p: Record<string, unknown>): string | null {
  const t = p["text"];
  return typeof t === "string" ? t : null;
}

export function useSession(
  sessionId: string = MOCK_SESSION_ID,
): UseSessionResult {
  const [connected, setConnected] = useState<boolean>(false);
  const [observation, setObservation] = useState<AriaObservation | null>(null);
  const [rewardBreakdown, setRewardBreakdown] =
    useState<RewardBreakdown | null>(null);
  const [events, setEvents] = useState<GwAgentEvent[]>([]);
  const [transcript, setTranscript] = useState<string>("");

  const wsRef = useRef<WebSocket | null>(null);
  const mockTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fallbackTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );

  const ingestEvent = useCallback((ev: GwAgentEvent) => {
    setEvents((prev) => [...prev, ev].slice(-200));
    switch (ev.kind) {
      case "partial_transcript":
      case "final_transcript": {
        const t = coerceTranscript(ev.payload);
        if (t !== null) setTranscript(t);
        break;
      }
      case "reply_text": {
        const t = coerceTranscript(ev.payload);
        if (t !== null) setTranscript(t);
        break;
      }
      case "reward": {
        const rb = coerceReward(ev.payload);
        if (rb !== null) setRewardBreakdown(rb);
        break;
      }
      case "env_step": {
        const obs = ev.payload["observation"];
        if (obs && typeof obs === "object") {
          setObservation(obs as AriaObservation);
        }
        break;
      }
      default:
        break;
    }
  }, []);

  const startMockReplay = useCallback(() => {
    if (mockTimerRef.current !== null) return;
    setObservation(mockObservation);
    setRewardBreakdown(mockRewardBreakdown);
    let i = 0;
    mockTimerRef.current = setInterval(() => {
      if (i >= mockEvents.length) {
        if (mockTimerRef.current !== null) {
          clearInterval(mockTimerRef.current);
          mockTimerRef.current = null;
        }
        return;
      }
      ingestEvent(mockEvents[i]!);
      i += 1;
    }, MOCK_REPLAY_INTERVAL_MS);
  }, [ingestEvent]);

  useEffect(() => {
    let cancelled = false;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      fallbackTimeoutRef.current = setTimeout(() => {
        if (!cancelled && ws.readyState !== WebSocket.OPEN) {
          try {
            ws.close();
          } catch {
            /* ignore */
          }
          startMockReplay();
        }
      }, CONNECT_TIMEOUT_MS);

      ws.onopen = () => {
        if (cancelled) return;
        if (fallbackTimeoutRef.current !== null) {
          clearTimeout(fallbackTimeoutRef.current);
          fallbackTimeoutRef.current = null;
        }
        setConnected(true);
        ws.send(
          JSON.stringify({
            kind: "session_start",
            session_id: sessionId,
            mode: "simulated",
          }),
        );
      };

      ws.onmessage = (msg: MessageEvent<string>) => {
        try {
          const parsed = JSON.parse(msg.data) as GwAgentEvent;
          ingestEvent(parsed);
        } catch {
          /* ignore malformed frames */
        }
      };

      ws.onerror = () => {
        if (cancelled) return;
        setConnected(false);
        startMockReplay();
      };

      ws.onclose = () => {
        if (cancelled) return;
        setConnected(false);
        startMockReplay();
      };
    } catch {
      startMockReplay();
    }

    return () => {
      cancelled = true;
      if (fallbackTimeoutRef.current !== null) {
        clearTimeout(fallbackTimeoutRef.current);
        fallbackTimeoutRef.current = null;
      }
      if (mockTimerRef.current !== null) {
        clearInterval(mockTimerRef.current);
        mockTimerRef.current = null;
      }
      if (wsRef.current !== null) {
        try {
          wsRef.current.close();
        } catch {
          /* ignore */
        }
        wsRef.current = null;
      }
    };
  }, [sessionId, startMockReplay, ingestEvent]);

  const send = useCallback((payload: Record<string, unknown>) => {
    const ws = wsRef.current;
    if (ws !== null && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
    }
  }, []);

  const startRecording = useCallback(() => {
    send({ kind: "voice_start", session_id: sessionId });
  }, [send, sessionId]);

  const stopRecording = useCallback(() => {
    send({ kind: "voice_stop", session_id: sessionId });
  }, [send, sessionId]);

  return {
    connected,
    observation,
    rewardBreakdown,
    events,
    transcript,
    startRecording,
    stopRecording,
    send,
  };
}
