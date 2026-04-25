"use client";

import { useEffect, useState } from "react";
import { Panel } from "./Panel";
import { VoiceOrb } from "./VoiceOrb";
import type { VoiceState } from "@/lib/ws";

interface VoiceDockProps {
  voiceState: VoiceState;
  partialTranscript: string;
  transcript: string;
  replyText: string;
  muted: boolean;
  analyserNode: AnalyserNode | null;
  onToggleMute: () => void;
  onSubmit: (text: string) => void;
}

const STATE_LABEL: Record<VoiceState, string> = {
  idle:      "STANDBY",
  listening: "LISTENING",
  wake:      "WAKE // ARIA",
  speaking:  "RESPONDING",
  muted:     "MIC // OFF",
};

const STATE_TEXT: Record<VoiceState, string> = {
  idle:      "text-(--color-fg-muted)",
  listening: "text-(--color-phosphor)",
  wake:      "text-(--color-cyan)",
  speaking:  "text-(--color-amber)",
  muted:     "text-(--color-red)",
};

const STATE_DOT: Record<VoiceState, "live" | "idle" | "warn" | "err"> = {
  idle:      "idle",
  listening: "live",
  wake:      "live",
  speaking:  "warn",
  muted:     "err",
};

const STATE_CAPTION: Record<VoiceState, string> = {
  idle:      "◌ STANDBY",
  listening: "• ABSORBING",
  wake:      "▼ TRANSCRIBING",
  speaking:  "▲ EMITTING",
  muted:     "■ MIC OFF",
};

export function VoiceDock({
  voiceState,
  partialTranscript,
  transcript,
  replyText,
  muted,
  analyserNode,
  onToggleMute,
  onSubmit,
}: VoiceDockProps) {
  const [draft, setDraft] = useState("");

  // Keyboard: `m` toggles mute (ignored when typing)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      )
        return;
      if (e.key.toLowerCase() === "m") {
        e.preventDefault();
        onToggleMute();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onToggleMute]);

  const liveLine =
    voiceState === "wake"
      ? partialTranscript || transcript || "…capturing…"
      : transcript ||
        (voiceState === "listening" ? "awaiting wake word" : "—");

  return (
    <Panel
      label="VOICE // JARVIS"
      meta={
        <span className="flex items-center gap-3 tracking-widest">
          <span className={`font-semibold ${STATE_TEXT[voiceState]}`}>
            {STATE_LABEL[voiceState]}
          </span>
          <span className="text-(--color-fg-muted)">WHISPER·ELEVENLABS</span>
        </span>
      }
      stateDot={STATE_DOT[voiceState]}
      className="h-full"
    >
      <div className="flex h-full flex-col">
        {/* HERO ORB — dominant visual. `flex-1` + `min-h-[280px]` give the
            container a guaranteed size; VoiceOrb self-positions inside. */}
        <div
          className="flex-1"
          style={{ position: "relative", minHeight: 280 }}
        >
          <VoiceOrb state={voiceState} analyser={analyserNode} />

          {/* corner chrome */}
          <div className="pointer-events-none absolute left-3 top-2 text-[9px] tracking-widest text-(--color-fg-muted)">
            SPECTRUM // 0-8KHZ
          </div>
          <div className="pointer-events-none absolute right-3 top-2 text-[9px] tracking-widest text-(--color-fg-muted)">
            CH·MONO · 16KHZ
          </div>
          <div className="pointer-events-none absolute left-3 bottom-2 text-[9px] tracking-widest text-(--color-fg-muted)">
            {STATE_CAPTION[voiceState]}
          </div>
          <div className="pointer-events-none absolute right-3 bottom-2 text-[9px] tracking-widest text-(--color-fg-muted)">
            WAKE=&quot;ARIA&quot;
          </div>

          {/* BIG state badge — top center */}
          <div className="pointer-events-none absolute left-1/2 top-6 -translate-x-1/2 text-center">
            <div className="text-[10px] tracking-[0.32em] text-(--color-fg-muted)">
              ARIA // ALWAYS-ON
            </div>
            <div
              className={`mt-1 text-[22px] font-bold tracking-[0.28em] drop-shadow-[0_0_8px_currentColor] ${STATE_TEXT[voiceState]}`}
            >
              {STATE_LABEL[voiceState]}
            </div>
          </div>

          {/* mute control — top-right, over the orb */}
          <button
            type="button"
            onClick={onToggleMute}
            className={`absolute right-3 top-10 hairline px-2 py-1 text-[10px] tracking-widest transition-colors backdrop-blur-sm ${
              muted
                ? "border-(--color-red) text-(--color-red) bg-(--color-red)/15"
                : "border-(--color-border-strong)/80 text-(--color-fg-dim) bg-black/35 hover:bg-black/50"
            }`}
            title="Toggle mic (M)"
          >
            {muted ? "■ MUTED" : "● LIVE"}
          </button>

          {/* live transcript strip — bottom, inside the orb frame */}
          <div className="pointer-events-none absolute inset-x-0 bottom-0 border-t border-(--color-border) bg-black/65 px-4 py-2 backdrop-blur-sm">
            <div className="flex items-center gap-2">
              <span className="text-[9px] tracking-widest text-(--color-fg-muted)">
                USER →
              </span>
              {voiceState === "wake" && (
                <span className="text-[9px] tracking-widest text-(--color-cyan)">
                  ◉ STREAMING
                </span>
              )}
            </div>
            <div className="mt-0.5 text-[13px] leading-tight text-(--color-fg)">
              <span
                className={
                  voiceState !== "wake" && !transcript
                    ? "text-(--color-fg-muted)"
                    : ""
                }
              >
                {liveLine}
              </span>
              {voiceState === "wake" && <span className="cursor" />}
            </div>
          </div>
        </div>

        {/* ARIA reply */}
        <div className="flex-shrink-0 border-t border-(--color-border) bg-(--color-panel-2) px-4 py-2">
          <div className="text-[9px] tracking-widest text-(--color-fg-muted)">
            ARIA →
            {voiceState === "speaking" && (
              <span className="ml-2 text-(--color-amber)">◉ SPEAKING</span>
            )}
          </div>
          <div className="mt-0.5 text-[13px] leading-snug text-(--color-amber)">
            {replyText || (
              <span className="text-(--color-fg-muted)">standing by</span>
            )}
          </div>
        </div>

        {/* command prompt */}
        <form
          className="flex flex-shrink-0 items-center gap-2 border-t border-(--color-border) bg-(--color-panel-2) px-3 py-2"
          onSubmit={(e) => {
            e.preventDefault();
            const text = draft.trim();
            if (text) {
              onSubmit(text);
              setDraft("");
            }
          }}
        >
          <span className="text-(--color-amber)">$</span>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="flex-1 bg-transparent text-[13px] text-(--color-fg) placeholder-(--color-fg-muted) outline-none"
            placeholder="say 'aria …' or type a command"
            autoComplete="off"
            spellCheck={false}
          />
          <button
            type="submit"
            className="hairline border-(--color-border-strong) px-2 py-1 text-[10px] tracking-widest text-(--color-fg-dim) hover:bg-(--color-hover)"
          >
            EXEC
          </button>
        </form>
      </div>
    </Panel>
  );
}
