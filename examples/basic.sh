# Make toys with upper_limit_results.py in multiple processes on one machine.
#
# Usage:
#
#     Set HISTFITTER_INSTALL_PATH and HISTFITTER_PATH
#
#     Set -filename, -prefix and -load arguments (or any others).
#
#     source examples/basic.sh
#

# Fill me in!
HISTFITTER_INSTALL_PATH=your_histfitter_install_path
HISTFITTER_PATH=your_histfitter_working_path

# Set an environment.
setupATLAS
lsetup "root 6.20.06-x86_64-centos7-gcc8-opt"
source ${HISTFITTER_INSTALL_PATH}/setup_afs.sh

cd ${HISTFITTER_PATH}

# Make two sets of results with different seeds and prefixes.
./upper_limit_results.py invert test dump \
    -filename results/disc1/Discovery_DRInt_combined_NormalMeasurement_model.root \
    -prefix results/disc1/example1 \
    -poi mu_Discovery \
    -points 0 30 6 \
    -ntoys 3000 \
    -nbatch 100 \
    -processes 16 \
    -seed 1

./upper_limit_results.py invert test dump \
    -filename results/disc1/Discovery_DRInt_combined_NormalMeasurement_model.root \
    -prefix results/disc1/example2 \
    -poi mu_Discovery \
    -points 0 30 6 \
    -ntoys 3000 \
    -nbatch 100 \
    -processes 16 \
    -seed 2


# Merge into a single file.
./upper_limit_results.py dump \
    -load results/disc1/example*_dump.pickle \
    -prefix results/disc1/merged


# Produce plots and tables.
./upper_limit_results.py output \
    -load results/disc1/merged_dump.pickle \
    -prefix results/disc1/example \
    -poi mu_Discovery \
    -lumi 139 \
    -channel DR-Example
