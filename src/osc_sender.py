from pythonosc import udp_client

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