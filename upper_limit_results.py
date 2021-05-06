#!/usr/bin/env python
"""
Generate "upper limit" results for discovery analyses.

Uses bailed_roostats.py to work around egregious memory leaks.

This script executes in three operations:

    invert:
        Prepare "HypoTestInverterResult" by evaluating statistics at an array
        of parameter-of-interest points.
    test:
        Prepare "HypoTestResult" by evalulating statistics at null values.
    output:
        Dump plots and results table.

Results from `invert' and `test' are serialized.

Combine serialized results with the -load argument.


# Example using asymptotic approximation

./upper_limit_results.py invert test output \
-filename results/disc1/Discovery_DRInt_combined_NormalMeasurement_model.root \
-prefix results/disc1/example_asym \
-poi mu_Discovery \
-lumi 139 \
-channel DRInt \
-points 0 30 6 \
-calculator asymptotic


# Example using toys

./upper_limit_results.py invert test \
-filename results/disc1/Discovery_DRInt_combined_NormalMeasurement_model.root \
-prefix results/disc1/example \
-poi mu_Discovery \
-lumi 139 \
-points 0 30 6 \
-ntoys 3000 \
-nbatch 100 \
-seed 1


./upper_limit_results.py output \
-prefix results/disc1/example \
-load results/disc1/example*_dump.pickle \
-poi mu_Discovery \
-lumi 139 \
-channel DRInt


# Help

./upper_limit_results.py -h


# Absolution

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

Please also respect that the association of a p-value or CLs with the words
'test', 'limit', 'confidence', 'significance', 'exclusion', 'evidence',
'observation' or 'discovery' is nominal, and may not reflect the words' meanings
in English.

Rupert Tombs 2021

"""
from __future__ import print_function, division

import argparse
import bisect
import enum
import logging
import multiprocessing
import os
import time
import pickle

# ROOT imports are deferred to stop it clobbering our -h help menu.

LOGGER = logging.getLogger("upper_limit_results")
logging.basicConfig(level=logging.INFO)



# Types

class Operation(enum.Enum):
    """ We make HypoTest inversion results, HypoTest results, and output. """
    # Produce a HypoTestInverterResult over parameter points.
    invert = "invert"
    # Produce a HypoTestResult.
    test = "test"
    # Output plots and tables from previous results.
    output = "output"

OPERATIONS = " ".join(op.name for op in Operation)



# Core functions

def main():
    """ Interpret the user's incantations. """
    parser = argparse.ArgumentParser(
        description="Make plots and tables for discovery fit statistics.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        argument_default=argparse.SUPPRESS,
    )

    parser.add_argument("operations", type=Operation, nargs="+",
                        help="instructions from {%s}; " % OPERATIONS +
                             "`invert' scans for upper limits; "
                             "`test' samples for the discovery p-value; "
                             "`output' dumps the plots and table")
    parser.add_argument("-lumi", type=float,
                        help="luminosity in inverse femtobarns")
    parser.add_argument("-prefix", type=str,
                        help="output file paths' prefix")
    parser.add_argument("-load", type=str, nargs="*", default=[],
                        help="filenames of pickled results from previous runs "
                             "to combine; for `output'")
    parser.add_argument("-filename", type=str,
                        help="workspace file path")
    parser.add_argument("-workspace", type=str, default="combined",
                        help="workspace name in its file")
    parser.add_argument("-poi", type=str, default="mu_SIG",
                        help="parameter of interest name")
    parser.add_argument("-points", type=float, nargs=3, default=[0.0, 40.0, 20],
                        metavar=("START", "STOP", "COUNT"),
                        help="inclusive linear spacing of poi points; "
                             "for `invert'")
    parser.add_argument("-ntoys", type=int, default=3000,
                        help="number of toys to simulate")
    parser.add_argument("-seed", type=int, default=None,
                        help="random seed in [0, 2**16); make yours unique; "
                             "if None, we use a mix of time and process id")
    parser.add_argument("-nbatch", type=int, default=10,
                        help="batch size for toys; reduce to cut memory usage")
    parser.add_argument("-processes", type=int, default=16,
                        help="maximum number of processes for generating toys; "
                             "also capped by your cpu count")
    parser.add_argument("-calculator", type=str, default="frequentist",
                        help="calculator type in "
                             "{frequentist, hybrid, asymptotic, asimov}; "
                             "see bailed_roostats.CalculatorType; "
                             "frequentist is standard with toys; "
                             "asymptotic is standard without toys")
    parser.add_argument("-statistic", type=str,
                        default="profile_likelihood_one_sided",
                        help="test statistic type "
                             "from bailed_roostats.TestStatistic")
    parser.add_argument("-channel", type=str, default="DR-WHO",
                        help="channel name for the tex table")
    parser.add_argument("-cl", type=float, default=0.95,
                        help="level for 'upper limits', in (0, 1)")
    parser.add_argument("-use_cls", type=bool, default=True,
                        help="use CLs for limits; if false use CLs+b")

    args = parser.parse_args()

    # Prepare arguments.
    assert args.lumi > 0
    assert 0 < args.cl < 1
    assert args.points[2] == int(args.points[2]), "count must be integral"
    args.points[2] = int(args.points[2])
    args.processes = min(multiprocessing.cpu_count(), args.processes)
    assert args.processes > 0

    if args.seed is None:
        args.seed = make_seed()

    from bailed_roostats import CalculatorType, TestStatistic

    args.calculator = CalculatorType[args.calculator]
    args.statistic = TestStatistic[args.statistic]

    execute(args)


def execute(args):
    """ Run our operations for given args namespace, as produced by main(). """
    from bailed_roostats import root_dumps

    do_invert = Operation.invert in args.operations
    do_test = Operation.test in args.operations
    do_output = Operation.output in args.operations

    # Prepare and dump new results.
    if do_invert:
        invert_result = invert(args)
        invert_result_dumps = root_dumps(invert_result)
    else:
        invert_result = None
        invert_result_dumps = None

    if do_test:
        test_result = test(args)
        test_result_dumps = root_dumps(test_result)
    else:
        test_result = None
        test_result_dumps = None

    if do_invert or do_test:
        dump(args, (args.seed, invert_result_dumps, test_result_dumps))

    if do_output:
        output(args, invert_result, test_result)


def invert(args):
    """ Return a HypoTestInverterResult for args. """
    from bailed_roostats import hypo_test_inversion

    return hypo_test_inversion(
        args.filename,
        args.workspace,
        args.poi,
        args.points,
        args.ntoys,
        args.seed,
        batch_size=args.nbatch,
        processes=args.processes,
        calculatorType=args.calculator,
        testStatType=args.statistic)


def test(args):
    """ Return a HypoTestResult for args. """
    from bailed_roostats import hypo_test, FitType

    # Flip some seed bits to give different context from `invert'.
    test_seed = args.seed ^ 0b101101

    return hypo_test(
        args.filename,
        args.workspace,
        args.ntoys,
        test_seed,
        FitType.discovery,
        batch_size=args.nbatch,
        processes=args.processes,
        calculatorType=args.calculator,
        testStatType=args.statistic)


def dump(args, content):
    """ Dump content to a pickle. """
    filename = args.prefix + "_dump.pickle"
    with open(filename, "wb") as file_:
        pickle.dump(content, file_)


def output(args, invert_result, test_result):
    """ Output plots and tables. """
    import ROOT
    from bailed_roostats import CalculatorType, TOY_CALCULATORS

    # Load results from previous runs.
    invert_result, test_result = extend(args, invert_result, test_result)

    # Log result points and ntoys
    if args.calculator in TOY_CALCULATORS:
        LOGGER.info("HypoTestInverterResult: %s", invert_result )
        LOGGER.info("i,x,nulltoys,alttoys")
        for i in range(invert_result.ArraySize()):
            result_i = invert_result.GetResult(i)
            nulltoys = result_i.GetNullDistribution().GetSize()
            alttoys = result_i.GetAltDistribution().GetSize()
            LOGGER.info("%d,%g,%d,%d",
                        i, invert_result.GetXValue(i), nulltoys, alttoys)

        LOGGER.info("HypoTestResult: %s", test_result)
        LOGGER.info("nulltoys,alttoys")
        nulltoys = test_result.GetNullDistribution().GetSize()
        alttoys = test_result.GetAltDistribution().GetSize()
        LOGGER.info("%d,%d", nulltoys, alttoys)

    if invert_result is None:
        raise ValueError("No `invert' result loaded.")
    if test_result is None:
        raise ValueError("No `test' result loaded.")

    # Inversion
    # Exclusion cleanup (errors if not asymptotic calculator)
    if args.calculator is CalculatorType.asymptotic:
        nremoved = invert_result.ExclusionCleanup()
        if nremoved > 0:
            LOGGER.warning("Removed %r points in ExclusionCleanup.", nremoved)

    # Find 'upper limit' on 'N_obs' (where N is a mean, not a count), by linear
    # interpolation to the poi where where its Y value meets our cl value.
    # The Y values are either CLs or CLs+b, depending on a flag.
    invert_result.UseCLs(args.use_cls)
    invert_result.SetConfidenceLevel(args.cl)
    invert_result.SetInterpolationOption(invert_result.kLinear)
    # UpperLimit ignores settings until FindInterpolatedLimit is called.
    visobs = invert_result.FindInterpolatedLimit(1 - args.cl)
    assert visobs == invert_result.UpperLimit()
    visxsec = visobs / args.lumi

    # Expected upper limit with errors
    visexp = invert_result.GetExpectedUpperLimit(0)
    visexp_up = invert_result.GetExpectedUpperLimit(1)
    visexp_down = invert_result.GetExpectedUpperLimit(-1)

    xs = sorted(map(invert_result.GetXValue, range(invert_result.ArraySize())))

    if xs[0] <= visobs < xs[-1]:
        # if visobs == xs[0], this returns 1
        ihi = bisect.bisect_right(xs, visobs)
        xhi = xs[hi]
        xlo = xs[hi - 1]

        bhi = invert_result.CLb(ihi)
        blo = invert_result.CLb(ihi - 1)

        alpha = (bhi - blo) / (xhi - xlo)
        beta = bhi - alpha*xhi
        clb = alpha*visobs + beta
    else:
        LOGGER.warning("Upper limit %r out of range of poi values [%r ... %r]; "
                       "setting CLb to 0.", visobs, xs[0], xs[-1])
        clb = 0.0

    # Dump plots
    # Ignore the `npoints' variable name. It is a flag which sets the file name
    # to include "auto" if npoints < 0 else "grid".
    npoints = 1
    outplotname = "%s_%s" % (args.prefix, args.poi)
    ROOT.RooStats.AnalyzeHypoTestInverterResult(
        invert_result,
        args.calculator.value,
        args.statistic.value,
        args.use_cls,
        npoints,
        outplotname,
        ".pdf",
    )
    plotnames = os.path.dirname(outplotname) + "/*" + os.path.basename(outplotname)
    LOGGER.info("Wrote upper limit plots '%s*.pdf'.", plotnames)

    # Test
    nullp = test_result.NullPValue()

    # Tabulate
    table = textable(
        args.channel,
        args.cl,
        args.use_cls,
        args.statistic,
        args.calculator,
        visobs,
        visxsec,
        visexp,
        visexp_up,
        visexp_down,
        clb,
        nullp,
    )

    # Dump table
    outfilename = "%s_upper_limit_table_%s.tex" % (args.prefix, args.channel)

    with open(outfilename, "w") as file_:
        file_.write(table)
    LOGGER.info("Wrote upper limit table %r", outfilename)


def extend(args, invert_result, test_result):
    """ Load previous results into invert_result and test_result. """
    from bailed_roostats import root_loads

    seed_to_filename = {}

    for filename in args.load:
        with open(filename, "rb") as file_:
            seed, invert_extra, test_extra = pickle.load(file_)

        if seed in seed_to_filename:
            raise ValueError("Seed `%d' reused in inputs %r and %r."
                             % (seed, seed_to_filename[seed], filename))

        seed_to_filename[seed] = filename

        if invert_extra is not None:
            if invert_result is None:
                invert_result = root_loads(invert_extra)
            else:
                invert_result.Add(root_loads(invert_extra))

        if test_extra is not None:
            if test_result is None:
                test_result = root_loads(test_extra)
            else:
                test_result.Append(root_loads(test_extra))

    return invert_result, test_result


def textable(
        channel,
        cl,
        use_cls,
        statistic,
        calculator,
        visobs,
        visxsec,
        visexp,
        visexp_up,
        visexp_down,
        clb,
        nullp):
    """ Return a string tex table displaying configuration and and results. """
    import ROOT
    from bailed_roostats import TestStatistic, CalculatorType

    level = int(100 * cl)
    assert level == 100 * cl
    assert 0 <= level <= 100
    channel = channel.replace("_", "\\_")

    # Header
    table = (
        r"\begin{table}\n "
        r"\centering\n "
        r"\setlength{\tabcolsep}{0.0pc}\n "
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lccccc}\n "
        r"\noalign{\smallskip}\hline\noalign{\smallskip}\n "
        r"{\bf Signal channel} & "
        r"$\langle\epsilon{\rm \sigma}\rangle_{\rm obs}^{%d}$[fb] & " % level +
        r"$S_{\rm obs}^{%d}$ & " % level +
        r"$S_{\rm exp}^{%d}$ & " % level +
        r"$\mathrm{CL_b}$ &\n "
        r"$p(s=0)$ ($Z$) \\\n "
        r"\noalign{\smallskip}\hline\noalign{\smallskip}\n "
    )

    # Channel row
    errup = visexp_up - visexp
    errdown = visexp_down - visexp
    nullpcap = min(nullp, 0.5)
    significancecap = ROOT.StatTools.GetSigma(nullpcap)

    table += (
        r"%s & " % channel +
        r"$%.2f$ & " % visxsec +
        r"$%.1f$ & " % visobs +
        r"$%.1f^{%+.1f}_{%+.1f}$ & " % (visexp, errup, errdown) +
        r"$%.2f$ & " % clb +
        r"$%.2f~(%.2f)$ \\\n " % (nullpcap, significancecap)
    )

    # Footer
    if use_cls:
        prescription = r"$\mathrm{CL_s}$"
    else:
        prescription = r"$\mathrm{CL_{s + b}}$"

    # Test statisric text; meaning taken from RooStats docs and source code.
    if statistic is TestStatistic.simple_likelihood_ratio:
        statistic_text = (r"All results use the simple likelihood ratio "
                          r"test statistic. ")
    elif statistic is TestStatistic.profile_likelihood_ratio:
        statistic_text = (r"All results use the profile likelihood ratio "
                          r"test statistic.")
    elif statistic is TestStatistic.profile_likelihood:
        statistic_text = (r"All results use the profile likelihood "
                          r"test statistic.")
    elif statistic is TestStatistic.profile_likelihood_one_sided:
        statistic_text = (r"Upper limits use the one-sided profile likelihood "
                          r"test statistic;\n "
                          r"the discovery p-value uses a profile likelihood "
                          r"test statistic in a one-sided test.")
    else:
        raise ValueError("statistic must be in bailed_roostats.TestStatistic; "
                         "got %r" % statistic)

    # Calculator text; meaning taken from RooStats docs
    if calculator is CalculatorType.frequentist:
        calculator_text = (
            r"sampling the test statistic distribution with nuisance "
            r"parameters at their best-fit values"
        )
    elif calculator is CalculatorType.hybrid:
        calculator_text = (
            r"sampling the test statistic distribution with nuisance  "
            r"parameters sampled from prior distributions"
        )
    elif calculator is CalculatorType.asymptotic:
        calculator_text = (
            r"their asymptotic approximation"
        )
    elif calculator is CalculatorType.asimov:
        calculator_text = (
            r"their asymptotic approximation with Asimov data obtained with "
            r"nuisance parameters set to their nominal values"
        )
    else:
        raise ValueError("calculator must be in bailed_roostats.CalculatorType; "
                         "got %r" % calculator)

    table += (
        r"\noalign{\smallskip}\hline\noalign{\smallskip}\n "
        r"\end{tabular*}\n "
        r"\caption{\n "
        r"Model-independent fit results.\n "
        r"Left to right: the observed "
        r"%d\%% upper limit on the visible cross-section\n " % level +
        r"$\langle\epsilon\sigma\rangle_{\rm obs}^{%d}$,\n " % level +
        r"its corresponding signal expectation "
        r"$S_{\rm obs}^{%d}$,\n " % level +
        r"expected %d\%% upper limits on the signal expectation " % level +
        r"$S_{\rm exp}^{%d}$ as would be obtained\n " % level +
        r"were the data the background expectation or its "
        r"$\pm 1\sigma$ variations,\n "
        r"$\mathrm{CL_b}$ evaluated with the "
        r"signal expectation set to its observed upper limit,\n "
        r"and the discovery $p$-value $p(s = 0)$ capped at 0.5,\n "
        r"with its equivalent significance.\n "
        r"Limits use the %s prescription.\n " % prescription +
        r"%s\n " % statistic_text +
        r"All p-values are estimated by\n %s.\n " % calculator_text +
        r"}\n "
        r"\label{tab:results.discoxsec.%s}\n " % channel +
        r"\end{table}\n"
    )
    return table.replace("\\n\\", "\n\\").replace(r"\n ", "\n")


def make_seed():
    """ Return seed in [0, 2**16) using process id and time.

        In sequence, times will differ.
        In parallel, process ids will differ.

        Only 16 bits is pathetic, but TRandom3.SetSeed only uses the low 32 bits
        of its argument and we reserve the others for batched execution.
    """
    hash_ = hash((0xd1ce, os.getpid(), time.time()))
    hash_ ^= hash_ >> 32
    hash_ ^= hash_ >> 16
    return hash_ & (2**16 - 1)


if __name__ == "__main__":
    main()
