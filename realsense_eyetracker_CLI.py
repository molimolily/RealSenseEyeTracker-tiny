import pyrealsense2 as rs
import mediapipe
import cv2
import numpy as np
from dataclasses import dataclass
from pythonosc import udp_client
import sys
import time
import socket
import ipaddress
import json
import glob

WINDOW_NAME = "EyeTracker"
EYE_LANDMARKS = [468, 473]

class EyeTracker:
    def __init__(self, serial, width=640, height=480, fps=30, is_flip=False, enable_estimation_compensation=False):
        self.serial = serial
        self.width = width
        self.height = height
        self.fps = fps
        self.is_flip = is_flip
        self.enable_estimation_compensation = enable_estimation_compensation
        self.pipeline_started = False
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        
        self.color_image = np.zeros((self.height, self.width, 3), dtype=np.uint8)
    
    def _configure_pipeline(self):
        try:
            self.config.enable_device(self.serial)
            self.config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, self.fps)
            self.config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)

            self.mp_face_mesh = mediapipe.solutions.face_mesh
            self.mp_drawing = mediapipe.solutions.drawing_utils
            self.mp_drawing_styles = mediapipe.solutions.drawing_styles
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.3,
                min_tracking_confidence=0.5
            )
            return True
        except Exception as e:
            print(f"Configuration Error: {e}")
            return False

    def start(self):
        result = self._configure_pipeline()
        if not result:
            return False
        self.pipeline.start(self.config)
        self.pipeline_started = True
        self.intrinsics = self.pipeline.get_active_profile().get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
        align_to = rs.stream.color
        self.align = rs.align(align_to)
        return True

    def update_image(self):
        frames = self.pipeline.wait_for_frames()
        aligned_frames = self.align.process(frames)
        color_frame = aligned_frames.get_color_frame()
        self.depth_frame = aligned_frames.get_depth_frame()
        if not color_frame or not self.depth_frame:
            return None
        
        color_data = np.asanyarray(color_frame.get_data())
        if self.is_flip:
            self.color_image = cv2.flip(color_data, -1)
        else:
            self.color_image = color_data
    
    def track_eyes(self):
        results = self.face_mesh.process(self.color_image)
        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                self.mp_drawing.draw_landmarks(
                    image=self.color_image,
                    landmark_list=face_landmarks,
                    connections=self.mp_face_mesh.FACEMESH_TESSELATION,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_tesselation_style()
                )
                self.mp_drawing.draw_landmarks(
                    image=self.color_image,
                    landmark_list=face_landmarks,
                    connections=self.mp_face_mesh.FACEMESH_CONTOURS,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_contours_style()
                )
                self.mp_drawing.draw_landmarks(
                    image=self.color_image,
                    landmark_list=face_landmarks,
                    connections=self.mp_face_mesh.FACEMESH_IRISES,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_iris_connections_style()
                )

                point = face_landmarks.landmark[EYE_LANDMARKS[0]]
                u = np.clip(int(point.x * self.width), 0, self.width - 1)
                v = np.clip(int(point.y * self.height), 0, self.height - 1)
                depth = self.get_depth(u, v)
                left_eye = (u, v, depth)

                point = face_landmarks.landmark[EYE_LANDMARKS[1]]
                u = np.clip(int(point.x * self.width), 0, self.width - 1)
                v = np.clip(int(point.y * self.height), 0, self.height - 1)
                depth = self.get_depth(u, v)
                right_eye = (u, v, depth)

                return left_eye, right_eye
        return None, None
    
    def get_depth(self, u, v):
        if self.is_flip:
            u = self.width - u - 1
            v = self.height - v - 1
        return self.depth_frame.get_distance(u, v)

    def estimate_eye_position(self, left_eye, right_eye):
        if self.enable_estimation_compensation:
            left_eye_position = self.deprojection(left_eye)
            right_eye_position = self.deprojection(right_eye)
            return left_eye_position, right_eye_position
        else:
            left_eye_position = self.deprojection(left_eye)
            right_eye_position = self.deprojection(right_eye)
        return left_eye_position, right_eye_position

    def transform_uv_to_norm_image_coords(self, u, v):
        x = (u - self.intrinsics.ppx) / self.intrinsics.fx
        y = -(v - self.intrinsics.ppy) / self.intrinsics.fy
        return x, y
    
    def deprojection(self, eye):
        u = eye[0]
        v = eye[1]
        depth = eye[2]
        x, y = self.transform_uv_to_norm_image_coords(u, v)
        x *= depth
        y *= depth
        return x, y, depth

    def get_eye_position(self):
        self.update_image()
        left_eye, right_eye = self.track_eyes()
        if left_eye is not None and right_eye is not None:
            return self.estimate_eye_position(left_eye, right_eye)
        return None, None
        
    def get_color_image(self):
        return self.color_image

    def stop(self):
        if self.pipeline_started:
            self.pipeline_started = False
            self.pipeline.stop()
        if self.face_mesh:
            self.face_mesh.close()

class OSCSender:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        try:
            self.client = udp_client.SimpleUDPClient(ip, port)
        except Exception as e:
            print(f"OSC Client Error: {e}")
            self.client = None
    
    def send_eye_position(self, left_eye, right_eye):
        if self.client is not None:
            self.client.send_message("/LeftEye", left_eye)
            self.client.send_message("/RightEye", right_eye)

            # temporary center (right-handed coordinate system)
            center = [(-left_eye[0] - right_eye[0]) / 2, (left_eye[1] + right_eye[1]) / 2, (left_eye[2] + right_eye[2]) / 2]
            self.client.send_message("/Center", center)


class FPSTimer:
    def __init__(self):
        self.start_time = time.time()
        self.frame_count = 0
        self.fps = 0
        self.wait_time = 1

    def set_wait_time(self, wait_time):
        self.wait_time = wait_time

    def get_fps(self):
        return self.fps
    
    def update(self):
        current_time = time.time()
        elapsed_time = current_time - self.start_time
        if elapsed_time > self.wait_time:
            self.fps = self.frame_count / elapsed_time
            self.frame_count = 0
            self.start_time = time.time()
            return True
        self.frame_count += 1
        return False

@dataclass
class CONFIG:
    serial: str = None
    ip: str = None
    port: int = 8000
    width: int = 640
    height: int = 480
    fps: int = 60
    is_flip: bool = True
    enable_estimation_compensation: bool = False
    show_image: bool = True
    print_fps: bool = True

def load_config(path):
    config = CONFIG()
    if path is None:
        context = rs.context()
        for camera in context.query_devices():
            serial = camera.get_info(rs.camera_info.serial_number)
            config.serial = serial
            break
        if config.serial is None:
            print("No camera is found.")
            return None
        config.ip = socket.gethostbyname(socket.gethostname())
        return config
    try:
        print(f"Loading config from {path}")
        with open(path, "r") as f:
            data = json.load(f)
            if "serial" in data:
                config.serial = data["serial"]
            else:
                print("serial is not found in the config file.")
                return
            
            if "ip" in data:
                ip = data["ip"]
                if ipaddress.ip_address(ip):
                    config.ip = ip
                else:
                    print("ip address is invalid.")
                    return
                if ip == "":
                    host_name = socket.gethostname()
                    config.ip = socket.gethostbyname(host_name)
            else:
                print("ip is not found in the config file.")
                return
            
            if "port" in data:
                if type(data["port"]) == int:
                    port = int(data["port"])
                    if 0 <= port <= 65535:
                        config.port = port
                    elif port == -1:
                        config.port = 8000
                    else:
                        print("port number is invalid.")
                        return
                else:
                    print("port number must be integer.")
                    return
            else:
                print("port is not found in the config file.")
                return
            
            if "width" in data:
                if type(data["width"]) == int:
                    width = int(data["width"])
                    if width == -1:
                        config.width = 640
                    else:
                        config.width = width
                else:
                    print("width must be integer.")
                    return
            else:
                print("width is not found in the config file.")
            
            if "height" in data:
                if type(data["height"]) == int:
                    height = int(data["height"])
                    if height == -1:
                        config.height = 480
                    else:
                        config.height = height
                else:
                    print("height must be integer.")
                    return
            else:
                print("height is not found in the config file.")
            
            if "fps" in data:
                if type(data["fps"]) == int:
                    fps = int(data["fps"])
                    if fps == -1:
                        config.fps = 30
                    else:
                        config.fps = fps
                else:
                    print("fps must be integer.")
                    return
            else:
                print("fps is not found in the config file.")

            if "is_flip" in data:
                if type(data["is_flip"]) == bool:
                    config.is_flip = data["is_flip"]
                else:
                    print("is_flip must be boolean.")
                    return
            else:
                print("is_flip is not found in the config file.")

            if "enable_estimation_compensation" in data:
                if type(data["enable_estimation_compensation"]) == bool:
                    config.enable_estimation_compensation = data["enable_estimation_compensation"]
                else:
                    print("enable_estimation_compensation must be boolean.")
                    return
            else:
                print("enable_estimation_compensation is not found in the config file.")
            
            if "show_image" in data:
                if type(data["show_image"]) == bool:
                    config.show_image = data["show_image"]
                else:
                    print("show_image must be boolean.")
                    return
            else:
                print("show_image is not found in the config file.")

            if "print_fps" in data:
                if type(data["print_fps"]) == bool:
                    config.print_fps = data["print_fps"]
                else:
                    print("print_fps must be boolean.")
                    return
            else:
                print("print_fps is not found in the config file.")

        print("complete loading config")
        print(f"serial: {config.serial}")
        print(f"ip: {config.ip}")
        print(f"port: {config.port}")
        print(f"width: {config.width}")
        print(f"height: {config.height}")
        print(f"fps: {config.fps}")
        print(f"is_flip: {config.is_flip}")
        print(f"enable_estimation_compensation: {config.enable_estimation_compensation}")
        print(f"show_image: {config.show_image}")
        print(f"print_fps: {config.print_fps}")
        return config
    except Exception as e:
        print(f"Loading Error: {e}")
        return None

    
def main(path):
    config = load_config(path)
    if config is None:
        print("Failed to initialize config.")
        return
    eye_tracker = EyeTracker(
        serial=config.serial,
        width=config.width,
        height=config.height,
        fps=config.fps,
        is_flip=config.is_flip,
        enable_estimation_compensation=config.enable_estimation_compensation
    )
    sender = OSCSender(config.ip, config.port)
    try:
        if config.print_fps:
            timer = FPSTimer()
            timer.set_wait_time(2)
        result = eye_tracker.start()
        if not result:
            print("Failed to start the eye tracker.")
            return
        if config.show_image:
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
            cv2.resizeWindow(WINDOW_NAME, config.width, config.height)
        while True:
            if config.print_fps:
                if timer.update(): 
                    print(f"FPS: {timer.get_fps()}")
            left_eye, right_eye = eye_tracker.get_eye_position()
            if left_eye is not None and right_eye is not None:
                sender.send_eye_position(left_eye, right_eye)
            if config.show_image:
                cv2.imshow(WINDOW_NAME, eye_tracker.get_color_image())
            if cv2.waitKey(1) == 27 or cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        eye_tracker.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        json_files = glob.glob("*.json")
        if len(json_files) > 0:
            path = json_files[0]
        else:
            path = None
            print("json file is not found. default settings will be used.")
    main(path)