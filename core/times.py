from bisect import bisect_right
from datetime import date, datetime, time
from itertools import pairwise

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


def layer_wind_rows(layer, date_field, time_field, speed_field,
                    direction_field, window=None):
    """Read a wind table layer and return elapsed-time rows for XBeach.

    Args:
        layer (QgsVectorLayer): The table/vector layer to read from.
        date_field (str): Name of the date field.
        time_field (str): Name of the time field.
        speed_field (str): Name of the wind-speed field (m/s).
        direction_field (str): Name of the wind-direction field
            (degrees, wind-from convention).
        window (tuple, optional): ``(start, end)`` absolute datetimes
            clipping the series, with the same bracket-and-re-zero
            semantics as ``layer_tide_rows``. ``None`` reads the full
            series relative to its own first row.

    Returns:
        list or None: ``[(elapsed_seconds, speed, direction), ...]``
        sorted by elapsed time, or None if any field name is invalid
        or fewer than two rows are usable.
    """

    fields = layer.fields()
    date_idx = fields.indexFromName(date_field)
    time_idx = fields.indexFromName(time_field)
    speed_idx = fields.indexFromName(speed_field)
    direction_idx = fields.indexFromName(direction_field)
    if date_idx < 0 or time_idx < 0 or speed_idx < 0 or direction_idx < 0:
        return None

    indices = [date_idx, time_idx, speed_idx, direction_idx]
    request = QgsFeatureRequest().setSubsetOfAttributes(indices)

    rows = []
    for feature in layer.getFeatures(request):
        try:
            dt = datetime.combine(_as_date(feature[date_idx]),
                                  _as_time(feature[time_idx]))
            speed = float(feature[speed_idx])
            direction = float(feature[direction_idx])
        except (AttributeError, TypeError, ValueError):
            continue
        rows.append((dt, speed, direction))

    if len(rows) < 2:
        return None

    rows.sort(key=lambda row: row[0])

    kept, t0 = _clip_rows(rows, window)
    if kept is None:
        return None

    return _rezero(kept, t0)


def intersect_ranges(ranges):
    """Classify how several absolute time ranges overlap.

    N-way generalization of :func:`classify_overlap`: the usable period
    is the intersection of every input range.

    Args:
        ranges (list): ``(earliest, latest)`` datetime tuples, at
            least one. None entries are not supported (filter first).

    Returns:
        tuple: ``(status, start, end)`` where status is ``'identical'``
        (every range equal; start/end span the range), ``'partial'``
        (usable intersection; start/end are the intersection bounds),
        or ``'none'`` (no usable intersection; start/end are None).
        Returns ``(None, None, None)`` for an empty list. A touching
        or zero-width intersection counts as ``'none'``.
    """

    if not ranges:
        return None, None, None

    start = max(r[0] for r in ranges)
    end = min(r[1] for r in ranges)
    if start >= end:
        return 'none', None, None
    if all(r == ranges[0] for r in ranges):
        return 'identical', start, end
    return 'partial', start, end


def series_step(rows, min_step=60):
    """Estimate the sampling step of an elapsed-time row series.

    Args:
        rows (list): Rows whose first element is elapsed seconds.
        min_step (int, optional): Steps below this many seconds are
            treated as unusable.

    Returns:
        int or None: Median positive step in whole seconds, or None when
        fewer than two rows differ in time or the step is below
        ``min_step``.
    """

    if len(rows) < 2:
        return None

    diffs = [b[0] - a[0] for a, b in pairwise(rows) if b[0] > a[0]]
    if not diffs:
        return None

    diffs.sort()
    middle = len(diffs) // 2
    if len(diffs) % 2:
        median = diffs[middle]
    else:
        median = (diffs[middle - 1] + diffs[middle]) / 2.0
    step = round(median)
    if step < min_step:
        return None
    return step


def align_series(tide_rows, wave_rows, duration, min_step=60,
                 wind_rows=None):
    """Snap active tide, wave and wind rows onto a shared time grid.

    Every active series is resampled onto the finer of their sampling
    steps so that water levels, sea states and winds change on the
    same clock. Tide values are linearly interpolated between the
    original rows, wave sea states are held (step) between changes
    with consecutive identical states collapsed, and wind is linearly
    interpolated for speed with shortest-arc circular interpolation
    for direction. Series already sampling at the same step are
    returned unchanged.

    Args:
        tide_rows (list): ``[(elapsed_seconds, left, right), ...]``
            sorted by elapsed time.
        wave_rows (list): ``[(elapsed_seconds, Hm0, Tp, mainang), ...]``
            sorted by elapsed time.
        duration (int): Model duration in seconds. The grid never
            extends past it and always includes it.
        min_step (int, optional): Steps finer than this many seconds are
            left untouched (avoids exploding sub-minute tables).
        wind_rows (list, optional): ``[(elapsed_seconds, speed,
            direction), ...]`` sorted by elapsed time. None (the
            default) keeps the legacy two-series behavior.

    Returns:
        tuple: ``(tide_rows, wave_rows, wind_rows, info)`` with the
        (possibly) resampled rows — ``wind_rows`` is passed through
        untouched when it was None — and ``info`` None when no
        alignment was needed, else a dict of ``tide_step``,
        ``wave_step`` (and ``wind_step`` when wind is active) plus
        ``base`` (the shared grid step in seconds).
    """

    series = [(rows, kind) for rows, kind in
              [(tide_rows, 'tide'), (wave_rows, 'wave')] if rows]
    if wind_rows:
        series.append((wind_rows, 'wind'))
    if len(series) < 2:
        return tide_rows, wave_rows, wind_rows, None

    steps = {kind: series_step(rows, min_step) for rows, kind in series}
    if any(step is None for step in steps.values()) \
            or len(set(steps.values())) == 1:
        return tide_rows, wave_rows, wind_rows, None

    base = min(steps.values())
    if duration < base:
        return tide_rows, wave_rows, wind_rows, None

    grid = list(range(0, int(duration) + 1, base))
    if grid[-1] != int(duration):
        grid.append(int(duration))

    resampled = {}
    for rows, kind in series:
        if kind == 'tide':
            resampled[kind] = _resample_tide(rows, grid)
        elif kind == 'wave':
            resampled[kind] = _resample_wave(rows, grid)
        else:
            resampled[kind] = _resample_wind(rows, grid)

    info = {f'{kind}_step': step for kind, step in steps.items()}
    info['base'] = base
    return (resampled.get('tide', tide_rows),
            resampled.get('wave', wave_rows),
            resampled.get('wind', wind_rows),
            info)


def _resample_tide(rows, grid):
    """Linearly interpolate elapsed-time rows onto a grid of times.

    Args:
        rows (list): ``(elapsed, value, ...)`` rows sorted by elapsed.
        grid (list): Ascending elapsed times to sample at.

    Returns:
        list: One row per grid time; times outside the rows' span hold
        the first/last row's values.
    """

    times = [row[0] for row in rows]
    out = []
    for elapsed in grid:
        if elapsed <= times[0]:
            out.append((elapsed,) + rows[0][1:])
            continue
        if elapsed >= times[-1]:
            out.append((elapsed,) + rows[-1][1:])
            continue
        hi = bisect_right(times, elapsed)
        lo = hi - 1
        span = times[hi] - times[lo]
        fraction = 0.0 if span == 0 else (elapsed - times[lo]) / span
        values = tuple(
            rows[lo][index]
            + (rows[hi][index] - rows[lo][index]) * fraction
            for index in range(1, len(rows[lo])))
        out.append((elapsed,) + values)
    return out


def _resample_wave(rows, grid):
    """Sample sea states onto a grid of times, holding each state.

    The state in force at each grid time is repeated, and consecutive
    grid rows with identical states are collapsed so only actual
    changes remain.

    Args:
        rows (list): ``[(elapsed, Hm0, Tp, mainang), ...]`` sorted by
            elapsed.
        grid (list): Ascending elapsed times to sample at.

    Returns:
        list: ``[(grid_time, Hm0, Tp, mainang), ...]`` starting at the
        first grid time, with unchanged states collapsed.
    """

    times = [row[0] for row in rows]
    out = []
    for elapsed in grid:
        index = bisect_right(times, elapsed) - 1
        index = max(0, index)
        candidate = (elapsed,) + rows[index][1:]
        if out and candidate[1:] == out[-1][1:]:
            continue
        out.append(candidate)
    return out


def _resample_wind(rows, grid):
    """Sample wind onto a grid of times, interpolating each component.

    Speed is linearly interpolated between rows; direction uses
    shortest-arc circular interpolation so a 350°→10° change passes
    through 0° rather than 180°. Values outside the rows' span are
    held at the first/last row.

    Args:
        rows (list): ``[(elapsed, speed, direction), ...]`` sorted by
            elapsed.
        grid (list): Ascending elapsed times to sample at.

    Returns:
        list: ``[(grid_time, speed, direction), ...]``, one row per
        grid time, direction normalized to ``[0, 360)``.
    """

    times = [row[0] for row in rows]
    out = []
    for elapsed in grid:
        if elapsed <= times[0]:
            out.append((elapsed,) + rows[0][1:])
            continue
        if elapsed >= times[-1]:
            out.append((elapsed,) + rows[-1][1:])
            continue
        hi = bisect_right(times, elapsed)
        lo = hi - 1
        span = times[hi] - times[lo]
        fraction = 0.0 if span == 0 else (elapsed - times[lo]) / span
        speed = rows[lo][1] + (rows[hi][1] - rows[lo][1]) * fraction
        # shortest-arc direction interpolation
        delta = (rows[hi][2] - rows[lo][2] + 180.0) % 360.0 - 180.0
        direction = (rows[lo][2] + delta * fraction) % 360.0
        out.append((elapsed, speed, direction))
    return out


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
