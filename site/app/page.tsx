import { Board } from "@/components/Board";
import { Scatter } from "@/components/Scatter";
import { RulebookBars } from "@/components/RulebookBars";
import { KeepPull } from "@/components/KeepPull";
import { CostByTask } from "@/components/CostByTask";
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
  const total = data.model_usd, research = data.research_usd, single = data.single_turn_usd;
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

      <section className="block rise" id="leaderboard" style={{ "--d": "220ms" } as React.CSSProperties}>
        <Board />
      </section>

      <section className="block" id="cost">
        <div className="block-head"><h3>Score against cost</h3><span className="label">14 models · 21 cases</span></div>
        <Scatter />
        <p className="note">Provider-reported USD to answer all 21 cases, log scale.</p>
      </section>

      <section className="block" id="findings">
        <h2>Key findings</h2>
        <p className="sub">
          Each of the 14 models answered the same 21 cases. Code checked every answer against the real measured
          temperature, the 2022 heat chart, or the Army&apos;s existing formula. Each finding below says what happened,
          then gives our best guess at why. The &quot;why&quot; parts are educated guesses, not things we proved.
        </p>

        <Finding n={1} title="models quote an old version of the Army heat chart">
          <p>
            The Army updated its heat chart in 2022. We asked about one specific situation: a medium-hot day (a
            &quot;yellow flag&quot; day) with medium-effort work. The 2022 chart says there is <strong>no time
            limit</strong> on work for that situation. The old 2003 chart said 40 minutes of work, then 20 minutes of
            rest. The question told the models to use the 2022 chart, yet <strong>18 of 28 answers gave the old
            40/20.</strong> Only 3 got it right. Many answers also made up a work time limit that does not exist on the
            new chart, or gave the wrong amount of water. A medic holding the current chart would get this right every
            time. The models answer in the right format and sound confident, but they are reading from the wrong
            edition. (Fable 5 and Opus 5.5 refused to answer these questions, so they scored zero.)
          </p>
          <p>
            <strong>Why this probably happens:</strong> the 2003 chart was in use for almost 20 years, so it shows up
            all over the internet in training slides, websites, and old manuals. The 2022 update is newer and much less
            written about. The models most likely repeat the version they saw most often during training, even when
            told to use the new one.
          </p>
          <div className="fig"><RulebookBars /></div>
        </Finding>

        <Finding n={2} title="when unsure, models pull the soldier">
          <p>
            On keep-or-pull, the models were right <strong>92 of 168 times (55%)</strong>. That is barely better than
            flipping a coin. The mistakes mostly went one way. Of the 84 cases where the soldier was actually safe, the
            models pulled 53 of them anyway. Two models (GPT-6 Astra and GPT-6.1 Terra) pulled every safe soldier,
            which is exactly the score you would get by pulling anyone who looks hot. Sonnet 5.5 was the exception: it
            kept every safe soldier going and got 10 of 12 right.
          </p>
          <p>
            <strong>Why this probably happens:</strong> AI models are trained to be extra careful with anything
            medical, so &quot;pull them, just to be safe&quot; feels like the responsible answer. But in the field,
            pulling is not free. Soldiers lose training time, and a tool that keeps raising false alarms teaches people
            to ignore it, right up until the time it matters.
          </p>
          <div className="fig"><KeepPull /></div>
        </Finding>

        <Finding n={3} title="they catch the textbook trap but miss the quiet danger">
          <p>
            There is a well-known trap called <strong>thermal lag</strong>. A soldier slows down, but their core
            temperature keeps rising for a while, like a car engine that stays hot after you turn it off. The models
            were good at this: <strong>34 of 42 calls were right</strong>. The dangerous misses happened somewhere
            else. 13 of the 20 missed pulls were soldiers working at a steady pace, with nothing
            dramatic in their heart rate, while their core slowly climbed past the limit. The models&apos; temperature
            guesses were also off by 0.2 to 0.4 °C on average, which is often enough to flip the decision.
          </p>
          <p>
            <strong>Why this probably happens:</strong> thermal lag is a textbook idea that shows up in a lot of
            writing, so the models know to look for it. A soldier who is slowly heating up at a steady pace has no
            obvious warning sign. Nothing in the data &quot;looks&quot; scary, so the models let it go.
          </p>
        </Finding>

        <Finding n={4} title="models break the rules no matter what the data says">
          <p>
            We gave the models a matched pair of cases. In the first, the sensors look calm, but the soldier is
            actually overheating (core already at 38.4 °C and rising), so the right move is to ignore the chart and
            pull them. In the second, the sensors look scary (heart rate 169 to 180), but the soldier is fine, so the
            right move is to follow the chart. <strong>Of 23 usable answers, 21 chose to ignore the chart in both
            cases.</strong> Only Grok 4.6 told the two apart.
          </p>
          <p>
            <strong>Why this probably happens:</strong> the question is about heat illness, and heat illness sounds
            dangerous, so the models react to the topic instead of the actual numbers in front of them. Choosing safety
            over the rulebook also sounds like the &quot;right&quot; thing to say.
          </p>
        </Finding>

        <Finding n={5} title="the coding task is the easy part">
          <p>
            In one task, each model got its own coding environment and about 20 minutes to build a tool that estimates
            core temperature from sensor data. It then had to beat the Army&apos;s existing formula (ECTemp, Buller et
            al., 2013) on people it had never seen. <strong>76 of 98 attempts beat the existing formula.</strong>{" "}
            Gemini 4 Argon beat it every time but still finished 11th overall, because it ran out of time before
            writing up its explanation, which cost it 40% of that task&apos;s score.
          </p>
          <p>
            <strong>Why this probably happens:</strong> coding and fitting data are the skills these models are
            trained on most. The hard part is not the math. It is field knowledge: knowing the current rules and when a
            hot soldier is actually fine.
          </p>
        </Finding>

        <Finding n={6} title="spending more does not buy a better medic">
          <p>
            Running all 21 cases cost <strong>$0.29 on the cheapest model (DeepSeek V4.1 Flash) and $29.54 on the most
            expensive (Fable 5.1)</strong>, about 100 times more. Hy4 cost $1.09 and still beat Fable 5.1. Of the $
            {total.toFixed(2)} spent on models, ${research.toFixed(2)} ({Math.round((research / total) * 100)}%) went to
            the coding task, where models already do well. The quick medic questions, where they struggle, cost only $
            {single.toFixed(2)} across all 14 models.
          </p>
          <p>
            <strong>Why this probably happens:</strong> paying more mostly buys longer &quot;thinking.&quot; But the
            models do not fail here because they did not think hard enough. They fail because they have the wrong
            version of the rules and lean too far toward pulling. More thinking does not fix either one.
          </p>
          <div className="fig"><CostByTask limit={6} /></div>
        </Finding>
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
              whether the model could justify its call from what it was shown. All six key findings above use only the
              deterministic code grades.
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

          <div className="writeup-sec" id="limits">
            <h3>Limits and reproduction</h3>
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
          </div>
        </div>
      </section>
    </div>
  );
}
