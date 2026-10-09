"""Live light-curve viewer for the exoplanet transit detector.

Requires: pip install pyserial matplotlib
Close the Arduino IDE serial monitor/plotter first (the port can only be opened once).
"""
import collections
import time
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

import serial
import serial.tools.list_ports
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

BAUD = 57600
MAX_POINTS = 200_000


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Exoplanet transit - light curve")
        self.ser = None
        self.t = collections.deque(maxlen=MAX_POINTS)
        self.y = collections.deque(maxlen=MAX_POINTS)
        self.t0 = None
        self.last_read = None
        self.bg = "#101820"
        self.fg = "#ffd23f"

        self._build_controls()
        self._build_plot()
        self._refresh_ports()
        self.after(30, self._tick)

    def _build_controls(self):
        bar = ttk.Frame(self, padding=4)
        bar.pack(fill="x")

        self.port = tk.StringVar()
        self.port_box = ttk.Combobox(bar, textvariable=self.port, width=16)
        self.port_box.pack(side="left")
        ttk.Button(bar, text="Refresh", command=self._refresh_ports).pack(side="left")
        self.conn_btn = ttk.Button(bar, text="Connect", command=self._toggle)
        self.conn_btn.pack(side="left", padx=4)
        ttk.Button(bar, text="Clear", command=self._clear).pack(side="left")
        ttk.Button(bar, text="Save CSV", command=self._save).pack(side="left", padx=4)

        ttk.Button(bar, text="Background", command=lambda: self._pick("bg")).pack(side="left", padx=(12, 0))
        ttk.Button(bar, text="Curve", command=lambda: self._pick("fg")).pack(side="left")

        bar2 = ttk.Frame(self, padding=4)
        bar2.pack(fill="x")

        self.window = tk.DoubleVar(value=30.0)
        ttk.Label(bar2, text="Time window (s):").pack(side="left")
        ttk.Spinbox(bar2, from_=1, to=3600, increment=5, width=6, textvariable=self.window).pack(side="left")

        self.auto_y = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar2, text="Auto Y", variable=self.auto_y).pack(side="left", padx=(12, 0))
        self.ymin = tk.DoubleVar(value=0)
        self.ymax = tk.DoubleVar(value=1023)
        ttk.Label(bar2, text="Y min:").pack(side="left")
        ttk.Spinbox(bar2, from_=0, to=1023, width=6, textvariable=self.ymin).pack(side="left")
        ttk.Label(bar2, text="Y max:").pack(side="left")
        ttk.Spinbox(bar2, from_=0, to=1023, width=6, textvariable=self.ymax).pack(side="left")

        self.smooth = tk.IntVar(value=1)
        ttk.Label(bar2, text="Smoothing (samples):").pack(side="left", padx=(12, 0))
        ttk.Spinbox(bar2, from_=1, to=500, width=5, textvariable=self.smooth).pack(side="left")

        self.width = tk.DoubleVar(value=1.2)
        ttk.Label(bar2, text="Line width:").pack(side="left", padx=(12, 0))
        ttk.Spinbox(bar2, from_=0.5, to=10, increment=0.5, width=5, textvariable=self.width).pack(side="left")

        self.detect = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar2, text="Detect transits", variable=self.detect).pack(side="left")
        self.marks = []

        bar3 = ttk.Frame(self, padding=4)
        bar3.pack(fill="x")
        ttk.Label(bar3, text="Detection:").pack(side="left")
        self.p_sigma = tk.DoubleVar(value=5.0)
        self.p_rel = tk.DoubleVar(value=2.0)
        self.p_gap = tk.DoubleVar(value=0.15)
        self.p_dur = tk.DoubleVar(value=0.3)
        for label, var, lo, hi, inc in (
            ("Threshold (x noise):", self.p_sigma, 1, 50, 0.5),
            ("Min depth (%):", self.p_rel, 0, 100, 0.5),
            ("Merge gap (s):", self.p_gap, 0, 10, 0.05),
            ("Min duration (s):", self.p_dur, 0, 60, 0.1),
        ):
            ttk.Label(bar3, text=label).pack(side="left", padx=(8, 0))
            ttk.Spinbox(bar3, from_=lo, to=hi, increment=inc, width=6, textvariable=var).pack(side="left")

        self.paused = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar2, text="Pause", variable=self.paused).pack(side="left", padx=12)

    def _build_plot(self):
        self.fig = Figure(figsize=(9, 5))
        self.ax = self.fig.add_subplot(111)
        (self.line,) = self.ax.plot([], [], lw=1.2)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Light intensity (ADC)")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._apply_colors()

    def _apply_colors(self):
        self.fig.set_facecolor(self.bg)
        self.ax.set_facecolor(self.bg)
        # Pick a readable axis color against the chosen background.
        r, g, b = (int(self.bg[i:i + 2], 16) for i in (1, 3, 5))
        axis = "white" if (0.299 * r + 0.587 * g + 0.114 * b) < 128 else "black"
        for s in self.ax.spines.values():
            s.set_color(axis)
        self.ax.tick_params(colors=axis)
        self.ax.xaxis.label.set_color(axis)
        self.ax.yaxis.label.set_color(axis)
        self.ax.grid(True, color=axis, alpha=0.15)
        self.line.set_color(self.fg)

    def _pick(self, which):
        c = colorchooser.askcolor(color=getattr(self, which))[1]
        if c:
            setattr(self, which, c)
            self._apply_colors()

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_box["values"] = ports
        if ports and not self.port.get():
            self.port.set(ports[0])

    def _toggle(self):
        if self.ser:
            self.ser.close()
            self.ser = None
            self.conn_btn.config(text="Connect")
            return
        try:
            self.ser = serial.Serial(self.port.get(), BAUD, timeout=0)
        except serial.SerialException as e:
            messagebox.showerror("Serial error", str(e))
            return
        self._buf = b""
        self.last_read = None
        self.conn_btn.config(text="Disconnect")

    def _clear(self):
        self.t.clear()
        self.y.clear()
        self.t0 = None

    def _save(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv")
        if path:
            with open(path, "w") as f:
                f.write("time_s,value\n")
                f.writelines(f"{a:.4f},{b}\n" for a, b in zip(self.t, self.y))

    def _read(self):
        if not self.ser:
            return
        try:
            self._buf += self.ser.read(65536)
        except serial.SerialException:
            self._toggle()
            return
        *lines, self._buf = self._buf.split(b"\n")
        now = time.monotonic()
        prev = self.last_read if self.last_read is not None else now
        self.last_read = now
        values = []
        for ln in lines:
            try:
                values.append(int(ln.strip()))
            except ValueError:
                continue
        if not values:
            return
        if self.t0 is None:
            self.t0 = prev
        # Samples in one batch arrived together: spread them evenly since the previous read.
        n = len(values)
        for i, v in enumerate(values):
            self.t.append(prev + (now - prev) * (i + 1) / n - self.t0)
            self.y.append(v)

    def _tick(self):
        self._read()
        if not self.paused.get() and self.t:
            try:
                win = max(float(self.window.get()), 0.1)
                k = max(int(self.smooth.get()), 1)
            except tk.TclError:
                win, k = 30.0, 1
            t_end = self.t[-1]
            ts, ys = [], []
            for a, b in zip(reversed(self.t), reversed(self.y)):
                if a < t_end - win:
                    break
                ts.append(a)
                ys.append(b)
            ts.reverse()
            ys.reverse()
            if k > 1 and len(ys) >= k:
                c, acc = [0], 0
                for v in ys:
                    acc += v
                    c.append(acc)
                ys = [(c[i + 1] - c[max(0, i + 1 - k)]) / min(k, i + 1) for i in range(len(ys))]
            self.line.set_data(ts, ys)
            try:
                self.line.set_linewidth(max(float(self.width.get()), 0.1))
            except tk.TclError:
                pass
            self.ax.set_xlim(max(0, t_end - win), max(t_end, win))
            try:
                if self.auto_y.get():
                    lo, hi = min(ys), max(ys)
                    pad = max((hi - lo) * 0.1, 1)
                    self.ax.set_ylim(lo - pad, hi + pad)
                else:
                    self.ax.set_ylim(self.ymin.get(), self.ymax.get())
            except tk.TclError:
                pass
            self._annotate(ts, ys)
            self.canvas.draw_idle()
        self.after(30, self._tick)

    def _annotate(self, ts, ys):
        for m in self.marks:
            m.remove()
        self.marks = []
        if not self.detect.get() or len(ys) < 20:
            return
        try:
            k_sigma, k_rel = self.p_sigma.get(), self.p_rel.get() / 100
            max_gap, min_dur = self.p_gap.get(), self.p_dur.get()
        except tk.TclError:
            return
        t, y = np.asarray(ts), np.asarray(ys, dtype=float)
        med = np.median(y)
        top = y[y >= med]
        base = np.median(top)
        sigma = 1.4826 * np.median(np.abs(top - base)) or 1.0
        below = y < base - max(k_sigma * sigma, k_rel * abs(base))

        # Runs of consecutive below-threshold samples, merging gaps shorter than max_gap.
        edges = np.flatnonzero(np.diff(np.concatenate(([0], below.astype(int), [0]))))
        runs = [[t[a], t[b - 1], a, b] for a, b in zip(edges[::2], edges[1::2])]
        merged = []
        for r in runs:
            if merged and r[0] - merged[-1][1] < max_gap:
                merged[-1][1:] = [r[1], merged[-1][2], r[3]]
            else:
                merged.append(r)

        axis = self.ax.xaxis.label.get_color()
        self.marks.append(self.ax.axhline(base, color=axis, ls="--", lw=0.8, alpha=0.5))
        for t0, t1, a, b in merged:
            if t1 - t0 < min_dur:
                continue
            depth = base - np.median(y[a:b])
            self.marks.append(self.ax.axvspan(t0, t1, color=self.fg, alpha=0.12))
            self.marks.append(self.ax.annotate(
                f"depth {depth:.1f} ({100 * depth / base:.1f} %)\nduration {t1 - t0:.2f} s",
                ((t0 + t1) / 2, base), xytext=(0, 14), textcoords="offset points",
                ha="center", color=axis,
                arrowprops=dict(arrowstyle="-", color=axis, alpha=0.5)))


if __name__ == "__main__":
    App().mainloop()
