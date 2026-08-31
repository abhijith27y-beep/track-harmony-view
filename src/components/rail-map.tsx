import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import type { Section } from "@/lib/types";
import { healthHex } from "./ui-bits";

function toLatLng(v: unknown): [number, number] | null {
  if (!v) return null;
  if (Array.isArray(v) && typeof v[0] === "number" && typeof v[1] === "number") return [v[0], v[1]];
  const o = v as Record<string | number, unknown>;
  if (typeof o[0] === "number" && typeof o[1] === "number") return [o[0] as number, o[1] as number];
  return null;
}

export default function RailMap({ sections }: { sections: Section[] }) {
  const valid = sections.filter((s) => toLatLng(s.from) && toLatLng(s.to));
  return (
    <MapContainer
      center={[20.5, 80.5]}
      zoom={5}
      scrollWheelZoom={false}
      style={{ height: "100%", width: "100%", borderRadius: "0.5rem" }}
    >
      <TileLayer
        attribution="&copy; OpenStreetMap contributors &copy; CARTO"
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
      {valid.map((s) => {
        const color = healthHex(s.healthScore);
        const from = toLatLng(s.from)!;
        const to = toLatLng(s.to)!;
        return (
          <Polyline
            key={s.id}
            positions={[from, to]}
            pathOptions={{ color, weight: 5, opacity: 0.9 }}
          >
            <Tooltip sticky>
              <strong>{s.id}</strong> — {s.name}
              <br />
              Health {s.healthScore} · Availability {s.availability}%
              <br />
              {s.openDefects} open defects
            </Tooltip>
          </Polyline>
        );
      })}
      {valid.map((s) => {
        const to = toLatLng(s.to)!;
        return (
          <CircleMarker
            key={`${s.id}-node`}
            center={to}
            radius={4}
            pathOptions={{
              color: healthHex(s.healthScore),
              fillColor: healthHex(s.healthScore),
              fillOpacity: 1,
            }}
          />
        );
      })}
    </MapContainer>
  );
}
