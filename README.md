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

## Test On Recorded Sessions

When you have recorded interaction data in `data/`, you can run the same pose pipeline offline against `.bag` or `.mp4` recordings:

```bash
.venv/bin/python scripts/test_recordings.py --data-dir data --recursive
```

On macOS, if the live RealSense path only works when launched with the setup from [RealSenseHWSetup.md](/Users/sparsh/Desktop/Sloan/First_Spring/Multimodal%20AI/mmai-posture-detection/RealSenseHWSetup.md), use the same command shape for offline replay as well:

```bash
sudo DYLD_LIBRARY_PATH=/usr/local/lib:$DYLD_LIBRARY_PATH \
  .venv/bin/python scripts/test_recordings.py --data-dir data --recursive
```

That is especially relevant for `.bag` playback, since it relies on the same manually built `pyrealsense2` / `librealsense` installation as the live camera script.

Useful options:

- `--prefer bag` uses RealSense playback with depth when a `.bag` is present.
- `--prefer mp4` forces color-only playback from video files.
- `--session SESSION_NAME` runs one recording stem only.
- `--render-video` saves an annotated playback video under `outputs/recording_tests/`.
- `--max-frames 300` is handy for fast smoke tests while files are still downloading.

Each processed session gets its own output folder with:

- `frames.csv` for frame-level detector outputs
- `summary.json` for quick session-level metrics
- `metadata.json` copied from the source `.json` file when present
- `annotated.mp4` when `--render-video` is enabled

## What The Detector Is Doing

The detector looks at each frame and uses body landmarks from MediaPipe, especially the shoulders, wrists, and nose.

From those landmarks, it produces three simple cues:

- `open posture`: how spread apart the hands are compared with shoulder width
- `covering mouth/face`: whether a hand is very close to the face
- `sudden withdrawal`: whether the hand quickly moves farther away from the robot in depth

The sudden-withdrawal cue only works for `.bag` recordings, because it needs RealSense depth data. The script also tries to avoid confusing a normal arm movement with withdrawal by comparing the depth change with the recent posture trend.

## What The Output Files Mean

Each processed session gets its own folder under `outputs/recording_tests/`.

- `summary.json`: the overall result for that session
- `frames.csv`: one row per frame with the detector's outputs
- `metadata.json`: copied session metadata from the source recording, when available
- `annotated.mp4`: an optional rendered video with detector overlays, created when `--render-video` is used

### `summary.json`

This is the quickest file to read. It tells you:

- which recording was processed
- whether the script used the `.bag` or `.mp4`
- how many frames were processed
- how often a pose was found
- how many frames were flagged as mouth-covering
- how many frames were flagged as sudden withdrawal
- the average open-posture score for that session

### `frames.csv`

This is the detailed frame-by-frame output. Each row corresponds to one frame and includes:

- `has_pose`: whether a pose was detected in that frame
- `open_posture_score`: how open or closed the posture looked
- `is_covering_mouth`: whether a hand was near the face
- `is_withdrawing`: whether the detector flagged sudden withdrawal
- `interaction_z_meters`: wrist depth in meters, when depth is available

Use `summary.json` when you want the big picture and `frames.csv` when you want to inspect exactly when something happened.

## Notes

- Requires an Intel RealSense depth camera and a `pyrealsense2` binding compiled against this repo's venv on macOS.
- The visualization shows posture score, depth, and active warning state.
- All thresholds are configurable in `config/default.yaml`.
- Offline `.bag` replay also requires `pyrealsense2`; `.mp4` replay works without depth.
