#!/bin/bash
export CUDA_VISIBLE_DEVICES=1

# HDRSplat args
# python train.py -s /nobackup3/aryan/dataset/binary/f1000/train \
#  --is_binary --position_lr_init 0.00001 --scaling_lr 0.0001 --add_points \
#  --iterations 20000 --save_iterations 5000 10000 20000 \
#  --point_sample_interval 500 --densify_until_iter 10000

# python train.py -s /nobackup3/aryan/dataset/binary/f1000/train --is_binary \
#     --densify_until_iter 20000 --iterations 50000

# --position_lr_init 0.00001 --scaling_lr 0.0001 --opacity_lr 0.001 --feature_lr 0.0001 --sh_degree 2 --densify_until_iter 100
python train.py -s /nobackup3/aryan/dataset/binary/f1000/train \
    --start_checkpoint /nobackup3/aryan/HDRSplat/output/moped2_graded_till200_default/point_cloud/iteration_50000/point_cloud.ply \
    --is_binary --iterations 52000 --save_iterations 50100 51000 52000 \
    --position_lr_init 0.000001 --scaling_lr 0.0001 --opacity_lr 0.001 --feature_lr 0.0001 --sh_degree 2 --densify_until_iter 100

# Infer right here as well.
python render.py -s /nobackup3/aryan/dataset_moped2/gt/test --iteration 51000 --skip_train \
    --model_path /nobackup3/aryan/HDRSplat/output/6eeb4341-9 --eval