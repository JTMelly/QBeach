# -*- coding: utf-8 -*-
"""Circular mean of a wave-direction column for XBeach angle windows."""
import math

from qgis.core import QgsFeatureRequest


def layer_mean_direction(layer, field):
    """Compute the circular mean of a numeric direction column.

    Args:
        layer (QgsVectorLayer): The table/vector layer to read from.
        field (str): Name of the numeric direction field.

    Returns:
        float or None: Mean direction normalized to ``[0, 360)``, or
        None when the field name is invalid, no usable values exist,
        or the unit vectors cancel (degenerate spread).
    """

    fields = layer.fields()
    idx = fields.indexFromName(field)
    if idx < 0:
        return None

    request = QgsFeatureRequest().setSubsetOfAttributes([idx])

    sins = []
    coss = []
    for feature in layer.getFeatures(request):
        try:
            value = float(feature[idx])
        except (AttributeError, TypeError, ValueError):
            continue
        if math.isnan(value):
            continue
        rad = math.radians(value)
        sins.append(math.sin(rad))
        coss.append(math.cos(rad))

    if not sins:
        return None

    x = sum(coss) / len(coss)
    y = sum(sins) / len(sins)
    if math.hypot(x, y) < 1e-12:
        return None

    mean = math.degrees(math.atan2(y, x)) % 360.0
    # rounding at the seam can yield exactly 360.0; keep within [0, 360)
    return 0.0 if mean >= 360.0 else mean
