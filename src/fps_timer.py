import time

class FPSTimer:
    def __init__(self, wait_time=2):
        self.start_time = time.time()
        self.frame_count = 0
        self.fps = 0
        self.wait_time = wait_time

    def set_wait_time(self, wait_time):
        self.wait_time = wait_time

    def get_fps(self):
        return self.fps
    
    def update(self):
        current_time = time.time()
        elapsed_time = current_time - self.start_time
        if elapsed_time > self.wait_time:
            #print(f"elapsed_time: {elapsed_time}, frame_count: {self.frame_count}")
            self.fps = self.frame_count / elapsed_time
            self.frame_count = 0
            self.start_time = time.time()
            return True
        self.frame_count += 1
        return False