#!/bin/bash
set -e
GAMEDIR="${ISAAC_GAMEDIR:?}"
LOGDIR="${ISAAC_LOG_DIR:-/dev/shm/gameboy-of-isaac}"
mkdir -p "$LOGDIR"
python3 "$GAMEDIR/runtime/stock/startup.py" "$GAMEDIR"
export controlfolder="$GAMEDIR/runtime/PortMaster"
source "$GAMEDIR/runtime/stock/control.txt"
export TERM=linux
export LD_LIBRARY_PATH="$controlfolder:/usr/lib"
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0.2800.5
export SDL_VIDEODRIVER=mali SDL_VIDEO_EGL_DRIVER=/usr/lib/libmali.so.0
export CRUSTY_LIBSDL=/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0.2800.5
if [ "${ISAAC_DIAGNOSTICS:-0}" = 1 ] && [ -f "$GAMEDIR/runtime/libfps-sdl.so" ]; then
    export CRUSTY_LIBSDL="$GAMEDIR/runtime/libfps-sdl.so"
    export ISAAC_FPS_FILE="$LOGDIR/fps.csv"
fi
export CRUSTY_LIBEGL=/usr/lib/libmali.so.0
# Crusty's loader keeps these symlinks between launches; refresh our selected libraries.
ln -sfn "$CRUSTY_LIBSDL" /tmp/CRUSTY_LIBSDL64.so
ln -sfn "$CRUSTY_LIBEGL" /tmp/CRUSTY_LIBEGL64.so
export SDL_AUDIODRIVER=alsa ALSOFT_DRIVERS=alsa
export ALSA_CONFIG_PATH="$GAMEDIR/runtime/stock/asound.conf"
export SDL_GAMECONTROLLERCONFIG_FILE="$controlfolder/gamecontrollerdb.txt"
export XDG_DATA_HOME="${ISAAC_CONFIG_DIR:-$GAMEDIR/conf}"
export ISAAC_WESTON_DIR=/tmp/isaac-weston
if mountpoint -q "$ISAAC_WESTON_DIR" || pgrep -x wp_weston >/dev/null; then
    echo "Another Weston session is active; refusing to interfere with it"
    exit 1
fi
mkdir -p "$ISAAC_WESTON_DIR" /dev/dri
created_drm=0
mounted=0
gpt_pid=""
volume_pid=""
cleanup() {
    [ -z "$gpt_pid" ] || kill "$gpt_pid" 2>/dev/null || true
    [ -z "$volume_pid" ] || kill "$volume_pid" 2>/dev/null || true
    if [ "$mounted" -eq 1 ]; then
        bash "$GAMEDIR/runtime/westonwrap-stock.sh" cleanup >/dev/null 2>&1 || true
        for attempt in $(seq 1 20); do
            mountpoint -q "$ISAAC_WESTON_DIR" || break
            umount "$ISAAC_WESTON_DIR" 2>/dev/null && break
            sleep .1
        done
    fi
    [ "$created_drm" -eq 0 ] || rm -f /dev/dri/card0
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
if [ ! -e /dev/dri/card0 ]; then
    mknod /dev/dri/card0 c 226 0
    created_drm=1
fi
mount -o loop,ro "$GAMEDIR/runtime/weston_pkg_0.2.squashfs" "$ISAAC_WESTON_DIR"
mounted=1
export ISAAC_INPUT_READY="$LOGDIR/input-ready"
rm -f "$ISAAC_INPUT_READY"
python3 "$GAMEDIR/runtime/stock/volume.py" > "$LOGDIR/volume.log" 2>&1 &
volume_pid=$!
for attempt in $(seq 1 30); do
    [ ! -f "$ISAAC_INPUT_READY" ] || break
    kill -0 "$volume_pid" 2>/dev/null || break
    sleep .1
done
if [ ! -f "$ISAAC_INPUT_READY" ]; then
    echo "Input isolation failed; see $LOGDIR/volume.log"
    exit 1
fi
"$controlfolder/gptokeyb2" isaac.x64.hack -Z -c "$GAMEDIR/isaac.gptk" > "$LOGDIR/controls.log" 2>&1 &
gpt_pid=$!
cd "$GAMEDIR/gamefiles"
export LIBGL_ALPHAHACK=1 LIBGL_NOHIGHP=1 LIBGL_FORCE16BITS=1
export LIBGL_FPS=1
export BOX64_DYNAREC_CALLRET=1
export BOX64_LD_PRELOAD="$GAMEDIR/libs.x64/libx11_cache_fast.so:$GAMEDIR/libs.x64/libxkb_fix.so"
export BOX64_LD_LIBRARY_PATH="$GAMEDIR/libs.x64:$GAMEDIR/gamefiles/lib64"
bash "$GAMEDIR/runtime/westonwrap-stock.sh" headless noop kiosk crusty_glx_gl4es \
    "$GAMEDIR/box64" isaac.x64.hack
