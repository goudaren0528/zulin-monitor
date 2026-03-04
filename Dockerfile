FROM mcr.microsoft.com/playwright/python:v1.57.0-jammy

WORKDIR /app

# Set timezone to Shanghai
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    fluxbox \
    novnc \
    websockify \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5050 5900 6080

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    ORDER_POINT_ENV=production \
    ORDER_POINT_HEADED=1

# Run Flask app
CMD ["bash", "-lc", "set -euo pipefail; if [ -z \"${VNC_PASSWORD:-}\" ]; then echo \"VNC_PASSWORD is required\" >&2; exit 2; fi; Xvfb :99 -screen 0 1920x1080x24 -ac -nolisten tcp -dpi 96 & fluxbox -display :99 & x11vnc -storepasswd \"$VNC_PASSWORD\" /tmp/x11vnc.pass >/dev/null; x11vnc -display :99 -rfbport 5900 -rfbauth /tmp/x11vnc.pass -forever -shared -repeat -noxdamage -listen 0.0.0.0 & websockify --web /usr/share/novnc/ 6080 localhost:5900 & python app.py"]
