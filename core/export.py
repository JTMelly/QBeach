import os

import numpy as np


def export_xbeach_model(
    output_dir,
    template_path,
    p2,
    tide_rows=None,
    wave_rows=None,
    min_wave_segment=None,
    wind_rows=None,
):
    """Write tide.txt, jonswap.txt, wind.txt and params.txt for XBeach.

    Reads params template, substitutes placeholder values, writes
    the model files to output directory.

    Args:
        output_dir (str): Path to the output directory.
        template_path (str): Path to the params.txt template file.
        p2 (dict): Model parameters dictionary with keys matching the
            template placeholders (date, duration, tstop, tintg, tide,
            Hm0, Tp, mainAngle, thetamin, thetamax, spread, gammajsp,
            wind, alfa, nx, ny, nglobalvar, global_vars, nmeanvar,
            mean_vars, bedfriction, sedimentation).
        tide_rows (list, optional): ``[(elapsed_seconds, left, right),
            ...]`` time-varying tide series, where left/right are the
            offshore domain corners facing shore.
        wave_rows (list, optional): ``[(elapsed_seconds, Hm0, Tp,
            mainang), ...]`` time-varying sea states. When None, a
            single constant sea state is written instead.
        min_wave_segment (int, optional): Minimum jonswap segment length
            in seconds; shorter segments are folded into the preceding
            one so the sea-state list never ends on a stub. None keeps
            every row.
        wind_rows (list, optional): ``[(elapsed_seconds, speed,
            direction), ...]`` time-varying wind series; written to
            wind.txt. When None, no wind.txt is written (constant wind
            is inlined in params.txt instead).

    Raises:
        ValueError: If the tide or wind series does not reach
            ``tstop`` or the jonswap segment durations do not sum to
            ``tstop``.
    """

    with open(template_path, 'r', encoding='utf-8') as pt:
        template_content = pt.read()

    tideFilePath = os.path.join(output_dir, "tide.txt")
    jonsFilePath = os.path.join(output_dir, "jonswap.txt")
    windFilePath = os.path.join(output_dir, "wind.txt")
    paramsFilePath = os.path.join(output_dir, "params.txt")
    tstop = float(p2['duration']) + 1

    with open(tideFilePath, 'w') as f:
        if tide_rows:
            lines = [f"{elapsed:.1f} {right:.3f} {left:.3f}"
                     for elapsed, left, right in tide_rows]
            last_elapsed = tide_rows[-1][0]
            if tstop > last_elapsed:
                _, last_left, last_right = tide_rows[-1]
                lines.append(f"{tstop:.1f} {last_right:.3f} {last_left:.3f}")
                last_elapsed = tstop
            if last_elapsed < tstop:
                raise ValueError(
                    f"tide series ends at {last_elapsed:g} s, before "
                    f"tstop = {tstop:g} s")
            f.write("\n".join(lines))
        else:
            f.write(
                f"0 {p2['tide']} {p2['tide']}\n"
                f"{p2['duration'] + 1} {p2['tide']} {p2['tide']}"
            )

    with open(jonsFilePath, 'w') as f2:
        if wave_rows:
            f2.write(_jonswap_text(wave_rows, p2,
                                   min_segment=min_wave_segment))
        else:
            f2.write(
                f"{p2['Hm0']} {p2['Tp']} {p2['mainAngle']} "
                f"{p2['gammajsp']} {p2['spread']} {p2['duration'] + 1} 1"
            )

    if wind_rows:
        with open(windFilePath, 'w') as f4:
            f4.write(_wind_text(wind_rows, tstop))

    with open(paramsFilePath, 'w') as f3:
        f3.write(template_content.format(**p2))


def _wind_text(wind_rows, tstop):
    """Format a time-varying wind.txt body.

    Args:
        wind_rows (list): ``[(elapsed_seconds, speed, direction), ...]``
            sorted by elapsed time, with the first row at elapsed 0.
        tstop (float): Final model time; the series must cover it.

    Returns:
        str: Space-delimited lines in ``elapsed speed direction``
        column order, with a trailing row holding the last wind state
        at ``tstop`` when the series ends earlier.

    Raises:
        ValueError: If the series ends before ``tstop`` after the
            trailing row is added.
    """

    lines = [f"{elapsed:.1f} {speed:.3f} {direction:.3f}"
             for elapsed, speed, direction in wind_rows]
    last_elapsed = wind_rows[-1][0]
    if tstop > last_elapsed:
        _, last_speed, last_direction = wind_rows[-1]
        lines.append(f"{tstop:.1f} {last_speed:.3f} {last_direction:.3f}")
        last_elapsed = tstop
    if last_elapsed < tstop:
        raise ValueError(
            f"wind series ends at {last_elapsed:g} s, before "
            f"tstop = {tstop:g} s")
    return "\n".join(lines)


def _jonswap_text(wave_rows, p2, min_segment=None):
    """Format a time-varying jonswap.txt body.

    Args:
        wave_rows (list): ``[(elapsed_seconds, Hm0, Tp, mainang), ...]``
            sorted by elapsed time, with the first row at elapsed 0.
        p2 (dict): Model parameters dictionary; ``duration``,
            ``gammajsp`` and ``spread`` are used.
        min_segment (int, optional): Minimum segment length in seconds.

    Returns:
        str: Space-delimited sea-state lines, one per row, in
        ``Hm0 Tp mainang gammajsp s duration dtbc`` column order.

    Raises:
        ValueError: If the segment durations do not sum to ``tstop``.
    """

    tstop = int(p2['duration']) + 1

    marks = []
    for index, (elapsed, hm0, period, mainang) in enumerate(wave_rows):
        mark = 0 if index == 0 else round(elapsed)
        if marks and mark <= marks[-1][0]:
            continue
        if mark >= tstop:
            continue
        marks.append((mark, hm0, period, mainang))

    if min_segment:
        kept = [marks[0]]
        for mark in marks[1:]:
            if mark[0] - kept[-1][0] >= min_segment:
                kept.append(mark)
        while len(kept) > 1 and tstop - kept[-1][0] < min_segment:
            kept.pop()
        marks = kept

    lines = []
    total = 0
    for index, (mark, hm0, period, mainang) in enumerate(marks):
        end = marks[index + 1][0] if index + 1 < len(marks) else tstop
        total += end - mark
        lines.append(f"{hm0} {period} {mainang} {p2['gammajsp']} "
                     f"{p2['spread']} {end - mark} 1")
    if total != tstop:
        raise ValueError(
            f"jonswap durations sum to {total} s, expected tstop = "
            f"{tstop} s")
    return "\n".join(lines)


def load_grid_files(path_x, path_y, path_z):
    """Load XBeach grid and depth files.

    Args:
        path_x (str): Path to x.grd (Easting grid).
        path_y (str): Path to y.grd (Northing grid).
        path_z (str): Path to bed.dep (depth/elevation values).

    Returns:
        tuple: (E, N, Z) where each is an ndarray of identical shape.
    """

    E = np.loadtxt(path_x)
    N = np.loadtxt(path_y)
    Z = np.loadtxt(path_z)
    return E, N, Z
