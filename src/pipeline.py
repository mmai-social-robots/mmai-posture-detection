import numpy as np

from .detectors.pose_detector import PoseDetector
from .types import FrameResult


class PosePipeline:
    """Orchestrates pose detection and depth-aware safety cues."""

    def __init__(self, config: dict):
        self.pose_detector = PoseDetector(config.get("pose_detector", {}))
        self.device = config.get("device", "cpu")

    def load_models(self) -> None:
        print(f"Loading pose pipeline on {self.device}...")
        self.pose_detector.load_model(self.device)
        print("Pose pipeline ready.")

    def process_frame(
        self,
        color_frame: np.ndarray,
        timestamp_ms: float = 0.0,
        depth_frame=None,
    ) -> FrameResult:
        result = FrameResult(timestamp_ms=timestamp_ms)
        result.pose = self.pose_detector.predict(color_frame, depth_frame=depth_frame)
        return result
