import os
import sys
from PIL import Image
from typing import NamedTuple
from scene.colmap_loader import read_extrinsics_text, read_intrinsics_text, qvec2rotmat, \
    read_extrinsics_binary, read_intrinsics_binary, read_points3D_binary, read_points3D_text
from utils.graphics_utils import getWorld2View2, focal2fov, fov2focal
import numpy as np
import json
from pathlib import Path
from plyfile import PlyData, PlyElement
from utils.sh_utils import SH2RGB
from scene.gaussian_model import BasicPointCloud
import random
from tqdm import tqdm

class CameraInfo(NamedTuple):
    uid: int
    R: np.array
    T: np.array
    FovY: np.array
    FovX: np.array
    # image: np.array
    image_path: str
    image_name: str
    width: int
    height: int
    iterate_after: int = 0

class SceneInfo(NamedTuple):
    point_cloud: BasicPointCloud
    train_cameras: list
    test_cameras: list
    nerf_normalization: dict
    ply_path: str


def getNerfppNorm(cam_info):
    def get_center_and_diag(cam_centers):
        cam_centers = np.hstack(cam_centers)
        avg_cam_center = np.mean(cam_centers, axis=1, keepdims=True)
        center = avg_cam_center
        dist = np.linalg.norm(cam_centers - center, axis=0, keepdims=True)
        diagonal = np.max(dist)
        return center.flatten(), diagonal

    cam_centers = []

    for cam in cam_info:
        W2C = getWorld2View2(cam.R, cam.T)
        C2W = np.linalg.inv(W2C)
        cam_centers.append(C2W[:3, 3:4])

    center, diagonal = get_center_and_diag(cam_centers)
    radius = diagonal * 1.1

    translate = -center

    return {"translate": translate, "radius": radius}


def readColmapCameras(cam_extrinsics, cam_intrinsics, images_folder):
    cam_infos = []
    for idx, key in enumerate(cam_extrinsics):
        sys.stdout.write('\r')
        # the exact output you're looking for:
        sys.stdout.write("Reading camera {}/{}".format(idx+1, len(cam_extrinsics)))
        sys.stdout.flush()

        extr = cam_extrinsics[key]
        intr = cam_intrinsics[extr.camera_id]
        height = intr.height
        width = intr.width

        uid = intr.id
        R = np.transpose(qvec2rotmat(extr.qvec))
        T = np.array(extr.tvec)

        if intr.model=="SIMPLE_PINHOLE":
            focal_length_x = intr.params[0]
            FovY = focal2fov(focal_length_x, height)
            FovX = focal2fov(focal_length_x, width)
        elif intr.model=="PINHOLE":
            focal_length_x = intr.params[0]
            focal_length_y = intr.params[1]
            FovY = focal2fov(focal_length_y, height)
            FovX = focal2fov(focal_length_x, width)
        else:
            assert False, "Colmap camera model not handled: only undistorted datasets (PINHOLE or SIMPLE_PINHOLE cameras) supported!"

        image_path = os.path.join(images_folder, os.path.basename(extr.name))
        image_name = os.path.basename(image_path).split(".")[0]
        image = Image.open(image_path)

        cam_info = CameraInfo(uid=uid, R=R, T=T, FovY=FovY, FovX=FovX, image=image,
                              image_path=image_path, image_name=image_name, width=width, height=height)
        cam_infos.append(cam_info)
    sys.stdout.write('\n')
    return cam_infos


def fetchPly(path):
    plydata = PlyData.read(path)
    vertices = plydata['vertex']
    positions = np.vstack([vertices['x'], vertices['y'], vertices['z']]).T
    colors = np.vstack([vertices['red'], vertices['green'], vertices['blue']]).T / 255.0
    normals = np.vstack([vertices['nx'], vertices['ny'], vertices['nz']]).T
    return BasicPointCloud(points=positions, colors=colors, normals=normals)


def storePly(path, xyz, rgb):
    # Define the dtype for the structured array
    dtype = [('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
            ('nx', 'f4'), ('ny', 'f4'), ('nz', 'f4'),
            ('red', 'u1'), ('green', 'u1'), ('blue', 'u1')]
    
    normals = np.zeros_like(xyz)

    elements = np.empty(xyz.shape[0], dtype=dtype)
    attributes = np.concatenate((xyz, normals, rgb), axis=1)
    elements[:] = list(map(tuple, attributes))

    # Create the PlyData object and write to file
    vertex_element = PlyElement.describe(elements, 'vertex')
    ply_data = PlyData([vertex_element])
    ply_data.write(path)


def readColmapSceneInfo(path, images, eval, llffhold=8):
    try:
        cameras_extrinsic_file = os.path.join(path, "sparse/0", "images.bin")
        cameras_intrinsic_file = os.path.join(path, "sparse/0", "cameras.bin")
        cam_extrinsics = read_extrinsics_binary(cameras_extrinsic_file)
        cam_intrinsics = read_intrinsics_binary(cameras_intrinsic_file)
    except:
        cameras_extrinsic_file = os.path.join(path, "sparse/0", "images.txt")
        cameras_intrinsic_file = os.path.join(path, "sparse/0", "cameras.txt")
        cam_extrinsics = read_extrinsics_text(cameras_extrinsic_file)
        cam_intrinsics = read_intrinsics_text(cameras_intrinsic_file)

   
    reading_dir = "images" if images == None else images
    # BUG Fix for camdle scene 173 images stored in colmap output but only 77 scenes
    if path.split("/")[-1] == "candle":
        for i in range(78,len(cam_extrinsics)+1):
            del cam_extrinsics[i]
        for (k,v) in cam_extrinsics.items():
            print(k, v.name)
    # BUG Fix for camdle scene 173 images stored in colmap output but only 77 scenes
    if path.split("/")[-1] == "stove":
        for i in range(65,len(cam_extrinsics)+1):
            del cam_extrinsics[i]
        for (k,v) in cam_extrinsics.items():
            print(k, v.name)
    print(len(cam_extrinsics))
    # BUG Fix for camdle scene 173 images stored in colmap output but only 77 scenes
    if path.split("/")[-1] == "windowlegovary":
        for i in range(1,52):
            del cam_extrinsics[i]
        for (k,v) in cam_extrinsics.items():
            print(k, v.name)
    print(len(cam_extrinsics))
    
    cam_infos_unsorted = readColmapCameras(cam_extrinsics=cam_extrinsics, cam_intrinsics=cam_intrinsics, images_folder=os.path.join(path, reading_dir))
    cam_infos = sorted(cam_infos_unsorted.copy(), key = lambda x : x.image_name)

    # if eval:
    #     train_cam_infos = [c for idx, c in enumerate(cam_infos) if idx % llffhold != 0]
    #     test_cam_infos = [c for idx, c in enumerate(cam_infos) if idx % llffhold == 0]
   
    if eval:
        train_file_path = os.path.join(path, "train.txt")
        with open(train_file_path, 'r') as file:
            train_file = file.read().splitlines()
        test_file_path = os.path.join(path, "test.txt")
        with open(test_file_path, 'r') as file:
            test_file = file.read().splitlines()
        
        train_cam_infos = [c for idx, c in enumerate(cam_infos) if c.image_name in train_file]
        test_cam_infos = [c for idx, c in enumerate(cam_infos) if c.image_name in test_file]
    else:
        train_cam_infos = cam_infos
        test_cam_infos = []

    nerf_normalization = getNerfppNorm(train_cam_infos)

    ply_path = os.path.join(path, "sparse/0/points3D.ply")
    bin_path = os.path.join(path, "sparse/0/points3D.bin")
    txt_path = os.path.join(path, "sparse/0/points3D.txt")
    if not os.path.exists(ply_path):
        print("Converting point3d.bin to .ply, will happen only the first time you open the scene.")
        try:
            xyz, rgb, _ = read_points3D_binary(bin_path)
        except:
            xyz, rgb, _ = read_points3D_text(txt_path)
        storePly(ply_path, xyz, rgb)
    try:
        pcd = fetchPly(ply_path)
    except:
        pcd = None

    scene_info = SceneInfo(point_cloud=pcd,
                           train_cameras=train_cam_infos,
                           test_cameras=test_cam_infos,
                           nerf_normalization=nerf_normalization,
                           ply_path=ply_path)
    return scene_info


# TODO: Directly read in all the pre-processed Camera Info things and pass in img_name
# Load the img directly in train.py for the loss computation. (No need for left of right)
# This will bring down training time back to under < ~40 mins
def readCamerasFromTransforms(path, transformsfile, white_background, extension=".png"):
    splits = [0, 20000, 35000, 45000, 50000, 52500]
    cam_infos = []
    with open(os.path.join(path, transformsfile)) as json_file:
        contents = json.load(json_file)
        fovx = contents["angle_x"]
        frames = contents["frames"]
        # len_frames = len(frames) =~ 800,000
        chunk_sizes = [80000 // 25, 40000 // 25, 40000 // 50, 40000 // 100, 40000 // 200, 1] 
        # chunk size = total_frames // capture_time * fps OR total_frames // num_frames in that fps bucket 
        # Ex - Our capture time was 20s, fps was 25, so chunk size = 40000 // 25 = 1600
        for split_idx in range(len(splits)):
            these_cams = []
            this_chunk_size = chunk_sizes[split_idx]
            if this_chunk_size == 1: # binary frames. No left_right pairs.
                pbar = tqdm(total=len(frames))
                for idx_bin, frame in enumerate(frames):
                    cam_name = str(idx_bin)
                    pbar.set_description(f"Reading {idx_bin}/{len(frames)}")
                    c2w = np.array(frame["transform_matrix"])
                    c2w[:3, 1:3] *= -1
                    w2c = np.linalg.inv(c2w)
                    R = np.transpose(w2c[:3,:3])  
                    T = w2c[:3, 3]
                    image_path = os.path.join(path, "frames.npy")

                    image_name = f"bin_{cam_name}"
                    width, height = 800, 800
                    # bg = np.array([1,1,1]) if white_background else np.array([0, 0, 0])

                    fovy = focal2fov(fov2focal(fovx, width), height)
                    FovY = fovy 
                    FovX = fovx
                    these_cams.append(CameraInfo(uid=idx_bin, R=R, T=T, FovY=FovY, FovX=FovX, 
                                    image_path=image_path, image_name=image_name, 
                                    width=width, height=height, iterate_after=splits[split_idx]))
                random.shuffle(these_cams)
                print(f"Read {len(these_cams)} cameras for split {split_idx}")
                cam_infos.extend(these_cams)
            else:
                if split_idx == 0:
                    lookup_dir = "/nobackup3/aryan/dataset/avg_0012fps"
                elif split_idx == 1:
                    lookup_dir = "/nobackup3/aryan/dataset/avg_0025fps"
                elif split_idx == 2:
                    lookup_dir = "/nobackup3/aryan/dataset/avg_0050fps"
                elif split_idx == 3:
                    lookup_dir = "/nobackup3/aryan/dataset/avg_00100fps"
                elif split_idx == 4:
                    lookup_dir = "/nobackup3/aryan/dataset/avg_00200fps"

                for f in os.listdir(lookup_dir):
                    if f.endswith(".npy"):
                        cam_info = np.load(os.path.join(lookup_dir, f), allow_pickle=True).item()
                        image_name = "frame_" + str(f.split("_")[1].split(".")[0]) + ".png"
                        these_cams.append(CameraInfo(uid=cam_info['uid'], 
                                                     R=cam_info['R'], 
                                                     T=cam_info['T'], 
                                                     FovY=cam_info['FovY'], 
                                                     FovX=cam_info['FovX'], 
                                                     image_path=os.path.join(lookup_dir, image_name),
                                                     image_name=image_name, 
                                                     width=cam_info['width'], 
                                                     height=cam_info['height'], 
                                                     iterate_after=cam_info['iterate_after']))
                random.shuffle(these_cams)
                print(f"Read {len(these_cams)} cameras for split {split_idx}")
                cam_infos.extend(these_cams)
    print("Cam infos len:", len(cam_infos))
    return cam_infos


def readCamerasFromTransforms_moped2(path, transformsfile, white_background, extension=".png"):
    splits = [0, 20000, 35000, 45000, 50000, 52500]
    dirs_to_do = {"binavg0025fps": 0, 
                  "binavg0050fps": 20000,
                  "binavg0100fps": 35000,
                  "binavg0200fps": 45000,
                  "binavg1000fps": 50000}
    cam_infos = []
    for k, v in dirs_to_do.items():
        with open(os.path.join(path, k, "f1000", "train", transformsfile)) as json_file:
            contents = json.load(json_file)
            fovx = contents["angle_x"]
            frames = contents["frames"]
        
            these_cams = []
            pbar = tqdm(total=len(frames))
            for idx, frame in enumerate(frames):
                zfilled_idx = str(idx).zfill(6)
                cam_name = os.path.join(path, k, "f1000", "train", "frames") + f"/frame_{zfilled_idx}{extension}"
                image_path = os.path.join(path, cam_name)
                image_name = Path(cam_name).stem
                # image = Image.open(image_path)
                # im_data = np.array(image.convert("RGBA"))
                # bg = np.array([1,1,1]) if white_background else np.array([0, 0, 0])
                # norm_data = im_data / 255.0
                # arr = norm_data[:,:,:3] * norm_data[:, :, 3:4] + bg * (1 - norm_data[:, :, 3:4])
                # image = Image.fromarray(np.array(arr*255.0, dtype=np.byte), "RGB")
                height, width = 800, 800
                fovy = focal2fov(fov2focal(fovx, width), height)
                # pbar.set_description(f"{idx}/{len(idxs)}")
                pbar.update(1)

                c2w = np.array(frame["transform_matrix"])
                # change from OpenGL/Blender camera axes (Y up, Z back) to COLMAP (Y down, Z forward)
                c2w[:3, 1:3] *= -1

                # get the world-to-camera transform and set R, T
                w2c = np.linalg.inv(c2w)
                R = np.transpose(w2c[:3,:3])  # R is stored transposed due to 'glm' in CUDA code
                T = w2c[:3, 3]

                FovY = fovy 
                FovX = fovx
                these_cams.append(CameraInfo(uid=idx, R=R, T=T, FovY=FovY, FovX=FovX,
                                image_path=image_path, image_name=image_name,
                                width=width, height=height, iterate_after=v))
                
            random.shuffle(these_cams)
            print(f"[+] Read {len(these_cams)} cameras for {k}")
            cam_infos.extend(these_cams)
    return cam_infos



def readNerfSyntheticInfo(path, white_background, eval, extension=".png"):
    print("Reading Training Transforms")
    # train_cam_infos = readCamerasFromTransforms(path, "transforms.json", white_background, extension)
    train_cam_infos = readCamerasFromTransforms(path, "transforms.json", white_background, extension)
    nerf_normalization = getNerfppNorm(train_cam_infos)  
    
    test_cam_infos = []
    if eval:
        print("Reading Test Transforms")
        # test_cam_infos = readCamerasFromTransforms(path, "transforms.json", white_background, extension)
        test_cam_infos = readCamerasFromTransforms(path, "transforms.json", white_background, extension)
    
    # if not eval:
    #     train_cam_infos.extend(test_cam_infos)
    #     test_cam_infos = []

    # Numbers from moped RGB scene run 
    # nerf_normalization = {'translate': np.array([ 0.00519361,  0.02486794, -0.07495658], dtype=np.float32), 
                        #   'radius': 6.1275053024292}
    
    print("[+] Nerf normalization dict:", nerf_normalization)

    ply_path = os.path.join(path, "points3d.ply")
    if not os.path.exists(ply_path): # SKIP this for now
        # Since this data set has no colmap data, we start with random points
        num_pts = 100_000
        print(f"[-] Generating random point cloud ({num_pts})...")
        
        # We create random points inside the bounds of the synthetic Blender scenes
        xyz = np.random.random((num_pts, 3)) * 2.6 - 1.3
        shs = np.random.random((num_pts, 3)) / 255.0
        pcd = BasicPointCloud(points=xyz, colors=SH2RGB(shs), normals=np.zeros((num_pts, 3)))

        storePly(ply_path, xyz, SH2RGB(shs) * 255)
    try:
        # NOTE: Hard coded PCD from RGB scene
        pcd = fetchPly(ply_path)
        print(f"[+] Point cloud loaded from {ply_path}")
    except:
        pcd = None
        print("[-] Could not read the point cloud from the .ply file. pcd is None.")

    scene_info = SceneInfo(point_cloud=pcd,
                           train_cameras=train_cam_infos,
                           test_cameras=test_cam_infos,
                           nerf_normalization=nerf_normalization,
                           ply_path=ply_path)
    return scene_info

sceneLoadTypeCallbacks = {
    "Colmap": readColmapSceneInfo,
    "Blender" : readNerfSyntheticInfo
}