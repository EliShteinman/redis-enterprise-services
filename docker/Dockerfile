ARG PYTHON_IMAGE=python:3.14.7-slim

FROM ${PYTHON_IMAGE} AS builder
RUN pip install --no-cache-dir uv==0.12.17
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN uv sync --no-dev --no-editable

FROM ${PYTHON_IMAGE}
ARG RES_UID=10001
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY docker/entrypoint.py ./docker/entrypoint.py
RUN mkdir logs && chown ${RES_UID}:0 logs && chmod g=u logs
USER ${RES_UID}:0
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "docker/entrypoint.py"]
