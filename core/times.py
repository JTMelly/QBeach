# -*- coding: utf-8 -*-
from datetime import date, datetime, time

from qgis.core import QgsFeatureRequest


def elapsed_seconds(date_values, time_values):
    """Compute the total elapsed time span between paired date and time values.

    Combines each (date, time) pair into a datetime, then returns the
    difference between the maximum and minimum combined datetimes.

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

    combined = []
    for d, t in zip(date_values, time_values):
        try:
            combined.append(datetime.combine(d, t))
        except TypeError:
            continue

    if len(combined) < 2:
        return None

    return (max(combined) - min(combined)).total_seconds()


def layer_elapsed_seconds(layer, date_field, time_field):
    """Read a table layer's date and time columns and return the elapsed span.

    Iterates the layer's features once, normalizes the selected date
    and time field values to Python ``date``/``time`` objects (skipping
    NULL or unconvertible rows), and delegates the span calculation to
    :func:`elapsed_seconds`.

    Args:
        layer (QgsVectorLayer): The table/vector layer to read from.
        date_field (str): Name of the date field.
        time_field (str): Name of the time field.

    Returns:
        float or None: Elapsed time in seconds between the maximum and
        minimum combined datetimes, or None if the field names are
        invalid or fewer than two rows combine successfully.
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

    return elapsed_seconds(dates, times)


def layer_tide_rows(layer, date_field, time_field, left_field, right_field=None):
    """Read a tide table layer and return elapsed-time rows for XBeach.

    Combines each feature's date and time fields into a datetime,
    converts the tide corner fields to floats, sorts by time, and
    expresses each timestamp as elapsed seconds from the earliest
    valid row. Rows with unusable date, time, or left-tide values are
    skipped. When ``right_field`` is omitted or a right value is
    unusable, the left value is reused for the right corner (per the
    XBeach two-corner convention, facing shore).

    Args:
        layer (QgsVectorLayer): The table/vector layer to read from.
        date_field (str): Name of the date field.
        time_field (str): Name of the time field.
        left_field (str): Name of the left-corner tide field.
        right_field (str, optional): Name of the right-corner tide
            field. May be empty/None to mirror the left values.

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
    t0 = rows[0][0]
    return [((dt - t0).total_seconds(), left, right) for dt, left, right in rows]


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
