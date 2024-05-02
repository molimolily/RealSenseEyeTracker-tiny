import pyrealsense2 as rs
import ipaddress
import socket
import json

class Config:
    def __init__(self, serial=None, port=None, is_flip=None):
        self.serials = self.load_serials_from_connected_devices()
        self.serial: str = serial
        if self.serial is None:
            self.serial: str = self.serials[0] if len(self.serials) > 0 else None
        self.ip: str = socket.gethostbyname(socket.gethostname())
        self.port: int = port
        if self.port is None:
            self.port: int = 8000
        self.width: int = 640
        self.height: int = 480
        self.fps: int = 60
        self.is_flip: bool = is_flip
        if self.is_flip is None:
            self.is_flip: bool = False
        self.enable_depth_estimation: bool = False
        self.show_image: bool = True
        self.print_fps: bool = False

    @staticmethod
    def load_serials_from_connected_devices():
        context = rs.context()
        serials = []
        for camera in context.query_devices():
            serial = camera.get_info(rs.camera_info.serial_number)
            serials.append(serial)
        return serials
    
    @staticmethod
    def load_names_from_connected_devices():
        context = rs.context()
        names = []
        for camera in context.query_devices():
            name = camera.get_info(rs.camera_info.name)
            names.append(name)
        return names
    
    def get_host_ip(self):
        return socket.gethostbyname(socket.gethostname())
    
    def get_connected_device_count(self):
        return len(self.serials)

    def load_config(self, path):
        if path is None:
            print("set default config")
            if self.serial is None:
                print("No camera is found.")
                return False
            return True
        try:
            print(f"Loading config from {path}")
            with open(path, "r") as f:
                data = json.load(f)
                if "serial" in data:
                    serial = data["serial"]
                    print(f"serial: {serial}")
                    if serial == "":
                        serial = self.serial
                        print(f"set default serial {self.serial}")
                    if serial in self.serials:
                        self.serial = serial
                    else:
                        print("serial is not found in the connected devices.")
                        return False
                    self.serial = data["serial"]
                else:
                    print("serial is not found in the config file.")
                    return False
                
                if "ip" in data:
                    ip = data["ip"]
                    if ip == "":
                        ip = self.get_host_ip()
                        print(f"set default ip {self.ip}")
                    if ipaddress.ip_address(ip):
                        self.ip = ip
                    else:
                        print("ip address is invalid.")
                        return False
                else:
                    print("ip is not found in the config file.")
                    return False
                
                if "port" in data:
                    if type(data["port"]) == int:
                        port = int(data["port"])
                        if 1023 < port <= 65535:
                            self.port = port
                        elif port == -1:
                            self.port = 8000
                            print(f"set default port {self.port}")
                        elif 0 <= port <= 1023:
                            print("0-1023 are well-known ports. They are reserved for system services.")
                            return False
                        else:
                            print("port number is invalid.")
                            return False
                    else:
                        print("port number must be integer.")
                        return False
                else:
                    print("port is not found in the config file.")
                    return False
                
                if "width" in data:
                    if type(data["width"]) == int:
                        width = int(data["width"])
                        if width == -1:
                            self.width = 640
                            print(f"set default width {self.width}")
                        else:
                            self.width = width
                    else:
                        print("width must be integer.")
                        return False
                else:
                    print("width is not found in the config file.")
                    return False
                
                if "height" in data:
                    if type(data["height"]) == int:
                        height = int(data["height"])
                        if height == -1:
                            self.height = 480
                            print(f"set default height {self.height}")
                        else:
                            self.height = height
                    else:
                        print("height must be integer.")
                        return False
                else:
                    print("height is not found in the config file.")
                    return False
                
                if "fps" in data:
                    if type(data["fps"]) == int:
                        fps = int(data["fps"])
                        if fps == -1:
                            self.fps = 30
                            print(f"set default fps {self.fps}")
                        else:
                            self.fps = fps
                    else:
                        print("fps must be integer.")
                        return False
                else:
                    print("fps is not found in the config file.")
                    return False
                
                if "is_flip" in data:
                    if type(data["is_flip"]) == bool:
                        self.is_flip = data["is_flip"]
                    else:
                        print(f"is_flip must be boolean. set default is_flip {self.is_flip}.")
                else:
                    print("is_flip is not found in the config file.")
                    return False
                
                if "enable_depth_estimation" in data:
                    if type(data["enable_depth_estimation"]) == bool:
                        self.enable_depth_estimation = data["enable_depth_estimation"]
                    else:
                        print(f"enable_depth_estimation must be boolean. set default enable_depth_estimation {self.enable_depth_estimation}.")
                else:
                    print("enable_depth_estimation is not found in the config file.")
                    return False
                
                if "show_image" in data:
                    if type(data["show_image"]) == bool:
                        self.show_image = data["show_image"]
                    else:
                        print(f"show_image must be boolean. set default show_image {self.show_image}.")
                else:
                    print("show_image is not found in the config file.")
                    return False
                
                if "print_fps" in data:
                    if type(data["print_fps"]) == bool:
                        self.print_fps = data["print_fps"]
                    else:
                        print(f"print_fps must be boolean. set default print_fps {self.print_fps}.")
                else:
                    print("print_fps is not found in the config file.")
                    return False
                
            print("complete loading config")
            print(f"serial: {self.serial}")
            print(f"ip: {self.ip}")
            print(f"port: {self.port}")
            print(f"width: {self.width}")
            print(f"height: {self.height}")
            print(f"fps: {self.fps}")
            print(f"is_flip: {self.is_flip}")
            print(f"enable_depth_estimation: {self.enable_depth_estimation}")
            print(f"show_image: {self.show_image}")
            print(f"print_fps: {self.print_fps}")
            return True
        except Exception as e:
            print(f"Loading Error: {e}")
            return False