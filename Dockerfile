# Container for the public demo (Hugging Face Spaces, SDK: docker).
#
# Python 3.12 rather than the 3.14 used locally: the code only needs 3.10+ syntax, and 3.12
# has mature wheels for every dependency, so the image builds without a compiler toolchain.

FROM python:3.12-slim

# HF Spaces runs the container as UID 1000. Creating that user explicitly (rather than
# relying on root) keeps the writable paths below predictable.
RUN useradd -m -u 1000 app

WORKDIR /app

# Dependencies first, so edits to the source don't invalidate the pip layer.
COPY --chown=app:app requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt -r requirements-web.txt

COPY --chown=app:app src/ ./src/
COPY --chown=app:app web/ ./web/
COPY --chown=app:app scripts/ ./scripts/
COPY --chown=app:app eval/ ./eval/

# `index/` is intentionally NOT copied — it holds the full calendar corpus text and is
# pulled at startup from a private dataset repo (see web/bootstrap.py). This directory just
# needs to exist and be writable.
RUN mkdir -p /app/index /app/web/cache && chown -R app:app /app/index /app/web/cache

USER app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/tmp/huggingface \
    DEMO_DB_PATH=/tmp/ubchelper-demo.sqlite3

EXPOSE 7860

# One worker on purpose: the index and BM25 postings are cached in module globals, and the
# rate limiter's in-process queue state would fragment across workers.
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
