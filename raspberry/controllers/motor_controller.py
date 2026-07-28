import time


class MotorController:
    def __init__(self, command_timeout_sec=0.5):
        self.command_timeout_sec = command_timeout_sec
        self.last_command_at = 0.0
        self.current_motion = "stop"

    def move(self, direction, speed=0.4):
        self.last_command_at = time.time()
        self.current_motion = direction
        print(f"[motor] move direction={direction} speed={speed}")

    def stop(self, reason="stop"):
        if self.current_motion != "stop":
            print(f"[motor] stop reason={reason}")
        self.current_motion = "stop"

    def failsafe_tick(self):
        if self.current_motion == "stop":
            return
        if time.time() - self.last_command_at > self.command_timeout_sec:
            self.stop(reason="command timeout")

