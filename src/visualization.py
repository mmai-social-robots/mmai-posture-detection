import time

import cv2
import numpy as np

from .types import FrameResult


class Visualizer:
    """Renders pose status overlays on top of RealSense color frames."""

    def __init__(self, config: dict):
        self.show_landmarks = config.get("show_landmarks", True)
        self.show_pose_text = config.get("show_pose_text", True)
        self.show_depth_marker = config.get("show_depth_marker", True)
        self.show_fps = config.get("show_fps", True)
        self._prev_time = time.time()
        self._fps = 0.0

    def _update_fps(self) -> None:
        now = time.time()
        dt = now - self._prev_time
        if dt > 0:
            self._fps = 0.3 * (1.0 / dt) + 0.7 * self._fps
        self._prev_time = now

    def draw(self, frame: np.ndarray, result: FrameResult) -> np.ndarray:
        self._update_fps()
        overlay = frame.copy()
        h, w = overlay.shape[:2]

        if self.show_pose_text and result.pose is not None:
            pose = result.pose
            posture_color = (
                0,
                int(255 * pose.open_posture_score),
                int(255 * (1 - pose.open_posture_score)),
            )
            cv2.putText(
                overlay,
                f"Posture Score: {pose.open_posture_score:.2f}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                posture_color,
                2,
            )

            if pose.interaction_z_meters is not None:
                cv2.putText(
                    overlay,
                    f"Interaction Z: {pose.interaction_z_meters:.2f}m",
                    (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 0),
                    2,
                )

            if pose.is_covering_mouth:
                cv2.putText(
                    overlay,
                    "STATE: SCARED (mouth/face covered)",
                    (20, 120),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75,
                    (0, 0, 255),
                    2,
                )
            elif pose.is_withdrawing:
                cv2.putText(
                    overlay,
                    "STATE: SUDDEN WITHDRAWAL",
                    (20, 120),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75,
                    (0, 0, 255),
                    2,
                )

            if self.show_depth_marker and pose.closest_wrist_px is not None:
                cv2.circle(overlay, pose.closest_wrist_px, 8, (255, 255, 0), -1)

        if self.show_fps:
            cv2.putText(
                overlay,
                f"FPS: {self._fps:.1f}",
                (w - 140, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

        return overlay
