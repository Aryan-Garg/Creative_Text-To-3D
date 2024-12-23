#!/usr/bin/env python

import os
import numpy as np
from PIL import Image
import torch
from random import randint
from utils.loss_utils import l1_loss, ssim
from gaussian_renderer import render, network_gui
import sys
from scene import Scene, GaussianModel
from utils.general_utils import safe_state
import uuid
from tqdm import tqdm
from utils.image_utils import psnr
from utils.raw_utils import postprocess_raw_gpu
from argparse import ArgumentParser, Namespace
from arguments import ModelParams, PipelineParams, OptimizationParams
from internal.raw_utils import pixels_to_bayer_mask
from internal.camera_utils import pixel_coordinates
from render import render_set_raw, render_set, project_point_cloud
import time
import jax
import jax.numpy as jnp
try:
    from torch.utils.tensorboard import SummaryWriter
    TENSORBOARD_FOUND = True
except ImportError:
    TENSORBOARD_FOUND = False


def loss_fn(pred_image, gt_image, lambda_dssim, mode):
    if mode == "raw3dgs":
        Ll2 = (pred_image - gt_image)**2 
        scaling_grad = (1. /  (1e-3 + torch.autograd.Variable(pred_image).detach())) ** 2
        loss = (Ll2 * scaling_grad).mean()
        return loss 
    if mode == "hdrsplat":
        # print("hdrsplat loss")
        Ll1 = torch.abs(pred_image-gt_image)
        scaling_grad = torch.abs(1. /  (1e-3 + torch.autograd.Variable(pred_image).detach()))
        loss = (1.0 - lambda_dssim) * (Ll1*scaling_grad).mean() + lambda_dssim * (1.0 - ssim(pred_image,gt_image))
        return loss 
    if mode == "LDR":
        Ll1 = l1_loss(pred_image, gt_image)
        loss = (1.0 - lambda_dssim) * Ll1 + lambda_dssim * (1.0 - ssim(pred_image, gt_image))
        return loss 
    if mode == "binary":
        # print("Calc. L1 Loss ...")
        Ll1 = l1_loss(pred_image, gt_image)
        # loss = (1.0 - lambda_dssim) * Ll1 + lambda_dssim * (1.0 - ssim(pred_image, gt_image))
        loss = Ll1
        return loss
        

def training(dataset, opt, pipe, render_iterations, testing_iterations, saving_iterations, 
             checkpoint_iterations, checkpoint,  debug_from):
    
   
    first_iter = 0
    res = args.resolution if args.resolution != -1 else -args.resolution
    is_raw = dataset.is_raw
    add_points = dataset.add_points

    # print(opt.feature_lr)
    # print(opt.position_lr_init)
    # print(opt.scaling_lr)
    # print(opt.sh_degree)
   

    gaussians = GaussianModel(dataset.sh_degree)
    scene = Scene(dataset, gaussians)
    # print(scene)
    # print(scene.cameras_extent)
    # sys.exit()
    gaussians.training_setup(opt)
    if checkpoint:
        # (model_params, first_iter) = torch.load(checkpoint)
        gaussians.load_ply(checkpoint)
        first_iter = 50000
        print(f"Loaded checkpoint {checkpoint} at iteration {first_iter}")

    
    bg_color = [1, 1, 1] if dataset.white_background else [0, 0, 0]
    background = torch.tensor(bg_color, dtype=torch.float32, device=dataset.data_device)
    
    os.makedirs("temp_gt", exist_ok=True)
    
    if dataset.is_binary:
        DATA_PATH = "/nobackup3/aryan/dataset/binary/f1000/"
        SPLIT = "train"
        data_npy = np.load(DATA_PATH+SPLIT+"/frames.npy", mmap_mode="r")
  
    if dataset.is_graded: # pre-load all npys on disk
        DATA_PATH = "/nobackup3/aryan/dataset_moped2/"
        data_npy_025 = np.load(DATA_PATH+"moped_rgb0025/frames.npy", mmap_mode="r")
        data_npy_050 = np.load(DATA_PATH+"moped_rgb0050/frames.npy", mmap_mode="r")
        data_npy_100 = np.load(DATA_PATH+"moped_rgb0100/frames.npy", mmap_mode="r")
        data_npy_200 = np.load(DATA_PATH+"moped_rgb0200/frames.npy", mmap_mode="r")
        data_npy_binary = np.load(DATA_PATH+"binary/f1000/train/frames.npy", mmap_mode="r")

    if dataset.is_pure_graded:
        DATA_PATH = "/nobackup3/aryan/dataset/"
        data_npy_pure_bin = np.load(DATA_PATH+"binary/f1000/train/frames.npy", mmap_mode="r")
        # data_npy_pure_bin = None

    iter_start = torch.cuda.Event(enable_timing = True)
    iter_end = torch.cuda.Event(enable_timing = True)

    viewpoint_stack = scene.getTrainCameras().copy()
    if dataset.is_pure_graded:
        sample_cam_intervals = [0]
        this_iter = -1 # NOTE - Change this to 0 when using moped2's avg frames
        for i in range(len(viewpoint_stack)):
            if viewpoint_stack[i].iterate_after != this_iter:
                sample_cam_intervals.append(i)
                this_iter = viewpoint_stack[i].iterate_after
        sample_cam_intervals.append(len(viewpoint_stack)-1)
        print("\n[+] Sample Cam Intervals:", sample_cam_intervals)    

    ema_loss_for_log = 0.0
    progress_bar = tqdm(range(first_iter, opt.iterations), desc="Training progress")
    first_iter += 1
    for iteration in range(first_iter, opt.iterations + 1):        
        if network_gui.conn == None:
            network_gui.try_connect()
        while network_gui.conn != None:
            try:
                net_image_bytes = None
                custom_cam, do_training, pipe.convert_SHs_python, pipe.compute_cov3D_python, keep_alive, scaling_modifer = network_gui.receive()
                if custom_cam != None:
                    net_image = render(custom_cam, gaussians, pipe, background, scaling_modifer)["render"]
                    net_image_bytes = memoryview((torch.clamp(net_image, min=0, max=1.0) * 255).byte().permute(1, 2, 0).contiguous().cpu().numpy())
                network_gui.send(net_image_bytes, dataset.source_path)
                if do_training and ((iteration < int(opt.iterations)) or not keep_alive):
                    break
            except Exception as e:
                network_gui.conn = None

        iter_start.record()

        gaussians.update_learning_rate(iteration)

        # Every 1000 its we increase the levels of SH up to a maximum degree
        if iteration % 1000 == 0:
            gaussians.oneupSHdegree()

        if dataset.is_pure_graded:
            if iteration == 20000:
                # And clause to keep the lr same after 20k.
                # After 20k, is the binary dataset training
                gaussians.update_other_learning_rates(iteration, factor=0.5) 
                # other lrs means apart from position. 
                # Which already has a scheduler
            elif iteration == 35000:
                gaussians.update_other_learning_rates(iteration, factor=0.1)
            elif iteration == 45000:
                gaussians.update_other_learning_rates(iteration, factor=0.05)
            elif iteration == 50000:
                gaussians.update_other_learning_rates(iteration, factor=0.02)
            elif iteration == 52500:
                gaussians.update_other_learning_rates(iteration, factor=0.01)

        
        # if not viewpoint_stack:
        #     viewpoint_stack = scene.getTrainCameras().copy()

        # Getting the camera for this iteration
        if dataset.is_pure_graded:
            if iteration < 20000: # 25fps till here
                viewpoint_cam = viewpoint_stack[randint(sample_cam_intervals[0], 
                                                        sample_cam_intervals[1])]
            elif iteration < 35000: # 50fps till here
                viewpoint_cam = viewpoint_stack[randint(sample_cam_intervals[1], 
                                                        sample_cam_intervals[2])]
            elif iteration < 45000: # 100fps till here
                viewpoint_cam = viewpoint_stack[randint(sample_cam_intervals[2], 
                                                        sample_cam_intervals[3])]
            elif iteration < 50000: # 200fps till here
                viewpoint_cam = viewpoint_stack[randint(sample_cam_intervals[3], 
                                                        sample_cam_intervals[4])]
            elif iteration <= 52500: 
                viewpoint_cam = viewpoint_stack[randint(sample_cam_intervals[4], 
                                                        sample_cam_intervals[5])]
            else: # iteration > 52500
                viewpoint_cam = viewpoint_stack[randint(sample_cam_intervals[5], 
                                                        sample_cam_intervals[6])]
        else:
            if not viewpoint_stack:
                viewpoint_stack = scene.getTrainCameras().copy()
            viewpoint_cam = viewpoint_stack.pop(randint(0, len(viewpoint_stack)-1))
        
        # print("Viewpoint Cam:", viewpoint_cam.image_name, 
        #       "Iteration:",     iteration, 
        #       "Iterate After:", viewpoint_cam.iterate_after)

        # Render
        if (iteration - 1) == debug_from:
            pipe.debug = True

        bg = torch.rand((3), device=dataset.data_device) if opt.random_background else background

        render_pkg = render(viewpoint_cam, gaussians, pipe, bg)
        image, viewspace_point_tensor, visibility_filter, radii = render_pkg["render"], render_pkg["viewspace_points"], render_pkg["visibility_filter"], render_pkg["radii"]
       
        if iteration % 10 == 0:
            num_points = gaussians.get_xyz.shape[0]

        if dataset.is_raw:
            gt_image_raw = viewpoint_cam.original_image_raw.cuda()
            pred_image_raw = torch.clamp(image, 0., 1.)
            loss = loss_fn(pred_image_raw,gt_image_raw,opt.lambda_dssim,dataset.loss_mode)
        
        elif dataset.is_binary: 
            bin_img = np.unpackbits(data_npy[int(viewpoint_cam.image_name)], axis=1)
            # DOn't need this: 
            # .convert("RGBA") / 255.
            # bg = np.array([1,1,1]) if dataset.white_background else np.array([0, 0, 0])
            # arr = norm_data[:,:,:3] * norm_data[:, :, 3:4] + bg * (1 - norm_data[:, :, 3:4])
            # Save bin_img

            gt_image = torch.from_numpy(bin_img).float().cuda().permute(2,0,1)
            pred_image = torch.clamp(image,0.,1.)
            # print(pred_image.shape, gt_image.shape) [3, 800, 800] [3, 800, 800]
            # loss = loss_fn(pred_image, gt_image, opt.lambda_dssim, dataset.loss_mode)
            loss = loss_fn(pred_image, gt_image, opt.lambda_dssim, "binary")

        elif dataset.is_graded:
            pred_image = torch.clamp(image,0.,1.)
            if viewpoint_cam.iterate_after == 24000: # NOTE-Graded: These need to be changed everytime
                bin_img = np.unpackbits(data_npy_binary[int(viewpoint_cam.image_name)], axis=1)
                gt_image = torch.from_numpy(bin_img).float().cuda().permute(2,0,1)
                loss = loss_fn(pred_image, gt_image, opt.lambda_dssim, "binary")
            elif viewpoint_cam.iterate_after == 18000:
                gt_image = torch.from_numpy(data_npy_200[int(viewpoint_cam.image_name)] / 255.).float().cuda().permute(2,0,1)
                loss = loss_fn(pred_image, gt_image, opt.lambda_dssim, "LDR")
            elif viewpoint_cam.iterate_after == 12000:
                gt_image = torch.from_numpy(data_npy_100[int(viewpoint_cam.image_name)] / 255.).float().cuda().permute(2,0,1)
                loss = loss_fn(pred_image, gt_image, opt.lambda_dssim, "LDR")
            elif viewpoint_cam.iterate_after == 6000:
                gt_image = torch.from_numpy(data_npy_050[int(viewpoint_cam.image_name)] / 255.).float().cuda().permute(2,0,1)
                loss = loss_fn(pred_image, gt_image, opt.lambda_dssim, "LDR")
            elif viewpoint_cam.iterate_after == 0:
                gt_image = torch.from_numpy(data_npy_025[int(viewpoint_cam.image_name)] / 255.).float().cuda().permute(2,0,1)
                loss = loss_fn(pred_image, gt_image, opt.lambda_dssim, "LDR")
        
        elif dataset.is_pure_graded:
            pred_image = torch.clamp(image,0.,1.)
            if "bin_" in viewpoint_cam.image_name:
                cam_idx = int(viewpoint_cam.image_name.split("_")[-1])
                bin_img = np.unpackbits(data_npy_pure_bin[cam_idx], axis=1)
                gt_image = torch.from_numpy(bin_img).float().cuda().permute(2,0,1)
                loss = loss_fn(pred_image, gt_image, opt.lambda_dssim, "binary")
            else:
                # print("[+] image path", viewpoint_cam.image_path)
                avg_frame = np.array(Image.open(viewpoint_cam.image_path).convert("RGB")) / 255.
                gt_image = torch.from_numpy(avg_frame).float().cuda().permute(2,0,1)
                loss = loss_fn(pred_image, gt_image, opt.lambda_dssim, "LDR")
        
        else:
            if viewpoint_cam.original_image is None:
                gt_image = Image.open(viewpoint_cam.image_path).convert("RGB")
                gt_image = torch.from_numpy(np.array(gt_image) / 255.).float().cuda()
            else:
                gt_image = viewpoint_cam.original_image.cuda()
            pred_image = torch.clamp(image,0.,1.)
            loss = loss_fn(pred_image,gt_image,opt.lambda_dssim,dataset.loss_mode)
        loss.backward()

        iter_end.record()

        with torch.no_grad():
           
            # Progress bar
            ema_loss_for_log = 0.4 * loss.item() + 0.6 * ema_loss_for_log
            # ema_points_for_log = 0.4 * num_points + 0.6 * ema_loss_for_log


            if iteration % 25 == 0:
                progress_bar.set_postfix({"Loss": f"{ema_loss_for_log:.{7}f}" , "Points": f"{num_points}"})
                progress_bar.update(25)

            if iteration % 200 == 0:
                pred_image = pred_image.cpu().permute(1,2,0).numpy() * 255.
                pred_image = Image.fromarray(pred_image.astype(np.uint8))
                pred_image.save(f"temp_gt/itr{iteration}_pred.png")

                gt_image = gt_image.cpu().permute(1,2,0).numpy() * 255.
                gt_image = Image.fromarray(gt_image.astype(np.uint8))
                gt_image.save(f"temp_gt/itr{iteration}_gt.png")

            if iteration == opt.iterations:
                progress_bar.close()

            # Log and save
            # # if is_raw:
            # #     training_report_HDR(tb_writer, iteration, Ll2, iter_start.elapsed_time(iter_end), testing_iterations, scene, render, (pipe, background))
            # else:
        
            #     training_report(tb_writer, iteration, Ll1, loss, l1_loss, iter_start.elapsed_time(iter_end), testing_iterations, scene, render, (pipe, background))
        


            if (iteration in saving_iterations):
                print("\n[ITER {}] Saving Gaussians".format(iteration))
                scene.save(iteration)
            # if (iteration in render_iterations): 
            #     rendering(dataset, scene, gaussians, pipe, iteration)

            # Densification
            if iteration < opt.densify_until_iter:
                # Keep track of max radii in image-space for pruning
                gaussians.max_radii2D[visibility_filter] = torch.max(gaussians.max_radii2D[visibility_filter], radii[visibility_filter])
                gaussians.add_densification_stats(viewspace_point_tensor, visibility_filter)

                if iteration > opt.densify_from_iter and iteration % opt.densification_interval == 0:
                    size_threshold = 20 if iteration > opt.opacity_reset_interval else None
                    gaussians.densify_and_prune(opt.densify_grad_threshold,
                                                opt.opacity_thresh, 
                                                scene.cameras_extent, 
                                                size_threshold) #0.005
                
                if iteration % opt.opacity_reset_interval == 0 or (dataset.white_background and iteration == opt.densify_from_iter):
                    gaussians.reset_opacity()

                # Paper implementations: Deblurring Gaussians
                if dataset.add_points and iteration % opt.point_sample_interval == 0 and iteration < opt.densify_until_iter: # N_st
                    start = time.time()
                    gaussians.add_extra_points(Np = 20_000)  # Play around with Np. Curr: 100_000
                    end = time.time()
                    print("Extra Points Time:", end-start, "seconds")

            # Optimizer step
            if iteration < opt.iterations:
                gaussians.optimizer.step()
                gaussians.optimizer.zero_grad(set_to_none = True)

            if (iteration in checkpoint_iterations):
                print("\n[ITER {}] Saving Checkpoint".format(iteration))
                torch.save((gaussians.capture(), iteration), scene.model_path + "/chkpnt" + str(iteration) + ".pth")


def rendering(dataset, scene, gaussians, pipeline, iter):
    bg_color = [1,1,1] if dataset.white_background else [0, 0, 0]
    background = torch.tensor(bg_color, dtype=torch.float32, device="cuda")
    is_cc = dataset.color_correct
    is_affine_cc = dataset.affine_color_fit
    
    if dataset.is_raw:
        # print("Rendering Traning")
        # render_set_raw(dataset.model_path, dataset.source_path, "train", iter, scene.getTrainCameras(), gaussians, pipeline, background, is_affine_cc, is_cc)
        print("Rendering Test")
        render_set_raw(dataset.model_path, dataset.source_path, "test", iter, scene.getTestCameras(), gaussians, pipeline, background, is_affine_cc, is_cc)
        project_point_cloud(dataset.model_path, dataset.source_path,iter)
    else:   
        # print("Rendering Traning")
        # render_set(dataset.model_path, "train", iter, scene.getTrainCameras(), gaussians, pipeline, background)
        print("Rendering Test")
        # NOTE: Start Fixing from here
        render_set(dataset.model_path, "test", iter, scene.getTestCameras(), gaussians, pipeline, background)
        project_point_cloud(dataset.model_path, dataset.source_path,iter)


def prepare_output_and_logger(args):    
    if not args.model_path:
        if os.getenv('OAR_JOB_ID'):
            unique_str=os.getenv('OAR_JOB_ID')
        else:
            unique_str = str(uuid.uuid4())
        args.model_path = os.path.join("./output/", unique_str[0:10])
        
    # Set up output folder
    print("Output folder: {}".format(args.model_path))
    os.makedirs(args.model_path, exist_ok = True)
    with open(os.path.join(args.model_path, "cfg_args"), 'w') as cfg_log_f:
        cfg_log_f.write(str(Namespace(**vars(args))))

    # Create Tensorboard writer
    # tb_writer = None
    # if TENSORBOARD_FOUND:
    #     tb_writer = SummaryWriter(args.model_path)
    # else:
    #     print("Tensorboard not available: not logging progress")
    # return tb_writer


def training_report(tb_writer, iteration, Ll1, loss, l1_loss, elapsed, testing_iterations, scene : Scene, renderFunc, renderArgs):
    if tb_writer:
        tb_writer.add_scalar('train_loss_patches/l1_loss', Ll1.item(), iteration)
        tb_writer.add_scalar('train_loss_patches/total_loss', loss.item(), iteration)
        tb_writer.add_scalar('iter_time', elapsed, iteration)

    # Report test and samples of training set
    if iteration in testing_iterations:
        torch.cuda.empty_cache()
        validation_configs = ({'name': 'test', 'cameras' : scene.getTestCameras()}, 
                              {'name': 'train', 'cameras' : [scene.getTrainCameras()[idx % len(scene.getTrainCameras())] for idx in range(5, 30, 5)]})

        for config in validation_configs:
            if config['cameras'] and len(config['cameras']) > 0:
                l1_test = 0.0
                psnr_test = 0.0
                for idx, viewpoint in enumerate(config['cameras']):
                    image = torch.clamp(renderFunc(viewpoint, scene.gaussians, *renderArgs)["render"], 0.0, 1.0)
                    gt_image = torch.clamp(viewpoint.original_image.to("cuda"), 0.0, 1.0)
                    if tb_writer and (idx < 5):
                        tb_writer.add_images(config['name'] + "_view_{}/render".format(viewpoint.image_name), image[None], global_step=iteration)
                        if iteration == testing_iterations[0]:
                            tb_writer.add_images(config['name'] + "_view_{}/ground_truth".format(viewpoint.image_name), gt_image[None], global_step=iteration)
                    l1_test += l1_loss(image, gt_image).mean().double()
                    psnr_test += psnr(image, gt_image).mean().double()
                psnr_test /= len(config['cameras'])
                l1_test /= len(config['cameras'])          
                print("\n[ITER {}] Evaluating {}: L1 {} PSNR {}".format(iteration, config['name'], l1_test, psnr_test))
                if tb_writer:
                    tb_writer.add_scalar(config['name'] + '/loss_viewpoint - l1_loss', l1_test, iteration)
                    tb_writer.add_scalar(config['name'] + '/loss_viewpoint - psnr', psnr_test, iteration)

        if tb_writer:
            tb_writer.add_histogram("scene/opacity_histogram", scene.gaussians.get_opacity, iteration)
            tb_writer.add_scalar('total_points', scene.gaussians.get_xyz.shape[0], iteration)
        torch.cuda.empty_cache()


def training_report_HDR(tb_writer, iteration, Ll2, elapsed, testing_iterations, scene : Scene, renderFunc, renderArgs):
    if tb_writer:
        tb_writer.add_scalar('train_loss_patches/L1_loss', Ll2.mean().item(), iteration)
        tb_writer.add_scalar('iter_time', elapsed, iteration)

    # Report test and samples of training set
    if iteration in testing_iterations:
        torch.cuda.empty_cache()
        validation_configs = ({'name': 'test', 'cameras' : scene.getTestCameras()}, 
                              {'name': 'train', 'cameras' : [scene.getTrainCameras()[idx % len(scene.getTrainCameras())] for idx in range(5, 30, 5)]})

        for config in validation_configs:
            if config['cameras'] and len(config['cameras']) > 0:
                l2_test = 0.0
                psnr_test = 0.0
                for idx, viewpoint in enumerate(config['cameras']):
                    image = torch.clamp(renderFunc(viewpoint, scene.gaussians, *renderArgs)["render"], 0.0, 1.0)
                    gt_image = torch.clamp(viewpoint.original_image_raw.to("cuda"), 0.0, 1.0)
                    if tb_writer and (idx < 5):
                        tb_writer.add_images(config['name'] + "_view_{}/render".format(viewpoint.image_name), image[None], global_step=iteration)
                        if iteration == testing_iterations[0]:
                            tb_writer.add_images(config['name'] + "_view_{}/ground_truth".format(viewpoint.image_name), gt_image[None], global_step=iteration)
                    l2_test += torch.nn.functional.mse_loss(image, gt_image).mean().double()
                    psnr_test += psnr(image, gt_image).mean().double()
                psnr_test /= len(config['cameras'])
                l2_test /= len(config['cameras'])          
                print("\n[ITER {}] Evaluating {}: L2 {} PSNR {}".format(iteration, config['name'], l2_test, psnr_test))
                if tb_writer:
                    tb_writer.add_scalar(config['name'] + '/loss_viewpoint - l2_loss', l2_test, iteration)
                    tb_writer.add_scalar(config['name'] + '/loss_viewpoint - psnr', psnr_test, iteration)

        if tb_writer:
            tb_writer.add_histogram("scene/opacity_histogram", scene.gaussians.get_opacity, iteration)
            tb_writer.add_scalar('total_points', scene.gaussians.get_xyz.shape[0], iteration)
        torch.cuda.empty_cache()


if __name__ == "__main__":
    # Set up command line argument parser
    parser = ArgumentParser(description="Training script parameters")
    lp = ModelParams(parser)
    op = OptimizationParams(parser)
    pp = PipelineParams(parser)
    parser.add_argument('--ip', type=str, default="127.0.0.1")
    parser.add_argument('--port', type=int, default=6009)
    parser.add_argument('--debug_from', type=int, default=-1)
    parser.add_argument('--detect_anomaly', action='store_true', default=False)
    parser.add_argument("--test_iterations", nargs="+", type=int, default=[7_000, 30_000])

    # NOTE-Pure Graded: Save whenever data changes to higher fps
    # parser.add_argument("--save_iterations", nargs="+", type=int, default=[20_000, 40_000, 
    #                                                                        50_000, 60_000, 
    #                                                                        65_000, 70_000])
    parser.add_argument("--save_iterations", nargs="+", type=int, default=[10_000, 30_000, 50_000])
    
    parser.add_argument("--render_iterations", nargs="+", type=int, default=[30_000])
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--checkpoint_iterations", nargs="+", type=int, default=[])
    parser.add_argument("--start_checkpoint", type=str, default = None)
    # parser.add_argument("--densify_grad_threh", type=float, default = 0.0001)
    # parser.add_argument("--densify_iter", type=int, default = 15_000)
    # parser.add_argument("--iters", type=int, default = 30_000)
    # parser.add_argument("--per_dense", type=int, default = 0.01)
    # parser.add_argument("--res", type=int, default = 4)
    # parser.add_argument("--Ll1_weight", type=float, default = 0.)
    # parser.add_argument("--Lssim_weight", type=float, default = 0.)
    # parser.add_argument("--use_bayer_mask", type = str, default = "true")
    args = parser.parse_args(sys.argv[1:])
    args.save_iterations.append(args.iterations)
    prepare_output_and_logger(args)
    
    
    print("Optimizing " + args.model_path)
    
   
    # Initialize system state (RNG)
    safe_state(args.quiet)

    # Start GUI server, configure and run training
    network_gui.init(args.ip, args.port)
    torch.autograd.set_detect_anomaly(args.detect_anomaly)

    training(lp.extract(args), op.extract(args), pp.extract(args), 
             args.render_iterations, args.test_iterations, args.save_iterations, 
             args.checkpoint_iterations, args.start_checkpoint, args.debug_from)

    # All done
    print("\nTraining complete.")

