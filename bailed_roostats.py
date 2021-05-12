"""
# Wrap statistical tools to work around memory leaks.

Freely allocate memory, and let the operating systems clean up.
This is an efficient design pattern for short-lived programs.

To track and free memory oneself is duplication of effort.

RooStats and its HistFitter extensions operate under this design.
We must therefore ensure short lives to our programs using them.

We execute leaky code to simulate small batches of toys in a
`multiprocessing.Pool`, which frees resources after each batch.

Each batch executes with a unique random seed; the user must provide a unique
random seed for each call.


# Interface

Our primary tools are hypo_test_inversion(...) and hypo_test(...).

CalculatorType, TestStatistic and FitType are enums for configuration.

Bailed execution is done through bailmap(...).

Execute this script to run some tests of utility functions.


# "Bailed"
Named by the meaning of

    "The boat's sinking! Start bailing quickly!"

and most definitely not

    "She was yesterday bailed for three weeks on drink-driving offences."

        (https://dictionary.cambridge.org/dictionary/english/bailed)

Our worst offender is HypoTestInverter.GetInterval since it is the long loop.
Also implicated is no free after ModelConfig.GetSnapshot or RooArgSet.snapshot,
as well as allocations in .Add and .Append *Result methods.

"""
from __future__ import print_function, division

import enum
import itertools
import functools
import logging
import more_itertools
import multiprocessing
import tempfile

from six.moves import xrange as range
from six.moves import map

# Kick HistFitter and ROOT in just the right way.
import ROOT
ROOT.gSystem.Load("libSusyFitter.so")
import ROOT.ConfigMgr
ROOT.gROOT.SetBatch(True)
ROOT.gROOT.Reset()


LOGGER = logging.getLogger("bailed_roostats")
logging.basicConfig(level=logging.INFO)


# Remove references to data sets which we never look at?
CLEAN_DETAILED_OUTPUT = True



# Types

class CalculatorType(enum.Enum):
    """ Type flags HistFitter DoHypoTestInversion and DoHypoTest quoted.

        Quotes from comments in HistFitter StatTools.cxx.

        Note: different from ROOT.RooStats.HypoTestInverter::ECalculatorType.
    """
    # "type = 0 Freq calculator"
    frequentist = 0
    # "type = 1 Hybrid calculator"
    hybrid = 1
    # "type = 2 Asymptotic calculator"
    asymptotic = 2
    # "type = 3 Asymptotic calculator using nominal Asimov data sets (not using
    #           fitted parameter values but nominal ones)"
    # Not for DoHypoTest.
    asimov = 3


TOY_CALCULATORS = {CalculatorType.frequentist, CalculatorType.hybrid}


class TestStatistic(enum.Enum):
    """ Labels for HistFitter HypoTestTool SetupHypoTestCalculator.

        Quotes from comments in HistFitter StatTools.cxx.
    """
    simple_likelihood_ratio = 0
    # "Tevatron"
    profile_likelihood_ratio = 1
    # "Profile Likelihood"
    profile_likelihood = 2
    # "Profile Likelihood one sided (i.e. = 0 if mu < mu_hat)"
    profile_likelihood_one_sided = 3
    # ""
    max_likelihood = 4


class FitType(enum.Enum):
    """ Labels for classes of fit. """
    discovery = 0
    exclusion = 1


# Core function definitions


def hypo_test_inversion(
        filename,
        workspacename,
        poiname,
        points,
        ntoys,
        random_seed,
        # *,
        batch_size=100,
        processes=None,
        calculatorType=CalculatorType.frequentist,
        testStatType=TestStatistic.profile_likelihood_one_sided,
        useCLs=True,
        doAnalyze=False,
        useNumberCounting=False,
        modelSBName="ModelConfig",
        modelBName="",
        dataName="obsData",
        nuisPriorName="",
        generateAsimovDataForObserved=False):
    """ Run an "hypothesis test inversion" while bailing out memory leaks.

        Arguments:
            filename:
                String path to file from which to load the RooWorkspace
            workspacename:
                String name of the RooWorkspace in the input file.
            poiname:
                String name of the Parameter Of Interest (POI)
            points:
                (start, stop, count) for linearly spaced points to evaluate.
            ntoys:
                Number of `toy' samples to simulate at each point.
            random_seed:
                int in [0, 2**16) for deterministic random number generation.
            batch_size:
                Maximum number of objects per batch of bailed execution;
                both number of toys and number of results merged.
                Reduce when limited by memory.
            processes:
                Number of processes to use in execution.
                If None (default), use cpu count
            Others taken from StatTools.h RooStats::DoHypoTestInversion
                (in HistFitter), with the same defaults where appropriate.

        Returns:
            dumped HypoTestInverterResult
    """
    if calculatorType.value in TOY_CALCULATORS:
        assert ntoys > 0
        assert batch_size > 0
    seed = init_seed(random_seed)

    workspace_args = (
        filename,
        workspacename,
        poiname,
    )

    fixed_args = (
        calculatorType,
        testStatType,
        useCLs,
        doAnalyze,
        useNumberCounting,
        modelSBName,
        modelBName,
        dataName,
        nuisPriorName,
        generateAsimovDataForObserved
    )

    if calculatorType not in TOY_CALCULATORS:
        return hypo_test_inversion_no_toys(workspace_args, fixed_args, points, seed)

    # Build generator for point, nbatch pairs.
    batches = lambda point: ((point, n) for n in batch(ntoys, batch_size))

    point_nbatches = itertools.chain(*(
        batches(point)
        for point in linspace(*points)
    ))

    specs = (
        (workspace_args, fixed_args, point_nbatch, seed + i)
        for i, point_nbatch in enumerate(point_nbatches)
    )

    # Execute with memory bailing.
    inversions = bailmap(hypo_test_inversion_batch, specs, processes)

    # `Add' also leaks like a sieve, so bail that too; first in batch_size
    # chunks, then reduce pairs of the larger merged results.
    batches = more_itertools.chunked(inversions, batch_size)
    merges = bailmap(hypo_test_inversion_merge, batches)
    reduction = lambda a, b: next(bailmap(hypo_test_inversion_merge, [(a, b)], 1))
    return cascade(reduction, merges)


def hypo_test(
        filename,
        workspacename,
        ntoys,
        random_seed,
        fit_type,
        # *,
        batch_size=100,
        processes=None,
        calculatorType=CalculatorType.frequentist,
        testStatType=TestStatistic.profile_likelihood_one_sided,
        modelSBName="ModelConfig",
        modelBName="",
        dataName="obsData",
        useNumberCounting=False,
        nuisPriorName=""):
    """ Run an "hypothesis test" while chucking memory leaks overboard.

        Argument order chosen to match HistFitter RooStats.DoHypoTest

        Arguments:
            filename:
                String path to file from which to load the RooWorkspace
            workspacename:
                String name of the RooWorkspace in the input file.
            random_seed:
                int in [0, 2**16) for deterministic random number generation.
            fit_type:
                FitType - discovery or exclusion?
            ntoys:
                Number of samples to generate.
            batch_size:
                Maximum number of objects per batch of bailed execution;
                both number of toys and number of results merged.
                Reduce when limited by memory.
            processes:
                Number of processes to use in execution.
                If None (default), use cpu count.
            Others taken from StatTools.h RooStats::DoHypoTest (in HistFitter),
                with the same defaults where appropriate.

        Returns:
            dumped HypoTestResult
    """
    if calculatorType.value in TOY_CALCULATORS:
        assert ntoys > 0
        assert batch_size > 0
    seed = init_seed(random_seed)

    if fit_type is FitType.discovery:
        do_upper_limit = False
    elif fit_type is FitType.exclusion:
        do_upper_limit = True
    else:
        raise ValueError("fit_type must be FitType.{discovery or exclusion};"
                         "got %r" % fit_type)

    # Mimic logic from HistFitter RooStats.get_htr
    if (not do_upper_limit
        and testStatType.value is TestStatistic.profile_likelihood_one_sided.value):
        testStatType = TestStatistic.profile_likelihood

    workspace_args = (
        filename,
        workspacename,
    )

    fixed_args = (
        do_upper_limit,
        calculatorType,
        testStatType,
        modelSBName,
        modelBName,
        dataName,
        useNumberCounting,
        nuisPriorName,
    )

    if calculatorType not in TOY_CALCULATORS:
        return hypo_test_no_toys(workspace_args, fixed_args, seed)

    # Split up our ntoys into blocks of size up to batch_size
    specs = (
        (workspace_args, fixed_args, nbatch, seed + i)
        for i, nbatch in enumerate(batch(ntoys, batch_size))
    )

    # Execute with memory bailing.
    tests = bailmap(hypo_test_batch, specs, processes)

    # `Append' also leaks like a sieve, so bail that too; first in batch_size
    # chunks, then reduce pairs of the larger merged results.
    batches = more_itertools.chunked(tests, batch_size)
    merges = bailmap(hypo_test_merge, batches)
    reduction = lambda a, b: next(bailmap(hypo_test_merge, [(a, b)], 1))
    return cascade(reduction, merges)



def hypo_test_inversion_batch(spec):
    """ Return a dumped HypoTestInverterResult.

        Parameters are bundled into tuples in spec for Pool.map usage.
    """
    workspace_args, fixed_args, (point, nbatch), seed = spec

    filename, workspacename, poiname = workspace_args
    try:
        workspace = get_workspace(filename, workspacename)
        set_poi(workspace, poiname)
    except IOError as error:
        # Log to get the message out from generator environments.
        LOGGER.error(error)
        raise error

    (
        calculatorType,
        testStatType,
        useCLs,
        doAnalyze,
        useNumberCounting,
        modelSBName,
        modelBName,
        dataName,
        nuisPriorName,
        generateAsimovDataForObserved,
    ) = fixed_args

    npoints = 1
    poimin = point
    poimax = point
    nCPUs = 1

    seed_roo_random(seed)

    result = ROOT.RooStats.DoHypoTestInversion(
        workspace,
        nbatch,
        calculatorType.value,
        testStatType.value,
        useCLs,
        npoints,
        poimin,
        poimax,
        doAnalyze,
        useNumberCounting,
        modelSBName,
        modelBName,
        dataName,
        nuisPriorName,
        generateAsimovDataForObserved,
        nCPUs)

    if CLEAN_DETAILED_OUTPUT:
        # This should loop over one element.
        for i in range(result.ArraySize()):
            result_i = result.GetResult(i)
            result_i.SetNullDetailedOutput(ROOT.nullptr)
            result_i.SetAltDetailedOutput(ROOT.nullptr)

    return root_dumps(result)


def hypo_test_inversion_merge(results):
    """ Return a dumped combination of dumped HypoTestInverterResults. """
    root_results = map(root_loads, results)
    out = next(root_results)
    for result in root_results:
        out.Add(result)
    return root_dumps(out)


def hypo_test_inversion_no_toys(workspace_args, fixed_args, points, seed):
    """ Return a dumped HypoTestInverterResult for a non-toy calculator. """
    filename, workspacename, poiname = workspace_args
    try:
        workspace = get_workspace(filename, workspacename)
        set_poi(workspace, poiname)
    except IOError as error:
        # Log to get the message out from generator environments.
        LOGGER.error(error)
        raise error

    (
        calculatorType,
        testStatType,
        useCLs,
        doAnalyze,
        useNumberCounting,
        modelSBName,
        modelBName,
        dataName,
        nuisPriorName,
        generateAsimovDataForObserved,
    ) = fixed_args

    assert calculatorType not in TOY_CALCULATORS

    ntoys = -1
    poimin, poimax, npoints = points
    nCPUs = 1

    # This might not make a difference, but including it for consistency.
    seed_roo_random(seed)

    result = ROOT.RooStats.DoHypoTestInversion(
        workspace,
        ntoys,
        calculatorType.value,
        testStatType.value,
        useCLs,
        npoints,
        poimin,
        poimax,
        doAnalyze,
        useNumberCounting,
        modelSBName,
        modelBName,
        dataName,
        nuisPriorName,
        generateAsimovDataForObserved,
        nCPUs)

    return root_dumps(result)


def hypo_test_batch(spec):
    """ Return a dumped HypoTestResult.

        Parameters are bundled into tuples in spec for Pool.map usage.
    """
    workspace_args, fixed_args, nbatch, seed = spec

    filename, workspacename = workspace_args
    try:
        workspace = get_workspace(filename, workspacename)
    except IOError as error:
        # Log to get the message out from generator environments.
        LOGGER.error(error)
        raise error

    (
        do_upper_limit,
        calculatorType,
        testStatType,
        modelSBName,
        modelBName,
        dataName,
        useNumberCounting,
        nuisPriorName,
    ) = fixed_args

    seed_roo_random(seed)

    result = ROOT.RooStats.DoHypoTest(
        workspace,
        do_upper_limit,
        nbatch,
        calculatorType.value,
        testStatType.value,
        modelSBName,
        modelBName,
        dataName,
        useNumberCounting,
        nuisPriorName,
    )

    if CLEAN_DETAILED_OUTPUT:
        result.SetNullDetailedOutput(ROOT.nullptr)
        result.SetAltDetailedOutput(ROOT.nullptr)

    return root_dumps(result)


def hypo_test_merge(results):
    """ Return a dumped combination of dumped HypoTestResults. """
    root_results = map(root_loads, results)
    out = next(root_results)
    for result in root_results:
        out.Append(result)
    return root_dumps(out)


def hypo_test_no_toys(workspace_args, fixed_args, seed):
    """ Return a dumped HypoTestResult for a non-toy calculator. """
    filename, workspacename = workspace_args
    try:
        workspace = get_workspace(filename, workspacename)
    except IOError as error:
        # Log to get the message out from generator environments.
        LOGGER.error(error)
        raise error

    (
        do_upper_limit,
        calculatorType,
        testStatType,
        modelSBName,
        modelBName,
        dataName,
        useNumberCounting,
        nuisPriorName,
    ) = fixed_args

    assert calculatorType not in TOY_CALCULATORS

    # This might not make a difference, but including it for consistency.
    seed_roo_random(seed)

    ntoys = -1

    result = ROOT.RooStats.DoHypoTest(
        workspace,
        do_upper_limit,
        ntoys,
        calculatorType.value,
        testStatType.value,
        modelSBName,
        modelBName,
        dataName,
        useNumberCounting,
        nuisPriorName,
    )

    return root_dumps(result)



# Utility function definitions


def bailmap(func, iterable, processes=None):
    """ Return a func mapped over iterable with memory leaks bailed out.

        Uses a pool of processes of size `processes'; if None, uses cpu count.
    """
    # maxtasksperchild and chunksize set to 1 ensure cleanup after each call.
    pool = multiprocessing.Pool(processes, maxtasksperchild=1)
    mapped = pool.imap(func, iterable, chunksize=1)
    pool.close()
    return mapped


def cascade(func, items):
    """ Return the reduction of items by func applied pairwise. """
    # We need len and slicing properties. Not trying to be a perfect iterator!
    items = list(items)
    while len(items) > 1:
        # Split off an odd loner if it exists.
        len_even = len(items) & -2
        even = items[:len_even]
        last = items[len_even:]
        # Reduce by func in pairs.
        pairs = more_itertools.chunked(even, 2)
        items = list(itertools.starmap(func, pairs)) + last
    return items[0]


def root_dumps(root_object):
    """ Return (name, binary) which serialize root_object.

        None dumps to None.
    """
    if root_object is None:
        return None
    name = root_object.GetName()
    file_ = tempfile.NamedTemporaryFile()
    # Write ROOT's serialization into the temporary file.
    tfile = ROOT.TFile.Open(file_.name, "RECREATE")
    tfile.cd()
    root_object.Write()
    tfile.Close()
    # Reopen to read ROOT's updates
    file_written = open(file_.name, "rb")
    binary = file_written.read()
    file_written.close()
    file_.close()
    return (name, binary)


def root_loads(name_binary):
    """ Return a root object de-serialized from a (name, binary) pair.

        None loads to None.
    """
    if name_binary is None:
        return None
    name, binary = name_binary
    # Reproduce ROOT's file as a temporary.
    file_ = tempfile.NamedTemporaryFile()
    file_.write(binary)
    file_.flush()
    # Read it with ROOT.
    tfile = ROOT.TFile.Open(file_.name, "READ")
    root_object = tfile.Get(name)
    if hasattr(root_object, "SetDirectory"):
        # Avoid its deletion with closing the file.
        root_object.SetDirectory(ROOT.gROOT)
    tfile.Close()
    file_.close()
    return root_object


def init_seed(random_seed):
    """ Return a 32 bit random seed for batched execution. """
    # Move user seed to high half of 32 bits, start counter in low half; mix so
    # adjacent seeds don't clash if the counter overflows.
    assert 0 <= random_seed < 2**16
    seed = (random_seed * 0x9e37) & (2**16 - 1)
    return (seed << 16) + 1


def seed_roo_random(seed):
    """ Set the RooRandom global state seed. """
    assert seed != 0, "Got seed 0, which TRandom3 scrambles."
    ROOT.RooRandom.randomGenerator().SetSeed(seed)
    ROOT.RooRandom.uniform() # Burn-in ...
    ROOT.RooRandom.uniform() # ... to allay ...
    ROOT.RooRandom.uniform() # ... some doubt.


def get_workspace(filename, workspacename):
    """ Load and return a workspace from a file. """
    workspace = ROOT.Util.GetWorkspaceFromFile(filename, workspacename)
    # Attempts to check against None do not work; using name as a proxy.
    try:
        workspace.GetName()
    except ReferenceError:
        raise IOError("Failed to load workspace %r from file %r" %
            (workspacename, filename))
    return workspace


def set_poi(workspace, poiname):
    """ Set the Parameter Of Interest in the workspace model config. """
    poi = workspace.var(poiname)
    # Attempts to check against None do not work; using name as a proxy.
    try:
        poi.GetName()
    except ReferenceError:
        raise IOError("Failed to get POI %r from workspace %r" %
            (poiname, workspace))
    model_config = workspace.obj("ModelConfig")
    model_config.SetParametersOfInterest(ROOT.RooArgSet(poi))
    model_config.GetNuisanceParameters().remove(poi)


def batch(n, k):
    """ Yield fragments of n of sizes up to k. """
    ceil_n_over_k = (n // k) + bool(n % k)
    for i in range(ceil_n_over_k):
        yield min(k, n - i*k)


def linspace(start, stop, count):
    """ Return a linearly spaced list of count points from start to stop,

        Mimics numpy.linspace and observations of RooStats.
    """
    if count == 1:
        return [float(start)]
    scale = (stop - start)/(count - 1)
    return [start + scale*i for i in range(count)]



# Testing


def test_batch():
    """ Run tests for batch. """
    for n, k in itertools.product(range(99), range(1, 9)):
        assert sum(batch(n, k)) == n
        assert all(0 < i <= k for i in batch(n, k))


def test_linspace():
    """ Assert behaviors of linspace(...). """
    args_ref = (
        ((5, 6, 0), []),
        ((5, 6, 1), [5.0]),
        ((5, 6, 2), [5.0, 6.0]),
        ((5, 6, 3), [5.0, 5.5, 6.0]),
    )
    for args, ref in args_ref:
        assert linspace(*args) == ref


def test_root_dumps_loads():
    """ Assert features of root_dumps and root_loads. """
    hist = ROOT.TH1F("test", "", 2, 0, 1)
    hist.Fill(0.4)
    test = root_dumps(hist)
    hist2 = root_loads(test)
    assert hist2.GetName() == hist.GetName()
    assert hist2.Sizeof() == hist.Sizeof()
    for i in range(4):
        assert hist2.GetBinContent(i) == hist.GetBinContent(i)
        assert hist2.GetBinError(i) == hist.GetBinError(i)


def test_seed_roo_random():
    """ Assert that seed_roo_random works as intended. """
    for seed in (1, 1000, 1 << 30):
        seed_roo_random(seed)
        numbers = [ROOT.RooRandom.uniform() for _ in range(99)]
        seed_roo_random(seed)
        numbers2 = [ROOT.RooRandom.uniform() for _ in range(99)]
        seed_roo_random(seed + (1 << 31))
        numbers3 = [ROOT.RooRandom.uniform() for _ in range(99)]
        assert all(x == y for x, y in zip(numbers, numbers2))
        assert not all(x == y for x, y in zip(numbers, numbers3))
        # Although TRandom3 SetSeed takes a 64 bit integer, it immediately
        # downcasts to 32 bits, discarding the high half.
        seed_roo_random(seed + (123 << 32))
        numbers4 = [ROOT.RooRandom.uniform() for _ in range(99)]
        assert all(x == y for x, y in zip(numbers, numbers4))


def test_cascade():
    """ Assert that cascade works as intended. """
    add = lambda a, b: a + b
    data = list(range(-5123, 1234, 7))
    assert cascade(add, data) == sum(data)
    assert cascade(add, data[1:]) == sum(data[1:])
    assert cascade(add, data[:1]) == sum(data[:1])
    assert cascade(add, data[:2]) == sum(data[:2])


def test_all():
    """ Run all tests. """
    test_batch()
    test_linspace()
    test_root_dumps_loads()
    test_seed_roo_random()
    test_cascade()


if __name__ == "__main__":
    test_all()
