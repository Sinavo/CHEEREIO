#!/bin/bash

#Check if all columns are saved. If so, combine and overwrite

MY_PATH="$(jq -r ".MY_PATH" ../ens_config.json)"
RUN_NAME="$(jq -r ".RUN_NAME" ../ens_config.json)"
CONDA_ENV=$(jq -r ".CondaEnv" ../ens_config.json)
TESTSTR='PRODUCTION'

end_timestamp="$(tail -n 1 ${MY_PATH}/${RUN_NAME}/scratch/INPUT_GEOS_TEMP)"
end_timestamp="${end_timestamp%??}" #Clear last two characters
end_timestamp="${end_timestamp// /_}" #Replace space with underscore

source activate ${CONDA_ENV} #Activate conda environment.
python check_for_all_columns.py ${TESTSTR}

if [ -f ${MY_PATH}/${RUN_NAME}/scratch/ALL_COLUMNS_FOUND ]; then
	python -u combine_columns_and_update.py ${end_timestamp} ${TESTSTR} >> ${MY_PATH}/${RUN_NAME}/ensemble_runs/logs/letkf_master.out
	echo 'Done' > ${MY_PATH}/${RUN_NAME}/scratch/ASSIMILATION_COMPLETE
fi

conda deactivate #Exit Conda environment