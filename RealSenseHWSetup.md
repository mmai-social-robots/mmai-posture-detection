### macOS Local Development Setup for Intel RealSense

Follow these exact steps to compile the drivers and bypass the macOS USB restrictions for this repository.

#### 1. System Prerequisites

You will need Homebrew to install the core C++ compilers and the `libusb` backend.

```bash
xcode-select --install
brew install cmake libusb pkg-config
```

#### 2. Create the Project Virtual Environment

Create and activate a local virtual environment inside `mmai-posture-detection`:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### 3. Install Python Dependencies Safely

Force `pip` to use pre-built binaries for the Python packages that come from PyPI:

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

Note: on this macOS setup, `pyrealsense2` is not installed from `pip`. It is provided by a manual `librealsense` build in the next step.

#### 4. Compile the RealSense Python Wrapper

Compile the `librealsense` SDK manually and force it to use the RSUSB backend. This flag, `-DFORCE_RSUSB_BACKEND=ON`, avoids the macOS USB path that blocks the camera video stream.

Run these commands from a directory outside this repository, or reuse an existing local clone of `librealsense`:

```bash
git clone https://github.com/IntelRealSense/librealsense.git
cd librealsense

mkdir build && cd build

cmake .. \
  -DBUILD_PYTHON_BINDINGS:bool=true \
  -DPYTHON_EXECUTABLE="$(which python)" \
  -DFORCE_RSUSB_BACKEND=ON

make -j4
sudo make install
```

The important detail is that `$(which python)` must resolve to this repo's virtualenv interpreter, so the generated `pyrealsense2` binding matches `.venv/bin/python`.

#### 5. Running the Pipeline on macOS

Because macOS's dynamic linker loses track of manually compiled C++ libraries, and because reading raw USB data requires elevated privileges on this setup, run the pipeline with this exact command shape:

```bash
sudo DYLD_LIBRARY_PATH=/usr/local/lib:$DYLD_LIBRARY_PATH \
  .venv/bin/python scripts/run_realsense.py
```

It will prompt for your Mac user password to grant USB access before running the script.

#### 6. Common Failure Mode

If `pyrealsense2` fails to import with a symbol error, the usual cause is a mismatch between:

- the Python interpreter used during the `librealsense` CMake build
- the Python interpreter used to run `scripts/run_realsense.py`

If that happens, reactivate `.venv` and rebuild `librealsense` with the same interpreter:

```bash
source .venv/bin/activate
cmake .. -DBUILD_PYTHON_BINDINGS:bool=true -DPYTHON_EXECUTABLE="$(which python)" -DFORCE_RSUSB_BACKEND=ON
```
