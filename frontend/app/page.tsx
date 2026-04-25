"use client";

import { useState } from "react";
import { BootSequence } from "@/components/BootSequence";
import { CalendarPanel } from "@/components/CalendarPanel";
import { EventTrace } from "@/components/EventTrace";
import { Header } from "@/components/Header";
import { InboxPanel } from "@/components/InboxPanel";
import { RelationshipsPanel } from "@/components/RelationshipsPanel";
import { RewardRadar } from "@/components/RewardRadar";
import { StatusBar } from "@/components/StatusBar";
import { TasksPanel } from "@/components/TasksPanel";
import { Ticker } from "@/components/Ticker";
import { VoiceDock } from "@/components/VoiceDock";
import { useSession } from "@/lib/ws";

// Sections appear in this order; adjust stagger spacing here.
const ENTRANCE = {
  inbox:    40,
  tasks:    100,
  voice:    0,      // hero leads
  radar:    60,
  rels:    140,
  cal:     200,
  trace:   260,
};

type EntranceKey = keyof typeof ENTRANCE;

function stagger(key: EntranceKey): React.CSSProperties {
  return { ["--aria-delay" as string]: `${ENTRANCE[key]}ms` };
}

export default function Page() {
  const s = useSession();
  const [booted, setBooted] = useState(false);

  const modeText =
    s.connected === "live"
      ? "MODE:LIVE · GW:OK"
      : s.connected === "mock"
        ? "MODE:OFFLINE · GW:MOCK"
        : s.connected === "error"
          ? "MODE:FAULT · GW:X"
          : "MODE:LINK…";

  return (
    <>
      {!booted && <BootSequence onComplete={() => setBooted(true)} />}

      <div className="flex h-screen w-screen flex-col overflow-hidden bg-(--color-bg)">
        <Header
          sessionId={s.sessionId}
          connected={s.connected}
          tickCount={s.tickCount}
          latencyMs={s.latencyMs}
          scenarioCategory={s.observation.scenario_category}
          difficulty={s.observation.difficulty}
        />
        <Ticker observation={s.observation} runningReward={s.runningReward} />

        {/* ======== HERO ROW — voice centered, world-state flanks ======== */}
        <main className="grid min-h-0 flex-1 grid-cols-12 grid-rows-5 gap-[1px] bg-(--color-border) p-[1px]">
          {/* LEFT — Inbox (top) + Tasks (bottom) */}
          <section className="col-span-3 row-span-3 flex min-h-0 flex-col gap-[1px]">
            <div className="flex-[0_0_58%] panel-stagger" style={stagger("inbox")}>
              <InboxPanel inbox={s.observation.inbox} />
            </div>
            <div className="flex-1 min-h-0 panel-stagger" style={stagger("tasks")}>
              <TasksPanel tasks={s.observation.pending_tasks} />
            </div>
          </section>

          {/* CENTER — VoiceDock HERO */}
          <section
            className="col-span-6 row-span-3 min-h-0 panel-stagger"
            style={stagger("voice")}
          >
            <VoiceDock
              voiceState={s.voiceState}
              partialTranscript={s.partialTranscript}
              transcript={s.transcript}
              replyText={s.replyText}
              muted={s.muted}
              analyserNode={s.analyserNode}
              onToggleMute={s.toggleMute}
              onSubmit={s.send}
            />
          </section>

          {/* RIGHT — RewardRadar (top) + Relationships (bottom) */}
          <section className="col-span-3 row-span-3 flex min-h-0 flex-col gap-[1px]">
            <div className="flex-[0_0_52%] panel-stagger" style={stagger("radar")}>
              <RewardRadar step={s.rewardBreakdown} running={s.runningReward} />
            </div>
            <div className="flex-1 min-h-0 panel-stagger" style={stagger("rels")}>
              <RelationshipsPanel relationships={s.observation.relationships} />
            </div>
          </section>

          {/* BOTTOM ROW — Calendar + Event trace */}
          <section
            className="col-span-7 row-span-2 min-h-0 panel-stagger"
            style={stagger("cal")}
          >
            <CalendarPanel
              calendar={s.observation.calendar}
              currentTime={s.observation.time}
            />
          </section>
          <section
            className="col-span-5 row-span-2 min-h-0 panel-stagger"
            style={stagger("trace")}
          >
            <EventTrace events={s.events} />
          </section>
        </main>

        <StatusBar modeText={modeText} />

        {/* Bloomberg-era CRT scanline overlay — fixed, non-interactive. */}
        <div className="crt-scanlines" aria-hidden />
      </div>
    </>
  );
}
