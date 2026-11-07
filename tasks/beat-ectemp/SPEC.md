# Beat ECTemp

Status: preserved design; baseline, data export, runner and grader are not implemented.

Give the model measured training data, a verified ECTemp baseline, a public
development scorer and a 20-minute offline CPU research budget. It must build
an executable core-temperature predictor and submit a frozen artifact selected
using development evidence. The recovered plan proposed two cases of this type.

Use whole-person train/development/test partitions. Development labels and all
hidden records stay outside the participant workspace. The historical cycling
14/5/5 split is a starting point for auditing, not proof that previously
inspected test people are unexposed. Workload/history inputs and prediction
horizons need a new explicit causal contract.

Compare against ECTemp on predeclared measured slices: elevated temperature
(the proposed research slice was above 38.5 C), falling workload and appropriate
controls. Freeze slice definitions, aggregation and reference validity before
inference. These are research evaluation definitions, not medical-action
thresholds. Grade validity, prediction error and uncertainty explicitly.

Required before running: verified baseline equations/initialization and tests,
a workload-inclusive causal data export, person-separated scorers, valid/broken
controls, bounded offline execution and immutable submission/replay. Test
time-only shortcuts directly: shifting a clock does not by itself prove they
are removed, and must not alter ground-truth physiology labels arbitrarily.
