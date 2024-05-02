import sys
import os
import time
import tempfile
import glob
import msvcrt
import cv2
from config import Config
from eye_tracker import EyeTracker
from osc_sender import OSCSender
from fps_timer import FPSTimer

WINDOW_NAME = "Eye Tracker"

def check_serial_from_tmp_file(path,serial):
    try:
        with open(path, "r+") as f:
            used_serials = f.readlines()
            used_serials = [s.strip() for s in used_serials]
            if serial in used_serials:
                print("This camera is already in use.")
                return False
            else:
                f.write(serial + "\n")
                return True
    except FileNotFoundError:
        with open(path, "w") as f:
            f.write(serial + "\n")
            return True
        
def remove_serial_from_tmp_file(path,serial):
    try:
        with open(path, "r") as f:
            used_serials = f.readlines()
            used_serials = [s.strip() for s in used_serials]
            if serial in used_serials:
                used_serials.remove(serial)
                with open(path, "w") as f:
                    for s in used_serials:
                        f.write(s + "\n")
    except FileNotFoundError:
        pass
    
def main(path,serial=None,port=None,is_flip=False):
    config = Config(serial, port, is_flip)
    result = config.load_config(path)
    if not result:
        print("Failed to load config.")
        return
    
    temp_file_path = os.path.join(tempfile.gettempdir(), 'RealSenseEyeTracker_device_usage.txt')
    print("There is a temp file to check the device usage.")
    print(f"temp file path: {temp_file_path}")
    
    if not check_serial_from_tmp_file(temp_file_path,config.serial):
        print(f"Failed to use the camera S/N: {config.serial}")
        return
    print("Succeeded to check the device usage.")
    
    tracker = EyeTracker(
        config.serial,
        config.width,
        config.height,
        config.fps,
        config.is_flip,
        config.enable_depth_estimation
    )
    sender = OSCSender(config.ip, config.port)
    if config.print_fps:
        timer = FPSTimer()
    try:
        if config.show_image:
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW_NAME, config.width, config.height)
        if tracker.start():
            while True:
                if config.print_fps:
                    if timer.update():
                        print(f"{timer.get_fps():.2f} fps")
                left_eye, right_eye = tracker.get_eye_position()
                if left_eye is not None and right_eye is not None:
                    sender.send_eye_position(left_eye, right_eye)
                if config.show_image:
                    cv2.imshow(WINDOW_NAME, tracker.get_color_image())
                    if cv2.waitKey(1) == 27 or cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                        break
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'\x1b':  # ESCキー
                        break
    finally:
        tracker.stop()
        if config.show_image:
            cv2.destroyAllWindows()
        remove_serial_from_tmp_file(temp_file_path,config.serial)

def set_args_from_stdin():
    serials = Config.load_serials_from_connected_devices()
    serial = None
    if len(serials) == 0:
        print("No camera is found.")
        return None, None, None
    elif len(serials) == 1:
        serial = serials[0]
    else:
        print("Please specify the camera.")
        names = Config.load_names_from_connected_devices()
        for i in range(len(serials)):
            print(f"{i}: {names[i]} {serials[i]}")
        index = input("Enter the index of the camera: ")
        if not index.isdigit():
            print("Index must be a number.")
            return None, None, None
        index = int(index)
        if index < 0 or index >= len(serials):
            print("Invalid index.")
            return None, None, None
        serial = serials[index]

    port = None
    print("Please specify the port number.")
    port = input("Enter the port number: ")
    if not port.isdigit():
        print("Port number must be a number.")
        return None, None, None
    port = int(port)
    if 0 <= port <= 1023:
        print("0-1023 are well-known ports. They are reserved for system services.")
        return None, None, None
    if port < 0 or port > 65535:
        print("Invalid port number.")
        return None, None, None
    
    is_flip = None
    print("Do you want to flip the image?")
    input_str = input("Enter y/n: ")
    if input_str == "y":
        is_flip = True
    elif input_str == "n":
        is_flip = False
    else:
        print("Invalid input.")
        return None, None, None
    return serial, port, is_flip
    

if __name__ == "__main__":
    json_files = glob.glob("*.json")
    if len(sys.argv) < 2:
        if len(json_files) == 1:
            main(json_files[0])
        elif len(json_files) > 1:
            print("Please specify the path to the config file.")
            print("Available config files")
            for i in range(len(json_files)):
                print(f"{i}: {json_files[i]}")
            print(f"{len(json_files)}: do not use config file")
            index = input("Enter the index of the config file: ")
            if not index.isdigit():
                print("Index must be a number.")
                sys.exit(1)
            index = int(index)
            if index == len(json_files):
                serial, port, is_flip = set_args_from_stdin()
                if serial is None or port is None or is_flip is None:
                    print("Failed to set args.")
                    sys.exit(1)
                main(path=None, serial=serial, port=port, is_flip=is_flip)
            elif 0 <= index < len(json_files):
                main(json_files[index])
            else:
                print("Invalid index.")
                sys.exit(1)
        else:
            print("json file is not found. default settings will be used.")
            serial, port, is_flip= set_args_from_stdin()
            if serial is None or port is None or is_flip is None:
                print("Failed to set args.")
                sys.exit(1)
            main(path=None, serial=serial, port=port, is_flip=is_flip)
    else:
        if sys.argv[1] in json_files:
            main(sys.argv[1])
