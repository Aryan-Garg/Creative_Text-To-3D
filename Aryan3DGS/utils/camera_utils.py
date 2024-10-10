#
# Copyright (C) 2023, Inria
# GRAPHDECO research group, https://team.inria.fr/graphdeco
# All rights reserved.
#
# This software is free for non-commercial, research and evaluation use 
# under the terms of the LICENSE.md file.
#
# For inquiries contact  george.drettakis@inria.fr
#

from scene.cameras import Camera, CameraRAW, CameraBin, CameraGraded
import numpy as np
from utils.general_utils import PILtoTorch, NPtoTorch
from utils.graphics_utils import fov2focal

WARNED = False

def loadCam(args, id, cam_info, resolution_scale):
    if args.is_raw:
        orig_w, orig_h = cam_info.raw_image.shape[1], cam_info.raw_image.shape[0]
      
    else:
        # NOTE ToG: original was L25. New is L27.
        # orig_w, orig_h = cam_info.image.size
        # print("Correct", orig_w, orig_h)
        orig_w, orig_h = cam_info.width, cam_info.height

    if args.resolution in [1, 2, 4, 8]:
        resolution = round(orig_w/(resolution_scale * args.resolution)), round(orig_h/(resolution_scale * args.resolution))
    else:  # should be a type that converts to float
        if args.resolution == -1:
            if orig_w > 1600:
                global WARNED
                if not WARNED:
                    print("[ INFO ] Encountered quite large input images (>1.6K pixels width), rescaling to 1.6K.\n "
                        "If this is not desired, please explicitly specify '--resolution/-r' as 1")
                    WARNED = True
                global_down = orig_w / 1600
            else:
                global_down = 1
        else:
            global_down = orig_w / args.resolution

        scale = float(global_down) * float(resolution_scale)
        resolution = (int(orig_w / scale), int(orig_h / scale))

    if args.is_raw:
        resized_image_raw = NPtoTorch(cam_info.raw_image, resolution)
        gt_raw_image = resized_image_raw[:3, ...]
    
        return CameraRAW(colmap_id=cam_info.uid, R=cam_info.R, T=cam_info.T, 
                    FoVx=cam_info.FovX, FoVy=cam_info.FovY,raw_image=gt_raw_image, 
                    image_name=cam_info.image_name, uid=id, data_device=args.data_device, meta =  cam_info.meta, post_fn = cam_info.post_fn)
    
    elif args.is_binary:
        return CameraBin(colmap_id=cam_info.uid, 
                         R=cam_info.R, 
                         T=cam_info.T, 
                         FoVx=cam_info.FovX, FoVy=cam_info.FovY, 
                        # NOTE:  image=gt_image, 
                         image_path=cam_info.image_path,
                         image_name=cam_info.image_name, 
                         uid=id, 
                         data_device=args.data_device)
    elif args.is_graded or args.is_pure_graded:
        return CameraGraded(colmap_id=cam_info.uid, 
                         R=cam_info.R, 
                         T=cam_info.T, 
                         FoVx=cam_info.FovX, FoVy=cam_info.FovY, 
                        # NOTE:  image=gt_image, 
                         image_path=cam_info.image_path,
                         image_name=cam_info.image_name, 
                         iterate_after=cam_info.iterate_after,
                         uid=id, 
                         data_device=args.data_device)
    else:
        if cam_info.image is None:
            gt_image = None
        else:
            resized_image_rgb = PILtoTorch(cam_info.image, resolution)
            gt_image = resized_image_rgb[:3, ...]
        return Camera(colmap_id=cam_info.uid, R=cam_info.R, T=cam_info.T, 
                  FoVx=cam_info.FovX, FoVy=cam_info.FovY, 
                  image=gt_image, image_name=cam_info.image_name, uid=id, data_device=args.data_device)

def cameraList_from_camInfos(cam_infos, resolution_scale, args):
    camera_list = []

    for id, c in enumerate(cam_infos):
        camera_list.append(loadCam(args, id, c, resolution_scale))

    return camera_list

def camera_to_JSON(id, camera : Camera):
    Rt = np.zeros((4, 4))
    Rt[:3, :3] = camera.R.transpose()
    Rt[:3, 3] = camera.T
    Rt[3, 3] = 1.0

    W2C = np.linalg.inv(Rt)
    pos = W2C[:3, 3]
    rot = W2C[:3, :3]
    serializable_array_2d = [x.tolist() for x in rot]
    camera_entry = {
        'id' : id,
        'img_name' : camera.image_name,
        'width' : camera.width,
        'height' : camera.height,
        'position': pos.tolist(),
        'rotation': serializable_array_2d,
        'fy' : fov2focal(camera.FovY, camera.height),
        'fx' : fov2focal(camera.FovX, camera.width)
    }
    return camera_entry
