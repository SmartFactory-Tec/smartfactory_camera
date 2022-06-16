import cv2
from threading import Thread, Lock
from typing import TypedDict
from Camera import Camera
from server.CameraController import CameraController
from server.PersonDetector import PersonDetector
from server.utils import draw_detection_boxes, calculate_target_position
from copy import deepcopy


class SystemConfig(TypedDict):
    address: str
    port: int
    user: str
    password: str
    pid_x: tuple[float, float, float]
    pid_y: tuple[float, float, float]

class CameraSystem():
    def __init__(self, camera_config: SystemConfig):
        self.__camera_config = camera_config
        self.__latest_frame = None
        self.__latest_detections = []

        self.__frame_lock = Lock()
        self.__detections_lock = Lock()

        self.__thread = Thread(target=self.__update)
        self.__thread.start()

    def __async_init(self):
        address = self.__camera_config["address"]
        port = self.__camera_config["port"]
        user = self.__camera_config["user"]
        password = self.__camera_config["password"]
        pid_x  = self.__camera_config["pid_x"]
        pid_y  = self.__camera_config["pid_y"]
        self.__camera = Camera(address, port, user, password)
        self.__controller = CameraController(self.__camera, pid_x, pid_y)
        self.__detector = PersonDetector()

    def __update(self):
        self.__async_init()

        while True:
            frame = self.__camera.get_latest_frame()

            if frame is None: continue

            frame = frame.copy()

            scale = 0.4
            resized_frame = cv2.resize(frame, dsize=(int(frame.shape[1] * scale), int(frame.shape[0] * scale)),
                                       interpolation=cv2.INTER_AREA)

            boxes, weights = self.__detector.get_detections(resized_frame)

            for idx, box in enumerate(boxes):
                x, y, w, h = box
                x = int(x / scale)
                y = int(y / scale)
                w = int(w / scale)
                h = int(h / scale)
                boxes[idx] = (x, y, w, h)

            draw_detection_boxes(frame, boxes, weights)

            x_error = 0
            y_error = 0
            if len(weights) != 0:
                focus_x, focus_y = calculate_target_position(boxes, weights)

                cv2.rectangle(frame, (focus_x - 5, focus_y - 5), (focus_x + 5, focus_y + 5), (255, 0, 0), 2)
                x_error = 2 * (focus_x - (frame.shape[1] / 2)) / frame.shape[1]
                y_error = 2 * ((frame.shape[0] / 2) - focus_y) / frame.shape[0]

            self.__controller.set_error(x_error, y_error)

            with self.__detections_lock:
                self.__latest_detections = zip(boxes, weights)

            with self.__frame_lock:
                self.__latest_frame = frame

    def get_latest_frame(self):
        return self.__camera.get_latest_frame()

    def get_latest_detections(self):
        with self.__detections_lock:
            return self.__latest_detections

    def get_latest_detections_frame(self):
        with self.__frame_lock:
            return self.__latest_frame
