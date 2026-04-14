#pre-final-artillery-detection.py

import argparse
import csv
import os
import platform
import sys
import math
import time
from pathlib import Path
import torch
import numpy as np
import cv2
from math import radians, cos, sin, sqrt, atan2, asin, degrees
from dronekit import connect, VehicleMode, LocationGlobalRelative
from pymavlink import mavutil
import rasterio

FILE = Path(__file__).resolve()
ROOT = FILE.parents[0]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
ROOT = Path(os.path.relpath(ROOT, Path.cwd()))

from ultralytics.utils.plotting import Annotator, colors, save_one_box

from models.common import DetectMultiBackend
from utils.dataloaders import IMG_FORMATS, VID_FORMATS, LoadImages, LoadScreenshots, LoadStreams
from utils.general import (
    LOGGER, Profile, check_file, check_img_size, check_imshow,
    check_requirements, colorstr, increment_path, non_max_suppression,
    print_args, scale_boxes, strip_optimizer, xyxy2xywh
)
from utils.torch_utils import select_device, smart_inference_mode
import logging

LOG_FILE = "/home/nisha-/agra_demo/result_afd-u.txt"
logger = logging.getLogger("backend_logger")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
logger.addHandler(file_handler)
logger.info("anything")

def connect_vehicle(connection_str: str):
    logger.info(f"[INFO] Connecting to vehicle at {connection_str}...")
    vehicle = connect(connection_str, wait_ready=False)
    logger.info("[INFO] Connected successfully\n")
    return vehicle

# =========================================================
# CAMERA PARAMETERS

sensor_width_mm = 5.76
sensor_height_mm = 4.29
focal_length_mm = 88.4
image_width = 1280
image_height = 720

# =========================================================

# ================= DEM LOADER =================
DEM_PATH = "/home/nisha-/Downloads/rasters_SRTM15Plus/output_SRTM15Plus.tif"
dem_src = rasterio.open(DEM_PATH)

def get_elevation(lat, lon):
    try:
        if not (dem_src.bounds.left <= lon <= dem_src.bounds.right and
                dem_src.bounds.bottom <= lat <= dem_src.bounds.top):
            return None

        for val in dem_src.sample([(lon, lat)]):
            z = val[0]
            return None if np.isnan(z) else float(z)

    except Exception as e:
        print("DEM error:", e)
        return None

@smart_inference_mode()
def run(
    drone_lat,
    drone_lon,
    center_lat,
    center_lon,
    vehicle=None,
    weights=ROOT / "v2.pt",
    source=ROOT / "data/images",
    data=ROOT / "data_v2.yaml",
    imgsz=(640, 640),
    conf_thres=0.25,
    iou_thres=0.45,
    max_det=1000,
    device="",
    view_img=False,
    save_txt=False,
    save_format=0,
    save_csv=False,
    save_conf=False,
    save_crop=False,
    nosave=False,
    classes=None,
    agnostic_nms=False,
    augment=False,
    visualize=False,
    update=False,
    project=ROOT / "runs/detect",
    name="exp",
    exist_ok=False,
    line_thickness=3,
    hide_labels=False,
    hide_conf=False,
    half=False,
    dnn=False,
    vid_stride=1,
    
):
    
    source = str(source)
    save_img = not nosave and not source.endswith(".txt")
    is_file = Path(source).suffix[1:] in (IMG_FORMATS + VID_FORMATS)
    is_url = source.lower().startswith(("rtsp://", "rtmp://", "http://", "https://"))
    webcam = source.isnumeric() or source.endswith(".streams") or (is_url and not is_file)
    screenshot = source.lower().startswith("screen")

    if is_url and is_file:
        source = check_file(source)
    save_dir = increment_path(Path(project) / name, exist_ok=exist_ok)
    (save_dir / "labels" if save_txt else save_dir).mkdir(parents=True, exist_ok=True)

    # ================= MODEL =================
    device = select_device(device)
    model = DetectMultiBackend(weights, device=device, dnn=dnn, data=data, fp16=half)
    stride, names, pt = model.stride, model.names, model.pt
    imgsz = check_img_size(imgsz, s=stride)

    # ================= DATA =================
    bs = 1
    if webcam:
        view_img = check_imshow(warn=True)
        dataset = LoadStreams(source, img_size=imgsz, stride=stride, auto=pt, vid_stride=vid_stride)
        bs = len(dataset)
    elif screenshot:
        dataset = LoadScreenshots(source, img_size=imgsz, stride=stride, auto=pt)
    else:
        dataset = LoadImages(source, img_size=imgsz, stride=stride, auto=pt, vid_stride=vid_stride)
    vid_path, vid_writer = [None] * bs, [None] * bs
    model.warmup(imgsz=(1, 3, *imgsz))
    seen, windows, dt = 0, [], (Profile(device=device), Profile(device=device), Profile(device=device))
    
    # ---------- MANUAL GEO INPUT ----------
    #drone_lat  = 28.60468
    #drone_lon  = 77.368759
    #center_lat = 28.60490
    #center_lon = 77.368900
    
    last_print_time = 0
    data_buffer = []
    print_count = 0       # counts how many times output has been printed
    paused = False        # pause flag
    z_ground = None       # holds last known ground elevation for display
    for path, im, im0s, vid_cap, s in dataset:
        
        # ---------- PREPROCESS ----------
        with dt[0]:
            im = torch.from_numpy(im).to(model.device)
            im = im.half() if model.fp16 else im.float()
            im /= 255
            if len(im.shape) == 3:
                im = im[None]

        # ---------- INFERENCE ----------
        with dt[1]:
            pred = model(im, augment=augment, visualize=False)

        # ---------- NMS ----------
        with dt[2]:
            pred = non_max_suppression(pred, conf_thres, iou_thres, classes, agnostic_nms, max_det=max_det)

        for i, det in enumerate(pred):
            seen += 1
            if webcam:
                p, im0 = path[i], im0s[i].copy()
            else:
                p, im0 = path, im0s.copy()
            p = Path(p)
            annotator = Annotator(im0, line_width=line_thickness, example=str(names))
            h, w = im0.shape[:2]

            # FIX 1: Use actual frame dimensions instead of hardcoded values
            center_x = w // 2
            center_y = h // 2
            
            # Draw center crosshair — bold and clear
            # Black outline for contrast
            cv2.drawMarker(
                im0,
                (center_x, center_y),
                (0, 0, 0),
                markerType=cv2.MARKER_CROSS,
                markerSize=60,
                thickness=6
            )
            # Bright green inner cross
            cv2.drawMarker(
                im0,
                (center_x, center_y),
                (0, 255, 0),
                markerType=cv2.MARKER_CROSS,
                markerSize=60,
                thickness=3
            )
            # Center dot for precision
            cv2.circle(im0, (center_x, center_y), 5, (0, 0, 0), -1)
            cv2.circle(im0, (center_x, center_y), 3, (0, 255, 0), -1)

            # ================= TELEMETRY =================
            #try:
                #lat_A = vehicle.location.global_frame.lat
                #lon_A = vehicle.location.global_frame.lon
                #altitude_a = vehicle.location.global_frame.alt
                #altitude_m = vehicle.location.global_relative_frame.alt
                #if vehicle.gimbal.pitch is not None:
                    #pitch_deg = vehicle.gimbal.pitch
                #else:
                    #pitch_deg = math.degrees(vehicle.attitude.pitch)
            #except Exception as e:
                #print("Telemetry read failed:", e)
                #continue
            #pitch_rad = math.radians(pitch_deg)
            
            # ================= TELEMETRY =================
            try:
                #drone_lat = vehicle.location.global_frame.lat
                #drone_lon = vehicle.location.global_frame.lon
                drone_lat = 28.7736
                drone_lon = 77.14825
                
                # Absolute altitude (AMSL) — only for display
                altitude_abs = vehicle.location.global_frame.alt

                # Relative altitude (AGL/home) — used in calculations
                #altitude_m = vehicle.location.global_relative_frame.alt
                altitude_m = 10
                logger.info(f"altitude: {altitude_m}")
                
                # ----- PRINT VALUES -----
                if altitude_abs is not None:
                    logger.info(f"Global Altitude (AMSL): {altitude_abs:.2f} m")
                else:
                    print("Global Altitude not available")

                print(f"Relative Altitude (AGL): {altitude_m:.2f} m")

            except Exception as e:
                logger.error(f"Telemetry read failed: {e}")
                continue
    
            # ================= CAMERA GEOMETRY =================
            hfov_rad = 2 * math.atan(sensor_width_mm / (2 * focal_length_mm))
            vfov_rad = 2 * math.atan(sensor_height_mm / (2 * focal_length_mm))
            logger.info(f"hfov_rad: {hfov_rad:.6f}, vfov_rad: {vfov_rad:.6f}")

            #L = altitude_m / max(math.cos(pitch_rad), 0.001)
            # distance between drone GPS and frame center GPS
            # ================= SLANT DISTANCE =================
            #dlat = center_lat - drone_lat
            #dlon = center_lon - drone_lon
            #horizontal = math.sqrt(dlat*dlat + dlon*dlon) * 1.113195e5
            #L = math.sqrt(horizontal**2 + altitude_m**2)
            #print(f"Slant_distance: {L:.3f}")
            
            # Difference in coordinates
            dlat = center_lat - drone_lat
            dlon = center_lon - drone_lon

            # Convert degree difference → meters
            dy = dlat * 111320
            dx = dlon * 111320 * math.cos(math.radians(center_lat))
            
            # Ground distance between drone ground point and frame center
            horizontal = math.sqrt(dx**2 + dy**2)

            # Slant distance (true distance from camera to ground point)
            L = math.sqrt(horizontal**2 + altitude_m**2)
            ground_width_m = 2 * L * math.tan(hfov_rad / 2)
            ground_height_m = 2 * L * math.tan(vfov_rad / 2)
            logger.info(f"ground_width_m: {ground_width_m:.6f}, ground_height_m: {ground_height_m:.6f}")
            mpp_x = ground_width_m / w
            mpp_y = ground_height_m / h
            logger.info(f"mpp_x: {mpp_x:.6f}, mpp_y: {mpp_y:.6f}")

            # ================= DETECTIONS =================
            # only draw bboxes and run geo calc when NOT paused
            if len(det) and not paused:
                # DEBUG: print all detected class indices and names
                detected_classes = det[:, 5].unique().tolist()
                print(f"[DEBUG] Raw detections: {len(det)} | Classes found: {[names[int(c)] for c in detected_classes]}")

                # Removed wrong class filter (was filtering class 0 = 'person' from COCO)
                # Now detects all classes from v2.pt model
                det[:, :4] = scale_boxes(im.shape[2:], det[:, :4], im0.shape).round()

                for *xyxy, conf, cls in det:
                    x1, y1, x2, y2 = map(int, xyxy)

                    # FIX 2: Use actual bbox center instead of hardcoded values
                    cx = (x1 + x2) // 2
                    cy = (y1 + y2) // 2

                    # draw bbox center
                    cv2.circle(im0, (cx, cy), 5, (0,0,255), -1)

                    # ---------- OFFSET FROM FRAME CENTER ----------
                    dx_px = cx - center_x      # RIGHT = +
                    dy_px = center_y - cy      # UP = +

                    logger.info(f"dx_px: {dx_px:.6f}, dy_px: {dy_px:.6f}")

                    # ---------- PIXEL → METERS ----------
                    dx_m = dx_px * mpp_x
                    dy_m = dy_px * mpp_y
                    logger.info(f"dx_m: {dx_m:.6f}, dy_m: {dy_m:.6f}")

                    dir_x = "+x" if dx_m > 0 else "-x"
                    dir_y = "+y" if dy_m > 0 else "-y"

                    logger.info(f"dx_m: {dx_m:.2f} ({dir_x})   dy_m: {dy_m:.2f} ({dir_y})")
                    logger.info(f"Direction → X: {dir_x} | Y: {dir_y}")

                    # ---------- DISTANCE ----------
                    distance_m = math.sqrt(dx_m**2 + dy_m**2)
                    logger.info(f"distance_meter: {distance_m:.6f}")

                    # ---------- GEO CONVERSION ----------
                    cos_lat = math.cos(math.radians(center_lat))
                    cos_lat = max(cos_lat, 1e-6)

                    delta_lat = dy_m / 111320
                    delta_lon = dx_m / (111320 * cos_lat)

                    lat_B = center_lat + delta_lat
                    lon_B = center_lon + delta_lon
                    logger.info(f"lat_B: {lat_B:.6f}, lon_B: {lon_B:.6f}")
                    #print(f"Distance: {distance_m:.2f} m")
                    logger.info(f"final_lat,final_lon: {lat_B:.6f}, {lon_B:.6f}")
                    #print(f"altitude")

                    current_time = time.time()
                    if current_time - last_print_time >= 1.0:
                        data_buffer.append({
                            "drone_lat": drone_lat,
                            "drone_lon": drone_lon,
                            "center_lat": center_lat,
                            "center_lon": center_lon,
                            "alt": altitude_m,
                            "lat_b": lat_B,
                            "lon_b": lon_B,
                            "dist": distance_m,
                            "dx": dx_m,
                            "dy": dy_m
                        })

                        if len(data_buffer) >= 5:

                            avg = lambda key: sum(d[key] for d in data_buffer) / len(data_buffer)

                            avg_drone_lat = avg("drone_lat")
                            avg_drone_lon = avg("drone_lon")
                            avg_center_lat = avg("center_lat")
                            avg_center_lon = avg("center_lon")
                            avg_alt = avg("alt")
                            avg_lat_b = avg("lat_b")
                            avg_lon_b = avg("lon_b")
                            avg_dist = avg("dist")
                            avg_dx = avg("dx")
                            avg_dy = avg("dy")

                            dir_x = "X" if avg_dx > 0 else "-X"
                            dir_y = "y" if avg_dy > 0 else "-y"

                            # DEM elevation
                            a = center_lat
                            b = center_lon
                            z_ground_center = get_elevation(a, b)
                            z_ground_target = get_elevation(avg_lat_b, avg_lon_b)

                            if z_ground_center is not None and z_ground_target is not None:
                                offset_z = z_ground_target - z_ground_center
                            else:
                                offset_z = None

                            z_center_str = f"{z_ground_center:.2f} m" if z_ground_center is not None else "OUTSIDE DEM"
                            z_target_str = f"{z_ground_target:.2f} m" if z_ground_target is not None else "OUTSIDE DEM"
                            z_offset_str = f"{offset_z:.2f} m" if offset_z is not None else "N/A"

                            print(
                                f"DroneLat: {avg_drone_lat:.6f} | "
                                f"DroneLon: {avg_drone_lon:.6f} | "
                                f"CenterLat: {avg_center_lat:.6f} | "
                                f"CenterLon: {avg_center_lon:.6f} | "
                                f"Alt: {avg_alt:.2f} m | "
                                f"Lat_B: {avg_lat_b:.6f} | "
                                f"Lon_B: {avg_lon_b:.6f} | "
                                f"Dist: {avg_dist:.2f} m | "
                                f"Offset: {abs(avg_dx):.2f} m {dir_x}, "
                                f"{abs(avg_dy):.2f} m {dir_y} | "
                                f"Z Center: {z_center_str} | "
                                f"Z Target: {z_target_str} | "
                                f"Z Offset: {z_offset_str}\n" + "-"*120
                            )

                            data_buffer.clear()

                            # increment print count after every 5 bbox prints
                            print_count += 1

                            # after every 2 prints (= 10 bbox detections), pause
                            if print_count % 2 == 0:
                                paused = True
                                print("\n" + "="*60)
                                print("  10 Frames Calculated — Press R to Resume Detection")
                                print("="*60 + "\n")

                        last_print_time = current_time

                    label = f"a-blast{conf:.2f}"
                    annotator.box_label(xyxy, label, color=colors(0, True))

                # save frame only when bbox detected
                if len(det):
                    save_path = str(save_dir / f"frame_{seen}.jpg")
                    cv2.imwrite(save_path, im0)

            # ================= DISPLAY — always runs every frame =================
            im0 = annotator.result()

            if view_img:
                display_frame = cv2.resize(im0, (1280, 720))

                # draw overlay on video window when paused — bottom right corner
                if paused:
                    overlay = display_frame.copy()
                    cv2.rectangle(overlay, (900, 610), (1280, 720), (0, 165, 255), -1)
                    cv2.addWeighted(overlay, 0.7, display_frame, 0.3, 0, display_frame)
                    cv2.putText(display_frame, "10 Frames Calculated",
                                (910, 663), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
                    cv2.putText(display_frame, "Press R to Resume",
                                (910, 700), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

                # imshow and waitKey always called — video never freezes
                cv2.imshow(str(p), display_frame)
                key = cv2.waitKey(1) & 0xFF
                if paused and (key == ord('r') or key == ord('R')):
                    paused = False
                    print("[INFO] Resuming detection...")

        LOGGER.info(f"{s}{dt[1].dt * 1e3:.1f}ms inference")

    if update:
        strip_optimizer(weights[0])

def parse_opt():
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", nargs="+", type=str, default=ROOT / "v2.pt", help="model path or triton URL")
    parser.add_argument("--source", type=str, default="/home/nisha-/yolov5_doaff/trail.mp4", help="file/dir/URL/glob/screen/0(webcam)")
    parser.add_argument("--data", type=str, default=ROOT / "data_v2.yaml", help="(optional) dataset.yaml path")
    parser.add_argument("--imgsz", "--img", "--img-size", nargs="+", type=int, default=[640], help="inference size h,w")
    parser.add_argument("--conf-thres", type=float, default=0.25, help="confidence threshold")
    parser.add_argument("--iou-thres", type=float, default=0.45, help="NMS IoU threshold")
    parser.add_argument("--max-det", type=int, default=1000, help="maximum detections per image")
    parser.add_argument("--device", default="", help="cuda device, i.e. 0 or 0,1,2,3 or cpu")
    #parser.add_argument("--view-img", action="store_true", help="show results")
    parser.add_argument("--view-img", action="store_true", default=True, help="show results")
    parser.add_argument("--save-txt", action="store_true", help="save results to *.txt")
    parser.add_argument(
        "--save-format",
        type=int,
        default=0,
        help="whether to save boxes coordinates in YOLO format or Pascal-VOC format when save-txt is True, 0 for YOLO and 1 for Pascal-VOC",
    )
    parser.add_argument("--save-csv", action="store_true", help="save results in CSV format")
    parser.add_argument("--save-conf", action="store_true", help="save confidences in --save-txt labels")
    parser.add_argument("--save-crop", action="store_true", help="save cropped prediction boxes")
    parser.add_argument("--nosave", action="store_true", help="do not save images/videos")
    parser.add_argument("--classes", nargs="+", type=int, help="filter by class: --classes 0, or --classes 0 2 3")
    parser.add_argument("--agnostic-nms", action="store_true", help="class-agnostic NMS")
    parser.add_argument("--augment", action="store_true", help="augmented inference")
    parser.add_argument("--visualize", action="store_true", help="visualize features")
    parser.add_argument("--update", action="store_true", help="update all models")
    parser.add_argument("--project", default=ROOT / "runs/detect", help="save results to project/name")
    parser.add_argument("--name", default="exp", help="save results to project/name")
    parser.add_argument("--exist-ok", action="store_true", help="existing project/name ok, do not increment")
    parser.add_argument("--line-thickness", default=3, type=int, help="bounding box thickness (pixels)")
    parser.add_argument("--hide-labels", default=False, action="store_true", help="hide labels")
    parser.add_argument("--hide-conf", default=False, action="store_true", help="hide confidences")
    parser.add_argument("--half", action="store_true", help="use FP16 half-precision inference")
    parser.add_argument("--dnn", action="store_true", help="use OpenCV DNN for ONNX inference")
    parser.add_argument("--vid-stride", type=int, default=1, help="video frame-rate stride")
    opt = parser.parse_args()
    opt.imgsz *= 2 if len(opt.imgsz) == 1 else 1  # expand
    print_args(vars(opt))
    return opt

def start_with_coordinates(center_lat, center_lon):

    connection_string = "127.0.0.1:14551"
    vehicle = connect_vehicle(connection_string)
    
    # ---------- GET DRONE POSITION FROM TELEMETRY ----------
    drone_lat = 28.7736
    drone_lon = 77.14825

    opt = parse_opt()

    logger.info(f"drone_lat: {drone_lat}")
    logger.info(f"drone_lon: {drone_lon}")
    logger.info(f"center_lat: {center_lat}")
    logger.info(f"center_lon: {center_lon}")

    run(
    drone_lat=drone_lat,
    drone_lon=drone_lon,
    center_lat=center_lat,
    center_lon=center_lon,
    vehicle=vehicle,
    **vars(opt)
    )


if __name__ == "__main__":
    print("Run GUI file instead")
