import re
from io import StringIO

from qgis.core import Qgis
from qgis.PyQt.QtCore import Qt  # type: ignore

QGIS_INFO = Qgis.MessageLevel.Info
QGIS_SUCCESS = Qgis.MessageLevel.Success
QGIS_WARNING = Qgis.MessageLevel.Warning

try:
    RIGHT_DOCK_WIDGET_AREA = Qt.DockWidgetArea.RightDockWidgetArea
except AttributeError:
    # Qt5 fallback: only the flat form exists there (Qt.RightDockWidgetArea);
    # the value is 0x2 in both Qt5 and Qt6.
    RIGHT_DOCK_WIDGET_AREA = 2


def load_ui_type(ui_path):
    """Load a .ui file with Qt5/Qt6 enum compatibility.

    Converts scoped enums to the flat Qt5 form when running under Qt5 /
    QGIS 3.x.

    Args:
        ui_path (str): Absolute or relative path to the ``.ui`` file.

    Returns:
        tuple: ``(form_class, base_class)`` as returned by
        :func:`uic.loadUiType`.
    """
    from qgis.PyQt import uic  # type: ignore
    from qgis.PyQt.QtCore import QT_VERSION_STR  # type: ignore

    if QT_VERSION_STR.startswith('5.'):
        with open(ui_path, encoding='utf-8') as f:
            content = f.read()
        content = re.sub(r'Qt::(\w+)::(\w+)', r'Qt::\2', content)
        return uic.loadUiType(StringIO(content))

    return uic.loadUiType(ui_path)
