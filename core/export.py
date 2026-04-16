# -*- coding: utf-8 -*-
import os
import numpy as np

def export_xbeach_model(output_dir, template_path, p2):

    with open(template_path, 'r', encoding='utf-8') as pt:
        template_content = pt.read()

    tideFilePath = os.path.join(output_dir, "tide.txt")
    jonsFilePath = os.path.join(output_dir, "jonswap.txt")
    paramsFilePath = os.path.join(output_dir, "params.txt")
    
    with open(tideFilePath, 'w') as f:
        f.write(f"0 {p2['tide']}\n{p2['duration']+1} {p2['tide']}")
        
    with open(jonsFilePath, 'w') as f2:
        f2.write(f"{p2['Hm0']} {p2['Tp']} {p2['mainAngle']} {p2['gammajsp']} {p2['spread']} {p2['duration']+1} 1")
        
    with open(paramsFilePath, 'w') as f3:
        f3.write(template_content.format(**p2))

def load_grid_files(path_x, path_y, path_z):

    E = np.loadtxt(path_x)
    N = np.loadtxt(path_y)
    Z = np.loadtxt(path_z)
    return E, N, Z
