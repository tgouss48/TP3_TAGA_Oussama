FROM python:3.11-slim@sha256:0dd364ba7e10242f07755449e3a3d0e35f9efd987952737b90def6709ab0c5ce

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOME=/tmp

WORKDIR /app

ARG VCS_REF=local
LABEL org.opencontainers.image.title="Predictive Maintenance API" \
      org.opencontainers.image.description="MLOps TP3 inference service" \
      org.opencontainers.image.version="2.1.0" \
      org.opencontainers.image.revision="$VCS_REF"

COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt

COPY maintenance_ml/ maintenance_ml/
COPY models/ models/
COPY reports/ reports/
COPY configs/ configs/
COPY data/raw/ data/raw/

RUN groupadd --system app && useradd --system --gid app --home-dir /app app \
    && chown -R app:app /app
USER app

EXPOSE 8000

STOPSIGNAL SIGTERM

HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["uvicorn", "maintenance_ml.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
