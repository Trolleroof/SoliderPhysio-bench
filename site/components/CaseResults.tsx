import data from "@/lib/soldier.json";
import traces from "@/public/traces/cases.json";
import styles from "./CaseResults.module.css";

const groups = [
  { task: "keep_going", label: "Keep / Pull" },
  { task: "rulebook_vs_body", label: "Rulebook" },
  { task: "beat_ectemp", label: "Beat ECTemp" },
];
const cases = groups.flatMap(({ task, label }) =>
  [...new Set(traces.filter((row) => row.task === task).map((row) => row.case))]
    .map((id) => ({ task, label, id }))
);
const results = new Map(traces.map((row) => [`${row.model}:${row.task}:${row.case}`, row]));

export function CaseResults() {
  return (
    <section className="block" id="case-results">
      <div className="block-head"><h3>Case-level results</h3><span className="label">0–100 score</span></div>
      <p className="sub">Each cell shows one model’s score on one case. Select a cell to inspect its trace.</p>
      <div className={styles.scroll}>
        <table className={styles.grid}>
          <thead>
            <tr><th scope="col">Model</th>{groups.map((group) => <th key={group.task} scope="colgroup" colSpan={cases.filter((c) => c.task === group.task).length}>{group.label}</th>)}</tr>
            <tr><th scope="col">Case</th>{cases.map((c) => <th scope="col" key={`${c.task}:${c.id}`}>{c.id}</th>)}</tr>
          </thead>
          <tbody>{data.models.map((model) => <tr key={model.id}>
            <th scope="row">{model.name}</th>
            {cases.map((c) => {
              const row = results.get(`${model.name}:${c.task}:${c.id}`);
              if (!row) return <td key={`${c.task}:${c.id}`}>—</td>;
              const score = Math.round(row.score * 100);
              return <td key={`${c.task}:${c.id}`}><a href={`/traces/#${encodeURIComponent(row.id)}`} style={{ backgroundColor: `rgba(180, 83, 9, ${0.06 + row.score * 0.36})` }} aria-label={`${model.name}, ${c.label}, ${c.id}: ${score} out of 100${row.status === "absent_answer" ? ", no answer" : ""}. View trace.`}>{score}</a></td>;
            })}
          </tr>)}</tbody>
        </table>
      </div>
      <p className="note">One trial per case. Scores combine task-specific components, including the reasoning judge; they are not counts of repeated passes. Missing answers score 0.</p>
    </section>
  );
}
