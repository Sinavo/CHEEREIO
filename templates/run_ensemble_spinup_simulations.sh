#!/bin/bash

#SBATCH -J {RunName}
#SBATCH -c {NumCores}
#SBATCH -N 1
#SBATCH -p {Partition}
#SBATCH --mem {Memory}
#SBATCH -t {WallTime}
#SBATCH -o logs/ensemble_spinup_%j.out    # File to which STDOUT will be written, %j inserts jobid       
#SBATCH -e logs/ensemble_spinup_%j.err    # File to which STDERR will be written, %j inserts jobid

source {ASSIM}/environments/cheereio.env #This is specific to the Harvard cluster; rewrite for yours
eval "$(conda shell.bash hook)"

# Set the proper # of threads for OpenMP
# SLURM_CPUS_PER_TASK ensures this matches the number you set with -c above
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

### Get current task ID
x=${SLURM_ARRAY_TASK_ID}

### Add zeros to the current task ID
if [ $x -lt 10 ]; then
  xstr="000${x}"
elif [ $x -lt 100 ]; then
  xstr="00${x}"
elif [ $x -lt 1000 ]; then
  xstr="0${x}"
else
  xstr="${x}"
fi


### Run GEOS-Chem in the directory corresponding to the cluster Id
cd  {RunName}_${xstr}

# Run GEOS_Chem.  The "time" command will return CPU and wall times.
# Stdout and stderr will be directed to the "GC.log" log file
# (you can change the log file name below if you wish)
srun -c $OMP_NUM_THREADS time -p ./gcclassic >> GC.log
wait


nEnsemble="$(jq -r ".nEnsemble" {ASSIM}/ens_config.json)"

if [ $x = $nEnsemble ]; then
	MY_PATH="$(jq -r ".MY_PATH" {ASSIM}/ens_config.json)"
  	RUN_NAME="$(jq -r ".RUN_NAME" {ASSIM}/ens_config.json)"
  	START_DATE="$(jq -r ".START_DATE" {ASSIM}/ens_config.json)"
  	cd {ASSIM}/core
	printf "${START_DATE} 000000" > ${MY_PATH}/${RUN_NAME}/scratch/CURRENT_DATE_TIME
	bash update_input_geos.sh "FIRST" #Update input.geos to first assimilation period.
fi

# Exit normally
exit 0
#EOC
