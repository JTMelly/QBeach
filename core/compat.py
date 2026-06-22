from qgis.core import Qgis

try:
    QGIS_INFO = Qgis.MessageLevel.Info
    QGIS_SUCCESS = Qgis.MessageLevel.Success
    QGIS_WARNING = Qgis.MessageLevel.Warning
except AttributeError:
    QGIS_INFO = Qgis.Info
    QGIS_SUCCESS = Qgis.Success
    QGIS_WARNING = Qgis.Warning
