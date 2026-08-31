import re
from io import StringIO

from qgis.core import Qgis

try:
    QGIS_INFO = Qgis.MessageLevel.Info
    QGIS_SUCCESS = Qgis.MessageLevel.Success
    QGIS_WARNING = Qgis.MessageLevel.Warning
except AttributeError:
    QGIS_INFO = Qgis.Info
    QGIS_SUCCESS = Qgis.Success
    QGIS_WARNING = Qgis.Warning


def load_ui_type(ui_path):
    """Load a .ui file with Qt5/Qt6 enum compatibility.

    Qt6 Designer saves scoped enum syntax (e.g. Qt::Orientation::Horizontal)
    which PyQt5's ``uic`` cannot parse.  This function converts scoped enums
    to the flat Qt5 form when running under Qt5 / QGIS 3.x.

    Args:
        ui_path (str): Absolute or relative path to the ``.ui`` file.

    Returns:
        tuple: ``(form_class, base_class)`` as returned by
        :func:`uic.loadUiType`.
    """
    from qgis.PyQt import uic
    from qgis.PyQt.QtCore import QT_VERSION_STR

    if QT_VERSION_STR.startswith('5.'):
        with open(ui_path, encoding='utf-8') as f:
            content = f.read()
        content = re.sub(r'Qt::(\w+)::(\w+)', r'Qt::\2', content)
        return uic.loadUiType(StringIO(content))

    return uic.loadUiType(ui_path)
