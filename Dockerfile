FROM python:3.12-slim-bookworm AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=2

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY backend/ backend/
COPY recommendations/ recommendations/
COPY demo/ demo/
COPY scripts/ scripts/
COPY migrations/ migrations/
COPY alembic.ini ./
RUN pip install --no-cache-dir '.[demo]' \
    && useradd --uid 10001 --create-home music \
    && mkdir /app/data \
    && chown music:music /app/data
USER music
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]

FROM app AS test
USER root
COPY tests/ tests/
RUN pip install --no-cache-dir '.[dev]'
USER music
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM app AS runtime
