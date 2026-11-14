import data from "@/lib/soldier.json";
import { Plot } from "@/components/Plot";

export function KeepPull() {
  return (
    <Plot>
      {data.keep_pull.map((d, i) => {
        const n = d.correct + d.false_pull + d.missed;
        return (
          <div className="stack" key={d.design} style={{ "--d": `${i * 110}ms` } as React.CSSProperties}>
            <span>{d.design}</span>
            <span className="row">
              {d.correct > 0 && <i style={{ width: `${(d.correct / n) * 100}%`, "--c": "var(--good)" } as React.CSSProperties} title={`${d.correct} correct`} />}
              {d.false_pull > 0 && <i style={{ width: `${(d.false_pull / n) * 100}%`, "--c": "var(--warn)" } as React.CSSProperties} title={`${d.false_pull} needless pulls`} />}
              {d.missed > 0 && <i style={{ width: `${(d.missed / n) * 100}%`, "--c": "var(--bad)" } as React.CSSProperties} title={`${d.missed} missed pulls`} />}
            </span>
          </div>
        );
      })}
      <div className="legend">
        <span style={{ "--c": "var(--good)" } as React.CSSProperties}>correct</span>
        <span style={{ "--c": "var(--warn)" } as React.CSSProperties}>needless pull</span>
        <span style={{ "--c": "var(--bad)" } as React.CSSProperties}>missed pull</span>
      </div>
    </Plot>
  );
}
