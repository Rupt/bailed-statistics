# Discovery / Upper Limits with finite memory

Freely allocate memory, and let the operating systems clean up.

This is an efficient design pattern for short-lived programs;
to track and free memory oneself is duplication of effort.

RooStats and its HistFitter extensions operate under this design.
We must therefore ensure short lives to our programs using them.

We execute leaky code to simulate small batches of toys in a
pool of processes which frees resources after each batch.


### Usage

Set up your normal HistFitter environment.

Point the `upper_limit_results.py` to your discovery workspace.

Make upper limit results with `invert`.

Make discovery p-values with `test`.

Combine results with `-load`.

Make plots and tables with with `output`.


### Examples

#### Toys
```bash
python upper_limit_results.py invert test \
-filename results/disc1/Discovery_DRInt_combined_NormalMeasurement_model.root \
-prefix results/disc1/example \
-poi mu_Discovery \
-lumi 139 \
-points 0 30 6 \
-ntoys 3000 \
-nbatch 100 \
-seed 1
```

```bash
python upper_limit_results.py output \
-prefix results/disc1/example \
-load results/disc1/example_dump.pickle \
-poi mu_Discovery \
-lumi 139 \
-channel DRInt
```

#### Asymptotic approximation
```bash
./upper_limit_results.py invert test output \
-filename results/disc1/Discovery_DRInt_combined_NormalMeasurement_model.root \
-prefix results/disc1/example_asym \
-poi mu_Discovery \
-lumi 139 \
-channel DRInt \
-points 0 30 6 \
-calculator asymptotic
```


#### Help
```
usage: upper_limit_results.py [-h] [-lumi LUMI] [-prefix PREFIX]
                              [-load [LOAD [LOAD ...]]] [-filename FILENAME]
                              [-workspace WORKSPACE] [-poi POI]
                              [-points POINTS POINTS POINTS] [-ntoys NTOYS]
                              [-seed SEED] [-nbatch NBATCH]
                              [-processes PROCESSES] [-calculator CALCULATOR]
                              [-statistic STATISTIC] [-cl CL] [-splusb]
                              [-channel CHANNEL]
                              operation [operation ...]

Interpret discovery fit workspaces.

positional arguments:
  operation             Operations from {invert output test} to perform.

optional arguments:
  -h, --help            show this help message and exit
  -lumi LUMI            Luminosity in inverse femtobarns.
  -prefix PREFIX        Output file paths' prefix.
  -load [LOAD [LOAD ...]]
                        Load results from previous runs of `invert or `test'
                        to combine for `output'.
  -filename FILENAME    Input ROOT workspace file path.
  -workspace WORKSPACE  Workspace name to TFile.Get from the input file.
  -poi POI              Parameter Of Interest name in the workspace.
  -points POINTS POINTS POINTS
                        (start, stop, count) to linearly space points; for
                        `invert'.
  -ntoys NTOYS          Number of toys to simulate.
  -seed SEED            Random seed in [0, 2**16); make yours unique. If None,
                        use a mix of time and process id.
  -nbatch NBATCH        Batch size for toys. Reduce to cut memory usage.
  -processes PROCESSES  Number of processes for generating toys. By default,
                        use min(cpu count, 16).
  -calculator CALCULATOR
                        Calculator type in {frequentist, hybrid, asymptotic,
                        asimov}; from bailed_roostats.CalculatorType.
                        frequentist is standard with toys. asymptotic is
                        standard without toys.
  -statistic STATISTIC  Test statistic type from
                        bailed_roostats.TestStatistic.
  -cl CL                Level for 'upper limits', in [0, 1].
  -splusb               Use CLs+b for 'upper limits'; do not use CLs.
  -channel CHANNEL      Channel name for `output' tex tables.
```