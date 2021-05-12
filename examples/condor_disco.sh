#!/bin/bash

# Fill me in!
DISCO_HF=your_histfitter_working_path
DISCO_HOME=${DISCO_HF}/results/${DISCO}

# Make toys.
DISCO_ID=$1
DISCO_REGION=$2
DISCO_START=$3
DISCO_STOP=$4
DISCO_COUNT=$5
DISCO_NTOYS=$6
DISCO_OFFSET=$7
DISCO='disco'

DISCO_SEED=$(expr ${DISCO_OFFSET} + ${DISCO_ID})

echo "starting \
REGION=${DISCO_REGION} \
START=${DISCO_START} \
STOP=${DISCO_STOP} \
COUNT=${DISCO_COUNT} \
NTOYS=${DISCO_NTOYS} \
SEED=${DISCO_SEED} \
"

# (RooStats spews into both stdout and stderr; nullify both for our own sanity)
${DISCO_HF}/upper_limit_results.py invert test dump \
    -filename ${DISCO_HOME}/Discovery_DR${DISCO_REGION}_combined_NormalMeasurement_model.root \
    -prefix ${DISCO_HF}/toys/DR${DISCO_REGION}_toys${DISCO_SEED} \
    -poi mu_Discovery \
    -lumi 139.0 \
    -points ${DISCO_START} ${DISCO_STOP} ${DISCO_COUNT} \
    -ntoys ${DISCO_NTOYS} \
    -nbatch 100 \
    -processes 1 \
    -seed ${DISCO_SEED} \
    > /dev/null 2> /dev/null

SUCCESS=$?

if [ ${SUCCESS} -eq 0 ]
then
    echo "success"
else
    echo "failure"
fi

echo "finished \
REGION=${DISCO_REGION} \
START=${DISCO_START} \
STOP=${DISCO_STOP} \
COUNT=${DISCO_COUNT} \
NTOYS=${DISCO_NTOYS} \
SEED=${DISCO_SEED} \
"

exit ${SUCCESS}
