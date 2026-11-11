FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SPARK_LOCAL_IP=127.0.0.1
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home satyasetu \
    && install -d -o satyasetu -g satyasetu /state /app/data/raw
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir '.[local,portal]'
COPY config ./config
COPY examples ./examples
COPY data/sample ./data/sample
USER satyasetu
EXPOSE 8080
ENTRYPOINT ["satyasetu", "--repo", "/app", "--state", "/state", "--host", "0.0.0.0", "--port", "8080"]
