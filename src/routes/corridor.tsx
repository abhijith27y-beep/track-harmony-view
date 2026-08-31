import { createFileRoute } from "@tanstack/react-router";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/components/ui-bits";
import { useRealtime } from "@/hooks/use-realtime";
import { SLOTS, TRAIN_PATHS } from "@/lib/mock-data";

export const Route = createFileRoute("/corridor")({
  head: () => ({
    meta: [
      { title: "Corridor View — ABPS Rail Block Planning" },
      {
        name: "description",
        content:
          "Space-time train path diagram and AI-recommended block windows derived from timetable and goods forecast.",
      },
      { property: "og:title", content: "Corridor View — ABPS" },
      {
        property: "og:description",
        content: "Space-time train paths and AI-recommended maintenance windows.",
      },
    ],
  }),
  component: Corridor,
});

const W = 960;
const H = 380;
const PAD = 44;
const MAX_KM = 300;
const COLORS = ["var(--color-tms)", "var(--color-tdms)", "var(--color-smms)"];

function toArray<T>(v: unknown): T[] {
  if (Array.isArray(v)) return v as T[];
  if (v && typeof v === "object") return Object.values(v as Record<string, T>);
  return [];
}

type PathPoint = { hour: number; km: number };
type TrainPath = { id: string; name: string; points: PathPoint[] };

function Corridor() {
  const { data: rawPaths } = useRealtime("/telemetry", TRAIN_PATHS);
  const { data: rawSlots } = useRealtime("/slots", SLOTS);

  const paths: TrainPath[] = toArray<TrainPath>(rawPaths)
    .map((p) => ({ ...p, points: toArray<PathPoint>(p?.points) }))
    .filter((p) => p.points.length > 0);
  const slots = toArray<(typeof SLOTS)[number]>(rawSlots);

  const x = (hour: number) => PAD + (hour / 24) * (W - PAD * 2);
  const y = (km: number) => PAD + (km / MAX_KM) * (H - PAD * 2);

  return (
    <div>
      <PageHeader
        title="Corridor View"
        subtitle="BPL–ET corridor · train paths vs available maintenance windows"
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Space–time diagram</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <svg viewBox={`0 0 ${W} ${H}`} className="min-w-[720px] w-full">
            {Array.from({ length: 9 }, (_, i) => i * 3).map((h) => (
              <g key={h}>
                <line
                  x1={x(h)}
                  y1={PAD}
                  x2={x(h)}
                  y2={H - PAD}
                  stroke="var(--color-border)"
                  strokeDasharray="3 4"
                />
                <text
                  x={x(h)}
                  y={H - PAD + 18}
                  textAnchor="middle"
                  fill="var(--color-muted-foreground)"
                  fontSize={11}
                >
                  {String(h).padStart(2, "0")}:00
                </text>
              </g>
            ))}
            {[0, 75, 150, 225, 300].map((km) => (
              <g key={km}>
                <line
                  x1={PAD}
                  y1={y(km)}
                  x2={W - PAD}
                  y2={y(km)}
                  stroke="var(--color-border)"
                  strokeDasharray="3 4"
                />
                <text
                  x={PAD - 8}
                  y={y(km) + 4}
                  textAnchor="end"
                  fill="var(--color-muted-foreground)"
                  fontSize={11}
                >
                  {km} km
                </text>
              </g>
            ))}

            {/* AI-recommended maintenance windows */}
            <rect
              x={x(1.5)}
              y={PAD}
              width={x(4.5) - x(1.5)}
              height={H - PAD * 2}
              fill="var(--color-ok)"
              opacity={0.12}
            />
            <text
              x={x(3)}
              y={PAD + 16}
              textAnchor="middle"
              fill="var(--color-ok)"
              fontSize={11}
            >
              ★ Recommended block window
            </text>

            {paths.map((p, i) => (
              <g key={p.id}>
                <polyline
                  points={p.points.map((pt) => `${x(pt.hour)},${y(pt.km)}`).join(" ")}
                  fill="none"
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={2}
                />
                <text
                  x={x(p.points[p.points.length - 1]!.hour) + 6}
                  y={y(p.points[p.points.length - 1]!.km)}
                  fill={COLORS[i % COLORS.length]}
                  fontSize={11}
                >
                  {p.id}
                </text>
              </g>
            ))}
          </svg>
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
            {paths.map((p, i) => (
              <span key={p.id} className="flex items-center gap-1.5">
                <span
                  className="size-2.5 rounded-sm"
                  style={{ background: COLORS[i % COLORS.length] }}
                />
                {p.name}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">Block window availability</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Section</TableHead>
                <TableHead>Window</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Trains affected</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead className="text-right">AI slot</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {slots.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-medium">{s.section}</TableCell>
                  <TableCell className="font-mono text-xs">{s.window}</TableCell>
                  <TableCell>{s.durationMin} min</TableCell>
                  <TableCell>{s.trainsAffected}</TableCell>
                  <TableCell>{s.confidence}%</TableCell>
                  <TableCell className="text-right">
                    {s.aiRecommended ? (
                      <span className="text-warning">★ Recommended</span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
