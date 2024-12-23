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

import os
import random
import json
from utils.system_utils import searchForMaxIteration
# from scene.dataset_readers_raw import sceneLoadTypeCallbacks as rawsceneloader
from scene.dataset_readers import sceneLoadTypeCallbacks as sceneloader
from scene.dataset_readers_binary import sceneLoadTypeCallbacks as binarysceneloader
from scene.dataset_readers_graded import sceneLoadTypeCallbacks as gradedsceneloader
from scene.dataset_readers_pure_graded import sceneLoadTypeCallbacks as pure_gradedsceneloader
from scene.gaussian_model import GaussianModel
# from scene.gm_aryan import GaussianModel
from arguments import ModelParams
from utils.camera_utils import cameraList_from_camInfos, camera_to_JSON

class Scene:

    gaussians : GaussianModel

    def __init__(self, args : ModelParams, gaussians : GaussianModel, load_iteration=None, 
                 shuffle=True, resolution_scales=[1.0]):
        """b
        :param path: Path to colmap scene main folder.
        """
       
        self.model_path = args.model_path
        self.loaded_iter = None
        self.gaussians = gaussians
        # print("[+] Is Binary?", args.is_binary)
        # self.callback = rawsceneloader if args.is_raw else sceneloader 
        self.callback = binarysceneloader if args.is_binary else sceneloader
        self.callback = gradedsceneloader if args.is_graded else self.callback
        self.callback = pure_gradedsceneloader if args.is_pure_graded else self.callback


        if load_iteration:
            if load_iteration == -1:
                self.loaded_iter = searchForMaxIteration(os.path.join(self.model_path, "point_cloud"))
            else:
                self.loaded_iter = load_iteration
            print("Loading trained model at iteration {}".format(self.loaded_iter))

        self.train_cameras = {}
        self.test_cameras = {}
        
        print("Given path:", os.path.join(args.source_path))

        if os.path.exists(os.path.join(args.source_path, "sparse")):
            # temp fix for raw3dgs
            if args.is_raw:
                scene_info = self.callback["Colmap"](args.source_path, args.images, args.eval, "demosaic", args.denoise_method)
            else:
                scene_info = self.callback["Colmap"](args.source_path, args.images, args.eval)
        elif not args.is_graded and not args.is_pure_graded and os.path.exists(os.path.join(args.source_path, "transforms.json")):
            print("Found transforms.json file, assuming Blender data set!")
            scene_info = self.callback["Blender"](args.source_path, args.white_background, args.eval)
        elif args.is_graded:
            print("[+] Graded Scene: Assuming Blender dataset.\n Iterations still hard-coded (5k intervals)")
            scene_info = self.callback["Blender"](args.source_path, args.white_background, args.eval)
        elif args.is_pure_graded:
            print("[+] Pure Graded Scene: Assuming Blender dataset.\n Iteration intervals still hard-coded!")
            scene_info = self.callback["Blender"](args.source_path, args.white_background, args.eval)
        else:
            assert False, "> Could not recognize scene type!"

        if not self.loaded_iter:
            with open(scene_info.ply_path, 'rb') as src_file, open(os.path.join(self.model_path, "input.ply") , 'wb') as dest_file:
                dest_file.write(src_file.read())
            json_cams = []
            camlist = []
            if scene_info.test_cameras:
                camlist.extend(scene_info.test_cameras)
            if scene_info.train_cameras:
                camlist.extend(scene_info.train_cameras)
            for id, cam in enumerate(camlist):
                json_cams.append(camera_to_JSON(id, cam))
            with open(os.path.join(self.model_path, "cameras.json"), 'w') as file:
                json.dump(json_cams, file)

        if not args.is_graded and not args.is_pure_graded and shuffle:
            random.shuffle(scene_info.train_cameras)  # Multi-res consistent random shuffling
            random.shuffle(scene_info.test_cameras)  # Multi-res consistent random shuffling
        elif args.is_graded or args.is_pure_graded: # Do not shuffle graded scenes (they are internally shuffled (per fps))
            random.shuffle(scene_info.test_cameras)
        
        self.cameras_extent = scene_info.nerf_normalization["radius"]

        for resolution_scale in resolution_scales:
            print("\nLoading Training Cameras")
            self.train_cameras[resolution_scale] = cameraList_from_camInfos(scene_info.train_cameras, resolution_scale, args)
            print("Loading Test Cameras")
            self.test_cameras[resolution_scale] = cameraList_from_camInfos(scene_info.test_cameras, resolution_scale, args)

        if self.loaded_iter:
            self.gaussians.load_ply(os.path.join(self.model_path,
                                                    "point_cloud",
                                                    "iteration_" + str(self.loaded_iter),
                                                    "point_cloud.ply"))
        else:
            self.gaussians.create_from_pcd(scene_info.point_cloud, self.cameras_extent)


    def save(self, iteration):
        point_cloud_path = os.path.join(self.model_path, "point_cloud/iteration_{}".format(iteration))
        self.gaussians.save_ply(os.path.join(point_cloud_path, "point_cloud.ply"))


    def getTrainCameras(self, scale=1.0):
        return self.train_cameras[scale]


    def getTestCameras(self, scale=1.0):
        return self.test_cameras[scale]
