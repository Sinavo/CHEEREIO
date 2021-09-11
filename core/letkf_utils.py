import numpy as np
import xarray as xr
from glob import glob
import observation_operators as obs
import scipy.linalg as la
import toolbox as tx 

def getLETKFConfig(testing=False):
	data = tx.getSpeciesConfig(testing)
	err_config = data['OBS_ERROR_MATRICES']
	if '.npy' in err_config[0]: #Load error matrices from numpy files
		raise NotImplementedError 
	else: #Assume list of strings
		errs = np.array([float(e) for e in err_config])
	#Provide a list of observation operator classes in order of the species to assimilate.
	obs_operator_classes = [getattr(obs, s) for s in data['OBS_OPERATORS']]
	#If you are simulating nature (SIMULATE_NATURE=true in setup_ensemble.sh), provide the nature helper class.
	if data['NATURE_OPERATOR'] == "NA":
		raise NotImplementedError #No support for real observations yet!
	else:
		nature_operator_class = getattr(obs, data['NATURE_OPERATOR'])
	inflation = float(data['INFLATION_FACTOR'])
	return [errs, obs_operator_classes,nature_operator_class,inflation]


#This class contains useful methods for getting data from GEOS-Chem restart files and 
#emissions scaling factor netCDFs. After initialization it contains the necessary data
#and can output it in useful ways to other functions in the LETKF procedure.
class GC_Translator(object):
	def __init__(self, path_to_rundir,timestamp,computeStateVec = False,testing=False):
		#self.latinds,self.loninds = tx.getLatLonList(ensnum)
		self.filename = f'{path_to_rundir}GEOSChem.Restart.{timestamp}z.nc4'
		self.timestring = f'minutes since {timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[9:11]}:{timestamp[11:13]}:00'
		self.restart_ds = xr.load_dataset(self.filename)
		self.emis_sf_filenames = glob(f'{path_to_rundir}*_SCALEFACTOR.nc')
		self.testing=testing
		self.emis_ds_list = {}
		for file in self.emis_sf_filenames:
			name = '_'.join(file.split('/')[-1].split('_')[0:-1])
			self.emis_ds_list[name] = xr.load_dataset(file)
		if computeStateVec:
			self.buildStateVector()
		else:
			self.statevec = None
			self.statevec_lengths = None #Until state vector is initialized this variable is None
	#Since only one timestamp, returns in format lev,lat,lon
	def getSpecies3Dconc(self, species):
		da = np.array(self.restart_ds[f'SpeciesRst_{species}']).squeeze()
		return da
	def setSpecies3Dconc(self, species, conc3d):
		baseshape = np.shape(conc3d)
		conc4d = conc3d.reshape(np.concatenate([np.array([1]),baseshape]))
		self.restart_ds[f'SpeciesRst_{species}'] = (["time","lev","lat","lon"],conc4d,{"long_name":f"Dry mixing ratio of species {species}","units":"mol mol-1 dry","averaging_method":"instantaneous"})
	def getLat(self):
		return np.array(self.restart_ds['lat'])
	def getLon(self):
		return np.array(self.restart_ds['lon'])
	def getLev(self):
		return np.array(self.restart_ds['lev'])
	def getRestartTime(self):
		return np.array(self.restart_ds['time'])
	def getEmisTime(self):
		return np.array(list(self.emis_ds_list.values())[0]['time'])
	#We work with the most recent timestamp. Rest are just for archival purposes.
	def getEmisSF(self, species):
		da = self.emis_ds_list[species]['Scalar']
		return np.array(da)[-1,:,:].squeeze()
	def getEmisLat(self, species):
		return np.array(self.emis_ds_list[species]['lat'])
	def getEmisLon(self, species):
		return np.array(self.emis_ds_list[species]['lon'])
	#Add 2d emissions scaling factors to the end of the emissions scaling factor
	def addEmisSF(self, species, emis2d, assim_time):
		timelist = self.getEmisTime()
		last_time = timelist[-1]
		new_last_time = last_time+np.timedelta64(assim_time,'h') #Add assim time hours to the last timestamp
		START_DATE = tx.getSpeciesConfig(self.testing)['START_DATE']
		orig_timestamp = f'{START_DATE[0:4]}-{START_DATE[4:6]}-{START_DATE[6:8]}' #Start date from  JSON
		#Create dataset with this timestep's scaling factors
		ds = xr.Dataset(
			{"Scalar": (("time","lat","lon"), np.expand_dims(emis2d,axis = 0),{"long_name": "Scaling factor", "units":"1"})},
			coords={
				"time": (["time"], np.array([new_last_time]), {"long_name": "time", "calendar": "standard", "units":f"hours since {orig_timestamp} 00:00:00"}),
				"lat": (["lat"], self.getEmisLat(species),{"long_name": "Latitude", "units":"degrees_north"}),
				"lon": (["lon"], self.getEmisLon(species),{"long_name": "Longitude", "units":"degrees_east"})
			},
			attrs={
				"Title":"Auto-generated scaling factors",
				"Conventions":"COARDS",
				"History":"Generated by LETKF"
			}
		)
		self.emis_ds_list[species] = xr.concat([self.emis_ds_list[species],ds],dim = 'time') #Concatenate
	def buildStateVector(self):
		species_config = tx.getSpeciesConfig(self.testing)
		statevec_components = []
		for spec_conc in species_config['STATE_VECTOR_CONC']:
			statevec_components.append(self.getSpecies3Dconc(spec_conc).flatten())
		for spec_emis in species_config['CONTROL_VECTOR_EMIS'].keys():
			statevec_components.append(self.getEmisSF(spec_emis).flatten())
		self.statevec_lengths = np.array([len(vec) for vec in statevec_components])
		self.statevec = np.concatenate(statevec_components)
	def getLocalizedStateVectorIndices(self,latind,lonind):
		surr_latinds, surr_loninds = tx.getIndsOfInterest(latind,lonind,self.testing)
		levcount = len(self.getLev())
		latcount = len(self.getLat())
		loncount = len(self.getLon())
		totalcount = levcount*latcount*loncount
		dummy3d = np.arange(0, totalcount).reshape((levcount,latcount,loncount))
		dummywhere_flat = dummy3d[:,surr_latinds,surr_loninds].flatten()
		dummy2d = np.arange(0, latcount*loncount).reshape((latcount,loncount))
		dummy2dwhere_flat = dummy2d[surr_latinds,surr_loninds].flatten()
		species_config = tx.getSpeciesConfig(self.testing)
		conccount = len(species_config['STATE_VECTOR_CONC'])
		emcount = len(species_config['STATE_VECTOR_CONC'])
		ind_collector = []
		cur_offset = 0
		for i in range(conccount):
			ind_collector.append((dummywhere_flat+cur_offset))
			cur_offset+=totalcount
		for i in range(emcount):
			ind_collector.append((dummy2dwhere_flat+cur_offset))
			cur_offset+=(latcount*loncount)
		statevecinds = np.concatenate(ind_collector)
		return statevecinds
	def getColumnIndicesFromLocalizedStateVector(self,latind,lonind):
		surr_latinds, surr_loninds = tx.getIndsOfInterest(latind,lonind,self.testing)
		levcount = len(self.getLev())
		latcount = len(self.getLat())
		loncount = len(self.getLon())
		totalcount = levcount*latcount*loncount
		dummy3d = np.arange(0, totalcount).reshape((levcount,latcount,loncount))
		dummywhere_flat = dummy3d[:,surr_latinds,surr_loninds].flatten()
		dummywhere_flat_column = dummy3d[:,latind,lonind].flatten()
		dummywhere_match = np.where(np.in1d(dummywhere_flat,dummywhere_flat_column))[0]
		dummy2d = np.arange(0, latcount*loncount).reshape((latcount,loncount))
		dummy2dwhere_flat = dummy2d[surr_latinds,surr_loninds].flatten()
		dummy2dwhere_flat_column = dummy2d[latind,lonind]
		dummy2dwhere_match = np.where(np.in1d(dummy2dwhere_flat,dummy2dwhere_flat_column))[0]
		species_config = tx.getSpeciesConfig(self.testing)
		conccount = len(species_config['STATE_VECTOR_CONC'])
		emcount = len(species_config['STATE_VECTOR_CONC'])
		ind_collector = []
		cur_offset = 0
		for i in range(conccount):
			ind_collector.append((dummy2dwhere_match+cur_offset))
			cur_offset+=len(dummywhere_flat_column)
		for i in range(emcount):
			ind_collector.append((dummy2dwhere_match+cur_offset))
			cur_offset+=len(dummy2dwhere_flat_column)
		localizedstatevecinds = np.concatenate(ind_collector)
		return localizedstatevecinds
	def getStateVector(self,latind=None,lonind=None):
		if self.statevec is None:
			self.buildStateVector()
		if latind: #User supplied ind
			statevecinds = self.getLocalizedStateVectorIndices(latind,lonind)
			return self.statevec[statevecinds]
		else: #Return the whole vector
			return self.statevec
	#Randomize the restart for purposes of testing. Perturbation is 1/2 of range of percent change selected from a uniform distribution.
	#E.g. 0.1 would range from 90% to 110% of initial values. Bias adds that percent on top of the perturbed fields (0.1 raises everything 10%).
	#Repeats this procedure for every species in the state vector (excluding emissions).
	def randomizeRestart(self,perturbation=0.1,bias=0):
		statevec_species = tx.getSpeciesConfig(self.testing)['STATE_VECTOR_CONC']
		offset = 1-perturbation
		scale = perturbation*2
		for spec in statevec_species:
			conc3d = self.getSpecies3Dconc(spec)
			conc3d *= (scale*np.random.rand(*np.shape(conc3d)))+offset
			conc3d *= 1+bias
			self.setSpecies3Dconc(spec,conc3d)
	#Reconstruct all the 3D concentrations from the analysis vector and overwrite relevant terms in the xr restart dataset.
	#Also construct new scaling factors and add them as a separate array at the new timestep in each of the scaling factor netCDFs.
	#However, only do so for species in the control vectors of emissions and concentrations.
	def reconstructArrays(self,analysis_vector):
		species_config = tx.getSpeciesConfig(self.testing)
		restart_shape = np.shape(self.getSpecies3Dconc(species_config['STATE_VECTOR_CONC'][0]))
		emis_shape = np.shape(self.getEmisSF(species_config['CONTROL_VECTOR_EMIS'].keys()[0]))
		counter =  0
		for spec_conc in species_config['STATE_VECTOR_CONC']:
			if spec_conc in species_config['CONTROL_VECTOR_CONC']: #Only overwrite if in the control vector; otherwise just increment.
				index_start = np.sum(self.statevec_lengths[0:counter])
				index_end = np.sum(self.statevec_lengths[0:(counter+1)])
				analysis_subset = analysis_vector[index_start:index_end]
				analysis_3d = np.reshape(analysis_subset,restart_shape) #Unflattens with 'C' order in python
				self.setSpecies3Dconc(spec_conc,analysis_3d) #Overwrite.
			counter+=1
		for spec_emis in species_config['CONTROL_VECTOR_EMIS'].keys(): #Emissions scaling factors are all in the control vector
			index_start = np.sum(self.statevec_lengths[0:counter])
			index_end = np.sum(self.statevec_lengths[0:(counter+1)])
			analysis_subset = analysis_vector[index_start:index_end]
			analysis_emis_2d = np.reshape(analysis_subset,emis_shape) #Unflattens with 'C' order in python
			self.addEmisSF(spec_emis,analysis_emis_2d,species_config['ASSIM_TIME'])
			counter+=1
	def saveRestart(self):
		self.restart_ds["time"] = (["time"], np.array([0]), {"long_name": "Time", "calendar": "gregorian", "axis":"T", "units":self.timestring})
		self.restart_ds.to_netcdf(self.filename)
	def saveEmissions(self):
		for file in self.emis_sf_filenames:
			name = '_'.join(file.split('/')[-1].split('_')[0:-1])
			self.emis_ds_list[name].to_netcdf(file)


#Contains a dictionary referencing GC_Translators for every run directory.
#In the special case where there is a nature run present (with number 0)
#store the nature run in GC_Translator object nature.
#Also contains an observation operator (pass in the class you would like to use) for each species to assimilate.
#Class contains function to calculate relvant assimilation variables.
#SPECIAL NOTE ON FILES: we will be assuming that geos-chem stopped and left a restart at assimilation time in each run directory.
#That restart will be overwritten in place (name not changed) so next run starts from the assimilation state vector.
#Emissions scaling factors are most recent available (one assimilation timestep ago). New values will be appended to netCDF. 
class Assimilator(object):
	def __init__(self,timestamp,ensnum,corenum,testing=False):
		self.testing = testing
		self.ensnum = ensnum
		self.corenum = corenum
		self.latinds,self.loninds = tx.getLatLonList(ensnum,corenum,self.testing)
		spc_config = tx.getSpeciesConfig(self.testing)
		path_to_ensemble = f"{spc_config['MY_PATH']}/{spc_config['RUN_NAME']}/ensemble_runs"
		self.path_to_scratch = f"{spc_config['MY_PATH']}/{spc_config['RUN_NAME']}/scratch"
		self.parfilename = f'ens_{ensnum}_core_{corenum}_time_{timestamp}'
		subdirs = glob(f"{path_to_ensemble}/*/")
		subdirs.remove(f"{path_to_ensemble}/logs/")
		dirnames = [d.split('/')[-2] for d in subdirs]
		subdir_numbers = [int(n.split('_')[-1]) for n in dirnames]
		ensemble_numbers = []
		self.nature = None
		self.gt = {}
		self.observed_species = spc_config['OBSERVED_SPECIES']
		for ens, directory in zip(subdir_numbers,subdirs):
			if ens==0:
				self.nature = GC_Translator(directory, timestamp, False,self.testing)
			else: 
				self.gt[ens] = GC_Translator(directory, timestamp, True,self.testing)
				ensemble_numbers.append(ens)
		self.ensemble_numbers=np.array(ensemble_numbers)
		error_multipliers_or_matrices, ObsOperatorClass_list,NatureHelperClass,self.inflation = getLETKFConfig(self.testing)
		if self.nature is None: #For the time being, we must have a nature run.
			raise NotImplementedError
		else:
			if NatureHelperClass is None:
				raise ValueError('Need a Nature Helper class defined if assimilating simulated nature run.')
			self.NatureHelperInstance = NatureHelperClass(self.nature,self.observed_species,error_multipliers_or_matrices,self.testing)
	def getLat(self):
		return self.gt[1].getLat() #Latitude of first ensemble member, who should always exist
	def getLon(self):
		return self.gt[1].getLon()
	def getLev(self):
		return self.gt[1].getLev()
	def makeObsOps(self,latind=None,lonind=None):
		self.ObsOp = {}
		for i in range(len(self.observed_species)):
			spec = self.observed_species[i]
			ObsOp_instance = self.NatureHelperInstance.makeObsOp(spec,ObsOperatorClass_list[i],latind,lonind)
			self.ObsOp[spec] = ObsOp_instance
	def combineEnsemble(self,latind=None,lonind=None):
		statevecs = []
		for num in self.ensemble_numbers:
			statevecs.append(self.gt[num].getStateVector(latind,lonind))
		statevec_mat = np.stack(statevecs,axis = -1) #Combine along second axis
		return statevec_mat
	def ensMeanAndPert(self,latval,lonval):
		statevecs = self.combineEnsemble(latval,lonval)
		state_mean = np.expand_dims(np.mean(statevecs,axis = 1),axis=1) #calculate ensemble mean
		bigX = np.transpose(np.transpose(statevecs)-np.transpose(state_mean))
		return [state_mean,bigX]
	def ensObsMeanPertDiff(self,latval,lonval):
		obsmeans = []
		obsperts = []
		obsdiffs = []
		for species in self.observed_species:
			obsmean,obspert  = self.ensObsMeanAndPertForSpecies(species,latval,lonval)
			obsmean = obsmean.squeeze()
			obsmeans.append(obsmean)
			obsperts.append(obspert)
			obsdiffs.append(self.obsDiffForSpecies(species,obsmean,latval,lonval))
		full_obsmeans = np.concatenate(obsmeans)
		full_obsperts = np.concatenate(obsperts,axis = 0)
		full_obsdiffs = np.concatenate(obsdiffs)
		return [full_obsmeans,full_obsperts,full_obsdiffs]
	def combineEnsembleForSpecies(self,species):
		conc3D = []
		for i in self.ensemble_numbers:
			conc3D.append(self.gt[i].getSpecies3Dconc(species))
		conc4D = np.stack(conc3D,axis = -1) #Combine along fourth axis
		return conc4D
	def ensMeanAndPertForSpecies(self, species):
		conc4D = self.conc4D_byspecies[species]
		ens_mean = np.mean(conc4D,axis = 3) #calculate ensemble mean
		bigX = conc4D-ens_mean
		return [ens_mean,bigX]
	def ensObsMeanAndPertForSpecies(self, species,latval,lonval):
		spec_4D = self.combineEnsembleForSpecies(species)
		return self.ObsOp[species].obsMeanAndPert(spec_4D,latval,lonval)
	def obsDiffForSpecies(self,species,ensvec,latval,lonval):
		return self.ObsOp[species].obsDiff(ensvec,latval,lonval)
	def prepareMeansAndPerts(self,latval,lonval):
		self.ybar_background, self.Ypert_background, self.ydiff = self.ensObsMeanPertDiff(latval,lonval)
		self.xbar_background, self.Xpert_background = self.ensMeanAndPert(latval,lonval)
	def makeR(self,latval=None,lonval=None):
		self.R = self.NatureHelperInstance.makeR(latval,lonval)
	def makeC(self):
		self.C = np.transpose(self.Ypert_background) @ la.inv(self.R)
	def makePtildeAnalysis(self):
		cyb = self.C @ self.Ypert_background
		k = len(self.ensemble_numbers)
		iden = (k-1)*np.identity(k)/(1+self.inflation)
		self.PtildeAnalysis = la.inv(iden+cyb)
	def makeWAnalysis(self):
		k = len(self.ensemble_numbers)
		self.WAnalysis = la.sqrtm((k-1)*self.PtildeAnalysis)
	def makeWbarAnalysis(self):
		self.WbarAnalysis = self.PtildeAnalysis@self.C@self.ydiff
	def adjWAnalysis(self):
		k = len(self.ensemble_numbers)
		wbartiled = np.transpose(np.tile(self.WbarAnalysis,(k,1)))
		self.WAnalysis+=wbartiled
	def makeAnalysisCombinedEnsemble(self):
		analysis_pert = self.Xpert_background @ self.WAnalysis
		self.analysisEnsemble = np.transpose(np.transpose(analysis_pert)+np.transpose(self.xbar_background))
	def saveColumn(self,latval,lonval):
		colinds = self.gt[1].getColumnIndicesFromLocalizedStateVector(latval,lonval)
		analysisSubset = self.analysisEnsemble[colinds,:]
		np.save(f'{self.path_to_scratch}/{self.parfilename}_lat_{latval}_lon_{lonval}.npy',analysisSubset)
	def LETKF(self):
		for latval,lonval in zip(self.latinds,self.loninds):
			self.makeObsOps(latval,lonval)
			self.prepareMeansAndPerts(latval,lonval)
			self.makeR(latval,lonval)
			self.makeC()
			self.makePtildeAnalysis()
			self.makeWAnalysis()
			self.makeWbarAnalysis()
			self.adjWAnalysis()
			self.makeAnalysisCombinedEnsemble()
			self.saveColumn(latval,lonval)
	def updateRestartsAndScalingFactors(self):
		for i in self.ensemble_numbers:
			self.gt[i].reconstructArrays(self.analysisEnsemble[:,i-1])
	def saveRestartsAndScalingFactors(self):
		for i in self.ensemble_numbers:
			self.gt[i].saveRestart()
			self.gt[i].saveEmissions()
