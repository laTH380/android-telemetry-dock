FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends android-tools-adb iputils-ping iproute2 arp-scan \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml requirements.txt README.md ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir .

ENV ATD_CONFIG=/config/config.yaml
VOLUME ["/data", "/config"]
CMD ["android-telemetry-dock"]
