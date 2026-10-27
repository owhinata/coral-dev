#!/usr/bin/env python3
"""uboot-boot.py — One-shot boot of an alternate kernel on the Coral Dev Board.

Drives the U-Boot serial console: waits for the autoboot prompt, interrupts it,
loads /boot/Image-<ver> and the matching DTB from eMMC partition 1, boots it,
and records the console log until a login prompt (or timeout) appears.
Nothing on the board is modified; the next normal reset boots Mendel as before.

Usage:
  kernel/uboot-boot.py --version 7.3.0-coral [--port /dev/ttyUSB0] [--reboot]
                       [--timeout 180] [--log kernel/out/boot.log]

--reboot issues `sudo reboot` over SSH via scripts/run.sh; otherwise power-cycle
or reset the board manually once the script says it is waiting.
"""
import argparse, os, re, subprocess, sys, time
import serial

ROOT_PARTUUID = "70672ec3-5eee-49ff-b3b1-eb1fbd406bf5"
# The stock U-Boot env may have a bad CRC (defaults only), so ${fdt_addr} is unset.
# Use explicit addresses: DRAM is 1 GiB at 0x40000000; a mainline Image is ~50 MB,
# so the DTB must sit well above the Mendel default 0x43000000.
KERNEL_ADDR = "0x40480000"
FDT_ADDR = "0x48000000"
HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--dtb", default=None,
                    help="DTB file name in /boot (default imx8mq-phanbell-<version>.dtb)")
    ap.add_argument("--image", default=None,
                    help="kernel image file name in /boot (default Image-<version>)")
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--reboot", action="store_true")
    ap.add_argument("--reboot-sysrq", action="store_true",
                    help="reboot via serial BREAK + sysrq 'b' (kernel booted with sysrq_always_enabled)")
    ap.add_argument("--at-prompt", action="store_true",
                    help="board is already sitting at the U-Boot prompt")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--banner-timeout", type=int, default=120,
                    help="seconds to wait for the U-Boot banner (reset/power-cycle)")
    ap.add_argument("--log", default=os.path.join(HERE, "out", "boot.log"))
    ap.add_argument("--extra-bootargs", default="")
    ap.add_argument("--linger", type=int, default=0,
                    help="after the login prompt, keep logging for N seconds and poke the "
                         "console every 15 s to detect a post-boot hang")
    a = ap.parse_args()

    bootargs = (f"console=ttymxc0,115200 earlycon=ec_imx6q,0x30860000,115200 "
                f"root=PARTUUID={ROOT_PARTUUID} "
                f"rootfstype=ext4 rw rootwait net.ifnames=0 "
                f"sysrq_always_enabled panic=10 {a.extra_bootargs}").strip()
    image = a.image or f"Image-{a.version}"
    dtb = a.dtb or f"imx8mq-phanbell-{a.version}.dtb"
    cmds = [
        f"ext2load mmc 0:1 {KERNEL_ADDR} {image}",
        f"ext2load mmc 0:1 {FDT_ADDR} {dtb}",
        f"setenv bootargs {bootargs}",
        f"booti {KERNEL_ADDR} - {FDT_ADDR}",
    ]

    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    log = open(a.log, "wb")
    ser = serial.Serial(a.port, a.baud, timeout=0.2)
    buf = b""

    def pump(dt=0.2):
        nonlocal buf
        d = ser.read(65536)
        if d:
            log.write(d); log.flush(); sys.stdout.buffer.write(d); sys.stdout.flush()
            buf += d
        else:
            time.sleep(dt)

    last_chunk = ""

    def wait_for(pattern, timeout):
        nonlocal buf, last_chunk
        rx = re.compile(pattern)
        end = time.time() + timeout
        while time.time() < end:
            pump()
            if rx.search(buf.decode(errors="replace")):
                last_chunk = buf.decode(errors="replace")
                buf = b""
                return True
        return False

    PROMPT = r"=> *$"
    if a.at_prompt:
        ser.write(b"\n")
    else:
        if a.reboot:
            print(">>> rebooting board over SSH", flush=True)
            subprocess.run([os.path.join(HERE, "..", "scripts", "run.sh"), "sudo reboot"], check=False)
        elif a.reboot_sysrq:
            print(">>> rebooting board via serial sysrq", flush=True)
            for key in (b"s", b"u", b"b"):  # sync, remount-ro, reboot
                ser.send_break(duration=0.25); time.sleep(0.1); ser.write(key)
                pump(); time.sleep(2.0); pump()
        else:
            print(">>> waiting for U-Boot: reset or power-cycle the board now", flush=True)
        # Interrupt autoboot: send a key once the U-Boot banner shows up.
        if not wait_for(r"U-Boot 20", a.banner_timeout):
            sys.exit("U-Boot banner not seen")
        for _ in range(40):
            ser.write(b" "); pump(0.05)
            if re.search(PROMPT.encode(), buf):
                break
        ser.write(b"\n")
    if not wait_for(PROMPT, 10):
        sys.exit("U-Boot prompt not reached")
    print("\n>>> U-Boot prompt reached", flush=True)

    for c in cmds:
        ser.write(c.encode() + b"\n")
        if c.startswith("booti"):
            break
        if not wait_for(PROMPT, 30):
            sys.exit(f"no prompt after: {c}")
        if c.startswith("ext2load") and not re.search(r"bytes read", last_chunk):
            sys.exit(f"load failed: {c}")

    print("\n>>> kernel booting; capturing console", flush=True)
    ok = wait_for(r"login: ", a.timeout)
    print(f"\n>>> {'login prompt reached' if ok else 'timeout waiting for login prompt'}; log: {a.log}")
    if ok and a.linger:
        end = time.time() + a.linger
        alive = True
        while time.time() < end:
            ser.write(b"\r")
            if wait_for(r"login: ", 15):
                print(f">>> [{time.strftime('%H:%M:%S')}] console alive", flush=True)
                time.sleep(15)
            else:
                print(f">>> [{time.strftime('%H:%M:%S')}] console NOT responding", flush=True)
                alive = False
        print(">>> linger done; console alive=%s" % alive)
        sys.exit(0 if alive else 3)
    sys.exit(0 if ok else 2)

if __name__ == "__main__":
    main()
