# syntax=docker/dockerfile:1


FROM python:3.14-slim AS builder

WORKDIR /app

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


COPY src/ ./src/
RUN pip install --no-cache-dir --prefix=/install --no-deps .


FROM python:3.14-slim AS runtime

WORKDIR /app

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser

COPY --from=builder /install /usr/local
COPY app/ ./app/
COPY scripts/ ./scripts/

RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=3)" || exit 1

ENTRYPOINT ["streamlit", "run", "app/streamlit_app.py"]
