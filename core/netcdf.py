# -*- coding: utf-8 -*-
import numpy as np

try:
    from osgeo import gdal
    HAS_GDAL = True
except ImportError:
    HAS_GDAL = False

def get_netcdf_info(file_path):

    if not file_path or not HAS_GDAL:
        return [], {}

    master_ds = gdal.Open(file_path)
    if not master_ds:
        return [], {}

    subdatasets = master_ds.GetMetadata('SUBDATASETS')
    master_ds = None
    variables = []
    var_map = {}
    
    coord_names = {'globalx', 'globaly', 'point_x', 'point_y', 'lat', 'lon', 'latitude', 'longitude', 'x', 'y'}
    
    for key, value in subdatasets.items():
        if '_NAME' in key:
            uri = value
            raw_var_name = uri.split(':')[-1]
            raw_var_name = raw_var_name.strip("'\"")

            if raw_var_name.lower() in coord_names:
                continue

            ds_var = gdal.Open(uri)
            if ds_var:
                count = ds_var.RasterCount
                ds_var = None
                variables.append(raw_var_name)
                var_map[raw_var_name] = {
                    'count': count,
                    'uri': uri
                }
                
    return sorted(variables), var_map

def read_netcdf_variable(file_path, var_name, timestep):

    if not HAS_GDAL:
        raise ImportError("GDAL is required to read NetCDF variables.")

    master_ds = gdal.Open(file_path)
    if not master_ds:
        return None, None, None
        
    subdatasets = master_ds.GetMetadata('SUBDATASETS')
    master_ds = None 
    
    def find_subdataset_uri(target_names):
        """Helper to find coordinate URIs dynamically."""
        for key, value in subdatasets.items():
            if '_NAME' in key:
                var_split = value.split(':')[-1].strip("'\"").lower()
                if var_split in target_names:
                    return value
        return None

    x_uri = find_subdataset_uri(['globalx', 'lon', 'longitude', 'x'])
    y_uri = find_subdataset_uri(['globaly', 'lat', 'latitude', 'y'])

    z_uri = None
    for key, value in subdatasets.items():
        if '_NAME' in key:
            if value.split(':')[-1].strip("'\"") == var_name:
                z_uri = value
                break
                
    if not z_uri:
        z_uri = f'NETCDF:"{file_path}":{var_name}'

    ds_z = gdal.Open(z_uri)
    if not ds_z:
        return None, None, None
        
    if timestep + 1 > ds_z.RasterCount:
        ds_z = None
        return None, None, None
        
    band = ds_z.GetRasterBand(timestep + 1)
    Z = band.ReadAsArray()
    ds_z = None 
    
    E, N = None, None
    if x_uri and y_uri:
        ds_x = gdal.Open(x_uri)
        ds_y = gdal.Open(y_uri)
        
        if ds_x and ds_y:
            E = ds_x.GetRasterBand(1).ReadAsArray()
            N = ds_y.GetRasterBand(1).ReadAsArray()
            ds_x, ds_y = None, None

            if E.ndim == 1 and N.ndim == 1:
                if E.shape[0] == Z.shape[1] and N.shape[0] == Z.shape[0]:
                    E, N = np.meshgrid(E, N)
                elif E.shape[0] == Z.shape[0] and N.shape[0] == Z.shape[1]:
                    N, E = np.meshgrid(N, E)

    if E is None or N is None:
        rows, cols = Z.shape
        E, N = np.meshgrid(np.arange(cols), np.arange(rows))
        
    return E, N, Z