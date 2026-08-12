FROM debian:bookworm-slim@sha256:abd67ffcfa541b485a3dff59865ab629aa048a6c613e639d36e7456b0b229241

ARG DEBIAN_FRONTEND=noninteractive

RUN sed -i \
        -e 's|http://deb.debian.org/debian-security|http://snapshot.debian.org/archive/debian-security/20260803T000000Z|' \
        -e 's|http://deb.debian.org/debian|http://snapshot.debian.org/archive/debian/20260803T000000Z|' \
        /etc/apt/sources.list.d/debian.sources \
    && printf 'Check-Valid-Until: no\n' >> /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends \
        bash=5.2.15-2+b13 \
        bubblewrap=0.8.0-2+deb12u1 \
        ca-certificates=20230311+deb12u1 \
        curl=7.88.1-10+deb12u15 \
        git=1:2.39.5-0+deb12u3 \
        jq=1.6-2.1+deb12u2 \
        nodejs=18.20.4+dfsg-1~deb12u2 \
        npm=9.2.0~ds1-1 \
        python3=3.11.2-1+b1 \
        python3-venv=3.11.2-1+b1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/codex-install
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund \
    && ln -s /opt/codex-install/node_modules/.bin/codex /usr/local/bin/codex

RUN useradd --create-home --uid 10001 --shell /bin/bash e2e

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TZ=UTC

WORKDIR /workspace

CMD ["/bin/bash"]
