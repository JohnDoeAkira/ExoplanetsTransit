"""Fake detector: emulates the Arduino by writing a noisy transit light curve to a virtual serial port.

Run it, then type the printed port path (e.g. /dev/pts/5) into the viewer's port box and click Connect.
"""
import math
import os
import pty
import random
import time

PERIOD = 10.0    # s between transits
DEPTH = 80       # ADC counts lost during transit
DURATION = 2.0   # s, transit duration
BASE = 600       # ADC counts out of transit
NOISE = 3
RATE = 200       # samples per second

master, slave = pty.openpty()
print("Fake port:", os.ttyname(slave), flush=True)

n = 0
start = time.monotonic()
while True:
    t = n / RATE
    phase = (t % PERIOD) - PERIOD / 2
    dip = 0.0
    if abs(phase) < DURATION / 2:
        # Smooth-edged box: limb-darkened ingress/egress
        dip = DEPTH * math.sqrt(max(0.0, 1 - (2 * phase / DURATION) ** 8))
    v = int(BASE - dip + random.gauss(0, NOISE))
    try:
        os.write(master, f"{v}\r\n".encode())
    except OSError:
        break
    n += 1
    time.sleep(max(0.0, start + n / RATE - time.monotonic()))
