import time

import numpy as np
import pyrealsense2 as rs


class RealSenseSource:
    """Aligned RGB-D input from an Intel RealSense camera."""

    def __init__(self, config: dict):
        self.color_width = config.get("color_width", 640)
        self.color_height = config.get("color_height", 480)
        self.depth_width = config.get("depth_width", 640)
        self.depth_height = config.get("depth_height", 480)
        self.fps = config.get("fps", 30)

        self.pipeline = rs.pipeline()
        self.config = rs.config()
        self.align = rs.align(rs.stream.color)

    def open(self) -> bool:
        self.config.enable_stream(
            rs.stream.depth,
            self.depth_width,
            self.depth_height,
            rs.format.z16,
            self.fps,
        )
        self.config.enable_stream(
            rs.stream.color,
            self.color_width,
            self.color_height,
            rs.format.bgr8,
            self.fps,
        )
        self.pipeline.start(self.config)
        return True

    def read(self) -> tuple[bool, np.ndarray | None, object | None, float]:
        frames = self.pipeline.wait_for_frames()
        aligned_frames = self.align.process(frames)

        depth_frame = aligned_frames.get_depth_frame()
        color_frame = aligned_frames.get_color_frame()
        if not depth_frame or not color_frame:
            return False, None, None, 0.0

        color_image = np.asanyarray(color_frame.get_data())
        timestamp_ms = time.time() * 1000.0
        return True, color_image, depth_frame, timestamp_ms

    def release(self) -> None:
        self.pipeline.stop()
