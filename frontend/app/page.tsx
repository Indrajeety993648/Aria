"use client";

import { EnvInspector } from "@/components/EnvInspector";
import { EventTrace } from "@/components/EventTrace";
import { RewardRadar } from "@/components/RewardRadar";
import { VoiceDock } from "@/components/VoiceDock";
import { useSession } from "@/lib/ws";
import { mockRunningTotal } from "@/lib/mockData";

export default function Page(): React.JSX.Element {
  const {
    connected,
    observation,
    rewardBreakdown,
    events,
    transcript,
    startRecording,
    stopRecording,
  } = useSession();

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-8 text-slate-200">
      <div className="mx-auto flex max-w-[1440px] flex-col gap-6">
        <header className="flex items-end justify-between border-b border-slate-800 pb-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-100">
              ARIA
            </h1>
            <p className="text-sm text-slate-500">
              Agentic Resource &amp; Intent Assistant — live session
            </p>
          </div>
          <div className="text-xs text-slate-500">
            session_id:{" "}
            <span className="font-mono text-slate-300">demo</span>
          </div>
        </header>

        <VoiceDock
          transcript={transcript}
          connected={connected}
          onStartRecording={startRecording}
          onStopRecording={stopRecording}
        />

        <div className="grid gap-6 lg:grid-cols-[1fr_minmax(360px,420px)]">
          <EnvInspector observation={observation} />
          <RewardRadar
            current={rewardBreakdown}
            runningTotal={mockRunningTotal}
          />
        </div>

        <EventTrace events={events} />
      </div>
    </main>
  );
}
