FROM ghcr.io/home-assistant/base:3.22

ARG BUILD_VERSION
ARG BUILD_ARCH

LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="app" \
  io.hass.arch="${BUILD_ARCH}" \
  org.opencontainers.image.title="GMC3xx Radiation Monitor" \
  org.opencontainers.image.description="USB-to-MQTT monitor for supported GQ GMC-300/320 family Geiger counters" \
  org.opencontainers.image.source="https://github.com/ArrowSK/ha-gmc3xx-fixed" \
  org.opencontainers.image.licenses="GPL-3.0-only"

RUN apk add --no-cache \
      ca-certificates \
      coreutils \
      jq \
      mosquitto-clients \
      socat \
    && apk add --no-cache --virtual .build-deps \
      build-base \
    && mkdir -p /usr/src/gmc3xx

COPY src/gmc320.c /usr/src/gmc3xx/gmc320.c

RUN cc -std=c11 -Wall -Wextra -Werror -O2 \
      /usr/src/gmc3xx/gmc320.c -o /usr/local/bin/gmc320 \
    && strip /usr/local/bin/gmc320 \
    && apk del .build-deps \
    && rm -rf /usr/src/gmc3xx

COPY run.sh /run.sh
RUN chmod 0755 /run.sh

CMD ["/run.sh"]
