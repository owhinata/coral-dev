# Cross-build environment for Linux kernel (arm64) targeting Coral Dev Board
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc-aarch64-linux-gnu bc bison flex \
    libssl-dev libelf-dev libncurses-dev python3 rsync cpio kmod \
    device-tree-compiler u-boot-tools git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-
WORKDIR /src
