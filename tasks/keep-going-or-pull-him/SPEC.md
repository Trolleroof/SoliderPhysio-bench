# Keep going or pull him?

Status: historical design notes. Current implementation and data contract: [README](../keep_going/README.md). Run with `python -m eval_suite run`; runtime readiness is checked by preflight.

Give the model an anonymized measured trace up to a cutoff: heart rate, skin
temperature, environment, workload in watts and permitted demographics. Hide
the core thermometer and future observations. Ask for a core-temperature
forecast at +15 minutes and a benchmark decision label: continue, slow, or
stop/cool. Include falling-power/rising-temperature cases and genuine controls.

The recovered plan proposed three cases of this task type. Freeze cases,
cutoffs and answer keys before inference. The source data are civilian
heat-chamber cycling measurements, not measured soldier field data.

Numerical forecasts can be graded against the measured thermometer. Operational
decision labels require a separately validated, explicit rubric: temperature
alone must not silently define every real-world intervention. That rubric is
not yet frozen.

Required before running: causal case exports, person/case separation, validated
decision labels, deterministic graders and correct/broken-control tests.
Public-data exposure and memorization risks remain disclosed; anonymization
does not establish an untouched test.
