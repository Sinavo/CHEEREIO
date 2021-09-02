import json
import numpy as np

def getSpeciesConfig():
	with open('../ens_config.json') as f:
		data = json.load(f)
	return data

#Get the latitude and longitude list for a particular core (indexed by ensemble and core)
def getLatLonList(ensnum,corenum):
	data = getSpeciesConfig()
	with open(f"{data['MY_PATH']}/{data['RUN_NAME']}/scratch/latlon_par.json") as f:
		gridsplit = json.load(f)
	return [gridsplit[f'{ensnum}'][f'{corenum}']['lat'],gridsplit[f'{ensnum}'][f'{corenum}']['lon']]

#Get the lat lon values for the grid from the JSON
def getLatLonVals(data=None):
	if not data:
		data = getSpeciesConfig()
	with open(f"{data['MY_PATH']}/{data['RUN_NAME']}/scratch/latlon_vals.json") as f:
		ll_data = json.load(f)
	return [ll_data['lat'],ll_data['lon']]

#Inputs are in degrees
def calcDist_km(lat1,lon1,lat2,lon2):
	R = 6371 # Radius of the earth in km
	dLat = deg2rad(lat2-lat1)
	dLon = deg2rad(lon2-lon1)
	a = (np.sin(dLat/2)**2) + (np.cos(deg2rad(lat1)) * np.cos(deg2rad(lat2)) * (np.sin(dLon/2)**2))
	c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a));
	d = c*R
	return d

def deg2rad(deg):
	return deg * (np.pi/180)

#Get index values within the localization range
#If negate is true, then get index values outside the localization range
def getIndsOfInterest(latind,lonind,negate=False):
	data = getSpeciesConfig()
	lat,lon = getLatLonVals(data)
	latval = lat[latind]
	lonval = lon[lonind]
	loc_rad = float(data['LOCALIZATION_RADIUS_km'])
	distgrid = np.zeros((len(lat),len(lon)))
	for i in range(len(lon)):
		dists_col = np.array([calcDist_km(latval,lonval,a,lon[i]) for a in lat])
		distgrid[:,i] = dists_col
	if negate:
		valid_inds = np.where(distgrid>loc_rad)
	else:
		valid_inds = np.where(distgrid<=loc_rad)
	return valid_inds