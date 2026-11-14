import { Board } from "@/components/Board";
import { CaseResults } from "@/components/CaseResults";
import { TaskScores } from "@/components/TaskScores";
import { Toc } from "@/components/Toc";
import { PinnedHeads } from "@/components/PinnedHeads";
import data from "@/lib/soldier.json";

const DIMS = [
  ["Keep / Pull", "Decision (0.40)", "PULL iff measured core at +15 min ≥ 38.5 °C", "A medic is judged on the call, not the guess"],
  ["Keep / Pull", "Forecast (0.30)", "1 − |error| / E_c, floored at 0", "E_c = 0.1712 °C is the error of a constant guess, so a worse forecast earns 0"],
  ["Keep / Pull", "Reasoning (0.30)", "Judge 0–5, shown the verified outcome", "Checks whether cited trends and uncertainty actually support the call"],
  ["Rulebook", "Table lookup (0.30)", "Exact match on four TB MED 507 (2022) cells", "Work/rest, water, continuous-work limit, continuous water; NL where no limit applies"],
  ["Rulebook", "Override (0.40)", "OVERRIDE iff measured core at +15 min ≥ 38.5 °C", "The card sets unit guidance; the override is the individual call"],
  ["Rulebook", "Reasoning (0.30)", "Judge 0–5, shown the verified outcome", "Checks whether the answer uses both the 2022 card and the trace accurately"],
  ["Beat ECTemp", "Predictor (0.60)", "1 − MAE / B on hidden people, floored at 0", "B is the frozen per-person baseline error; beating it is the job"],
  ["Beat ECTemp", "Explanation (0.40)", "Judge 0–5, shown the hidden MAE", "Claims of beating the baseline that fail on hidden people are unsupported"],
];

function Finding({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <article className="kf" id={`finding-${n}`}>
      <div className="n">{n}</div>
      <div>
        <h3>{title}</h3>
        {children}
      </div>
    </article>
  );
}

export default function Home() {
  return (
    <div className="wrap">
      <Toc />
      <PinnedHeads />
      <section className="hero" id="intro" aria-label="Benchmark overview">
        <h1 className="rise">SoldierPhysio</h1>
        <h2 className="hero-subhead rise" style={{ "--d": "80ms" } as React.CSSProperties}>
          Evaluating frontier models on <span className="khaki">a field medic&apos;s heat-casualty calls.</span>
        </h2>
        <div className="hero-copy rise" style={{ "--d": "120ms" } as React.CSSProperties}>
          <p>
            Heat illness is a real and growing problem for the Army. In 2024 it recorded 36.4 heat strokes and 183.9
            heat-exhaustion cases per 100,000 soldiers, and heat exhaustion has gone up every year since 2020 (MSMR,
            June 2025). People are starting to pitch AI models as helpers for medics. But most medical AI tests are
            multiple-choice questions where the answer is basically in the prompt. Almost nothing tests whether a model
            can make the actual call in the field before a soldier goes down.
          </p>
          <p>
            Here is that call. A medic watching soldiers train in the heat can see heart rate, skin temperature, how
            hard each soldier is working, and the weather. They cannot see core body temperature, the number that
            actually tells you someone is close to heat stroke. They also carry the Army&apos;s heat chart (TB MED 507,
            updated 2022), a one-page guide that says how long soldiers can work and how much water they need based on
            how hot it is and how hard the work is. Over and over, the medic has to decide: keep this soldier going, or
            pull them out.
          </p>
          <p>
            SoldierPhysio puts 14 AI models in the medic&apos;s seat. Each model sees 25 minutes of sensor data and must
            decide whether the soldier&apos;s core temperature will hit 38.5 °C (about 101 °F) in the next 15 minutes.
            The data comes from a real study where 24 people biked in a heat chamber with their core temperature
            measured every minute (D&apos;Lugos et al., 2025), so every case has a known right answer. Every model gets
            the same 21 cases, and code checks each answer against what actually happened.
          </p>
        </div>
      </section>

      <section className="block" id="methodology">
        <h2>Methodology</h2>
        <p className="sub">
          SoldierPhysio evaluates whether a model can make heat-casualty decisions from the sensors and doctrine a field
          medic actually carries. Every raw answer, deterministic grade, and judge verdict is saved in the repo so the
          full leaderboard can be recomputed offline without an API key.
        </p>

        <div className="writeup-card">
          <div className="writeup-sec">
            <h3>Constants for the environment</h3>
            <p>
              Ground truth is measured rectal temperature from a published heat-chamber study: 24 people cycling for
              about an hour in the heat (D&apos;Lugos et al., 2025; Figshare 29120024, CC BY 4.0). Each single-turn case
              shows the last 25 minutes of one person&apos;s wearable and chamber log, minute by minute:
            </p>
            <p>
              Heart rate, skin temperature, dry-bulb room temperature, relative humidity, and pedal watts, plus age and
              body mass. Core temperature is never shown. Blank cells stay blank rather than zero-filled.
            </p>
            <p>
              The decision rule is fixed and printed in every prompt: pull now if core temperature 15 minutes from now
              would reach or exceed 38.5 °C, otherwise keep going at the current workload. Single-turn tasks run with
              no tools, browsing, or retrieval, a 131,072-token output budget, provider-default temperature, and the
              reasoning effort recorded in the roster (<code>max</code> for ten models, <code>xhigh</code> for one,{" "}
              <code>high</code> for three). All 14 models saw identical prompts in a single trial run on November 7–8,
              2026 through OpenRouter.
            </p>
          </div>

          <div className="writeup-sec" id="tasks">
            <h3>What each task tests</h3>

            <h4>Keep going or pull him? — 12 cases</h4>
            <p>
              Twelve people at the point where a medic has to decide, split into four matched designs of three. In{" "}
              <strong>falling power, core still rising</strong>, the soldier has eased off the pedals but core
              temperature keeps climbing through 38.5 °C: thermal lag, the textbook trap. In{" "}
              <strong>steady power, core rising</strong>, nothing changes in the workload and core quietly crosses the
              cutoff. In <strong>falling power, actually safe</strong>, the slowdown really does keep the soldier under
              38.5 °C. In <strong>steady power, actually safe</strong>, the soldier is hot, working hard, and stays safe.
              The first two designs catch a model that trusts falling watts; the last two catch a model that pulls
              anyone who looks warm. Always-pull, always-keep, and &quot;power dropped, so he is cooling&quot; each
              score 50% (6 of 12). A thirteenth case where core had already peaked and fallen is kept in the repo as an
              edge check and left out of the scored index.
            </p>

            <h4>Rulebook versus body — 2 cases</h4>
            <p>
              Each case has two halves. First, the model must recite the TB MED 507 (12 April 2022) prescription for
              Moderate work at Yellow Flag across four cells: work/rest minutes per hour, water per hour,
              continuous-work limit, and continuous-work water. The 2022 answer is <code>NL</code>,{" "}
              <code>0.75 qt/h</code>, <code>NL</code>, <code>1 qt/h</code>; the superseded 2003 card said{" "}
              <code>40/20</code>. Second, the model must decide whether to <code>FOLLOW</code> that unit-level card for
              this soldier over the next 15 minutes or <code>OVERRIDE</code> it and pull now. <strong>RB-01</strong> is
              the trap: steady 195 W, heart rate drifting only from the high 140s to the high 150s, nothing alarming in
              the wearable, and a measured core already at 38.40 °C that reaches 38.92 °C. Override is right.{" "}
              <strong>RB-02</strong> is the control: 122 W with heart rate at 169 to 180 bpm, an alarming wearable
              trace, and a core that only moves from 38.22 to 38.36 °C. Follow is right. A model that overrides whenever
              the prompt mentions heat gets one of two.
            </p>

            <h4>Beat ECTemp — 7 hidden person-cases</h4>
            <p>
              The one agentic task. Each model gets a sandbox with labeled training data from the public cohort,
              label-free development requests, and a transparent ECTemp-style sequential filter (heart rate, skin
              temperature, and watts; inspired by Buller et al., 2013). It has 1,200 wall seconds and 64 turns per
              session to write a causal <code>predict(request)</code> returning a mean and a 90% interval. Variant 3A
              forecasts core temperature 15 minutes ahead at every minute after the first watts drop; Variant 3B
              estimates current core temperature at every minute. Once the session closes, the frozen predictor runs on
              five people the model never saw (H06, H13, H18, H22, H25) against a frozen per-person baseline error. Only
              two of those five people ever drop watts, giving two person-cases in 3A and five in 3B.
            </p>
          </div>

          <div className="writeup-sec" id="scoring">
            <h3>Evaluation and scoring</h3>
            <p>
              SoldierPhysio reports two complementary signals: a deterministic outcome score and a criterion review of
              each decision&apos;s stated reason. The first measures whether the call was right; the second examines
              whether the model could justify its call from what it was shown. The key takeaways draw on saved reasoning and final answers alongside deterministic code grades.
            </p>

            <h4>Deterministic outcome score</h4>
            <p>
              The outcome score is computed directly from the saved response and measured rectal temperature. It uses no
              LLM, network calls, or randomness, so re-scoring the saved outputs reproduces every number on this page.
              Unit tests verify that:
            </p>
            <ul>
              <li>the measured outcome scores 1.0 on every case;</li>
              <li>the superseded 2003 card value (<code>40/20</code>) fails the rulebook lookup;</li>
              <li>always-keep, always-pull, and the power-drop shortcut each score 50% on keep-or-pull and catch zero thermal-lag traps;</li>
              <li>equivalent surface forms such as <code>no limit</code> and <code>¾ qt/hr</code> pass normalization;</li>
              <li>a missing JSON key is never read as <code>NL</code>.</li>
            </ul>

            <table className="dt">
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Component</th>
                  <th>How it&apos;s scored</th>
                  <th>Why it&apos;s the right check</th>
                </tr>
              </thead>
              <tbody>
                {DIMS.map((d, i) => (
                  <tr key={i}>
                    <td className="s">{d[0]}</td>
                    <td>{d[1]}</td>
                    <td className="s">{d[2]}</td>
                    <td className="s">{d[3]}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <h4>How the grader works</h4>
            <p>
              The deterministic score measures whether the call matched the body or the manual. The grader checks why
              the model made the call. It uses <code>{data.judge}</code>, a model outside the evaluated roster, and never
              decides whether a clinical call or card lookup was right:
            </p>
            <ol>
              <li>
                <strong>Compute the verified outcome:</strong> code calculates the true rectal temperature, the
                model&apos;s exact error, and whether its decision matched ground truth.
              </li>
              <li>
                <strong>Build the evidence packet:</strong> pair the model&apos;s final answer with the verified outcome
                block and the task rubric. Tool history, intermediate scratchpads, and model identity are stripped.
              </li>
              <li>
                <strong>{data.judge} judges:</strong> one structured JSON call at high reasoning effort. It scores the
                reasoning in light of the verified outcome and must quote the exact passages it is scoring.
              </li>
              <li>
                <strong>Validate &amp; store:</strong> malformed verdicts are rejected and retried up to 2 times, and
                the judgment is saved beside the raw answer.
              </li>
            </ol>

            <p>The judge follows five rules:</p>
            <ul>
              <li>Read the code-verified outcome first and never alter any number in it.</li>
              <li>Judge only the final answer text. Length, tool logs, and model identity do not count.</li>
              <li>Do not invent evidence. Missing sensor cells are unknown, not normal, and forecasts are not observations.</li>
              <li>Wrong conclusions are capped: a wrong decision scores at most 1, its reasoning at most 2, and a predictor that lost to the baseline caps its explanation at 3 unless it flagged the risk up front.</li>
              <li>Return <code>not_scorable</code> when required material is missing; a grader error is never a zero.</li>
            </ul>

            <p>
              <strong>Reliability and human review.</strong> During resumed runs, 32 answers were independently judged
              between two and seventeen times. On identical answers the judge gave the exact same decision mark on 100%
              of 728 pairs, the same reasoning mark on 99% of 766 pairs (never differing by more than 1 point), the same
              override mark on 97% of 38 pairs, and the same research mark on 100% of 14 pairs. Its decision mark agreed
              with the code grader on all 305 decisions: every code-wrong call got 0 or 1, and every code-right call got
              3 to 5. I checked the judge&apos;s prompt, rubrics, and verdicts on saved answers myself, and an outside
              reviewer I met recently, kept anonymous here, also vetted it. Those checks were qualitative reviews rather
              than a scored inter-rater study.
            </p>

            <h4>Published all-model score</h4>
            <p>The leaderboard combines the task scores with frozen weights:</p>
            <div className="formula-box">keep/pull score = 0.40 × decision + 0.30 × forecast + 0.30 × reasoning</div>
            <div className="formula-box">rulebook score = 0.30 × table lookup + 0.40 × override + 0.30 × reasoning</div>
            <div className="formula-box">beat ECTemp score = 0.60 × hidden MAE score + 0.40 × explanation</div>
            <div className="formula-box">all-model index = (keep/pull + rulebook + beat ECTemp) / 3</div>
            <p className="note" style={{ marginBottom: 18 }}>
              Averaging the three task scores keeps the 12-case keep/pull task from drowning out the rulebook and
              research tasks. Missing or content-filtered answers score 0 on every component.
            </p>

            <div className="fig">
              <TaskScores />
              <p className="note">Index is the mean of the three task scores on a 0–1 scale. Amber marks the best value in each column.</p>
            </div>
          </div>

        </div>
      </section>

      <section className="block rise" id="leaderboard" style={{ "--d": "220ms" } as React.CSSProperties}>
        <Board />
      </section>

      <CaseResults />

      <section className="block" id="findings">
        <h2>Key takeaways</h2>
        <p className="sub">A closer look at individual saved reasoning traces and final answers. These examples illustrate how models approached particular cases; they do not establish a general tendency across all runs. Some providers expose summaries or encrypted reasoning instead of a complete trace.</p>

        <Finding n={1} title="The same cooling signal led to opposite calls">
          <p>In KG-04, both Sonnet 5.5 and Opus 5 considered falling skin temperature alongside a roughly 10 bpm rise in heart rate at constant workload. Sonnet’s visible reasoning treated the heart-rate drift as the stronger signal in a borderline case; Opus treated cooling below ambient as evidence that core temperature was leveling off.</p>
          <p>Sonnet forecast 38.7 °C and pulled; Opus forecast 38.3 °C and kept going. The measured outcome was 39.14 °C. The contrast is in how they weighed the same observations, not evidence that skin temperature alone determines core temperature.</p>
          <p className="note"><a href="/traces/#4-keep_going-KG-04">Sonnet 5.5 trace</a> · <a href="/traces/#12-keep_going-KG-04">Opus 5 trace</a></p>
        </Finding>

        <Finding n={2} title="A remembered rule became a ‘confirmed’ rule">
          <p>In Grok 4.6’s visible reasoning summary for RB-02, it recalled a 40/20 work-rest cycle, then described that value as confirmed while continuing to work through which table applied. Its final answer repeated 40/20. The 2022 card’s expected work-rest entry for this case is no limit.</p>
          <p>The model did correctly choose FOLLOW for this soldier, whose measured future core temperature stayed below the threshold. Getting the individual decision right did not mean its recalled table entry was right. The saved summary does not establish an external lookup.</p>
          <p className="note"><a href="/traces/#9-rulebook_vs_body-RB-02">Grok 4.6 trace</a></p>
        </Finding>

        <Finding n={3} title="An invented time limit became part of the decision">
          <p>In RB-01, DeepSeek V4.1 Flash’s visible reasoning explored several possible heat-chart values and expressed uncertainty about the continuous-work limit. Its final answer settled on a 60-minute limit, then used the soldier’s 44 minutes of work to argue that another 15 minutes remained within it.</p>
          <p>The expected 2022 continuous-work entry was no limit, and the case’s decision rule depended on predicted core temperature, not remaining time under that invented limit. DeepSeek forecast 38.4 °C and chose FOLLOW; the measured future core was 38.92 °C, requiring OVERRIDE.</p>
          <p className="note"><a href="/traces/#6-rulebook_vs_body-RB-01">DeepSeek trace</a></p>
        </Finding>
      </section>

      <section className="block" id="limits">
        <h2>Limits and reproduction</h2>
            <ul>
              <li>
                <strong>One trial per case.</strong> Model outputs vary run to run. The pooled failure counts (18 of 28
                old-card lookups, 53 needless pulls in 168 calls, 21 of 23 overrides) are much larger than single-run
                noise, but 2–3 point gaps between adjacent models on the leaderboard are not.
              </li>
              <li>
                <strong>21 frozen cases.</strong> Twelve keep-or-pull calls, two rulebook cases on the Moderate / Yellow
                Flag cell, and seven hidden person-cases across five held-out subjects.
              </li>
              <li>
                <strong>Chamber cycling vs. field kit.</strong> D&apos;Lugos et al. (2025) tested civilians on a bike in
                a chamber, not soldiers under armor and rucks. Nothing here validates a clinical device.
              </li>
              <li>
                <strong>Public workbook.</strong> The Figshare dataset is public, though tools were off on single-turn
                tasks and 55% triage accuracy rules out memorized lookup.
              </li>
              <li>
                <strong>Wall-clock cutoffs on Beat ECTemp.</strong> Sessions that hit 1,200 seconds before writing an
                explanation kept their saved predictor score (60%) and took 0 on the explanation (40%).
              </li>
            </ul>
            <p style={{ marginTop: 16 }}>
              <strong>Reproduce in 10 seconds (no API key):</strong> from a clean Python 3.13 environment, run{" "}
              <code>pip install -r requirements.txt</code> and{" "}
              <code>python -m eval_suite.report_leaderboard --root results/rerun-20261107</code>. To evaluate a new
              model from scratch, run{" "}
              <code>python -m eval_suite run --model &lt;openrouter-id&gt; --tasks all --spend-cap-usd 5</code>; a full
              run takes up to 45 minutes, and all 14 models plus the judge cost ${data.total_usd.toFixed(2)}.
            </p>
      </section>
    </div>
  );
}
