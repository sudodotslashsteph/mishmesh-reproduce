FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY --chown=65532:65532 experiments /app/experiments
COPY --chown=65532:65532 tests /app/tests
COPY --chown=65532:65532 scripts /app/scripts
USER 65532:65532
CMD ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"]
