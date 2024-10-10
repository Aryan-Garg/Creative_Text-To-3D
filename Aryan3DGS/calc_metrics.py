#!/usr/bin/env python3
import os
import numpy as np
from PIL import Image
import torch
from lpipsPyTorch import lpips
from tqdm import tqdm
from skimage.metrics import structural_similarity as ssim


def calc_metrics(output_dir, target_dir):
    output_files = os.listdir(output_dir)
    target_files = os.listdir(target_dir)
    output_files.sort()
    target_files.sort()
    assert len(output_files) == len(target_files)
    psnr = 0
    ssim = 0
    lpips_this = 0
    for i in tqdm(range(len(output_files))):
        output = np.array(Image.open(os.path.join(output_dir, output_files[i])).convert("RGB")).astype(np.float32)
        target = np.array(Image.open(os.path.join(target_dir, target_files[i])).convert("RGB")).astype(np.float32)
        mse = np.mean((output - target) ** 2)
        psnr += 20 * np.log10(255) - 10 * np.log10(mse)
        ssim += compare_ssim(output, target)
        output = torch.tensor(output).permute(2, 0, 1).unsqueeze(0).cuda()
        target = torch.tensor(target).permute(2, 0, 1).unsqueeze(0).cuda()
        lpips_this += lpips(output, target, net_type="vgg").item()

    return psnr / len(output_files), ssim / len(output_files), lpips_this / len(output_files)

def compare_ssim(img1, img2, channel_axis = 2):
    return ssim(img1, img2, channel_axis = channel_axis, data_range = 255.)

if __name__ == '__main__':
    print("Ours: QS (Temporal Smoothing graded):")
    print(calc_metrics("/nobackup3/aryan/HDRSplat/output/corrected_ours", 
                       "/nobackup3/aryan/dataset_moped2/gt/test/frames"))
    print("----------------------------------------------------------------------")
    print("Conventional Camera:")
    print(calc_metrics("/nobackup3/aryan/HDRSplat/output/moped2_gt_default/test/TogTest_50000/renders",
                       "/nobackup3/aryan/dataset_moped2/gt/test/frames"))
    print("----------------------------------------------------------------------")
    print("Deblur Gaussians:")
    print(calc_metrics("/nobackup3/aryan/Deblurring-3D-Gaussian-Splatting/output/test/ours_50000/renders",
                       "/nobackup3/aryan/dataset_moped2/gt/test/frames"))