# -*- coding: utf-8 -*-
import os
import tempfile
import numpy as np
from qgis.core import (QgsPointXY,
                       QgsSingleBandPseudoColorRenderer, QgsRasterShader,
                       QgsColorRampShader)
from qgis.PyQt.QtGui import QColor

try:
    from osgeo import gdal, osr
    HAS_GDAL = True
except ImportError:
    HAS_GDAL = False

def sample_raster_at_grid(raster_layer, E_world, N_world):

    provider = raster_layer.dataProvider()
    no_data = provider.sourceNoDataValue(1)
    rows, cols = E_world.shape
    Z_world = np.zeros((rows, cols))
    
    for i in range(rows):
        for j in range(cols):
            val, ok = provider.sample(QgsPointXY(E_world[i, j], N_world[i, j]), 1)
            Z_world[i, j] = val if (ok and val != no_data) else 0.0
            
    return Z_world

def create_temp_raster(E, N, Z, crs_wkt):

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