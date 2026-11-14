import data from "@/lib/soldier.json";
import { Plot } from "@/components/Plot";

export function RulebookBars() {
  const rb = Object.entries(data.rulebook);
  const rbMax = Math.max(...rb.map(([, v]) => v));
  return (
    <Plot>
      {rb.map(([k, v], i) => {
        const c = k.startsWith("40/20")
          ? "var(--bad)"
          : k.startsWith("NL")
            ? "var(--good)"
            : k.startsWith("other")
              ? "var(--warn)"
              : "var(--drab)";
        return (
          <div className="hbar" key={k} style={{ "--c": c, "--d": `${i * 90}ms` } as React.CSSProperties}>
            <span>{k}</span><i style={{ width: `${(v / rbMax) * 100}%` }} /><b>{v}</b>
          </div>
        );
      })}
    </Plot>
  );
}
