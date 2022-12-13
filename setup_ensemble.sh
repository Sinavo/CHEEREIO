#!/bin/bash

# This script will set up asynchronous localized ensemble transform kalman filter (4D-LETKF assimilations/inversions) with GEOS-Chem.
# This involves creating an ensemble of run directories configured for the specific needs of the user and the 4D-LETKF procedure.
# Organization and much of the code are heavily inspired or directly lifted from both the createRunDir utility and the excellent 
# CH4 analytical inversion workflow repository; both were initially written by M. Sulprizio.
#
# Usage: bash setup_ensemble.sh. Be sure to customize the switches below and prepare ens_config.json before running.
#
# See README.md for details (dcp, 29/06/2021)

##=======================================================================
## Read user settings. Modify ens_config.json (not this script) if at all possible!
##=======================================================================

# Turn on/off different steps. This will allow you to come back to this
# script and set up different stages later.
SetupTemplateRundir=true
CompileTemplateRundir=true
SetupSpinupRun=false
SetupControlRun=false
SetupEnsembleRuns=true

source setup_ensemble_prelims.sh #get the relevant variables.

##=======================================================================
## Set up template run directory
##=======================================================================
if "$SetupTemplateRundir"; then

  bash setup_ensemble_template_13.sh

  #Modify HEMCO_Config so that GEOS-Chem will read in assimilated scaling factors.
  cd ${ASSIM_PATH}/core
  bash prepare_template_hemco_config.sh
  printf "${thinline}"

  #Update HISTORY.rc
  source activate $(jq -r ".CondaEnv" ../ens_config.json) 
  if [ "${DO_ENS_SPINUP}" = true ]; then
    python update_history.py "SPINUP"
  else
    python update_history.py "TEMPLATEDIR"
  fi

  conda deactivate
  printf "${thinline}"

  printf "\n  -- Template run directory created at ${MY_PATH}/${RUN_NAME}/${RUN_TEMPLATE}."
  printf "\n     Modify all configuration files BEFORE creating spinup or ensemble run directories."
  printf "\n     All settings from this folder will be repeated throughout the ensemble.\n"

  printf "${thinline}CHEERIO TEMPLATE RUN DIRECTORY CREATED${thinline}"

  ### Navigate back to top-level directory
  cd ${MY_PATH}/${RUN_NAME}

fi # SetupTemplateRunDir

##=======================================================================
##  Compile template run directory
##=======================================================================

### Compile GEOS-Chem and store executable in template run directory
if "$CompileTemplateRundir"; then

  printf "${thickline}COMPILING TEMPLATE RUN DIRECTORY${thickline}"

  cd ${MY_PATH}/${RUN_NAME}/${RUN_TEMPLATE}/build
  cmake ../CodeDir
  cmake . -DRUNDIR=..
  make -j
  make install

  printf "${thinline}TEMPLATE RUN DIRECTORY COMPILED${thinline}"

  ### Navigate back to top-level directory
  cd ${MY_PATH}/${RUN_NAME}

fi

##=======================================================================
##  Set up spinup run directory
##=======================================================================
if  "$SetupSpinupRun"; then

  bash setup_ensemble_spinup.sh

fi # SetupSpinupRun

##=======================================================================
##  Set up control (no assimilation) run directory
##=======================================================================
if  "$SetupControlRun"; then

  bash setup_ensemble_control.sh
    
fi # SetupConrolRun


##=======================================================================
##  Set up Ensemble run directories
##=======================================================================
if "$SetupEnsembleRuns"; then

    bash setup_ensemble_make_ensemble.sh

fi  # SetupEnsembleRuns

exit 0
