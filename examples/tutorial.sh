# Reproduce the tutorial example:
#
#     twiki.cern.ch/twiki/bin/viewauth/AtlasProtected/HistFitterTutorial#Model_independent_upper_limits_t
#
# Our SPlusB_combined_NormalMeasurement_model.root workspace file is made by
#
#     HistFitter.py -wf analysis/tutorial/MyUpperLimitAnalysis_SS.py
#
# and reference results are generated by
#
#     UpperLimitTable.py -c SS -l 4.713 -n 1000 \
#         -w examples/tutorial_SPlusB_combined_NormalMeasurement_model.root
#
# whose tex table is at examples/tutorial_UpperLimitTable_SS_nToys1000.tex.
#
# (beware that results vary with random number generation)
#
# This script outputs results including a comparable tex table at
#
#     examples/tutorial_upper_limit_table_SS.tex
#
# Usage:
#
#     Set HISTFITTER_INSTALL_PATH below.
#
#     source examples/tutorial.sh
#

# Fill me in!
# HISTFITTER_INSTALL_PATH=your_histfitter_install_path
HISTFITTER_INSTALL_PATH=/var/work/pcnq/tombs/HistFitter65/


# Set an environment.
setupATLAS
lsetup "root 6.20.06-x86_64-centos7-gcc8-opt"
source ${HISTFITTER_INSTALL_PATH}/setup_afs.sh

./upper_limit_results.py invert test output \
    -filename examples/tutorial_SPlusB_combined_NormalMeasurement_model.root \
    -prefix examples/tutorial \
    -channel SS \
    -poi mu_SS \
    -lumi 4.713 \
    -ntoys 1000 \
    -nbatch 100 \
    -processes 16 \
    -seed 1
