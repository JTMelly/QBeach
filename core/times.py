# -*- coding: utf-8 -*-
from datetime import date, datetime, time

from qgis.core import QgsFeatureRequest


def _combine(date_values, time_values):
    """Pair date and time sequences into datetimes.

    Args:
        date_values (sequence): Date-like values, one per row.
        time_values (sequence): Time-like values, one per row. Must be
            the same length as ``date_values``.

    Returns:
        list: Successfully combined ``datetime`` objects; pairs that
        fail to combine are skipped.
    """

    combined = []
    for d, t in zip(date_values, time_values):
        try:
            combined.append(datetime.combine(d, t))
        except TypeError:
            continue
    return combined


def elapsed_seconds(date_values, time_values):
    """Compute the total elapsed time span between paired date and time values.

    Args:
        date_values (sequence): Date-like values (``datetime.date``),
            one per row.
        time_values (sequence): Time-like values (``datetime.time``),
            one per row. Must be the same length as ``date_values``.

    Returns:
        float or None: Elapsed time in seconds between the latest and
        earliest combined datetimes, or None if fewer than two rows
        combine successfully.
    """

    combined = _combine(date_values, time_values)
    if len(combined) < 2:
        return None

    return (max(combined) - min(combined)).total_seconds()


def time_range(date_values, time_values):
    """Compute the absolute (earliest, latest) span of paired date/time values.

    Args:
        date_values (sequence): Date-like values, one per row.
        time_values (sequence): Time-like values, one per row. Must be
            the same length as ``date_values``.

    Returns:
        tuple or None: ``(earliest, latest)`` combined datetimes, or
        None if fewer than two rows combine successfully.
    """

    combined = _combine(date_values, time_values)
    if len(combined) < 2:
        return None

    return (min(combined), max(combined))


def _layer_date_time_values(layer, date_field, time_field):
    """Read a table layer's date and time columns as paired raw values.

    Args:
        layer (QgsVectorLayer): The table/vector layer to read from.
        date_field (str): Name of the date field.
        time_field (str): Name of the time field.

    Returns:
        tuple or None: ``(dates, times)`` lists, or None if the field
        names are invalid.
    """

    fields = layer.fields()
    date_idx = fields.indexFromName(date_field)
    time_idx = fields.indexFromName(time_field)
    if date_idx < 0 or time_idx < 0:
        return None

    request = QgsFeatureRequest().setSubsetOfAttributes([date_idx, time_idx])

    dates = []
    times = []
    for feature in layer.getFeatures(request):
        try:
            dates.append(_as_date(feature[date_idx]))
            times.append(_as_time(feature[time_idx]))
        except (AttributeError, TypeError, ValueError):
            continue

    return dates, times


def layer_elapsed_seconds(layer, date_field, time_field):
    """Read a table layer's date and time columns and return the elapsed span.

    Args:
        layer (QgsVectorLayer): The table/vector layer to read from.
        date_field (str): Name of the date field.
        time_field (str): Name of the time field.

    Returns:
        float or None: Elapsed time in seconds between the maximum and
        minimum combined datetimes, or None if the field names are
        invalid or fewer than two rows combine successfully.
    """

    values = _layer_date_time_values(layer, date_field, time_field)
    if values is None:
        return None
    return elapsed_seconds(*values)


def layer_time_range(layer, date_field, time_field):
    """Read a table layer's date and time columns and return its absolute span.

    Args:
        layer (QgsVectorLayer): The table/vector layer to read from.
        date_field (str): Name of the date field.
        time_field (str): Name of the time field.

    Returns:
        tuple or None: ``(earliest, latest)`` combined datetimes, or
        None if the field names are invalid or fewer than two rows
        combine successfully.
    """

    values = _layer_date_time_values(layer, date_field, time_field)
    if values is None:
        return None
    return time_range(*values)


def classify_overlap(range_a, range_b):
    """Classify how two absolute time ranges overlap.

    Args:
        range_a (tuple): ``(earliest, latest)`` datetimes, or None.
        range_b (tuple): ``(earliest, latest)`` datetimes, or None.

    Returns:
        tuple: ``(status, start, end)`` where status is ``'identical'``
        (ranges equal; start/end span the range), ``'partial'``
        (usable intersection; start/end are the intersection bounds),
        or ``'none'`` (no usable intersection; start/end are None).
        Returns ``(None, None, None)`` when either input is None. A
        touching or zero-width intersection counts as ``'none'`` since
        it yields no simulatable period.
    """

    if range_a is None or range_b is None:
        return None, None, None
    if range_a == range_b:
        return 'identical', range_a[0], range_a[1]

    start = max(range_a[0], range_b[0])
    end = min(range_a[1], range_b[1])
    if start >= end:
        return 'none', None, None
    return 'partial', start, end


def _clip_rows(rows, window):
    """Clip sorted ``(datetime, ...)`` rows to a window with a bracket row.

    Args:
        rows (list): Rows sorted by their leading datetime.
        window (tuple, optional): ``(start, end)`` absolute datetimes.

    Returns:
        tuple: ``(kept, t0)`` where kept holds the rows to simulate and
        ``t0`` is the datetime elapsed times are measured from, or
        ``(None, None)`` when fewer than two rows survive.
    """

    if window is None:
        return rows, rows[0][0]

    w0, w1 = window
    inside = [r for r in rows if w0 <= r[0] <= w1]
    before = [r for r in rows if r[0] < w0]
    if inside and before and inside[0][0] == w0:
        kept = inside
    elif before:
        kept = [before[-1]] + inside
    else:
        kept = inside
    if len(kept) < 2:
        return None, None
    return kept, w0


def _rezero(kept, t0):
    """Convert kept rows to elapsed seconds, holding the first at zero.

    Args:
        kept (list): ``(datetime, value, ...)`` rows.
        t0 (datetime): Reference datetime (window start).

    Returns:
        list: ``[(0.0, value, ...), (elapsed_seconds, value, ...)]``.
    """

    out = [((row[0] - t0).total_seconds(),) + row[1:] for row in kept]
    out[0] = (0.0,) + out[0][1:]
    return out


def layer_tide_rows(layer, date_field, time_field, left_field,
                    right_field=None, window=None):
    """Read a tide table layer and return elapsed-time rows for XBeach.

    Args:
        layer (QgsVectorLayer): The table/vector layer to read from.
        date_field (str): Name of the date field.
        time_field (str): Name of the time field.
        left_field (str): Name of the left-corner tide field.
        right_field (str, optional): Name of the right-corner tide
            field. May be empty/None to mirror the left values.
        window (tuple, optional): ``(start, end)`` absolute datetimes
            clipping the series. Rows outside are dropped, the last
            row at-or-before ``start`` is kept as a bracket held at
            elapsed 0 (unless a row lands exactly on ``start``), and
            elapsed times are re-zeroed to ``start``. ``None`` reads
            the full series relative to its own first row.

    Returns:
        list or None: ``[(elapsed_seconds, left, right), ...]`` sorted
        by elapsed time, or None if the field names are invalid or
        fewer than two rows are usable.
    """

    fields = layer.fields()
    date_idx = fields.indexFromName(date_field)
    time_idx = fields.indexFromName(time_field)
    left_idx = fields.indexFromName(left_field)
    if date_idx < 0 or time_idx < 0 or left_idx < 0:
        return None

    right_idx = fields.indexFromName(right_field) if right_field else -1

    indices = [date_idx, time_idx, left_idx]
    if right_idx >= 0:
        indices.append(right_idx)
    request = QgsFeatureRequest().setSubsetOfAttributes(indices)

    rows = []
    for feature in layer.getFeatures(request):
        try:
            dt = datetime.combine(_as_date(feature[date_idx]),
                                  _as_time(feature[time_idx]))
            left = float(feature[left_idx])
        except (AttributeError, TypeError, ValueError):
            continue
        right = left
        if right_idx >= 0:
            try:
                right = float(feature[right_idx])
            except (AttributeError, TypeError, ValueError):
                pass
        rows.append((dt, left, right))

    if len(rows) < 2:
        return None

    rows.sort(key=lambda row: row[0])

    kept, t0 = _clip_rows(rows, window)
    if kept is None:
        return None

    return _rezero(kept, t0)


def layer_wave_rows(layer, date_field, time_field, height_field,
                    period_field, direction_field, window=None):
    """Read a wave table layer and return sea states for XBeach.

    Args:
        layer (QgsVectorLayer): The table/vector layer to read from.
        date_field (str): Name of the date field.
        time_field (str): Name of the time field.
        height_field (str): Name of the significant wave height field.
        period_field (str): Name of the peak wave period field.
        direction_field (str): Name of the mean wave direction field
            (degrees, nautical convention).
        window (tuple, optional): ``(start, end)`` absolute datetimes
            clipping the series, with the same bracket-and-re-zero
            semantics as ``layer_tide_rows``. ``None`` reads the full
            series relative to its own first row.

    Returns:
        list or None: ``[(elapsed_seconds, Hm0, Tp, mainang), ...]``
        sorted by elapsed time, or None if any field name is invalid
        or fewer than two rows are usable.
    """

    fields = layer.fields()
    date_idx = fields.indexFromName(date_field)
    time_idx = fields.indexFromName(time_field)
    height_idx = fields.indexFromName(height_field)
    period_idx = fields.indexFromName(period_field)
    direction_idx = fields.indexFromName(direction_field)
    if date_idx < 0 or time_idx < 0 or height_idx < 0 \
            or period_idx < 0 or direction_idx < 0:
        return None

    indices = [date_idx, time_idx, height_idx, period_idx, direction_idx]
    request = QgsFeatureRequest().setSubsetOfAttributes(indices)

    rows = []
    for feature in layer.getFeatures(request):
        try:
            dt = datetime.combine(_as_date(feature[date_idx]),
                                  _as_time(feature[time_idx]))
            hm0 = float(feature[height_idx])
            period = float(feature[period_idx])
            mainang = float(feature[direction_idx])
        except (AttributeError, TypeError, ValueError):
            continue
        rows.append((dt, hm0, period, mainang))

    if len(rows) < 2:
        return None

    rows.sort(key=lambda row: row[0])

    kept, t0 = _clip_rows(rows, window)
    if kept is None:
        return None

    return _rezero(kept, t0)


def _as_date(value):
    """Normalize a field value to ``datetime.date``.

    Accepts ``QDate``, ``datetime.datetime``, and ``datetime.date``.
    NULL and unconvertible values raise ``TypeError`` or ``ValueError``.

    Args:
        value: Raw field value.

    Returns:
        datetime.date: The normalized date.
    """

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date(value.year(), value.month(), value.day())


def _as_time(value):
    """Normalize a field value to ``datetime.time``.

    Accepts ``QTime``, ``datetime.datetime``, and ``datetime.time``.
    NULL and unconvertible values raise ``TypeError`` or ``ValueError``.

    Args:
        value: Raw field value.

    Returns:
        datetime.time: The normalized time.
    """

    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, time):
        return value
    return time(value.hour(), value.minute(), value.second(), value.msec())
