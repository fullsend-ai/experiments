FROM golang:1.25 AS builder
WORKDIR /build
COPY go.mod go.sum main.go ./
RUN go build -o safe-push .

FROM ghcr.io/nvidia/openshell-community/sandboxes/base@sha256:f0d1ec92bf219759c1e863c0fa6b1f432ec827331e79ab9e31dab91a3b86b413

USER root

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

COPY --from=builder /build/safe-push /usr/local/bin/safe-push
RUN chmod +x /usr/local/bin/safe-push

USER sandbox
