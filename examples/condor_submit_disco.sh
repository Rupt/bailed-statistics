#!/bin/bash

# Fill me in!
HISTFITTER_INSTALL_PATH=your_histfitter_install_path
HISTFITTER_PATH=your_histfitter_working_path
JOBS_PATH=your_condor_script_path

# Set an environment.
setupATLAS
lsetup "root 6.20.06-x86_64-centos7-gcc8-opt"
source ${HISTFITTER_INSTALL_PATH}/setup_afs.sh

cd ${HISTFITTER_PATH}

#
# Launch some jobs for discovery regions of the SUSY 2Ljets 2018 analysis.
#
# Each submission uses NJOBS seeds counting up form OFFSET.
# Seeds must only be unique within each region, where results will be merged.
#
# See condor_disco.sub and condor_disco.sh for how arguments are used.
#

# OffShell
condor_submit \
    ${JOBS_PATH}/condor_disco.sub \
    REGION=OffShell \
    START=0 STOP=20 COUNT=11 \
    NTOYS=200 \
    OFFSET=0 \
    NJOBS=1000

# Int
condor_submit \
    ${JOBS_PATH}/condor_disco.sub \
    REGION=Int \
    START=0 STOP=30 COUNT=16 \
    NTOYS=200 \
    OFFSET=0 \
    NJOBS=1000

# High
condor_submit \
    ${JOBS_PATH}/condor_disco.sub \
    REGION=High \
    START=0 STOP=10 COUNT=11 \
    NTOYS=200 \
    OFFSET=0 \
    NJOBS=1000

# llbb
condor_submit \
    ${JOBS_PATH}/condor_disco.sub \
    REGION=llbb \
    START=0 STOP=10 COUNT=11 \
    NTOYS=200 \
    OFFSET=0 \
    NJOBS=1000

# Low
condor_submit \
    ${JOBS_PATH}/condor_disco.sub \
    REGION=Low \
    START=0 STOP=30 COUNT=16 \
    NTOYS=200 \
    OFFSET=0 \
    NJOBS=1000


# Refine with more toys where needed.
condor_submit \
    ${JOBS_PATH}/condor_disco.sub \
    REGION=Low \
    START=2 STOP=10 COUNT=5 \
    NTOYS=200 \
    OFFSET=0 \
    NJOBS=2000
