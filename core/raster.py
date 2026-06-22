# -*- coding: utf-8 -*-
import os
import tempfile
import numpy as np
from qgis.core import (QgsPointXY, QgsGeometry, QgsSpatialIndex, QgsRectangle,
                       QgsCoordinateTransform, QgsProject,
                       QgsSingleBandPseudoColorRenderer, QgsRasterShader,
                       QgsColorRampShader)
from qgis.PyQt.QtGui import QColor

try:
    from osgeo import gdal, osr
    HAS_GDAL = True
except ImportError:
    HAS_GDAL = False

def sample_raster_at_grid(raster_layer, E_world, N_world):
    """Extract raster values at each grid node location.

    Samples the raster layer's data provider at each (Easting, Northing)
    coordinate. NoData cells and out-of-bounds samples are replaced with 0.0.

    Args:
        raster_layer (QgsRasterLayer): The raster layer to sample from.
        E_world (ndarray): 2D array of Easting coordinates.
        N_world (ndarray): 2D array of Northing coordinates.

    Returns:
        ndarray: 2D array of sampled values, same shape as E_world.
    """

    provider = raster_layer.dataProvider()
    no_data = provider.sourceNoDataValue(1)
    rows, cols = E_world.shape
    Z_world = np.zeros((rows, cols))
    
    for i in range(rows):
        for j in range(cols):
            val, ok = provider.sample(QgsPointXY(E_world[i, j], N_world[i, j]), 1)
            Z_world[i, j] = val if (ok and val != no_data) else 0.0
            
    return Z_world

def sample_vector_at_grid(vector_layer, attribute_name, default_value, E_world, N_world, destination_crs=None):
    """Sample a vector polygon layer at each grid node location.

    For each grid point, performs a spatial intersection test against
    cached polygon geometries using a QgsSpatialIndex. Points falling
    inside a polygon receive that feature's attribute value.

    Args:
        vector_layer (QgsVectorLayer): Polygon vector layer to sample.
        attribute_name (str): Field name containing the value to assign.
        default_value (float): Fallback value for points outside all polygons.
        E_world (ndarray): 2D array of Easting coordinates.
        N_world (ndarray): 2D array of Northing coordinates.
        destination_crs (QgsCoordinateReferenceSystem, optional): CRS to
            reproject the vector layer into. Defaults to the project CRS.

    Returns:
        ndarray: 2D float32 array of sampled values, same shape as E_world.
    """
    rows, cols = E_world.shape
    result = np.full((rows, cols), default_value, dtype=np.float32)
    
    # Setup CRS transformation if needed
    source_crs = vector_layer.crs()
    if destination_crs is None:
        destination_crs = QgsProject.instance().crs()
    
    transform = None
    if source_crs != destination_crs:
        transform = QgsCoordinateTransform(source_crs, destination_crs, QgsProject.instance())

    # Cache geometries and attributes for speed
    geom_map = {}
    attr_map = {}
    index = QgsSpatialIndex()
    
    for f in vector_layer.getFeatures():
        geom = f.geometry()
        if transform:
            geom.transform(transform)
        fid = f.id()
        geom_map[fid] = geom
        attr_map[fid] = f[attribute_name]
        index.addFeature(fid, geom.boundingBox())

    for i in range(rows):
        for j in range(cols):
            pt = QgsPointXY(E_world[i, j], N_world[i, j])
            # Quick bounding box check using spatial index
            candidate_ids = index.intersects(QgsRectangle(pt.x(), pt.y(), pt.x(), pt.y()))
            for fid in candidate_ids:
                if geom_map[fid].contains(pt):
                    val = attr_map[fid]
                    if val is not None:
                        try:
                            result[i, j] = float(val)
                        except (ValueError, TypeError):
                            pass
                    break
    return result

def create_temp_raster(E, N, Z, crs_wkt):
    """Write a temporary GeoTIFF from grid coordinates and depth values.

    Handles both 2D (meshgrid) and 1D (profile) input arrays. The
    affine geotransform is derived from the coordinate deltas, supporting
    rotated grids.

    Args:
        E (ndarray): 1D or 2D array of Easting coordinates.
        N (ndarray): 1D or 2D array of Northing coordinates.
        Z (ndarray): 1D or 2D array of depth/elevation values.
        crs_wkt (str): WKT representation of the output CRS.

    Returns:
        str: Path to the temporary GeoTIFF file.

    Raises:
        ImportError: If GDAL is not available.
    """

    if not HAS_GDAL:
        raise ImportError("GDAL is required for this operation.")

    if E.ndim == 2: # 2D case
        rows, cols = E.shape
        dx_col = E[0, 1] - E[0, 0] if cols > 1 else 1.0
        dy_col = N[0, 1] - N[0, 0] if cols > 1 else 0.0
        dx_row = E[1, 0] - E[0, 0] if rows > 1 else 0.0
        dy_row = N[1, 0] - N[0, 0] if rows > 1 else -1.0
        
        origin_x = E[0, 0] - 0.5 * dx_col - 0.5 * dx_row
        origin_y = N[0, 0] - 0.5 * dy_col - 0.5 * dy_row
        geotransform = (origin_x, dx_col, dx_row, origin_y, dy_col, dy_row)
    else: # 1D fallback
        rows = 1
        cols = len(E)
        dx_col = E[1] - E[0] if cols > 1 else 1.0
        dy_col = N[1] - N[0] if cols > 1 else 0.0
        angle = np.arctan2(dy_col, dx_col) + np.pi/2
        dx_row = np.cos(angle)
        dy_row = np.sin(angle)
        
        origin_x = E[0] - 0.5 * dx_col - 0.5 * dx_row
        origin_y = N[0] - 0.5 * dy_col - 0.5 * dy_row
        geotransform = (origin_x, dx_col, dx_row, origin_y, dy_col, dy_row)
        Z = Z.reshape(1, cols)

    fd, temp_path = tempfile.mkstemp(suffix=".tif")
    os.close(fd)
    
    driver = gdal.GetDriverByName('GTiff')
    ds = driver.Create(temp_path, cols, rows, 1, gdal.GDT_Float32)
    ds.SetGeoTransform(geotransform)
    srs = osr.SpatialReference()
    srs.ImportFromWkt(crs_wkt)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    Z_clean = np.where(np.isnan(Z), -9999.0, Z)
    band.WriteArray(Z_clean)
    band.SetNoDataValue(-9999.0)
    band.FlushCache()
    ds = None 
    
    return temp_path

def apply_viridis_renderer(layer, min_val, max_val):
    """Apply a Viridis-style pseudo-colour renderer to a raster layer.

    Creates a five-stop interpolated colour ramp spanning purple, blue,
    teal, green, and yellow.

    Args:
        layer (QgsRasterLayer): The target raster layer.
        min_val (float): Data value mapped to the bottom of the ramp.
        max_val (float): Data value mapped to the top of the ramp.
    """

    fcn = QgsColorRampShader()
    fcn.setColorRampType(QgsColorRampShader.Interpolated)
    
    if min_val == max_val:
        max_val += 1.0
    
    lst = [
        QgsColorRampShader.ColorRampItem(min_val, QColor("#440154"), f"{min_val:.2f}"),
        QgsColorRampShader.ColorRampItem(min_val + (max_val-min_val)*0.25, QColor("#3b528b")),
        QgsColorRampShader.ColorRampItem(min_val + (max_val-min_val)*0.50, QColor("#21918c")),
        QgsColorRampShader.ColorRampItem(min_val + (max_val-min_val)*0.75, QColor("#5ec962")),
        QgsColorRampShader.ColorRampItem(max_val, QColor("#fde725"), f"{max_val:.2f}")
    ]
    fcn.setColorRampItemList(lst)
    
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(fcn)
    renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
    layer.setRenderer(renderer)