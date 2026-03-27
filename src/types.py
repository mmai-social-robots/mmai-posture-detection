from dataclasses import dataclass
from typing import Optional


@dataclass
class PoseResult:
    open_posture_score: float
    is_covering_mouth: bool
    is_withdrawing: bool
    interaction_z_meters: Optional[float] = None
    closest_wrist_px: Optional[tuple[int, int]] = None
    has_pose: bool = True


@dataclass
class FrameResult:
    pose: Optional[PoseResult] = None
    timestamp_ms: float = 0.0
