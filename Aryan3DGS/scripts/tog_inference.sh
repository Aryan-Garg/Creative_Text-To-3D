#!/bin/bash
export CUDA_VISIBLE_DEVICES=1

# GT
# python render.py -s /nobackup3/aryan/dataset_moped2/gt/test --iteration 50000 --skip_train \
#     --model_path /nobackup3/aryan/HDRSplat/output/moped2_gt_default --eval

# RGB training
# python render.py -s /nobackup3/aryan/dataset_moped2/gt/test --iteration 50000 --skip_train \
#     --model_path /nobackup3/aryan/HDRSplat/output/moped2_rgb_default --eval

# TS + Bin training 
python render.py -s /nobackup3/aryan/dataset_moped2/gt/test --iteration 52000 --skip_train \
    --model_path /nobackup3/aryan/HDRSplat/output/6eeb4341-9 --eval

# TS training
# python render.py -s /nobackup3/aryan/dataset_moped2/gt/test --iteration 50000 --skip_train \
#     --model_path /nobackup3/aryan/HDRSplat/output/moped2_graded_till200_default --eval

# Only Bin training
# python render.py -s /nobackup3/aryan/dataset_moped2/gt/test --iteration 30000 --skip_train \
#     --model_path /nobackup3/aryan/HDRSplat/output/SPAD_20k_addpoints --eval

