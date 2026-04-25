"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AriaObservation,
  GwAgentEvent,
  RewardBreakdown,
} from "./contracts";
import {
  MOCK_EVENTS,
  MOCK_OBSERVATION,
  MOCK_REWARD_BREAKDOWN,
  MOCK_RUNNING_TOTAL,
  MOCK_STREAM,
} from "./mockData";

export type ConnectionState = "connecting" | "live" | "mock" | "error";

/**
 * High-level voice UX state. Drives the orb color and intensity.
 *   idle      — waiting for mic permission / muted / nothing happening
 *   listening — mic is hot, ambient audio, no wake word detected
 *   wake      — "aria …" detected, actively transcribing
 *   speaking  — ARIA is responding via TTS
 */
export type VoiceState = "idle" | "listening" | "wake" | "speaking" | "muted";

export interface SessionAPI {
  connected: ConnectionState;
  sessionId: string;
  observation: AriaObservation;
  rewardBreakdown: RewardBreakdown;
  runningReward: RewardBreakdown;
  events: GwAgentEvent[];
  transcript: string;
  partialTranscript: string;
  replyText: string;
  tickCount: number;
  latencyMs: number;
  send: (text: string) => void;
  toggleMute: () => void;
  muted: boolean;
  voiceState: VoiceState;
  analyserNode: AnalyserNode | null;
}

const GW_URL =
  typeof process !== "undefined"
    ? process.env.NEXT_PUBLIC_GATEWAY_WS_URL ??
      "ws://localhost:8000/ws/session/demo"
    : "ws://localhost:8000/ws/session/demo";

const WAKE_RE = /\b(hey )?(ok )?aria\b/i;
const SPEAKING_HOLD_MS = 2600;
const WAKE_HOLD_MS = 4000;

export function useSession(): SessionAPI {
  const [connected, setConnected] = useState<ConnectionState>("connecting");
  // SSR-safe: empty on the server, generated on first client render so server
  // and client trees agree. Consumers render a placeholder when empty.
  const [sessionId, setSessionId] = useState<string>("");
  useEffect(() => {
    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `s-${Math.floor(Math.random() * 1e9).toString(16)}`;
    setSessionId(id.slice(0, 12));

    // Rebase the pre-populated mock event log to the current wall clock.
    const now = Date.now();
    setEvents(
      MOCK_EVENTS.map((ev) => ({
        ...ev,
        ts_ms: now + ev.ts_ms, // ev.ts_ms is negative; result is in the past
      })),
    );
  }, []);
  const [observation] = useState<AriaObservation>(MOCK_OBSERVATION);
  const [rewardBreakdown, setRewardBreakdown] =
    useState<RewardBreakdown>(MOCK_REWARD_BREAKDOWN);
  const [runningReward, setRunningReward] =
    useState<RewardBreakdown>(MOCK_RUNNING_TOTAL);
  // Start empty so SSR + client agree. `MOCK_EVENTS` carries negative
  // offsets that we rebase to `Date.now()` on mount (effect below).
  const [events, setEvents] = useState<GwAgentEvent[]>([]);
  const [transcript, setTranscript] = useState("");
  const [partialTranscript, setPartialTranscript] = useState("");
  const [replyText, setReplyText] = useState(
    "Board review pushed to 6:15 pm. Priya notified. Riya's play protected.",
  );
  const [tickCount, setTickCount] = useState(0);
  const [latencyMs, setLatencyMs] = useState(0);

  // --- always-listening voice state -----------------------------------------
  const [muted, setMuted] = useState(false);
  const [micGranted, setMicGranted] = useState(false);
  const [voiceState, setVoiceStateRaw] = useState<VoiceState>("idle");
  const voiceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const setVoiceState = useCallback((next: VoiceState, holdMs = 0) => {
    if (voiceTimerRef.current) {
      clearTimeout(voiceTimerRef.current);
      voiceTimerRef.current = null;
    }
    setVoiceStateRaw(next);
    if (holdMs > 0 && (next === "wake" || next === "speaking")) {
      voiceTimerRef.current = setTimeout(() => {
        // Decay back to listening/idle after the hold window.
        setVoiceStateRaw(micGranted && !muted ? "listening" : "idle");
      }, holdMs);
    }
  }, [micGranted, muted]);

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);

  // --- event ingestion ------------------------------------------------------
  const ingest = useCallback(
    (ev: GwAgentEvent) => {
      setEvents((prev) => [...prev.slice(-199), ev]);
      switch (ev.kind) {
        case "partial_transcript": {
          const text = String(ev.payload.text ?? "");
          setPartialTranscript(text);
          if (WAKE_RE.test(text)) setVoiceState("wake", WAKE_HOLD_MS);
          break;
        }
        case "final_transcript": {
          const text = String(ev.payload.text ?? "");
          setTranscript(text);
          setPartialTranscript("");
          if (WAKE_RE.test(text)) setVoiceState("wake", WAKE_HOLD_MS);
          break;
        }
        case "reward": {
          const br = ev.payload.breakdown as RewardBreakdown | undefined;
          if (br) {
            setRewardBreakdown(br);
            setRunningReward((prev) => ({
              task_completion:     prev.task_completion     + br.task_completion,
              relationship_health: prev.relationship_health + br.relationship_health,
              user_satisfaction:   prev.user_satisfaction   + br.user_satisfaction,
              time_efficiency:     prev.time_efficiency     + br.time_efficiency,
              conflict_resolution: prev.conflict_resolution + br.conflict_resolution,
              safety:              prev.safety              + br.safety,
              total:               prev.total               + br.total,
            }));
          }
          break;
        }
        case "env_step":
          setTickCount((t) => t + 1);
          break;
        case "reply_text":
          setReplyText(String(ev.payload.text ?? ""));
          setVoiceState("speaking", SPEAKING_HOLD_MS);
          break;
      }
    },
    [setVoiceState],
  );

  // --- ws lifecycle ---------------------------------------------------------
  useEffect(() => {
    // Wait until sessionId has been generated on the client.
    if (!sessionId) return;
    let cancelled = false;
    let fallbackTimer: ReturnType<typeof setTimeout> | null = null;

    const enterMock = () => {
      if (cancelled) return;
      setConnected("mock");
      const replay = () => {
        let i = 0;
        const step = () => {
          if (cancelled) return;
          if (i >= MOCK_STREAM.length) {
            setTimeout(replay, 8000);
            return;
          }
          const ev = { ...MOCK_STREAM[i], ts_ms: Date.now() };
          ingest(ev);
          const delay =
            i + 1 < MOCK_STREAM.length
              ? MOCK_STREAM[i + 1].ts_ms - MOCK_STREAM[i].ts_ms
              : 1000;
          i += 1;
          setTimeout(step, Math.max(100, delay));
        };
        step();
      };
      replay();
    };

    try {
      const ws = new WebSocket(GW_URL);
      wsRef.current = ws;
      fallbackTimer = setTimeout(() => {
        if (ws.readyState !== WebSocket.OPEN) {
          try { ws.close(); } catch {}
          enterMock();
        }
      }, 1500);
      ws.onopen = () => {
        if (fallbackTimer) clearTimeout(fallbackTimer);
        if (cancelled) return;
        setConnected("live");
        ws.send(
          JSON.stringify({
            kind: "session_start",
            session_id: sessionId,
            mode: "simulated",
          }),
        );
      };
      ws.onmessage = (msg) => {
        try {
          const ev = JSON.parse(msg.data) as GwAgentEvent;
          ingest(ev);
        } catch {
          /* ignore */
        }
      };
      ws.onclose = () => {
        if (cancelled) return;
        enterMock();
      };
      ws.onerror = () => { /* fallback timer handles fallback */ };
    } catch {
      enterMock();
    }

    return () => {
      cancelled = true;
      if (fallbackTimer) clearTimeout(fallbackTimer);
      try { wsRef.current?.close(); } catch {}
    };
  }, [sessionId, ingest]);

  // --- latency tick (ambient) -----------------------------------------------
  useEffect(() => {
    const id = setInterval(() => {
      setLatencyMs(
        420 + Math.floor(Math.sin(Date.now() / 1800) * 40 + Math.random() * 10),
      );
    }, 1000);
    return () => clearInterval(id);
  }, []);

  // --- always-listening mic ------------------------------------------------
  const startMic = useCallback(async () => {
    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices?.getUserMedia
    )
      return;
    if (mediaStreamRef.current) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      const AC =
        window.AudioContext ||
        // @ts-expect-error webkitAudioContext fallback
        window.webkitAudioContext;
      const ctx = new AC();
      audioCtxRef.current = ctx;
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.85;
      src.connect(analyser);
      analyserRef.current = analyser;
      setMicGranted(true);
      setVoiceState("listening");
    } catch {
      setMicGranted(false);
      setVoiceState("idle");
    }
  }, [setVoiceState]);

  const stopMic = useCallback(() => {
    try {
      mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
      audioCtxRef.current?.close();
    } catch {}
    mediaStreamRef.current = null;
    audioCtxRef.current = null;
    analyserRef.current = null;
    setMicGranted(false);
  }, []);

  // auto-start mic on mount
  useEffect(() => {
    void startMic();
    return () => stopMic();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // keep voice state in sync with mute toggles
  useEffect(() => {
    if (muted) {
      setVoiceState("muted");
    } else if (micGranted) {
      // Only fall back to listening if we aren't already in wake/speaking.
      setVoiceStateRaw((s) =>
        s === "wake" || s === "speaking" ? s : "listening",
      );
    } else {
      setVoiceStateRaw("idle");
    }
  }, [muted, micGranted, setVoiceState]);

  const toggleMute = useCallback(() => {
    setMuted((m) => {
      const next = !m;
      const track = mediaStreamRef.current?.getAudioTracks()[0];
      if (track) track.enabled = !next;
      return next;
    });
  }, []);

  // --- send text turn -------------------------------------------------------
  const send = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            kind: "user_text",
            session_id: sessionId,
            user_text: text,
          }),
        );
      } else {
        ingest({
          session_id: sessionId,
          kind: "final_transcript",
          payload: { text },
          ts_ms: Date.now(),
        });
        setTimeout(() => {
          ingest({
            session_id: sessionId,
            kind: "reply_text",
            payload: { text: `Understood: "${text.slice(0, 64)}"` },
            ts_ms: Date.now(),
          });
        }, 400);
      }
    },
    [sessionId, ingest],
  );

  return {
    connected,
    sessionId,
    observation,
    rewardBreakdown,
    runningReward,
    events,
    transcript,
    partialTranscript,
    replyText,
    tickCount,
    latencyMs,
    send,
    toggleMute,
    muted,
    voiceState,
    analyserNode: analyserRef.current,
  };
}
