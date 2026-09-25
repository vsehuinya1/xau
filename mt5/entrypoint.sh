#!/usr/bin/env bash
# Starts the virtual screen and VNC, installs MT5 + Windows Python into the
# Wine prefix on first run (the prefix lives on a volume), then runs the terminal.
set -euo pipefail

: "${VNC_PASSWORD:?VNC_PASSWORD must be set}"

TERMINAL="$WINEPREFIX/drive_c/Program Files/MetaTrader 5/terminal64.exe"
PYTHON="$WINEPREFIX/drive_c/Program Files/Python311/python.exe"
MT5_PY_VERSION=5.0.5370
# numpy 2.x calls ucrtbase.crealf, which Wine 10 doesn't implement.
NUMPY_VERSION=1.26.4

# Wait for Wine to go idle, but never hang on a process that won't exit.
settle() { timeout 120 wineserver -w || wineserver -k || true; }

# /tmp survives container restarts; drop the previous run's X and Wine state.
rm -rf /tmp/.X99-lock /tmp/.X11-unix/X99 "/tmp/.wine-$(id -u)"
Xvfb :99 -screen 0 1366x768x24 -nolisten tcp &
for _ in $(seq 50); do [[ -S /tmp/.X11-unix/X99 ]] && break; sleep 0.2; done
openbox &
x11vnc -storepasswd "$VNC_PASSWORD" /tmp/vncpass >/dev/null 2>&1
x11vnc -display :99 -rfbauth /tmp/vncpass -rfbport 5900 -forever -shared -quiet -bg -o /tmp/x11vnc.log

if [[ ! -f "$TERMINAL" ]]; then
    echo "First run: creating Wine prefix"
    WINEDLLOVERRIDES="mscoree,mshtml=" wineboot --init
    settle
    winecfg -v=win11

    echo "Installing WebView2 runtime"
    timeout 600 wine /opt/installers/webview2.exe /silent /install \
        || echo "WebView2 install failed or timed out; continuing"
    # The installer registers Edge's updater as auto-start services that never
    # exit (and would update in the background). Disable them.
    for svc in edgeupdate edgeupdatem; do
        wine reg add "HKLM\\System\\CurrentControlSet\\Services\\$svc" /v Start /t REG_DWORD /d 4 /f || true
    done
    wineserver -k || true

    echo "Installing MetaTrader 5"
    timeout 900 wine /opt/installers/mt5setup.exe /auto || true
    # The installer launches the terminal when it finishes; stop everything
    # so the terminal starts cleanly below.
    wineserver -k || true
    [[ -f "$TERMINAL" ]] || { echo "MT5 install failed: $TERMINAL not found" >&2; exit 1; }

    echo "Installing Windows Python and the MetaTrader5 package"
    wine /opt/installers/python.exe /quiet InstallAllUsers=1 PrependPath=1 \
        Include_test=0 Include_doc=0 Include_tcltk=0 Include_launcher=0
    settle
    wine "$PYTHON" -m pip install --no-warn-script-location \
        "MetaTrader5==$MT5_PY_VERSION" "numpy==$NUMPY_VERSION"
    settle
    echo "First-run install complete"
fi

# Optional auto-login from MT5_LOGIN / MT5_PASSWORD / MT5_SERVER (mt5/.env),
# through MT5's startup config file. KeepPrivate saves the login in the prefix.
# MaxBars also caps how much history copy_rates_* can return (default 100k).
TERMINAL_ARGS=()
if [[ -n "${MT5_LOGIN:-}" ]]; then
    : "${MT5_PASSWORD:?MT5_PASSWORD must be set with MT5_LOGIN}"
    : "${MT5_SERVER:?MT5_SERVER must be set with MT5_LOGIN}"
    (umask 077; printf '[Common]\r\nLogin=%s\r\nPassword=%s\r\nServer=%s\r\nKeepPrivate=1\r\nNewsEnable=0\r\n[Charts]\r\nMaxBars=5000000\r\n' \
        "$MT5_LOGIN" "$MT5_PASSWORD" "$MT5_SERVER" > /tmp/mt5-startup.ini)
    TERMINAL_ARGS+=('/config:Z:\tmp\mt5-startup.ini')
fi

wine "$TERMINAL" "${TERMINAL_ARGS[@]}" &

# Tick recorder (mt5/winpy, mounted at /opt/xau), restarted whenever it exits.
# It waits for the terminal to log in by itself.
if [[ -n "${MT5_LOGIN:-}" && -f /opt/xau/recorder.py ]]; then
    (
        while true; do
            wine "$PYTHON" Z:/opt/xau/recorder.py || echo "recorder exited with $?"
            sleep 60
        done
    ) &
fi

# Stay up while the terminal runs. MT5 restarts itself to apply updates, so
# exit (and let Docker restart the container) only once it's been gone 60s.
gone=0
while (( gone < 60 )); do
    if pgrep -f 'MetaTrader 5.terminal64.exe' >/dev/null; then gone=0; else gone=$((gone + 5)); fi
    sleep 5
done
echo "terminal not running for 60s; exiting"
