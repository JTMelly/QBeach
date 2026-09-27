============
Changelog
============

This project began as a loose collection of *Python* scripts used to setup, run, and evaluate *XBeach* models in *Jupyter Notebooks*, *Google Colabs*, or an IDE:

* `CaorleCruscotto <https://github.com/JTMelly/CaorleCruscotto>`_
* `XBeach Utilities <https://github.com/JTMelly/XBeach-utils>`_

*QBeach* is an attempt to make these tools more accessible to those likely already working in *QGIS* to produce the necessary inputs for a working *XBeach* model.

Changelog=0.1.0 (Initial beta release)
--------------------------------------

* QGIS righthand docking pane. 
* Draws regular grids using rubber bands.
* Extracts elevation (depth) data from raster layer to grid cells.
* Creates simple XBeach model x.grd, y.grd, bed.dep, params.txt, jonswap.txt, and tide.txt files.
* Plots variable at timestep from xboutput.nc.