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

```bash
pip install mendel-development-tool
```

## 3. Connect to the Board

Connect the Coral Dev Board to your host PC via USB-C.

```bash
# Detect the board
mdt devices

# Access the shell
mdt shell
```

## 4. Network Configuration

Set up Wi-Fi:

```bash
# Run inside mdt shell
nmcli dev wifi connect <SSID> password <PASSWORD>

# Check IP address
ip addr show wlan0
```

## 5. Install the Cross-Compiler

Install the aarch64 cross-compiler on your host PC.

=== "Ubuntu / Debian"

    ```bash
    sudo apt install gcc-aarch64-linux-gnu g++-aarch64-linux-gnu
    ```

=== "Arch Linux"

    ```bash
    sudo pacman -S aarch64-linux-gnu-gcc
    ```

## 6. Set Up SSH Keys

Configure SSH keys for password-less deployment.

```bash
# Check Coral IP
mdt devices

# Copy SSH key
ssh-copy-id mendel@<CORAL_IP>
```

## Next Steps

Once the environment is ready, proceed to build and deploy applications.

```bash
cmake -B build/<app> -S apps/<app> \
    -DCMAKE_TOOLCHAIN_FILE=cmake/toolchain-coral-aarch64.cmake
cmake --build build/<app>
cmake --build build/<app> --target deploy
```
