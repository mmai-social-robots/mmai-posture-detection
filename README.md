# MMAI Posture Detection

Real-time pose perception from Intel RealSense RGB-D video.

## Features

- MediaPipe Pose detector wrapped as a reusable detector class
- Open posture scoring from wrist-to-shoulder geometry
- Face-covering detection for fear/discomfort cues
- Depth-aware sudden withdrawal detection from wrist Z motion
- RealSense video source abstraction with aligned color/depth frames
- OpenCV visualization layer separated from model logic

## Project Structure

```text
mmai-posture-detection/
├── config/
│   └── default.yaml
├── scripts/
│   └── run_realsense.py
├── src/
│   ├── detectors/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── pose_detector.py
│   ├── __init__.py
│   ├── pipeline.py
│   ├── realsense_source.py
│   ├── types.py
│   └── visualization.py
└── requirements.txt
```

## Setup

```bash
cd mmai-posture-detection
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

On macOS, complete the RealSense-specific setup in [RealSenseHWSetup.md](/Users/sparsh/Desktop/Sloan/First_Spring/Multimodal%20AI/mmai-emotion-detection/mmai-posture-detection/RealSenseHWSetup.md). That guide covers the manual `librealsense` build, RSUSB backend, and the exact launch command this project expects.

## Run

```bash
sudo DYLD_LIBRARY_PATH=/usr/local/lib:$DYLD_LIBRARY_PATH \
  .venv/bin/python scripts/run_realsense.py
```

Press `q` to quit.

## Notes

- Requires an Intel RealSense depth camera and a `pyrealsense2` binding compiled against this repo's venv on macOS.
- The visualization shows posture score, depth, and active warning state.
- All thresholds are configurable in `config/default.yaml`.
