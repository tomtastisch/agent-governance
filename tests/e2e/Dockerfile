FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        bubblewrap \
        ca-certificates \
        curl \
        git \
        jq \
        nodejs \
        npm \
        python3 \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN npm install --global --ignore-scripts --no-audit --no-fund @openai/codex@0.147.0

RUN useradd --create-home --uid 10001 --shell /bin/bash e2e

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TZ=UTC

WORKDIR /workspace

CMD ["/bin/bash"]
