import data from "@/lib/soldier.json";
import { Mark } from "@/components/Mark";
import { Plot } from "@/components/Plot";

// limit: show only the N most expensive models; omit to show all
export function CostByTask({ limit }: { limit?: number }) {
  const max = 30;
  const rows = [...data.models].sort((a, b) => b.cost - a.cost).slice(0, limit);
  return (
    <Plot>
      {rows.map((m, i) => (
        <div className="stack" key={m.id} style={{ "--d": `${i * 90}ms` } as React.CSSProperties}>
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}><Mark provider={m.provider} />{m.name}</span>
          <span className="row">
            <i style={{ width: `${(m.cost_tasks.keep_going / max) * 100}%`, "--c": "var(--task-keep)" } as React.CSSProperties} />
            <i style={{ width: `${(m.cost_tasks.rulebook / max) * 100}%`, "--c": "var(--task-rulebook)" } as React.CSSProperties} />
            <i style={{ width: `${(m.cost_tasks.research / max) * 100}%`, "--c": "var(--task-research)" } as React.CSSProperties} />
          </span>
        </div>
      ))}
      <div className="legend">
        <span style={{ "--c": "var(--task-keep)" } as React.CSSProperties}>keep / pull</span>
        <span style={{ "--c": "var(--task-rulebook)" } as React.CSSProperties}>rulebook</span>
        <span style={{ "--c": "var(--task-research)" } as React.CSSProperties}>beat ECTemp</span>
      </div>
    </Plot>
  );
}
