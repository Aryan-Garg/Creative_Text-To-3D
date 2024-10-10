#!/bin/bash
export CUDA_VISIBLE_DEVICES=1

python train.py -s /nobackup3/aryan/dataset/binary/f1000/train \
 --is_binary --position_lr_init 0.00008 --scaling_lr 0.001 \
 --opacity_lr 0.005 --feature_lr 0.0005 --sh_degree 3 --add_points --point_sample_interval 1500