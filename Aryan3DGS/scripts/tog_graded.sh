#!/bin/bash
export CUDA_VISIBLE_DEVICES=1

# HDRSplat args
#  --position_lr_init 0.00001 --scaling_lr 0.0001 \
#  --opacity_lr 0.001 --feature_lr 0.0001 --sh_degree 2


python train.py -s /nobackup3/aryan/dataset_moped2 --is_graded --densify_until_iter 20000 --iterations 50000
#  --position_lr_init 0.00008 --opacity_lr 0.01 