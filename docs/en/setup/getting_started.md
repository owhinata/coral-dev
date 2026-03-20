# Getting Started

Initial setup instructions for the Coral Dev Board.

## Prerequisites

- Coral Dev Board
- USB-C cable (data-capable)
- USB serial adapter (for initial setup)
- microSD card (pre-flashed or for flashing)
- Host PC (Linux / macOS)

## 1. Flash Mendel Linux

!!! note "Factory State"
    New Coral Dev Boards come with Mendel Linux pre-installed.
    Only perform this step if you need to re-flash the OS.

Follow the official documentation to flash Mendel Linux:

[Get started with the Dev Board | Coral](https://coral.ai/docs/dev-board/get-started/)

## 2. Install MDT

Install the Mendel Development Tool (mdt) on your host PC.
Create a virtual environment in the project root and install the dependencies.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

!!! tip "PATH Setup"
    Either add `.venv/bin` to your PATH, or run tools with their full path like `.venv/bin/mdt`.

## 3. Connect to the Board

Connect the Coral Dev Board to your host PC via USB-C.

```bash
# Detect the board
mdt devices

# Access the shell
mdt shell
```

!!! note "Automatic SSH Key Management"
    mdt automatically generates an SSH key on first connection and stores it at `~/.config/mdt/keys/mdt.key`.
    The deploy scripts also use this key, so no manual SSH key setup is required.

## 4. Network Configuration

Set up Wi-Fi:

```bash
# Run inside mdt shell
nmcli dev wifi connect <SSID> password <PASSWORD>

# Check IP address
ip addr show wlan0
```

## 5. Install the Cross-Compiler

Install ARM GNU Toolchain 8.3 that matches the Coral Dev Board's Mendel Linux
(Debian 10 Buster, glibc 2.28) using the setup script.

```bash
./cmake/setup-toolchain.sh
```

The toolchain is downloaded and extracted into the `toolchain/` directory.

## Next Steps

Once the environment is ready, try building and deploying with [Hello World](../development/hello_world.md).
