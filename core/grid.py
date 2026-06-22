# -*- coding: utf-8 -*-
import numpy as np
from qgis.core import QgsPointXY, QgsGeometry, QgsWkbTypes
from qgis.gui import QgsRubberBand
from qgis.PyQt.QtGui import QColor

def calculate_grid(p):
    """Compute the world-coordinate grid nodes and bounding polygon.

    Generates a rotated regular grid in local coordinates, then transforms
    it to world coordinates via a rotation matrix and origin offset.

    Args:
        p: Dictionary of grid parameters with the following keys:
            originEasting (float): X coordinate of the grid origin.
            originNorthing (float): Y coordinate of the grid origin.
            distx (float): Cross-shore extent in metres.
            disty (float): Longshore extent in metres.
            dx (float): Grid spacing in the x-direction.
            dy (float): Grid spacing in the y-direction.
            angle (float): Rotation angle in degrees, counter-clockwise from East.

    Returns:
        tuple: (worldROI, E_world, N_world)
            - worldROI (ndarray): 5x2 array of polygon vertices defining the
              grid extent in world coordinates (closed ring).
            - E_world (ndarray): 2D array of Easting values for each grid node.
            - N_world (ndarray): 2D array of Northing values for each grid node.
    """

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
        """Remove all rubber-band overlays from the map canvas.

        Deletes the ROI polygon, origin point marker, and grid-line
        rubber bands, then resets all internal references to None.
        """
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
        """Draw the grid ROI, origin marker, and grid lines on the canvas.

        Clears any existing overlay first, then draws:
          - Grid lines at the specified skip interval.
          - A semi-transparent red polygon for the ROI boundary.
          - A yellow circle at the origin corner.

        Args:
            worldROI (ndarray): 5x2 array of ROI polygon vertices.
            E_world (ndarray): 2D array of Easting values per grid node.
            N_world (ndarray): 2D array of Northing values per grid node.
            skip_x (int): Number of columns to skip between drawn grid lines.
            skip_y (int): Number of rows to skip between drawn grid lines.
        """
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
        """Create a single grid-line rubber band from coordinate arrays.

        Args:
            canvas (QgsMapCanvas): The map canvas to attach the rubber band to.
            E_line (ndarray): Easting values along the line.
            N_line (ndarray): Northing values along the line.

        Returns:
            QgsRubberBand: A line rubber band with default styling.
        """
        rb = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        rb.setColor(QColor(0, 0, 0, 80))
        rb.setWidth(1)
        line = [QgsPointXY(E_line[k], N_line[k]) for k in range(len(E_line))]
        rb.setToGeometry(QgsGeometry.fromPolylineXY(line), None)
        return rb
