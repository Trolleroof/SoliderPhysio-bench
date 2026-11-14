import data from "@/lib/soldier.json";
import { color } from "@/components/Mark";
import { Plot } from "@/components/Plot";

const W = 820, H = 380, L = 44, R = 150, T = 16, B = 40;
const xs = (c: number) => L + ((Math.log10(c) - Math.log10(0.2)) / (Math.log10(40) - Math.log10(0.2))) * (W - L - R);
const ys = (s: number) => T + (1 - (s - 25) / 35) * (H - T - B);
// hand-placed label nudges so names never collide
const NUDGE: Record<string, [number, number, "start" | "end"]> = {
  "Muse Wonder 1.0": [10, 14, "start"], "Sonnet 5.5": [-10, 4, "end"], "GPT-6 Astra": [10, -8, "start"],
  "Gemini 3.8 Flash": [-10, 14, "end"], "Kimi K3.1 Pro": [10, -6, "start"], "Hy4": [-10, -8, "end"],
  "Grok 4.6": [10, -6, "start"], "Fable 5": [-10, -10, "end"], "Opus 5.5": [10, 14, "start"],
};

export function Scatter() {
  const ticksX = [0.25, 1, 4, 16];
  return (
    <Plot className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Overall score against cost per full run">
        {[30, 40, 50, 60].map((v) => (
          <g key={v}>
            <line className="grid" x1={L} x2={W - R + 20} y1={ys(v)} y2={ys(v)} stroke="var(--line)" />
            <text x={L - 10} y={ys(v) + 4} fontSize="13" fill="var(--faint)" textAnchor="end">{v}</text>
          </g>
        ))}
        {ticksX.map((v) => (
          <text key={v} x={xs(v)} y={H - B + 22} fontSize="13" fill="var(--faint)" textAnchor="middle">${v}</text>
        ))}
        <text x={L} y={T - 2} fontSize="12.5" fill="var(--faint)" letterSpacing="1.2">SCORE</text>
        <text x={W - R + 20} y={H - 4} fontSize="12.5" fill="var(--faint)" textAnchor="end" letterSpacing="1.2">COST PER FULL RUN (USD, LOG)</text>
        {[...data.models].sort((a, b) => a.cost - b.cost).map((m, i) => {
          const [dx, dy, a] = NUDGE[m.name] ?? [10, 4, "start"];
          const x = xs(m.cost), y = ys(m.overall);
          return (
            <g key={m.id} className="pt" style={{ "--d": `${200 + i * 70}ms` } as React.CSSProperties}>
              <circle cx={x} cy={y} r="5" fill={color(m.provider)} style={{ transformOrigin: `${x}px ${y}px` }} />
              <text x={x + dx} y={y + dy} fontSize="14" fill={color(m.provider)} textAnchor={a}>{m.name}</text>
            </g>
          );
        })}
      </svg>
    </Plot>
  );
}
