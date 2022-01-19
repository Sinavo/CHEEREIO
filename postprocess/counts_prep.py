import pandas as pd
import numpy as np
import pickle
import json

with open('../ens_config.json') as f:
	data = json.load(f)

pp_dir = f"{data['MY_PATH']}/{data['RUN_NAME']}/postprocess"

with open(f"{pp_dir}/bigY.pkl",'rb') as f:
	bigy=pickle.load(f)

with open(f"{data['MY_PATH']}/{data['RUN_NAME']}/scratch/latlon_vals.json") as f:
	ll_data = json.load(f)

gclat = np.array(ll_data['lat'])
gclon = np.array(ll_data['lon'])

dates = list(bigy.keys())
specieslist = list(bigy[dates[0]].keys())

total_satellite_obs = np.zeros([len(dates),len(specieslist),len(gclat),len(gclon)])
total_averaged_obs = np.zeros([len(dates),len(specieslist),len(gclat),len(gclon)])

for ind1, date in enumerate(dates):
	daydict = bigy[date]
	for ind2, species in enumerate(specieslist):
		ydict = daydict[species]
		latdict = np.array(ydict['Latitude'])
		londict = np.array(ydict['Longitude'])
		countdict = np.array(ydict['Num_Averaged'])
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
			total_satellite_obs[ind1,ind2,latindval,lonindval]=totalcount


arraysbase = [total_satellite_obs,total_averaged_obs,dates,specieslist]

f = open(f'{pp_dir}/count_arrays_for_plotting.pkl',"wb")
pickle.dump(arraysbase,f)
f.close()
