# ToG Notes

------ --- --- --- --- --- --- --- --- --- --- ---  

1. Activate

micromamba activate /nobackup2/aryan/mambaenvs/nerfstudio

--- --- --- --- --- --- --- --- --- --- --- --- ---

2. Convert to imgs format

spsim colmap.run -i train-imgs2/frames/ -o train-colmap/ -a train-imgs2/transforms.json --force --no-cuda

--- --- --- --- --- --- --- --- --- --- --- --- ---

3. Undistort it to PINHOLE/SIMPLE_PINHOLE

colmap image_undistorter --image_path train-colmap/images/ --input_path train-colmap/sparse/0 --output_path train-colmap/dense --output_type COLMAP --max_image_size 2000

--- --- --- --- --- --- --- --- --- --- --- --- --- 

4. ./scripts/tog_random_init_cloud.sh

--- --- --- --- --- --- --- --- --- --- --- --- --- 

5. For rendering with SPC data:
