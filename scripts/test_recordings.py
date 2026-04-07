#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if TYPE_CHECKING:
    import numpy as np
    from src.pipeline import PosePipeline
    from src.visualization import Visualizer


SUPPORTED_EXTENSIONS = {".bag", ".json", ".mp4"}
VIDEO_STEM_SUFFIXES = ("_sidebyside",)
MPL_CONFIG_DIR = Path("/tmp") / "mmai_posture_matplotlib"


MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))


@dataclass
class RecordingSession:
    session_id: str
    stem: str
    relative_parent: Path
    bag_path: Path | None = None
    mp4_path: Path | None = None
    json_path: Path | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the posture detector against recorded sessions in a data directory."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "data",
        help="Directory containing recorded .bag, .json, and .mp4 files.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config" / "default.yaml",
        help="Path to config YAML file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "recording_tests",
        help="Directory for CSV summaries and optional rendered videos.",
    )
    parser.add_argument(
        "--session",
        type=str,
        default=None,
        help="Only run a single session id or stem instead of everything in the data directory.",
    )
    parser.add_argument(
        "--prefer",
        choices=("bag", "mp4"),
        default="bag",
        help="Which file type to prefer when both exist for the same session.",
    )
    parser.add_argument(
        "--render-video",
        action="store_true",
        help="Write an annotated MP4 for each processed session.",
    )
    parser.add_argument(
        "--display",
        action="store_true",
        help="Show a live playback window while processing.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional limit for quick smoke tests.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search recursively under the data directory.",
    )
    return parser.parse_args()


def discover_sessions(data_dir: Path, recursive: bool) -> list[RecordingSession]:
    pattern = "**/*" if recursive else "*"
    files = sorted(
        path for path in data_dir.glob(pattern) if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    sessions: dict[str, RecordingSession] = {}

    for path in files:
        relative_path = path.relative_to(data_dir)
        relative_parent = relative_path.parent
        stem = normalise_recording_stem(path.stem)
        session_id = str(relative_parent / stem) if relative_parent != Path(".") else stem
        session = sessions.setdefault(
            session_id,
            RecordingSession(session_id=session_id, stem=stem, relative_parent=relative_parent),
        )
        suffix = path.suffix.lower()
        if suffix == ".bag":
            session.bag_path = path
        elif suffix == ".mp4":
            session.mp4_path = path
        elif suffix == ".json":
            session.json_path = path

    return sorted(sessions.values(), key=lambda item: item.session_id)


def normalise_recording_stem(stem: str) -> str:
    for suffix in VIDEO_STEM_SUFFIXES:
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def load_config(config_path: Path) -> dict:
    import yaml

    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_metadata(json_path: Path | None) -> dict:
    if json_path is None or not json_path.exists():
        return {}

    try:
        with json_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        print(f"[WARN] Failed to parse metadata file {json_path}: {exc}")
        return {}

    if isinstance(payload, dict):
        return payload

    return {"raw_metadata": payload}


def safe_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def metadata_fps(metadata: dict, fallback_fps: float) -> float:
    candidate_keys = ("fps", "frame_rate", "framerate", "video_fps")
    for key in candidate_keys:
        if key in metadata:
            return safe_float(metadata[key], fallback_fps)
    return fallback_fps


def choose_playable_source(session: RecordingSession, prefer: str) -> tuple[str, Path]:
    choices: list[tuple[str, Path]] = []
    if prefer == "bag":
        if session.bag_path is not None:
            choices.append(("bag", session.bag_path))
        if session.mp4_path is not None:
            choices.append(("mp4", session.mp4_path))
    else:
        if session.mp4_path is not None:
            choices.append(("mp4", session.mp4_path))
        if session.bag_path is not None:
            choices.append(("bag", session.bag_path))

    if not choices:
        raise FileNotFoundError(f"Session '{session.session_id}' has no playable .bag or .mp4 file.")

    pyrealsense_available = None
    for source_kind, source_path in choices:
        if source_kind == "bag":
            if pyrealsense_available is None:
                pyrealsense_available = has_pyrealsense2()
            if not pyrealsense_available:
                continue
        return source_kind, source_path

    raise RuntimeError(
        f"Session '{session.session_id}' has a .bag recording but pyrealsense2 is unavailable, "
        "and no fallback .mp4 was found."
    )


def has_pyrealsense2() -> bool:
    try:
        import pyrealsense2  # noqa: F401
    except ImportError:
        return False
    return True


def iter_mp4_frames(
    video_path: Path,
    metadata: dict,
    max_frames: int | None,
) -> Iterator[tuple[np.ndarray, None, float]]:
    import cv2

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video file: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = metadata_fps(metadata, 30.0)

    frame_index = 0
    try:
        while True:
            if max_frames is not None and frame_index >= max_frames:
                break

            ret, frame = capture.read()
            if not ret or frame is None:
                break

            timestamp_ms = (frame_index / fps) * 1000.0
            yield frame, None, timestamp_ms
            frame_index += 1
    finally:
        capture.release()


def iter_bag_frames(
    bag_path: Path,
    config: dict,
    max_frames: int | None,
) -> Iterator[tuple[np.ndarray, object | None, float]]:
    import numpy as np

    try:
        import pyrealsense2 as rs
    except ImportError as exc:
        raise ImportError(
            "pyrealsense2 is required to replay .bag recordings. "
            "Use --prefer mp4 for color-only playback or install the RealSense bindings."
        ) from exc

    rs_pipeline = rs.pipeline()
    rs_config = rs.config()
    rs_config.enable_device_from_file(str(bag_path), repeat_playback=False)

    realsense_cfg = config.get("realsense", {})
    rs_config.enable_stream(
        rs.stream.depth,
        realsense_cfg.get("depth_width", 640),
        realsense_cfg.get("depth_height", 480),
        rs.format.z16,
        realsense_cfg.get("fps", 30),
    )
    rs_config.enable_stream(
        rs.stream.color,
        realsense_cfg.get("color_width", 640),
        realsense_cfg.get("color_height", 480),
        rs.format.bgr8,
        realsense_cfg.get("fps", 30),
    )

    profile = rs_pipeline.start(rs_config)
    playback = profile.get_device().as_playback()
    playback.set_real_time(False)
    align = rs.align(rs.stream.color)

    frame_index = 0
    try:
        while True:
            if max_frames is not None and frame_index >= max_frames:
                break

            try:
                frames = rs_pipeline.wait_for_frames(timeout_ms=1000)
            except RuntimeError:
                break

            aligned = align.process(frames)
            color_frame = aligned.get_color_frame()
            depth_frame = aligned.get_depth_frame()
            if not color_frame:
                continue

            color_image = np.asanyarray(color_frame.get_data())
            timestamp_ms = float(color_frame.get_timestamp())
            yield color_image, depth_frame if depth_frame else None, timestamp_ms
            frame_index += 1
    finally:
        rs_pipeline.stop()


def write_csv(rows: list[dict], csv_path: Path) -> None:
    fieldnames = [
        "frame_index",
        "timestamp_ms",
        "has_pose",
        "open_posture_score",
        "is_covering_mouth",
        "is_withdrawing",
        "interaction_z_meters",
        "closest_wrist_px_x",
        "closest_wrist_px_y",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarise_rows(rows: list[dict]) -> dict:
    if not rows:
        return {
            "frames_processed": 0,
            "pose_frames": 0,
            "pose_detection_rate": 0.0,
            "mouth_cover_frames": 0,
            "withdrawal_frames": 0,
            "avg_open_posture_score": None,
            "max_interaction_z_meters": None,
        }

    pose_rows = [row for row in rows if row["has_pose"]]
    posture_scores = [row["open_posture_score"] for row in pose_rows if row["open_posture_score"] is not None]
    depth_values = [row["interaction_z_meters"] for row in pose_rows if row["interaction_z_meters"] is not None]

    return {
        "frames_processed": len(rows),
        "pose_frames": len(pose_rows),
        "pose_detection_rate": len(pose_rows) / len(rows),
        "mouth_cover_frames": sum(1 for row in pose_rows if row["is_covering_mouth"]),
        "withdrawal_frames": sum(1 for row in pose_rows if row["is_withdrawing"]),
        "avg_open_posture_score": (sum(posture_scores) / len(posture_scores)) if posture_scores else None,
        "max_interaction_z_meters": max(depth_values) if depth_values else None,
    }


def row_from_result(frame_index: int, timestamp_ms: float, result) -> dict:
    pose = result.pose
    if pose is None:
        return {
            "frame_index": frame_index,
            "timestamp_ms": timestamp_ms,
            "has_pose": False,
            "open_posture_score": None,
            "is_covering_mouth": False,
            "is_withdrawing": False,
            "interaction_z_meters": None,
            "closest_wrist_px_x": None,
            "closest_wrist_px_y": None,
        }

    closest_wrist_px = pose.closest_wrist_px or (None, None)
    return {
        "frame_index": frame_index,
        "timestamp_ms": timestamp_ms,
        "has_pose": pose.has_pose,
        "open_posture_score": pose.open_posture_score,
        "is_covering_mouth": pose.is_covering_mouth,
        "is_withdrawing": pose.is_withdrawing,
        "interaction_z_meters": pose.interaction_z_meters,
        "closest_wrist_px_x": closest_wrist_px[0],
        "closest_wrist_px_y": closest_wrist_px[1],
    }


def make_video_writer(output_path: Path, frame_size: tuple[int, int], fps: float) -> cv2.VideoWriter:
    import cv2

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(str(output_path), fourcc, fps, frame_size)


def process_session(
    session: RecordingSession,
    pipeline: PosePipeline,
    visualizer: Visualizer,
    app_config: dict,
    args: argparse.Namespace,
) -> dict:
    import cv2

    metadata = load_metadata(session.json_path)
    source_kind, source_path = choose_playable_source(session, args.prefer)
    session_output_dir = args.output_dir / session.relative_parent / session.stem
    session_output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = session_output_dir / "summary.json"
    csv_path = session_output_dir / "frames.csv"
    annotated_video_path = session_output_dir / "annotated.mp4"
    metadata_copy_path = session_output_dir / "metadata.json"

    with metadata_copy_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, sort_keys=True)

    if source_kind == "bag":
        frame_iterator = iter_bag_frames(source_path, app_config, args.max_frames)
        writer_fps = app_config.get("realsense", {}).get("fps", 30)
    else:
        frame_iterator = iter_mp4_frames(source_path, metadata, args.max_frames)
        writer_fps = metadata_fps(metadata, 30.0)

    video_writer = None
    rows: list[dict] = []
    started_at = time.time()

    for frame_index, (color_frame, depth_frame, timestamp_ms) in enumerate(frame_iterator):
        result = pipeline.process_frame(color_frame, timestamp_ms=timestamp_ms, depth_frame=depth_frame)
        rows.append(row_from_result(frame_index, timestamp_ms, result))

        rendered = None
        if args.display or args.render_video:
            rendered = visualizer.draw(color_frame, result)

        if args.render_video:
            if video_writer is None:
                frame_h, frame_w = color_frame.shape[:2]
                video_writer = make_video_writer(annotated_video_path, (frame_w, frame_h), writer_fps)
            video_writer.write(rendered if rendered is not None else color_frame)

        if args.display:
            window_name = f"Recording Test - {session.session_id}"
            cv2.imshow(window_name, rendered if rendered is not None else color_frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("[INFO] Early exit requested by user.")
                break

    if video_writer is not None:
        video_writer.release()
    if args.display:
        cv2.destroyAllWindows()

    summary = summarise_rows(rows)
    summary.update(
        {
            "session": session.stem,
            "session_id": session.session_id,
            "source_kind": source_kind,
            "source_path": str(source_path),
            "metadata_path": str(session.json_path) if session.json_path is not None else None,
            "csv_path": str(csv_path),
            "annotated_video_path": str(annotated_video_path) if args.render_video else None,
            "elapsed_sec": round(time.time() - started_at, 3),
            "metadata": metadata,
        }
    )

    write_csv(rows, csv_path)
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)

    return summary


def main() -> int:
    args = parse_args()
    if not args.data_dir.exists():
        print(f"[ERROR] Data directory not found: {args.data_dir}")
        return 1

    from src.pipeline import PosePipeline
    from src.visualization import Visualizer

    config = load_config(args.config)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    sessions = discover_sessions(args.data_dir, args.recursive)
    if args.session is not None:
        sessions = [
            session
            for session in sessions
            if session.stem == args.session or session.session_id == args.session
        ]

    if not sessions:
        print("[ERROR] No matching recording sessions found.")
        return 1

    pipeline = PosePipeline(config)
    try:
        pipeline.load_models()
    except RuntimeError as exc:
        message = str(exc)
        if "NSOpenGLPixelFormat" in message or "kGpuService" in message:
            print(
                "[ERROR] MediaPipe Pose could not start in this shell because macOS OpenGL "
                "context creation failed. This is a local runtime limitation rather than a "
                "recording-format issue."
            )
            print(
                "[ERROR] Try running from a GUI-backed terminal session, or switch the detector "
                "implementation to a backend that does not require MediaPipe's OpenGL service."
            )
            return 3
        raise
    visualizer = Visualizer(config.get("visualization", {}))

    run_summaries = []
    failures = []

    for session in sessions:
        print(f"\n[INFO] Processing session: {session.stem}")
        try:
            pipeline.reset_state()
            summary = process_session(session, pipeline, visualizer, config, args)
            run_summaries.append(summary)
            print(
                "[INFO] Completed "
                f"{session.stem}: frames={summary['frames_processed']}, "
                f"pose_rate={summary['pose_detection_rate']:.2%}, "
                f"mouth_cover={summary['mouth_cover_frames']}, "
                f"withdrawal={summary['withdrawal_frames']}"
            )
        except Exception as exc:  # noqa: BLE001
            failures.append({"session": session.stem, "error": str(exc)})
            print(f"[ERROR] Failed session {session.stem}: {exc}")

    aggregate_path = args.output_dir / "run_summary.json"
    with aggregate_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "processed_sessions": run_summaries,
                "failures": failures,
            },
            handle,
            indent=2,
            sort_keys=True,
        )

    print(f"\n[INFO] Wrote aggregate summary to {aggregate_path}")
    if failures:
        print(f"[WARN] {len(failures)} session(s) failed.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
