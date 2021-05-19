#!/bin/bash
#
# Post-processes condor jobs; merge results, output plots and tables.
#

# Fill me in!
HISTFITTER_INSTALL_PATH=your_histfitter_install_path
HISTFITTER_PATH=your_histfitter_working_path
DISCO='disco'

# Set an environment.
setupATLAS
lsetup "root 6.20.06-x86_64-centos7-gcc8-opt"
source ${HISTFITTER_INSTALL_PATH}/setup_afs.sh

cd ${HISTFITTER_PATH}
mkdir -p toys merged

# Merge and output all 2Ljets discovery regions
regions='OffShell Low Int High llbb'

for region in ${regions}
do
    ./upper_limit_results.py dump \
        -prefix merged/DR${region}_toys \
        -load toys/DR${region}_toys*_dump.pickle \
        |& tee out${region}.txt
done

for region in ${regions}
do
    ./upper_limit_results.py output \
        -prefix results/${DISCO}/DR${region}_toys \
        -load merged/DR${region}_toys_dump.pickle \
        -poi mu_Discovery \
        -lumi 139.0 \
        -channel ${region} \
        |& tee out${region}.txt
done
