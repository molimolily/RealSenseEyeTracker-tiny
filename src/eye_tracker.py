import numpy as np
import pyrealsense2 as rs
import cv2
import mediapipe


EYE_LANDMARKS = [468, 473]
IRIS_LANDMARKS = [[471,469],[476,474]]
IRIS_SIZE = 0.0117 # m


class EyeTracker:
    def __init__(self, serial, width=640, height=480, fps=30, is_flip=False, enable_depth_estimation=False):
        self.serial = serial
        self.width = width
        self.height = height
        self.fps = fps
        self.is_flip = is_flip
        self.enable_depth_estimation = enable_depth_estimation
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
        try:
            self.pipeline.start(self.config)
            print("pipeline started.")
            self.pipeline_started = True
            self.intrinsics = self.pipeline.get_active_profile().get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
            align_to = rs.stream.color
            self.align = rs.align(align_to)
            return True
        except Exception as e:
            print(f"Pipeline Error: {e}")
            return False

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
                u, v = self.transform_point_to_uv(point)
                depth = self.get_depth(u, v)
                left_eye = (u, v, depth)

                point = face_landmarks.landmark[EYE_LANDMARKS[1]]
                u, v = self.transform_point_to_uv(point)
                depth = self.get_depth(u, v)
                right_eye = (u, v, depth)

                point = face_landmarks.landmark[IRIS_LANDMARKS[0][0]]
                u1, v1 = self.transform_point_to_uv(point)
                point = face_landmarks.landmark[IRIS_LANDMARKS[0][1]]
                u2, v2 = self.transform_point_to_uv(point)
                left_iris = ((u1,v1), (u2,v2))

                point = face_landmarks.landmark[IRIS_LANDMARKS[1][0]]
                u1, v1 = self.transform_point_to_uv(point)
                point = face_landmarks.landmark[IRIS_LANDMARKS[1][1]]
                u2, v2 = self.transform_point_to_uv(point)
                right_iris = ((u1,v1), (u2,v2))

                return left_eye, right_eye, left_iris, right_iris
        return None, None, None, None
    
    def transform_point_to_uv(self, point):
        u = np.clip(int(point.x * self.width), 0, self.width - 1)
        v = np.clip(int(point.y * self.height), 0, self.height - 1)
        return u, v
    
    def get_depth(self, u, v):
        if self.is_flip:
            u = self.width - u - 1
            v = self.height - v - 1
        return self.depth_frame.get_distance(u, v)

    def estimate_eye_position(self, left_eye, right_eye, left_iris, right_iris):
        if self.enable_depth_estimation:
            left_eye_estimated_depth = self.depth_estimation(left_iris)
            right_eye_estimated_depth = self.depth_estimation(right_iris)
            #print(f"left eye depth error: {np.abs(left_eye[2] - left_eye_estimated_depth)}, right eye depth error: {np.abs(right_eye[2] - right_eye_estimated_depth)}") 
            left_eye = (left_eye[0], left_eye[1], left_eye_estimated_depth)
            right_eye = (right_eye[0], right_eye[1], right_eye_estimated_depth)
            left_eye_position = self.deprojection(left_eye)
            right_eye_position = self.deprojection(right_eye)
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
    
    def depth_estimation(self, iris):
        iris1_norm_coords = self.transform_uv_to_norm_image_coords(iris[0][0], iris[0][1])
        iris2_norm_coords = self.transform_uv_to_norm_image_coords(iris[1][0], iris[1][1])
        iris_size_norm_coords = np.linalg.norm(np.array(iris1_norm_coords) - np.array(iris2_norm_coords))
        return IRIS_SIZE / iris_size_norm_coords

    def get_eye_position(self):
        self.update_image()
        left_eye, right_eye, left_iris, right_iris = self.track_eyes()
        if left_eye is not None and right_eye is not None and left_iris is not None and right_iris is not None:
            return self.estimate_eye_position(left_eye, right_eye, left_iris, right_iris)
        return None, None
        
    def get_color_image(self):
        return self.color_image

    def stop(self):
        if self.pipeline_started:
            self.pipeline_started = False
            self.pipeline.stop()
            print("pipeline stopped.")
        if self.face_mesh:
            self.face_mesh.close()