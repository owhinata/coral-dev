#!/usr/bin/env python3
"""serial-run.py — Run shell commands on the Coral Dev Board over the serial console.

Useful when the mainline kernel has no network yet. Logs in at the getty prompt
(default user mendel / password mendel, Mendel Linux defaults) if needed, runs each
command, and prints its output between markers. Nothing is left running.

Usage: kernel/serial-run.py [--port /dev/ttyUSB0] [--user mendel] [--password mendel]
                            [--timeout 60] 'cmd1' 'cmd2' ...
"""
import argparse, re, sys, time, serial

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--user", default="mendel")
    ap.add_argument("--password", default="mendel")
    ap.add_argument("--timeout", type=int, default=60, help="per-command timeout")
    ap.add_argument("cmds", nargs="+")
    a = ap.parse_args()

    ser = serial.Serial(a.port, 115200, timeout=0.2)
    buf = ""

    def read_until(pattern, timeout):
        nonlocal buf
        rx = re.compile(pattern, re.M)
        end = time.time() + timeout
        while time.time() < end:
            d = ser.read(65536)
            if d:
                buf += d.decode(errors="replace")
                m = rx.search(buf)
                if m:
                    out, buf = buf[:m.start()], buf[m.end():]
                    return out, m
            else:
                time.sleep(0.05)
        return None, None

    PROMPT = r"\$ $|# $"
    # Get to a shell prompt: poke the console and handle login/password prompts.
    for _ in range(6):
        ser.write(b"\r")
        out, m = read_until(r"login: $|Password: $|" + PROMPT, 5)
        if m is None:
            continue
        if m.group(0).startswith("login"):
            ser.write(a.user.encode() + b"\r")
            out, m = read_until(r"Password: $|" + PROMPT, 10)
            if m and m.group(0).startswith("Password"):
                ser.write(a.password.encode() + b"\r")
                out, m = read_until(PROMPT, 15)
        elif m.group(0).startswith("Password"):
            ser.write(a.password.encode() + b"\r")
            out, m = read_until(PROMPT, 15)
        if m and re.search(PROMPT, m.group(0)):
            break
    else:
        sys.exit("could not reach a shell prompt on " + a.port)

    # Quiet shell; large terminal width to avoid wrapping.
    ser.write(b"stty cols 500; export PS1='SERIALRUN$ '\r")
    read_until(r"SERIALRUN\$ $", 10)
    read_until(r"SERIALRUN\$ $", 2)
    rc = 0
    for c in a.cmds:
        marker = f"__END_{int(time.time()*1000)}__"
        ser.write((c + f"; echo {marker}$?\r").encode())
        out, m = read_until(re.escape(marker) + r"(\d+)", a.timeout)
        print(f"=== $ {c}")
        if m is None:
            print("!!! timeout"); rc = 2
            print(buf); buf = ""
            continue
        # drop the echoed command line
        lines = out.replace("\r", "").split("\n")
        if lines and c in lines[0]:
            lines = lines[1:]
        print("\n".join(lines).strip())
        if m.group(1) != "0":
            print(f"(exit {m.group(1)})")
        read_until(r"SERIALRUN\$ $", 5)
    sys.exit(rc)

if __name__ == "__main__":
    main()
