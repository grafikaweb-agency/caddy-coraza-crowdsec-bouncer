FROM golang:1.26-alpine3.24 AS builder

RUN apk add --no-cache ca-certificates git
RUN go install github.com/caddyserver/xcaddy/cmd/xcaddy@v0.4.7

ENV PATH="/root/go/bin:${PATH}"

RUN xcaddy build v2.11.9 \
    --with github.com/corazawaf/coraza-caddy/v2@v2.6.2 \
    --with github.com/hslatman/caddy-crowdsec-bouncer/http@v0.14.1 \
    --output /usr/bin/caddy

FROM alpine:3.24

RUN apk add --no-cache ca-certificates \
    && addgroup -S -g 8080 caddy \
    && adduser -S -D -H -u 8080 -G caddy caddy \
    && mkdir -p /etc/caddy /data /config \
    && chown -R caddy:caddy /etc/caddy /data /config

COPY --from=builder --chown=8080:8080 /usr/bin/caddy /usr/bin/caddy

LABEL org.opencontainers.image.source="https://github.com/grafikaweb-agency/caddy-coraza-crowdsec-bouncer"

ENV XDG_CONFIG_HOME=/config \
    XDG_DATA_HOME=/data

USER 8080:8080

EXPOSE 80 443 443/udp

ENTRYPOINT ["/usr/bin/caddy"]
CMD ["run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
