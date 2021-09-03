import numpy as np
import xarray as xr
from datetime import date
import toolbox as tx
from glob import glob
import sys

spc_config = tx.getSpeciesConfig()

parent_dir = f"{spc_config['MY_PATH']}/{spc_config['RUN_NAME']}/ensemble_runs"
subdirs = glob(f"{parent_dir}/*/")
dirnames = [d.split('/')[-2] for d in subdirs]
subdir_numstring = [n.split('_')[-1] for n in dirnames]
emis_scaling_factors = spc_config['CONTROL_VECTOR_EMIS'].keys()

timestamp = str(sys.argv[1]) #Time for scaling factor time dimension. Format assumed to be YYYYMMDD
timestamp = timestamp[0:4]+'-'+timestamp[4:6]+'-'+timestamp[6:8]

if len(spc_config["REGION"])==0:
	gridlabel = spc_config["RES"]
else:
	gridlabel = f'{spc_config["REGION"]}_{spc_config["met_name"]}'

#Create traditional GEOS-Chem longitude and latitude centers, as specified by the settings in ens_config.json
if gridlabel == '4.0x5.0':
	lon = np.arange(-180.0,176.0, 5.0)
	lat = np.concatenate([[-89.0],np.arange(-86.0,87.0, 4.0), [89.0]])
elif gridlabel == '2.0x2.5':
	lon = np.arange(-180.0,178.0, 2.5)
	lat = np.concatenate([[-89.5],np.arange(-88.0,89.0, 2.0), [89.5]])
elif gridlabel == '1x1':
	lon = np.arange(-179.5,180.0, 1.0)
	lat = np.arange(-89.5,90, 1.0)
elif (gridlabel == '0.5x0.625') | (gridlabel == 'MERRA2'): #MERRA2 NATIVE GRID
	lon = -180.0 + (0.625*np.arange(0.0,576.0,1.0))
	lat = -90.0 + (0.5*np.arange(0.0,361.0,1.0))
elif (gridlabel == 'AS_MERRA2'): #ASIA NESTED GRID FOR MERRA2
	lon = np.arange(60.0,150.01, 0.625)
	lat = np.arange(-11.0,55.01, 0.5)
elif (gridlabel == 'EU_MERRA2'): #EUROPE NESTED GRID FOR MERRA2
	lon = np.arange(-30.0,50.01, 0.625)
	lat = np.arange(30.0,70.01, 0.5)
elif (gridlabel == 'NA_MERRA2'): #NORTH AMERICA NESTED GRID FOR MERRA2
	lon = np.arange(-140.0,-39.99, 0.625)
	lat = np.arange(10.0,70.01, 0.5)
elif (gridlabel == '0.25x0.3125') | (gridlabel == 'GEOSFP'):
	lon = -180.0 + (0.3125*np.arange(0.0,1152.0,1.0))
	lat = -90.0 + (0.25*np.arange(0.0,721.0,1.0))
elif (gridlabel == 'CH_GEOSFP'): #CHINA NESTED GRID FOR GEOS-FP
	lon = np.arange(70.0,140.01, 0.3125)
	lat = np.arange(15.0,55.01, 0.25)
elif (gridlabel == 'EU_GEOSFP'): #EU NESTED GRID FOR GEOS-FP
	lon = np.arange(-15.0,40.01, 0.3125)
	lat = np.arange(32.75,61.26, 0.25)
elif (gridlabel == 'NA_GEOSFP'): #NA NESTED GRID FOR GEOS-FP
	lon = np.arange(-130.0,-59.99, 0.3125)
	lat = np.arange(9.75,60.01, 0.25)
else:
	raise ValueError('Scaling factor initialization utility does not recognize grid specification.')

perturbation = float(spc_config["pPERT"]) #perturbation, between 0 and 1 exclusive. 0 is 0% perturbation and 1 is between +/- 100%
#                                          chosen from a uniform distribution
if (perturbation <= 0) | (perturbation >= 1):
	raise ValueError('Perturbation must be between 0 and 1 exclusive.')

#Generate random uniform sdaling factors
offset = 1-perturbation
scale = perturbation*2
scaling_factors = (scale*np.random.rand(1,len(lat),len(lon)))+offset

for numstring in subdir_numstring: #Loop through the non-nature directories
	if numstring=='logs':
		continue #This is the log file
	num = int(numstring)
	if num == 0:
		continue
	for emis_name in emis_scaling_factors: #Loop through the species we want scaling factors for
		name = f'{emis_name}_SCALEFACTOR'
		outdir = f"{parent_dir}/{spc_config['RUN_NAME']}_{numstring}"
		ds = xr.Dataset(
			{"Scalar": (("time","lat","lon"), scaling_factors,{"long_name": "Scaling factor", "units":"1"})},
			coords={
				"time": (["time"], np.array([0.0]), {"long_name": "time", "calendar": "standard", "units":f"hours since {timestamp} 00:00:00"}),
				"lat": (["lat"], lat,{"long_name": "Latitude", "units":"degrees_north"}),
				"lon": (["lon"], lon,{"long_name": "Longitude", "units":"degrees_east"})
			},
			attrs={
				"Title":"Auto-generated scaling factors",
				"Conventions":"COARDS",
				"History":f"Auto-generated by the GC-LETKF utility on {str(date.today())}"
			}
		)
		ds.to_netcdf(f"{outdir}/{name}.nc")
		print(f"Scaling factors \'{name}.nc\' in folder {spc_config['RUN_NAME']}_{numstring} initialized successfully!")
