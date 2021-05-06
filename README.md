# Upper limits with finite memory

Freely allocate memory, and let the operating systems clean up.

This is an efficient design pattern for short-lived programs;
to track and free memory oneself is duplication of effort.

RooStats and its HistFitter extensions operate under this design.
We must therefore ensure short lives to our programs using them.

We execute leaky code to simulate small batches of toys in a
pool of processes which frees resources after each batch.


## Usage

Set up your normal HistFitter environment.

Point `upper_limit_results.py` to your discovery workspace.

Make upper limit results with `invert` and discovery p-values with `test`.

Make plots and tables with with `output` with results combined by `-load`.


## Examples

### Toys
```bash
./upper_limit_results.py invert test \
-filename results/disc1/Discovery_DRInt_combined_NormalMeasurement_model.root \
-prefix results/disc1/example \
-poi mu_Discovery \
-lumi 139 \
-points 0 30 6 \
-ntoys 3000 \
-nbatch 100 \
-seed 1
```

... optionally make more with different `-prefix` and `-seed` ...

```bash
./upper_limit_results.py output \
-prefix results/disc1/example \
-load results/disc1/example*_dump.pickle \
-poi mu_Discovery \
-lumi 139 \
-channel DRInt
```

### Asymptotics
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


## Help
```
usage: upper_limit_results.py [-h] [-lumi LUMI] [-prefix PREFIX]
                              [-load [LOAD [LOAD ...]]] [-filename FILENAME]
                              [-workspace WORKSPACE] [-poi POI]
                              [-points START STOP COUNT] [-ntoys NTOYS]
                              [-seed SEED] [-nbatch NBATCH]
                              [-processes PROCESSES] [-calculator CALCULATOR]
                              [-statistic STATISTIC] [-channel CHANNEL]
                              [-cl CL] [-splusb]
                              operation [operation ...]

Interpret discovery fit workspaces.

positional arguments:
  operation             instructions from {invert output test}; `invert' scans
                        for upper limits; `test' samples for the discovery
                        p-value; `output' dumps the plots and table

optional arguments:
  -h, --help            show this help message and exit
  -lumi LUMI            luminosity in inverse femtobarns
  -prefix PREFIX        output file paths' prefix
  -load [LOAD [LOAD ...]]
                        filenames of pickled results from previous runs of
                        `invert or `test'; to combine for `output'
  -filename FILENAME    file path from which to get the workspace
  -workspace WORKSPACE  workspace name to get from the input file
  -poi POI              parameter of interest name in the workspace
  -points START STOP COUNT
                        linear spacing of poi points; for `invert'
  -ntoys NTOYS          number of toys to simulate
  -seed SEED            random seed in [0, 2**16); make yours unique; if None,
                        we use a mix of time and process id
  -nbatch NBATCH        batch size for toys. Reduce to cut memory usage
  -processes PROCESSES  maximum number of processes for generating toys; also
                        capped by your cpu count
  -calculator CALCULATOR
                        calculator type in {frequentist, hybrid, asymptotic,
                        asimov}; see bailed_roostats.CalculatorType;
                        frequentist is standard with toys; asymptotic is
                        standard without toys
  -statistic STATISTIC  test statistic type from bailed_roostats.TestStatistic
  -channel CHANNEL      channel name for the `output' tex table
  -cl CL                level for 'upper limits', in [0, 1]
  -splusb               use CLs+b for 'upper limits'; do not use CLs
```


## Absolution

Hypotheses compare through the relative likelihoods they assign to data.

A p-value is a cumulative distribution function evaluated at data; CLs is a
ratio of p-values.

Please present results of this software accurately and clearly.
Examples of false or unclear presentations of a p-value or CLs include:

 - as a probability that an hypothesis is true or false,
 - as a probability of compatibility with an hypothesis,
 - as a probability that data occurred at random, by chance, or by
   statistical fluctuation,
 - as a likelihood or importance of data,
 - as necessary for an optimal or rational decision rule.

Please also respect that the association of a p-value or CLs with and of the
words 'test', 'limit', 'confidence', 'significance', 'exclusion', 'evidence',
'observation' or 'discovery' is nominal, and does not correspond to the words'
meanings in English.
