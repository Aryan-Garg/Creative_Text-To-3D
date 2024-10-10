#!/bin/bash
export CUDA_VISIBLE_DEVICES=1

# RGB0025fps exp (default):
python train.py  -s /nobackup3/aryan/dataset_moped2/rgb0025fps/train --densify_until_iter 20000 --iterations 50000
# (non-default hparams)    --densify_until_iter 20000 --iterations 50000 --position_lr_final 0.00000001 --scaling_lr 0.0025

# python train.py  -s /nobackup3/aryan/dataset_moped2/gt/train \
#     --densify_until_iter 20000 --iterations 50000


# NOTE don't forget to rename transforms_train.json to transforms.json
# NOTES about exps: 
# 1. RGB025fps run with random initialization
# --save_iterations are [10_000, 30_000, 50_000]
# 2. GT run with random initialization
# --save_iterations are [10_000, 30_000, 50_000]