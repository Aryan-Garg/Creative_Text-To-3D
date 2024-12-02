#!/usr/bin/env python3
import os
import pickle
import numpy as np
import cv2

def parse_camera_pkl(pkl_path):
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    return data


def main():
    pass


if __name__ == '__main__':
    main()


"""
The data structure appears to contain multiple elements relevant for 3D Gaussian splatting:

1. **Intrinsic Camera Matrix (`K`)**: The first array is a 3x3 intrinsic matrix.
2. **Camera Rotations (`R`)**: The fourth element is an array of rotation matrices for multiple cameras (each being 3x3).
3. **Field of View in X and Y (`FoVX` and `FoVY`)**: The second and third arrays provide field-of-view angles in radians for each camera.
4. **Translations (`T`)**: The translations are embedded in the last column of each 4x4 matrix in the fourth element.

I'll extract and prepare this data for you.

Here is the extracted data ready for use in 3D Gaussian splatting:

### **Intrinsic Matrix (K)**:
```
[[280.   0. 128.]
 [  0. 280. 128.]
 [  0.   0.   1.]]
```

### **Rotations (R)**:
An array of 16 rotation matrices (3x3 each). For example:
```
R[0]:
[[ 9.99704497e-08  1.00000000e+00 -4.21468478e-08]
 [ 5.00000000e-01 -9.99704497e-08 -8.66025388e-01]
 [-8.66025388e-01  4.21468478e-08 -5.00000000e-01]]
```

### **Translations (T)**:
An array of 16 translation vectors (3x1 each). For example:
```
T[0]: [-9.82552824e-08  1.49011612e-08  1.49999993e+00]
```

### **Field of View in X (FoVX)**:
```
[0.       , 0.3926991, 0.7853982, 1.1780972, 1.5707964, 1.9634954,
 2.3561945, 2.7488935, 3.1415927, 3.5342917, 3.9269907, 4.3196898,
 4.712389 , 5.105088 , 5.497787 , 5.8904862]
```

### **Field of View in Y (FoVY)**:
```
[0.5235988, 0.5235988, 0.5235988, 0.5235988, 0.5235988, 0.5235988,
 0.5235988, 0.5235988, 0.5235988, 0.5235988, 0.5235988, 0.5235988,
 0.5235988, 0.5235988, 0.5235988, 0.5235988]
```

Would you like this data saved in a specific format for downstream tasks?
"""