# Plain Linux container — this sidesteps two Windows-only problems we hit on
# the host: Celery's default worker pool needs os.fork() (unavailable on
# native Windows), and separately, some native-extension Python packages have
# had OpenSSL/DLL issues on the python-build-standalone Windows interpreter.
# Neither exists here.
FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency manifests first so Docker can cache the `uv sync` layer —
# it only reruns when pyproject.toml/uv.lock actually change, not on every
# source edit.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

CMD ["uv", "run", "celery", "-A", "app.tasks.celery_app", "worker", "--loglevel=info"]
