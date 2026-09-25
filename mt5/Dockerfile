# MetaTrader 5 under Wine on a virtual screen (Xvfb + VNC), plus Windows Python
# with the MetaTrader5 package. Follows MetaQuotes' own mt5linux.sh (Windows 11
# mode, WebView2 runtime) except for the Wine version: under Wine 11 the
# MetaTrader5 package's IPC to the terminal times out (-10005), so Wine is
# pinned to 10.0 stable.
FROM ubuntu:24.04

ARG WINE_VERSION=10.0.0.0~noble-1

ENV DEBIAN_FRONTEND=noninteractive \
    WINEPREFIX=/home/mt5/.wine \
    WINEARCH=win64 \
    WINEDEBUG=-all \
    DISPLAY=:99

RUN dpkg --add-architecture i386 \
 && apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates wget gnupg procps xvfb x11vnc openbox \
 && mkdir -pm755 /etc/apt/keyrings \
 && wget -qO- https://dl.winehq.org/wine-builds/winehq.key | gpg --dearmor -o /etc/apt/keyrings/winehq-archive.key \
 && wget -qNP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources \
 && apt-get update \
 && apt-get install -y --install-recommends \
      winehq-stable=$WINE_VERSION wine-stable=$WINE_VERSION \
      wine-stable-amd64=$WINE_VERSION wine-stable-i386:i386=$WINE_VERSION \
 && rm -rf /var/lib/apt/lists/*

ARG PYTHON_VERSION=3.11.9
RUN mkdir /opt/installers && cd /opt/installers \
 && wget -qO mt5setup.exe https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe \
 && wget -qO webview2.exe https://msedge.sf.dl.delivery.mp.microsoft.com/filestreamingservice/files/f2910a1e-e5a6-4f17-b52d-7faf525d17f8/MicrosoftEdgeWebview2Setup.exe \
 && wget -qO python.exe https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-amd64.exe

# Xvfb runs as mt5 and can't create the X socket directory itself.
RUN useradd -m -s /bin/bash mt5 \
 && mkdir -p /home/mt5/.wine /tmp/.X11-unix \
 && chown mt5:mt5 /home/mt5/.wine \
 && chmod 1777 /tmp/.X11-unix

COPY entrypoint.sh /usr/local/bin/entrypoint.sh

USER mt5
WORKDIR /home/mt5
EXPOSE 5900
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
