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

# opencv-python (pulled in transitively by Docling's table-structure model)
# dynamically links against X11/GL runtime libraries even though we only ever
# use it headlessly — python:3.12-slim doesn't ship them, so importing cv2
# crashes with "libxcb.so.1: cannot open shared object file" the first time a
# PDF with the table-structure model actually loads. Placed after `uv sync`
# so this layer doesn't invalidate the (very expensive, torch-sized) dependency
# cache above.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["uv", "run", "celery", "-A", "app.tasks.celery_app", "worker", "--loglevel=info"]
