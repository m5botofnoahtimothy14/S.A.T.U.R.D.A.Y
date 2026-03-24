# AEGIS Core - Build Instructions

## Dependencies

### Windows (Visual Studio 2019+)

**Required:**
- CMake 3.16+
- Visual Studio 2019 or later
- Windows 10 SDK

**Libraries (via vcpkg or manual install):**
```
vcpkg install glfw3:x64-windows
vcpkg install glew:x64-windows
vcpkg install libwebsockets:x64-windows
vcpkg install fftw3:x64-windows
```

**System Libraries:**
- OpenGL 4.5+ (included with GPU drivers)
- Windows Multimedia (winmm.lib)

### Linux

**Required:**
- CMake 3.16+
- GCC 10+ or Clang 12+
- libgl1-mesa-dev
- libglew-dev
- libglfw3-dev
- libwebsockets-dev
- libfftw3-dev

```bash
# Ubuntu/Debian
sudo apt install cmake build-essential libgl1-mesa-dev libglew-dev \
    libglfw3-dev libwebsockets-dev libfftw3-dev

# Fedora
sudo dnf install cmake gcc-c++ glew-devel glfw-devel \
    libwebsockets-devel fftw-devel
```

### macOS

```bash
brew install cmake glew glfw websocketpp fftw
```

---

## Building

### Windows (Visual Studio)

```powershell
# Create build directory
mkdir build
cd build

# Configure with CMake
cmake .. -G "Visual Studio 17 2019" -A x64

# Build
cmake --build . --config Release
```

### Linux/macOS

```bash
# Create build directory
mkdir -p build
cd build

# Configure
cmake .. -DCMAKE_BUILD_TYPE=Release

# Build
cmake --build . -j$(nproc)
```

---

## Running

```bash
# From build directory
./bin/aegis-core

# Or from project root
./build/bin/aegis-core
```

---

## Performance Targets

- **Frame Rate:** 60 FPS
- **CPU Usage:** <15% idle, <30% during audio processing
- **Memory:** <150MB resident
- **GPU:** Intel i5-1035G7 + Iris GPU baseline

---

## File Structure

```
aegis-core/
├── CMakeLists.txt
├── src/
│   ├── main.cpp
│   ├── core/
│   │   ├── logger.h/cpp
│   │   ├── raii.h
│   │   ├── timer.h
│   │   ├── application.h
│   │   └── orbitalcore.h
│   ├── rendering/
│   │   ├── renderer.h/cpp
│   │   ├── shader.h/cpp
│   │   ├── mesh.h/cpp
│   │   └── postprocess.h
│   ├── audio/
│   │   └── audioengine.h
│   ├── networking/
│   │   └── websocketclient.h
│   └── state/
│       └── aisstate.h
├── shaders/
│   ├── core.vert
│   ├── core.frag
│   └── bloom_*.frag
└── README.md
```

---

## State API

```cpp
// Set state programmatically
app.set_state(AIState::Listening);
app.set_state(AIState::Speaking);
app.set_state(AIState::Secure);
app.set_state(AIState::Idle);

// Update with audio data
AudioReactiveData data;
data.bass = 0.5f;
data.mid = 0.3f;
data.treble = 0.2f;
data.overall = 0.4f;
app.update_audio_level(data);
```

---

## Network Sync

```cpp
// Connect to AEGIS network
app.connect("ws://aegis-server:8765");

// State is automatically synced
// Receive state from other devices via callback
```
