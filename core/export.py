# -*- coding: utf-8 -*-
import os
import numpy as np

def export_xbeach_model(output_dir, template_path, p2, tide_rows=None,
                        wave_rows=None):
    """Write tide.txt, jonswap.txt, and params.txt for an XBeach model.

    Reads the params template, substitutes placeholder values from the
    model parameters dictionary, and writes all three files to the
    specified output directory.

    Args:
        output_dir (str): Path to the output directory.
        template_path (str): Path to the params.txt template file.
        p2 (dict): Model parameters dictionary with keys matching the
            template placeholders (date, duration, tstop, tintg, tide,
            Hm0, Tp, mainAngle, thetamin, thetamax, spread, gammajsp,
            alfa, nx, ny, nglobalvar, global_vars, nmeanvar, mean_vars,
            bedfriction, sedimentation).
        tide_rows (list, optional): ``[(elapsed_seconds, left, right),
            ...]`` time-varying tide series, where left/right are the
            offshore domain corners facing shore.
        wave_rows (list, optional): ``[(elapsed_seconds, Hm0, Tp,
            mainang), ...]`` time-varying sea states. When None, a
            single constant sea state is written instead.
    """

    with open(template_path, 'r', encoding='utf-8') as pt:
        template_content = pt.read()

    tideFilePath = os.path.join(output_dir, "tide.txt")
    jonsFilePath = os.path.join(output_dir, "jonswap.txt")
    paramsFilePath = os.path.join(output_dir, "params.txt")
    
    with open(tideFilePath, 'w') as f:
        if tide_rows:
            lines = [f"{elapsed:.1f} {right:.3f} {left:.3f}"
                     for elapsed, left, right in tide_rows]
            final_elapsed = float(p2['duration']) + 1
            if final_elapsed > tide_rows[-1][0]:
                _, last_left, last_right = tide_rows[-1]
                lines.append(f"{final_elapsed:.1f} {last_right:.3f} {last_left:.3f}")
            f.write("\n".join(lines))
        else:
            f.write(f"0 {p2['tide']} {p2['tide']}\n{p2['duration']+1} {p2['tide']} {p2['tide']}")
        
    with open(jonsFilePath, 'w') as f2:
        if wave_rows:
            f2.write(_jonswap_text(wave_rows, p2))
        else:
            f2.write(f"{p2['Hm0']} {p2['Tp']} {p2['mainAngle']} {p2['gammajsp']} {p2['spread']} {p2['duration']+1} 1")
        
    with open(paramsFilePath, 'w') as f3:
        f3.write(template_content.format(**p2))


def _jonswap_text(wave_rows, p2):
    """Format a time-varying jonswap.txt body.

    Args:
        wave_rows (list): ``[(elapsed_seconds, Hm0, Tp, mainang), ...]``
            sorted by elapsed time, with the first row at elapsed 0.
        p2 (dict): Model parameters dictionary; ``duration``,
            ``gammajsp`` and ``spread`` are used.

    Returns:
        str: Space-delimited sea-state lines, one per row, in
        ``Hm0 Tp mainang gammajsp s duration dtbc`` column order.
    """

    tstop = int(p2['duration']) + 1

    marks = []
    for index, (elapsed, hm0, period, mainang) in enumerate(wave_rows):
        mark = 0 if index == 0 else int(round(elapsed))
        if marks and mark <= marks[-1][0]:
            continue
        if mark >= tstop:
            continue
        marks.append((mark, hm0, period, mainang))

    lines = []
    for index, (mark, hm0, period, mainang) in enumerate(marks):
        end = marks[index + 1][0] if index + 1 < len(marks) else tstop
        lines.append(f"{hm0} {period} {mainang} {p2['gammajsp']} "
                     f"{p2['spread']} {end - mark} 1")
    return "\n".join(lines)

def load_grid_files(path_x, path_y, path_z):
    """Load XBeach grid and depth files from disk.

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