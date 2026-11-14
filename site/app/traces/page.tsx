"use client";
import { useEffect, useState } from "react";
import styles from "./traces.module.css";

type Trace = {
  reasoning?: Event[];
  activity_path?: string | null;
  id: string;
  model: string;
  task: string;
  case: string;
  score: number;
  status: string;
  prompt: string | null;
  answer: string | null;
  grade: Record<string, unknown> | null;
  judge: Record<string, unknown> | null;
  components: Record<string, unknown> | null;
  finish_reason: string | null;
};
type Event = { kind: string; name?: string; text: string; data?: string; format?: string };
type Role = "user" | "agent" | "tool" | "result" | "sealed";

const tasks: Record<string, string> = {
  keep_going: "Keep going or pull?",
  rulebook_vs_body: "Rulebook vs. body",
  beat_ectemp: "Beat ECTemp",
};
const SEALED = "Reasoning encrypted by model provider";
const roleLabel: Record<Role, string> = {
  user: "User",
  agent: "Agent",
  tool: "Tool",
  result: "Result",
  sealed: "Sealed",
};

function caseName(row: Trace) {
  if (row.case.startsWith("3A/")) return `Forecast after a work drop · Participant ${row.case.split("/")[1]}`;
  if (row.case.startsWith("3B/")) return `Estimate current temperature · Participant ${row.case.split("/")[1]}`;
  return `${tasks[row.task] || row.task} · Case ${Number(row.case.split("-")[1]) || row.case}`;
}
function preview(text: string, n = 110) {
  const flat = (text || "").replace(/\s+/g, " ").trim();
  return flat.length > n ? `${flat.slice(0, n)}…` : flat;
}
function isSealed(event: Event) {
  return event.kind === SEALED || (event.text || "").startsWith("gAAAAA");
}
function roleOf(event: Event): Role {
  if (isSealed(event)) return "sealed";
  if (event.kind === "Task prompt") return "user";
  if (event.kind === "Tool call") return "tool";
  if (event.kind === "Tool result") return "result";
  return "agent";
}
function bodyOf(event: Event) {
  if (!isSealed(event)) return event.text || "";
  return event.data || ((event.text || "").startsWith("gAAAAA") ? event.text : "");
}
function titleOf(event: Event) {
  if (isSealed(event)) return "Sealed by provider";
  if (event.kind === "Tool call" || event.kind === "Tool result") return event.name || event.kind;
  if (event.kind === "Reasoning summary" || event.kind === "Model reasoning") return event.kind;
  if (event.kind === "Assistant message") return "Agent";
  return event.kind;
}

function outcomeOf(row: Trace): { pass: boolean; label: string } {
  const comp = (row.components || {}) as Record<string, unknown>;
  const grade = (row.grade || {}) as Record<string, unknown>;
  if (row.task === "beat_ectemp") {
    const beat = typeof comp.predictor === "number" && comp.predictor > 0;
    return beat ? { pass: true, label: "Beat ECTemp" } : { pass: false, label: "Failed to beat" };
  }
  if (row.task === "keep_going") {
    return grade.decision_correct === true ? { pass: true, label: "Passed" } : { pass: false, label: "Failed" };
  }
  if (row.task === "rulebook_vs_body") {
    const body = (grade.body || {}) as Record<string, unknown>;
    return body.decision_correct === true ? { pass: true, label: "Passed" } : { pass: false, label: "Failed" };
  }
  return row.score >= 0.5 ? { pass: true, label: "Passed" } : { pass: false, label: "Failed" };
}

function num(v: unknown, digits = 3) {
  return typeof v === "number" ? v.toFixed(digits) : "—";
}

function summaryBullets(row: Trace): string[] {
  const comp = (row.components || {}) as Record<string, unknown>;
  const grade = (row.grade || {}) as Record<string, unknown>;
  const judge = (row.judge || {}) as Record<string, unknown>;

  if (row.task === "beat_ectemp") {
    const pred = typeof comp.predictor === "number" ? comp.predictor : 0;
    const mae = typeof grade.person_mae === "number" ? `${grade.person_mae.toFixed(3)}°C` : "—";
    const expl = typeof judge.research_explanation === "number" ? `${judge.research_explanation} / 5` : "—";
    return [
      pred > 0
        ? `Predictor beat the ECTemp baseline (component score ${pred.toFixed(3)}, person MAE ${mae}).`
        : `Predictor failed to beat the ECTemp baseline (component score 0.000, person MAE ${mae}).`,
      `Research explanation scored ${expl}${row.status === "absent_answer" ? " (no final answer submitted)" : ""}.`,
      `Submission checks: ${grade.valid ? "passed" : "failed"}.`,
    ];
  }

  if (row.task === "keep_going") {
    const modelDec = grade.model_decision ? String(grade.model_decision) : "none";
    const expDec = grade.expected_decision ? String(grade.expected_decision) : "—";
    const decJudge = typeof judge.decision === "number" ? `${judge.decision} / 5` : "—";
    const reasJudge = typeof judge.reasoning === "number" ? `${judge.reasoning} / 5` : "—";
    const err = typeof grade.core_abs_error_c === "number" ? `${grade.core_abs_error_c.toFixed(2)}°C error` : "no forecast";
    const est = typeof grade.core_estimate_c === "number" ? `${grade.core_estimate_c.toFixed(2)}°C` : "none";
    const truth = typeof grade.core_truth_c === "number" ? `${grade.core_truth_c.toFixed(2)}°C` : "—";
    return [
      grade.decision_correct
        ? `Correct call: predicted ${modelDec} (expected ${expDec}) · decision judge ${decJudge}.`
        : `Wrong call: predicted ${modelDec}, expected ${expDec}${grade.error_type ? ` (${String(grade.error_type).replaceAll("_", " ")})` : ""} · decision judge ${decJudge}.`,
      `15-min core temp forecast: ${est} vs. measured ${truth} (${err}).`,
      `Physiology reasoning scored ${reasJudge}.`,
    ];
  }

  const body = (grade.body || {}) as Record<string, unknown>;
  const rb = (grade.rulebook || {}) as Record<string, unknown>;
  const matches = (rb.matches || {}) as Record<string, unknown>;
  const matchedCount = Object.values(matches).filter(Boolean).length;
  const totalFields = Object.keys(matches).length || 4;
  const modelDec = body.model_decision ? String(body.model_decision) : "none";
  const expDec = body.expected_decision ? String(body.expected_decision) : "—";
  const ovJudge = typeof judge.override_decision === "number" ? `${judge.override_decision} / 5` : "—";
  const reasJudge = typeof judge.reasoning === "number" ? `${judge.reasoning} / 5` : "—";
  const est = typeof body.core_estimate_c === "number" ? `${body.core_estimate_c.toFixed(2)}°C` : "none";
  const truth = typeof body.core_truth_c === "number" ? `${body.core_truth_c.toFixed(2)}°C` : "—";
  return [
    body.decision_correct
      ? `Override call correct: ${modelDec} (expected ${expDec}) · judge ${ovJudge}.`
      : `Override call failed: predicted ${modelDec}, expected ${expDec} · judge ${ovJudge}.`,
    `Rulebook table lookup: matched ${matchedCount} of ${totalFields} fields (${num(rb.score, 2)}).`,
    `Core temp estimate ${est} vs. measured ${truth}; reasoning judge ${reasJudge}.`,
  ];
}

function Turn({ role, title, text }: { role: Role; title: string; text: string }) {
  return (
    <details className={`${styles.turn} ${styles[role]}`}>
      <summary>
        <i>{roleLabel[role]}</i>
        <b>{title}</b>
        <span>{preview(text) || "Empty"}</span>
      </summary>
      {text ? <pre>{text}</pre> : null}
    </details>
  );
}

function Activity({ path }: { path: string }) {
  const [events, setEvents] = useState<Event[]>([]);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    fetch(path)
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      })
      .then((data) => {
        if (live) setEvents(data);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [path]);
  const prompt = events.find((e) => e.kind === "Task prompt");
  const rest = events.filter((e) => e.kind !== "Task prompt");
  return (
    <>
      <section className={styles.block}>
        <h3>Task context</h3>
        {failed ? (
          <p className={styles.notice} role="alert">Could not load the task context. Please reload.</p>
        ) : prompt ? (
          <div className={styles.turns}><Turn role="user" title="Task prompt" text={prompt.text} /></div>
        ) : (
          <p className={styles.notice}>{events.length ? "No task prompt was saved with this run." : "Loading task context…"}</p>
        )}
      </section>
      <section className={styles.block}>
        <h3>Trajectory</h3>
        {failed ? null : !events.length ? (
          <p className={styles.notice}>Loading trajectory…</p>
        ) : (
          <div className={styles.turns}>
            {rest.map((event, i) => (
              <Turn key={i} role={roleOf(event)} title={titleOf(event)} text={bodyOf(event)} />
            ))}
          </div>
        )}
      </section>
    </>
  );
}

export default function Traces() {
  const [rows, setRows] = useState<Trace[]>([]);
  const [error, setError] = useState(false);
  const [model, setModel] = useState("");
  const [task, setTask] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState("");

  useEffect(() => {
    const sync = () => {
      try {
        setSelected(decodeURIComponent(location.hash.slice(1)));
      } catch {
        setSelected("");
      }
    };
    sync();
    window.addEventListener("hashchange", sync);
    fetch("/traces/cases.json")
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      })
      .then(setRows)
      .catch(() => setError(true));
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  const filtered = rows.filter(
    (r) =>
      (!model || r.model === model) &&
      (!task || r.task === task) &&
      `${caseName(r)} ${r.case} ${r.model} ${r.answer} ${r.status}`.toLowerCase().includes(query.toLowerCase())
  );
  const active = filtered.find((r) => r.id === selected) || filtered[0];
  const outcome = active ? outcomeOf(active) : null;
  const bullets = active ? summaryBullets(active) : [];

  return (
    <section className={styles.page}>
      <div className={styles.intro}>
        <a href="/" className={styles.back}>← Results</a>
        <h1>Trace explorer</h1>
        <p>Click any case to see whether it beat the benchmark, the results summary, task context, and color-coded trajectory.</p>
      </div>

      <div className={styles.toolbar}>
        <label>
          Model
          <select value={model} onChange={(e) => { setModel(e.target.value); setSelected(""); }}>
            <option value="">All models</option>
            {[...new Set(rows.map((r) => r.model))].map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        </label>
        <label>
          Task
          <select value={task} onChange={(e) => { setTask(e.target.value); setSelected(""); }}>
            <option value="">All tasks</option>
            {[...new Set(rows.map((r) => r.task))].map((t) => (
              <option value={t} key={t}>{tasks[t] || t}</option>
            ))}
          </select>
        </label>
        <label className={styles.search}>
          Search
          <input
            placeholder="Find a case or answer…"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelected(""); }}
          />
        </label>
      </div>

      {error && <p role="alert">Could not load traces. Please reload.</p>}

      <div className={styles.workspace}>
        <aside className={styles.sidebar}>
          <div className={styles.listHeading}>{rows.length ? `${filtered.length} cases` : "Loading cases…"}</div>
          <nav aria-label="Cases">
            {filtered.map((r) => {
              const res = outcomeOf(r);
              return (
                <a
                  key={r.id}
                  href={`#${encodeURIComponent(r.id)}`}
                  aria-current={active?.id === r.id ? "true" : undefined}
                  onClick={() => setSelected(r.id)}
                >
                  <span className={styles.model}>{r.model}</span>
                  <span>{caseName(r)}</span>
                  <small className={res.pass ? styles.scorePass : styles.scoreFail}>{r.score.toFixed(3)}</small>
                </a>
              );
            })}
          </nav>
        </aside>

        {active && outcome ? (
          <article className={styles.detail} key={active.id}>
            <header className={`${styles.results} ${outcome.pass ? styles.pass : styles.fail}`}>
              <div className={styles.resultsTop}>
                <strong>{active.score.toFixed(3)}</strong>
                <div>
                  <b>{caseName(active)}</b>
                  <span>{active.model} · {tasks[active.task] || active.task}</span>
                </div>
                <span className={styles.badge}>{outcome.label}</span>
              </div>
              <div className={styles.summaryBox}>
                <h3>Results summary</h3>
                <ul>
                  {bullets.map((line, i) => (
                    <li key={i}>{line}</li>
                  ))}
                </ul>
              </div>
            </header>

            <div className={styles.body}>
              <section className={styles.block}>
                <h3>Final answer</h3>
                <div className={styles.turns}>
                  <Turn role="agent" title="Answer" text={active.answer || "(empty)"} />
                </div>
              </section>

              {active.activity_path ? (
                <Activity key={active.activity_path} path={active.activity_path} />
              ) : (
                <>
                  <section className={styles.block}>
                    <h3>Task context</h3>
                    {active.prompt ? (
                      <div className={styles.turns}><Turn role="user" title="Task prompt" text={active.prompt} /></div>
                    ) : (
                      <p className={styles.notice}>No task prompt was recorded for this case.</p>
                    )}
                  </section>
                  <section className={styles.block}>
                    <h3>Trajectory</h3>
                    {active.reasoning?.length ? (
                      <div className={styles.turns}>
                        {active.reasoning.map((item, i) => (
                          <Turn key={i} role={roleOf(item)} title={titleOf(item)} text={bodyOf(item)} />
                        ))}
                      </div>
                    ) : (
                      <p className={styles.notice}>Single-turn response; no intermediate reasoning was returned.</p>
                    )}
                  </section>
                </>
              )}

              <details className={styles.record}>
                <summary>Raw grade &amp; judge JSON</summary>
                <pre>{JSON.stringify({ components: active.components, grade: active.grade, judge: active.judge }, null, 2)}</pre>
              </details>
            </div>
          </article>
        ) : (
          <p className={styles.empty}>{rows.length ? "No matching cases. Try a different search or filter." : ""}</p>
        )}
      </div>

      <div className={styles.export}>
        <span>Want to work with the data?</span> <a href="/traces/cases.json" download>Download all traces (JSON) ↓</a>
      </div>
    </section>
  );
}
