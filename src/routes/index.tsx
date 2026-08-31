import { createFileRoute } from "@tanstack/react-router";
import { ClientOnly } from "@tanstack/react-router";
import { lazy, Suspense, useMemo, useState } from "react";
import { Activity, AlertTriangle, CalendarClock, Brain, Check } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageHeader, DeptTag, SeverityTag, healthClass } from "@/components/ui-bits";
import { Gantt } from "@/components/gantt";
import { useRealtime } from "@/hooks/use-realtime";
import { ALERTS, BLOCKS, DEFECTS, SECTIONS } from "@/lib/mock-data";
import type { Alert } from "@/lib/types";

const RailMap = lazy(() => import("@/components/rail-map"));

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Control Dashboard — ABPS Rail Block Planning" },
      {
        name: "description",
        content:
          "Live asset availability, section health map, today's block plan and AI alerts across TMS, TDMS and SMMS.",
      },
      { property: "og:title", content: "Control Dashboard — ABPS" },
      {
        property: "og:description",
        content:
          "Live asset availability, section health and AI-prioritised maintenance blocks.",
      },
    ],
  }),
  component: Dashboard,
});

function Dashboard() {
  const { data: sections } = useRealtime("/sections", SECTIONS);
  const { data: blocks } = useRealtime("/schedule", BLOCKS);
  const { data: defects } = useRealtime("/defects", DEFECTS);
  const { data: alertsData, state } = useRealtime("/alerts", ALERTS);
  const [acked, setAcked] = useState<string[]>([]);

  const today = blocks.filter((b) => b.date === "2026-08-28");
  const availability = useMemo(
    () =>
      sections.length
        ? (
            sections.reduce((s, x) => s + (x.availability ?? 0), 0) / sections.length
          ).toFixed(1)
        : "0.0",
    [sections],
  );
  const critical = defects.filter((d) => d.severity === "Critical").length;
  const aiScore = blocks.length
    ? Math.round(blocks.reduce((s, b) => s + (b.aiScore ?? 0), 0) / blocks.length)
    : 0;

  const alerts: Alert[] = alertsData.map((a) =>
    acked.includes(a.id) ? { ...a, acknowledged: true } : a,
  );

  return (
    <div>
      <PageHeader
        title="Control Dashboard"
        subtitle="Integrated block planning across Engineering, Traction Distribution and S&T"
        right={
          <span className="rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
            {state === "live" ? "Firebase live" : "Demo data (Firebase idle)"}
          </span>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          icon={<Activity className="size-4" />}
          label="Asset Availability"
          value={`${availability}%`}
          note="7-day rolling average"
        />
        <Kpi
          icon={<AlertTriangle className="size-4 text-critical" />}
          label="Critical Defects"
          value={String(critical)}
          note={`${defects.filter((d) => d.overdue).length} overdue overall`}
        />
        <Kpi
          icon={<CalendarClock className="size-4 text-tdms" />}
          label="Blocks Today"
          value={String(today.length)}
          note={`${today.filter((b) => b.status === "Approved").length} approved`}
        />
        <Kpi
          icon={<Brain className="size-4 text-smms" />}
          label="AI Optimisation Score"
          value={String(aiScore)}
          note="Schedule quality index"
        />
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Network health map</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[380px] overflow-hidden rounded-lg border border-border">
              <ClientOnly
                fallback={
                  <div className="grid h-full place-items-center text-sm text-muted-foreground">
                    Loading map…
                  </div>
                }
              >
                <Suspense
                  fallback={
                    <div className="grid h-full place-items-center text-sm text-muted-foreground">
                      Loading map…
                    </div>
                  }
                >
                  <RailMap sections={sections} />
                </Suspense>
              </ClientOnly>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Live alerts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {alerts.map((a) => (
              <div
                key={a.id}
                className="rounded-lg border border-border bg-background/40 p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <SeverityTag severity={a.severity} />
                    <DeptTag dept={a.dept} />
                  </div>
                  <span className="text-[11px] text-muted-foreground">{a.time}</span>
                </div>
                <p className="mt-2 text-sm">{a.message}</p>
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-[11px] text-muted-foreground">{a.section}</span>
                  {a.acknowledged ? (
                    <span className="flex items-center gap-1 text-[11px] text-ok">
                      <Check className="size-3" /> Acknowledged
                    </span>
                  ) : (
                    <Button
                      size="sm"
                      variant="secondary"
                      className="h-7 text-xs"
                      onClick={() => setAcked((p) => [...p, a.id])}
                    >
                      Acknowledge
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">Today&apos;s block plan</CardTitle>
        </CardHeader>
        <CardContent>
          <Gantt blocks={today} compact />
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">Section health</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {sections.map((s) => (
            <div key={s.id} className="rounded-lg border border-border p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{s.id}</span>
                <span className={`text-sm font-semibold ${healthClass(s.healthScore)}`}>
                  {s.healthScore}
                </span>
              </div>
              <p className="mt-1 truncate text-xs text-muted-foreground">{s.name}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function Kpi({
  icon,
  label,
  value,
  note,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  note: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {icon}
          {label}
        </div>
        <p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p>
        <p className="mt-1 text-xs text-muted-foreground">{note}</p>
      </CardContent>
    </Card>
  );
}
