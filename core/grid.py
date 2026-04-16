# -*- coding: utf-8 -*-
import numpy as np
from qgis.core import QgsPointXY, QgsGeometry, QgsWkbTypes
from qgis.gui import QgsRubberBand
from qgis.PyQt.QtGui import QColor

def calculate_grid(p):

    theta = np.radians(p['angle'])
    c, s = np.cos(theta), np.sin(theta)
    rotmat = np.array([[c, -s], [s, c]])

    localROI = np.array([
        [0, 0],
        [p['distx'], 0],
        [p['distx'], p['disty']],
        [0, p['disty']],
        [0, 0]
    ])

    worldROI = (rotmat @ localROI.T).T + [p['originEasting'], p['originNorthing']]

    nx = int(p['distx'] / p['dx'])
    ny = int(p['disty'] / p['dy'])
    x_grid_1d = np.linspace(0, p['distx'], nx + 1)
    y_grid_1d = np.linspace(0, p['disty'], ny + 1)
    
    localX, localY = np.meshgrid(x_grid_1d, y_grid_1d)
    localCoords = np.vstack([localX.ravel(), localY.ravel()])
    worldGrid = (rotmat @ localCoords).T + [p['originEasting'], p['originNorthing']]
    
    E_world = worldGrid[:, 0].reshape(localX.shape)
    N_world = worldGrid[:, 1].reshape(localX.shape)

    return worldROI, E_world, N_world

class GridVisualizer:
    def __init__(self, iface):
        self.iface = iface
        self.roi_rubberband = None
        self.origin_rubberband = None
        self.grid_rubberbands = []

    def clear(self):
        if self.roi_rubberband:
            self.iface.mapCanvas().scene().removeItem(self.roi_rubberband)
            self.roi_rubberband = None
        if self.origin_rubberband:
            self.iface.mapCanvas().scene().removeItem(self.origin_rubberband)
            self.origin_rubberband = None
        for rb in self.grid_rubberbands:
            self.iface.mapCanvas().scene().removeItem(rb)
        self.grid_rubberbands = []

    def draw(self, worldROI, E_world, N_world, skip_x, skip_y):
        self.clear()
        canvas = self.iface.mapCanvas()
        
        # grid lines
        for i in range(0, E_world.shape[0], skip_y):
            rb = self._create_line_rb(canvas, E_world[i, :], N_world[i, :])
            self.grid_rubberbands.append(rb)
        if (E_world.shape[0]-1) % skip_y != 0:
            rb = self._create_line_rb(canvas, E_world[-1, :], N_world[-1, :])
            self.grid_rubberbands.append(rb)

        for j in range(0, E_world.shape[1], skip_x):
            rb = self._create_line_rb(canvas, E_world[:, j], N_world[:, j])
            self.grid_rubberbands.append(rb)
        if (E_world.shape[1]-1) % skip_x != 0:
            rb = self._create_line_rb(canvas, E_world[:, -1], N_world[:, -1])
            self.grid_rubberbands.append(rb)

        # ROI
        self.roi_rubberband = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.roi_rubberband.setColor(QColor(255, 0, 0, 100))
        self.roi_rubberband.setWidth(2)
        points = [QgsPointXY(pt[0], pt[1]) for pt in worldROI]
        points.append(QgsPointXY(worldROI[0][0], worldROI[0][1]))
        self.roi_rubberband.setToGeometry(QgsGeometry.fromPolylineXY(points), None)

        # origin
        self.origin_rubberband = QgsRubberBand(canvas, QgsWkbTypes.PointGeometry)
        self.origin_rubberband.setIcon(QgsRubberBand.ICON_CIRCLE)
        self.origin_rubberband.setIconSize(10)
        self.origin_rubberband.setColor(QColor(255, 255, 0))
        self.origin_rubberband.addPoint(QgsPointXY(worldROI[0][0], worldROI[0][1]))

    def _create_line_rb(self, canvas, E_line, N_line):
        rb = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        rb.setColor(QColor(0, 0, 0, 80))
        rb.setWidth(1)
        line = [QgsPointXY(E_line[k], N_line[k]) for k in range(len(E_line))]
        rb.setToGeometry(QgsGeometry.fromPolylineXY(line), None)
        return rb
