"use client";

import { useState } from "react";
import data from "@/lib/soldier.json";
import { Mark, color } from "@/components/Mark";
import { Plot } from "@/components/Plot";

type M = (typeof data.models)[number];
const METRICS = [
  { key: "overall", label: "Overall" },
  { key: "keep", label: "Keep / Pull" },
  { key: "rulebook", label: "Rulebook" },
  { key: "research", label: "Beat ECTemp" },
] as const;

export function Board() {
  const [k, setK] = useState<(typeof METRICS)[number]["key"]>("overall");
  const rows = [...data.models].sort((a: M, b: M) => b[k] - a[k]);
  // scale to the leader so the longest bar + its score ends just before the cost column
  const top = Math.max(...rows.map((r) => r[k])) || 1;
  return (
    <>
      <div className="block-head">
        <h2>Leaderboard</h2>
        <div className="tabs" role="tablist" aria-label="Score">
          {METRICS.map((m) => (
            <button key={m.key} role="tab" aria-selected={k === m.key} onClick={() => setK(m.key)}>{m.label}</button>
          ))}
        </div>
      </div>
      <Plot>
      <table className="lb">
        <thead>
          <tr><th>#</th><th>Model</th><th>Score / 100</th><th style={{ textAlign: "right" }}>Cost</th></tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${k}-${r.id}`}>
              <td className="rk">{i + 1}</td>
              <td className="mdl"><span className="mdl-in"><Mark provider={r.provider} />{r.name}<span className="eff">{r.effort}</span></span></td>
              <td className="bar-cell">
                <div className="bar" style={{ "--c": color(r.provider), "--d": `${i * 45}ms` } as React.CSSProperties}>
                  <i style={{ width: `calc((100% - 52px) * ${r[k] / top})` }} />
                  <span>{r[k].toFixed(1)}</span>
                </div>
              </td>
              <td className="cost">${r.cost.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </Plot>
      <p className="note">
        One trial per case, run {data.run}. Overall is the mean of the three task scores. Cost is provider-reported USD for all
        21 cases. Fable 5 and Opus 5.5 score 0 on the rulebook after content-filter refusals.
      </p>
    </>
  );
}
