#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

import cv2
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import PosePipeline
from src.realsense_source import RealSenseSource
from src.visualization import Visualizer


def main():
    parser = argparse.ArgumentParser(description="Real-time pose perception from RealSense RGB-D video")
    parser.add_argument(
        "--config",
        type=str,
        default=str(PROJECT_ROOT / "config" / "default.yaml"),
        help="Path to config YAML file",
    )
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    pipeline = PosePipeline(config)
    pipeline.load_models()

    source = RealSenseSource(config.get("realsense", {}))
    source.open()

    visualizer = Visualizer(config.get("visualization", {}))

    print("Pose pipeline running. Press 'q' to quit.")

    try:
        while True:
            ret, color_frame, depth_frame, timestamp_ms = source.read()
            if not ret or color_frame is None:
                continue

            result = pipeline.process_frame(
                color_frame,
                timestamp_ms=timestamp_ms,
                depth_frame=depth_frame,
            )
            display = visualizer.draw(color_frame, result)

            cv2.imshow("Pose Perception Pipeline", display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        source.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
