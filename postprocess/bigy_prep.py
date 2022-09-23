import pandas as pd
import numpy as np
import pickle
import sys 
sys.path.append('../core')
import settings_interface as si 

data = si.getSpeciesConfig()

pp_dir = f"{data['MY_PATH']}/{data['RUN_NAME']}/postprocess"

with open(f"{pp_dir}/bigY.pkl",'rb') as f:
	bigy=pickle.load(f)

gclat,gclon = si.getLatLonVals(data)
gclat = np.array(gclat)
gclon = np.array(gclon)

#Saving albedo isn't a default option for all runs, so have to check if it is even in the ens config.
if "postprocess_save_albedo" in data:
	postprocess_save_albedo = data['postprocess_save_albedo']=="True"
else:
	postprocess_save_albedo = False

useControl=data['DO_CONTROL_RUN']=="true"
nEnsemble = int(data['nEnsemble'])

dates = list(bigy.keys())
specieslist = list(bigy[dates[0]].keys())

simulated_obs_mean_value = np.zeros([len(dates),len(specieslist),len(gclat),len(gclon)])*np.nan
true_obs_value = np.zeros([len(dates),len(specieslist),len(gclat),len(gclon)])*np.nan

total_obs_count = np.zeros([len(dates),len(specieslist),len(gclat),len(gclon)])
total_averaged_obs = np.zeros([len(dates),len(specieslist),len(gclat),len(gclon)])
if postprocess_save_albedo:
	total_swir = np.zeros([len(dates),len(specieslist),len(gclat),len(gclon)])*np.nan
	total_nir = np.zeros([len(dates),len(specieslist),len(gclat),len(gclon)])*np.nan
	total_blended = np.zeros([len(dates),len(specieslist),len(gclat),len(gclon)])*np.nan
if useControl:
	control_obs_value = np.zeros([len(dates),len(specieslist),len(gclat),len(gclon)])*np.nan


for ind1, date in enumerate(dates):
	daydict = bigy[date]
	for ind2, species in enumerate(specieslist):
		ydict = daydict[species]
		latdict = np.array(ydict['Latitude'])
		londict = np.array(ydict['Longitude'])
		countdict = np.array(ydict['Num_Averaged'])
		trueobsdict = np.array(ydict['Observations'])
		simobsdict = np.mean(np.array(ydict.iloc[:,0:nEnsemble]),axis=1) #Get the ensemble sim obs values, average to get sim obs dict
		if postprocess_save_albedo:
			swirdict = np.array(ydict['Albedo_SWIR'])
			nirdict = np.array(ydict['Albedo_NIR'])
			blendeddict = np.array(ydict['Blended_Albedo'])
		if useControl:
			controldict = np.array(ydict['Control'])
		latind = np.abs(latdict.reshape((1, -1)) - gclat.reshape((-1, 1)))
		latind = latind.argmin(axis=0)
		lonind = np.abs(londict.reshape((1, -1)) - gclon.reshape((-1, 1)))
		lonind = lonind.argmin(axis=0)
		pairedind = ((latind+1)*10000)+(lonind+1)
		uniqueind,countind = np.unique(pairedind,return_counts=True)
		uniquelonind = (uniqueind % 10000)-1
		uniquelatind = np.floor(uniqueind / 10000).astype(int)-1
		total_averaged_obs[ind1,ind2,uniquelatind,uniquelonind]=countind
		for lonindval,latindval in zip(uniquelonind,uniquelatind):
			dictind = np.where((latdict==gclat[latindval])&(londict==gclon[lonindval]))[0]
			totalcount = np.sum(countdict[dictind])
			total_obs_count[ind1,ind2,latindval,lonindval]=totalcount
			true_obs_value[ind1,ind2,latindval,lonindval]=np.mean(trueobsdict[dictind])
			simulated_obs_mean_value[ind1,ind2,latindval,lonindval]=np.mean(simobsdict[dictind])
			if useControl:
				control_obs_value[ind1,ind2,latindval,lonindval]=np.mean(controldict[dictind])
			if postprocess_save_albedo:	
				total_swir[ind1,ind2,latindval,lonindval]=np.mean(swirdict[dictind])
				total_nir[ind1,ind2,latindval,lonindval]=np.mean(nirdict[dictind])
				total_blended[ind1,ind2,latindval,lonindval]=np.mean(blendeddict[dictind])

arraysbase = {"obscount":total_obs_count,"obscount_avg":total_averaged_obs,"dates":dates,"species":specieslist,"obs":true_obs_value,"sim_obs":simulated_obs_mean_value}
if postprocess_save_albedo:
	arraysbase['swir_albedo']=total_swir
	arraysbase['nir_albedo']=total_nir
	arraysbase['blended_albedo']=total_blended

if useControl:
	arraysbase['control']=control_obs_value

f = open(f'{pp_dir}/bigy_arrays_for_plotting.pkl',"wb")
pickle.dump(arraysbase,f)
f.close()
