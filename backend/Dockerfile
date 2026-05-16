FROM python:3.11-slim

# Qt runtime libs — required because the "with glucose" .pkcls drags in
# Orange.widgets.utils.colorpalettes → AnyQt → PyQt5 at unpickle time.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libegl1 libxkbcommon0 libdbus-1-3 libfontconfig1 \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
    libxcb-render-util0 libxcb-shape0 libxcb-sync1 libxcb-xfixes0 \
    libxcb-xkb1 libxkbcommon-x11-0 \
    libxext6 libsm6 libxrender1 \
 && rm -rf /var/lib/apt/lists/*

ENV QT_QPA_PLATFORM=offscreen \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY app ./app
COPY models ./models
RUN mkdir -p /app/uploads

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys;\
sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health',timeout=3).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
