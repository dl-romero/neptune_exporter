FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium chromium-driver ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/workspace \
    && useradd --create-home --shell /usr/sbin/nologin exporter \
    && chown -R exporter:exporter /app

USER exporter

EXPOSE 5006

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5006/health').read()" || exit 1

CMD ["uvicorn", "neptune_exporter:app", "--host", "0.0.0.0", "--port", "5006"]