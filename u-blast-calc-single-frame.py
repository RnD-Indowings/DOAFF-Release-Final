"""
blast_geo_gui.py
─────────────────────────────────────────────────────────────────────────────
Single-frame blast geo-estimation GUI with DEM elevation extraction.

  Inputs:
    • Center (target car) lat/lon  — typed in left panel
    • Target car PIXEL             — click on canvas in TARGET mode (green)
    • Blast PIXEL                  — click on canvas in BLAST  mode (red)
    • DEM .tif raster              — browse button

  The target pixel replaces the hardcoded frame-center assumption.
  All geo math is relative to: (target_pixel) → (center_lat, center_lon).

Requires: pillow rasterio numpy
  pip install pillow rasterio numpy
─────────────────────────────────────────────────────────────────────────────
"""

import math
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import numpy as np

try:
    import rasterio
    RASTERIO_OK = True
except ImportError:
    RASTERIO_OK = False

# ═══════════════════════════════════════════════════════════════════════════
#  COLOURS
# ═══════════════════════════════════════════════════════════════════════════
BG        = "#0d1117"
PANEL_BG  = "#161b22"
BORDER    = "#30363d"
ACCENT    = "#00ff88"   # green  — target
ACCENT2   = "#ff4444"   # red    — blast
ACCENT3   = "#f0a500"   # amber  — DEM
DIM_TEXT  = "#8b949e"
TEXT      = "#e6edf3"
FONT_MONO = ("Courier New", 10)
FONT_BOLD = ("Courier New", 11, "bold")
FONT_LG   = ("Courier New", 13, "bold")
FONT_SM   = ("Courier New", 9)

# ═══════════════════════════════════════════════════════════════════════════
#  CAMERA
# ═══════════════════════════════════════════════════════════════════════════
SENSOR_W_MM  = 5.76
SENSOR_H_MM  = 4.29
FOCAL_LEN_MM = 88.4

# ═══════════════════════════════════════════════════════════════════════════
#  GEOMETRY
# ═══════════════════════════════════════════════════════════════════════════

def compute_mpp(img_w, img_h, drone_lat, drone_lon,
                center_lat, center_lon, altitude_m):
    hfov = 2 * math.atan(SENSOR_W_MM / (2 * FOCAL_LEN_MM))
    vfov = 2 * math.atan(SENSOR_H_MM / (2 * FOCAL_LEN_MM))
    dlat = center_lat - drone_lat
    dlon = center_lon - drone_lon
    dy   = dlat * 111320
    dx   = dlon * 111320 * math.cos(math.radians(center_lat))
    L    = math.sqrt(dx**2 + dy**2 + altitude_m**2)
    gw   = 2 * L * math.tan(hfov / 2)
    gh   = 2 * L * math.tan(vfov / 2)
    return gw / img_w, gh / img_h


def pixel_to_latlon(blast_cx, blast_cy,
                    target_px, target_py,
                    mpp_x, mpp_y,
                    center_lat, center_lon):
    """
    blast pixel → lat/lon, using target pixel as the geo anchor.
    target_px, target_py  = pixel that maps to (center_lat, center_lon)
    """
    dx_px   = blast_cx - target_px
    dy_px   = target_py - blast_cy     # image Y is flipped (up = +)
    dx_m    = dx_px * mpp_x
    dy_m    = dy_px * mpp_y
    cos_lat = max(math.cos(math.radians(center_lat)), 1e-6)
    blast_lat = center_lat + dy_m / 111320
    blast_lon = center_lon + dx_m / (111320 * cos_lat)
    dist_m  = math.sqrt(dx_m**2 + dy_m**2)
    return blast_lat, blast_lon, dx_m, dy_m, dist_m

# ═══════════════════════════════════════════════════════════════════════════
#  DEM
# ═══════════════════════════════════════════════════════════════════════════

_dem_src = None

def load_dem(path):
    global _dem_src
    if not RASTERIO_OK:
        return "rasterio not installed  (pip install rasterio)"
    try:
        if _dem_src is not None:
            _dem_src.close()
        _dem_src = rasterio.open(path)
        return ""
    except Exception as e:
        _dem_src = None
        return str(e)

def get_elevation(lat, lon):
    if _dem_src is None:
        return None
    try:
        b = _dem_src.bounds
        if not (b.left <= lon <= b.right and b.bottom <= lat <= b.top):
            return None
        for val in _dem_src.sample([(lon, lat)]):
            z = val[0]
            return None if np.isnan(z) else float(z)
    except Exception as e:
        print("DEM sample error:", e)
        return None

# ═══════════════════════════════════════════════════════════════════════════
#  HELPER
# ═══════════════════════════════════════════════════════════════════════════

def labeled_entry(parent, row, label_text, default="", width=20, accent=ACCENT):
    tk.Label(parent, text=label_text, fg=DIM_TEXT, bg=PANEL_BG,
             font=FONT_SM, anchor="w").grid(
                 row=row, column=0, sticky="w", pady=2, padx=(0, 8))
    var = tk.StringVar(value=default)
    tk.Entry(parent, textvariable=var, width=width,
             bg="#1c2128", fg=accent, insertbackground=accent,
             relief="flat", font=FONT_MONO,
             highlightthickness=1, highlightcolor=accent,
             highlightbackground=BORDER).grid(row=row, column=1, sticky="ew", pady=2)
    return var

def section_label(parent, row, text):
    tk.Label(parent, text=text, fg=BORDER, bg=PANEL_BG,
             font=("Courier New", 8)).grid(
                 row=row, column=0, columnspan=2,
                 sticky="w", padx=4, pady=(8, 2))

def hsep(parent, row):
    tk.Frame(parent, bg=BORDER, height=1).grid(
        row=row, column=0, columnspan=2, sticky="ew", pady=8, padx=4)

def make_btn(parent, text, cmd, fg, bg):
    return tk.Button(parent, text=text, command=cmd,
                     fg=fg, bg=bg, activeforeground=BG,
                     activebackground=ACCENT, relief="flat",
                     font=("Courier New", 10, "bold"),
                     padx=10, pady=5, cursor="hand2",
                     bd=0, highlightthickness=1, highlightbackground=BORDER)

# ═══════════════════════════════════════════════════════════════════════════
#  APP
# ═══════════════════════════════════════════════════════════════════════════

class BlastGeoApp(tk.Tk):

    CANVAS_W = 840
    CANVAS_H = 500

    # click mode
    MODE_TARGET = "target"
    MODE_BLAST  = "blast"

    def __init__(self):
        super().__init__()
        self.title("IndoSentinel — Blast Geo Estimator")
        self.configure(bg=BG)
        self.resizable(False, False)

        self.orig_img  = None
        self.tk_img    = None
        self.scale_x   = 1.0
        self.scale_y   = 1.0
        self._off_x    = 0
        self._off_y    = 0

        # pixel coords in ORIGINAL image space
        self.target_px = None   # target car pixel
        self.target_py = None
        self.blast_cx  = None   # blast pixel
        self.blast_cy  = None

        self.click_mode = tk.StringVar(value=self.MODE_TARGET)

        self._build_ui()

    # ── BUILD ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(hdr, text="◈ INDOSENTINEL", fg=ACCENT, bg=BG,
                 font=("Courier New", 15, "bold")).pack(side="left")
        tk.Label(hdr, text="  BLAST GEO ESTIMATOR  —  SINGLE FRAME",
                 fg=DIM_TEXT, bg=BG, font=FONT_SM).pack(side="left", pady=(4, 0))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=20, pady=8)

        main = tk.Frame(self, bg=BG)
        main.pack(padx=14, fill="both", expand=True)

        self._build_left(main)
        self._build_canvas(main)
        self._build_results()

    # ── LEFT PANEL ─────────────────────────────────────────────────────────

    def _build_left(self, parent):
        lf = tk.Frame(parent, bg=PANEL_BG,
                      highlightthickness=1, highlightbackground=BORDER)
        lf.pack(side="left", fill="y", padx=(0, 10), ipadx=10, ipady=10)

        tk.Label(lf, text="PARAMETERS", fg=ACCENT, bg=PANEL_BG,
                 font=FONT_BOLD).grid(row=0, column=0, columnspan=2,
                                       pady=(6, 8), padx=8, sticky="w")

        # Drone GPS
        section_label(lf, 1, "── DRONE GPS")
        self.v_dlat = labeled_entry(lf, 2, "Drone Lat",  "28.773600")
        self.v_dlon = labeled_entry(lf, 3, "Drone Lon",  "77.148250")

        # Frame center GPS
        section_label(lf, 4, "── TARGET GPS  (center lat/lon)")
        self.v_clat = labeled_entry(lf, 5, "Center Lat", "28.773800")
        self.v_clon = labeled_entry(lf, 6, "Center Lon", "77.148500")

        # Altitude
        section_label(lf, 7, "── ALTITUDE")
        self.v_alt  = labeled_entry(lf, 8, "AGL (m)",    "10.0")

        hsep(lf, 9)

        # DEM
        section_label(lf, 10, "── DEM  (.tif SRTM raster)")
        self.v_dem = tk.StringVar(value="No DEM loaded")
        tk.Entry(lf, textvariable=self.v_dem, width=20,
                 bg="#1c2128", fg=ACCENT3, relief="flat", font=("Courier New", 8),
                 highlightthickness=1, highlightbackground=BORDER,
                 state="readonly").grid(row=11, column=0, columnspan=2,
                                        sticky="ew", pady=2, padx=2)
        make_btn(lf, "📁  BROWSE DEM", self._load_dem,
                 ACCENT3, "#1c2128").grid(row=12, column=0, columnspan=2,
                                           sticky="ew", pady=(3,0), padx=2)
        self.dem_status = tk.StringVar(value="DEM not loaded — Z skipped.")
        tk.Label(lf, textvariable=self.dem_status, fg=DIM_TEXT, bg=PANEL_BG,
                 font=("Courier New", 7), wraplength=190,
                 justify="left").grid(row=13, column=0, columnspan=2,
                                       sticky="w", padx=2, pady=(2,0))

        hsep(lf, 14)

        # ── TARGET PIXEL ──────────────────────────────────────────────────
        section_label(lf, 15, "── TARGET CAR PIXEL  (click ● TARGET)")
        self.v_tx = labeled_entry(lf, 16, "Target X", "—", width=10, accent=ACCENT)
        self.v_ty = labeled_entry(lf, 17, "Target Y", "—", width=10, accent=ACCENT)

        # ── BLAST PIXEL ───────────────────────────────────────────────────
        section_label(lf, 18, "── BLAST PIXEL  (click ● BLAST)")
        self.v_cx = labeled_entry(lf, 19, "Blast X",  "—", width=10, accent=ACCENT2)
        self.v_cy = labeled_entry(lf, 20, "Blast Y",  "—", width=10, accent=ACCENT2)

        hsep(lf, 21)

        # ── CLICK MODE TOGGLE ─────────────────────────────────────────────
        mode_frame = tk.Frame(lf, bg=PANEL_BG)
        mode_frame.grid(row=22, column=0, columnspan=2, sticky="ew", padx=2, pady=(0,6))

        tk.Label(mode_frame, text="Click mode:", fg=DIM_TEXT, bg=PANEL_BG,
                 font=FONT_SM).pack(side="left", padx=(0,6))

        self._btn_mode_target = tk.Button(
            mode_frame, text="● TARGET", font=("Courier New", 9, "bold"),
            fg=BG, bg=ACCENT, relief="flat", padx=8, pady=3,
            cursor="hand2", command=lambda: self._set_mode(self.MODE_TARGET))
        self._btn_mode_target.pack(side="left", padx=(0,4))

        self._btn_mode_blast = tk.Button(
            mode_frame, text="● BLAST", font=("Courier New", 9, "bold"),
            fg=ACCENT2, bg=PANEL_BG, relief="flat", padx=8, pady=3,
            cursor="hand2",
            highlightthickness=1, highlightbackground=ACCENT2,
            command=lambda: self._set_mode(self.MODE_BLAST))
        self._btn_mode_blast.pack(side="left")

        # ── ACTION BUTTONS ────────────────────────────────────────────────
        btn_frame = tk.Frame(lf, bg=PANEL_BG)
        btn_frame.grid(row=23, column=0, columnspan=2, pady=4, padx=2)

        make_btn(btn_frame, "📂  LOAD IMAGE",   self._load_image,
                 ACCENT, "#0d1117").pack(fill="x", pady=(0, 5))
        make_btn(btn_frame, "⟳  CLEAR ALL",     self._clear_all,
                 DIM_TEXT, PANEL_BG).pack(fill="x", pady=(0, 5))
        make_btn(btn_frame, "▶  COMPUTE",        self._compute,
                 "#0d1117", ACCENT).pack(fill="x")

    # ── CANVAS ─────────────────────────────────────────────────────────────

    def _build_canvas(self, parent):
        cf = tk.Frame(parent, bg=PANEL_BG,
                      highlightthickness=1, highlightbackground=BORDER)
        cf.pack(side="left", fill="both", expand=True, ipady=6, ipadx=6)

        # header with live mode indicator
        top = tk.Frame(cf, bg=PANEL_BG)
        top.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(top, text="SCENE", fg=DIM_TEXT, bg=PANEL_BG,
                 font=FONT_SM).pack(side="left")
        self.mode_indicator = tk.Label(top, text="  ● Clicking: TARGET",
                                       fg=ACCENT, bg=PANEL_BG,
                                       font=("Courier New", 9, "bold"))
        self.mode_indicator.pack(side="left")

        self.canvas = tk.Canvas(cf, width=self.CANVAS_W, height=self.CANVAS_H,
                                bg="#090c10", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(padx=6, pady=(0, 4))
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>",   self._on_move)

        self._placeholder()

        self.status_var = tk.StringVar(value="Load an image to begin.")
        tk.Label(cf, textvariable=self.status_var, fg=DIM_TEXT, bg=PANEL_BG,
                 font=FONT_SM, anchor="w").pack(anchor="w", padx=8)

    # ── RESULT BARS ────────────────────────────────────────────────────────

    def _build_results(self):
        # GEO bar
        rb = tk.Frame(self, bg=PANEL_BG,
                      highlightthickness=1, highlightbackground=BORDER)
        rb.pack(fill="x", padx=14, pady=(8, 2), ipady=8, ipadx=14)
        tk.Label(rb, text="GEO", fg=ACCENT, bg=PANEL_BG,
                 font=FONT_BOLD).grid(row=0, column=0, sticky="w", padx=(0, 16))
        self.result_vars = {}
        for i, lbl in enumerate(["Blast Lat", "Blast Lon", "Dist (m)", "ΔX (m)", "ΔY (m)"]):
            tk.Label(rb, text=lbl + ":", fg=DIM_TEXT, bg=PANEL_BG,
                     font=FONT_SM).grid(row=0, column=1+i*2, sticky="e", padx=(10,2))
            v = tk.StringVar(value="—")
            tk.Label(rb, textvariable=v,
                     fg=ACCENT2 if i < 2 else TEXT,
                     bg=PANEL_BG,
                     font=FONT_LG if i < 2 else FONT_BOLD,
                     width=14 if i < 2 else 9, anchor="w").grid(
                         row=0, column=2+i*2, sticky="w")
            self.result_vars[lbl] = v

        # DEM bar
        rb2 = tk.Frame(self, bg=PANEL_BG,
                       highlightthickness=1, highlightbackground=BORDER)
        rb2.pack(fill="x", padx=14, pady=(2, 14), ipady=8, ipadx=14)
        tk.Label(rb2, text="DEM", fg=ACCENT3, bg=PANEL_BG,
                 font=FONT_BOLD).grid(row=0, column=0, sticky="w", padx=(0, 16))
        self.dem_vars = {}
        for i, lbl in enumerate(["Z Center (m)", "Z Blast (m)", "Z Offset (m)"]):
            tk.Label(rb2, text=lbl + ":", fg=DIM_TEXT, bg=PANEL_BG,
                     font=FONT_SM).grid(row=0, column=1+i*2, sticky="e", padx=(18,2))
            v = tk.StringVar(value="—")
            tk.Label(rb2, textvariable=v, fg=ACCENT3, bg=PANEL_BG,
                     font=FONT_LG, width=12, anchor="w").grid(
                         row=0, column=2+i*2, sticky="w")
            self.dem_vars[lbl] = v
        tk.Label(rb2, text="(Z Offset = blast elev − target elev)",
                 fg=BORDER, bg=PANEL_BG,
                 font=("Courier New", 7)).grid(row=0, column=7, sticky="w", padx=(16,0))

    # ── CLICK MODE ─────────────────────────────────────────────────────────

    def _set_mode(self, mode):
        self.click_mode.set(mode)
        if mode == self.MODE_TARGET:
            self._btn_mode_target.config(fg=BG, bg=ACCENT)
            self._btn_mode_blast.config(fg=ACCENT2, bg=PANEL_BG)
            self.mode_indicator.config(text="  ● Clicking: TARGET", fg=ACCENT)
            self.canvas.config(cursor="crosshair")
        else:
            self._btn_mode_blast.config(fg=BG, bg=ACCENT2)
            self._btn_mode_target.config(fg=ACCENT, bg=PANEL_BG)
            self.mode_indicator.config(text="  ● Clicking: BLAST", fg=ACCENT2)
            self.canvas.config(cursor="crosshair")

    # ── PLACEHOLDER ────────────────────────────────────────────────────────

    def _placeholder(self):
        self.canvas.delete("all")
        cw, ch = self.CANVAS_W, self.CANVAS_H
        for x in range(0, cw, 60):
            self.canvas.create_line(x, 0, x, ch, fill="#1a2030")
        for y in range(0, ch, 60):
            self.canvas.create_line(0, y, cw, y, fill="#1a2030")
        self.canvas.create_text(cw//2, ch//2,
                                text="[ No image loaded — click  📂 LOAD IMAGE ]",
                                fill=BORDER, font=("Courier New", 12))

    # ── RENDER ─────────────────────────────────────────────────────────────

    def _render(self):
        if self.orig_img is None:
            return
        ow, oh = self.orig_img.width, self.orig_img.height
        scale  = min(self.CANVAS_W / ow, self.CANVAS_H / oh)
        dw, dh = int(ow * scale), int(oh * scale)
        self.scale_x = ow / dw
        self.scale_y = oh / dh

        disp = self.orig_img.copy().resize((dw, dh), Image.LANCZOS)
        draw = ImageDraw.Draw(disp)

        # target marker — green crosshair
        if self.target_px is not None:
            tx = int(self.target_px / self.scale_x)
            ty = int(self.target_py / self.scale_y)
            draw.line([(tx-28, ty), (tx+28, ty)], fill="#00ff88", width=2)
            draw.line([(tx, ty-28), (tx, ty+28)], fill="#00ff88", width=2)
            draw.ellipse([(tx-5, ty-5), (tx+5, ty+5)], outline="#00ff88", width=2)
            draw.ellipse([(tx-2, ty-2), (tx+2, ty+2)], fill="#00ff88")

        # blast marker — red crosshair + circle
        if self.blast_cx is not None:
            bx = int(self.blast_cx / self.scale_x)
            by = int(self.blast_cy / self.scale_y)
            r  = 10
            draw.ellipse([(bx-r, by-r), (bx+r, by+r)], outline="#ff4444", width=3)
            draw.ellipse([(bx-3, by-3), (bx+3, by+3)], fill="#ff4444")
            draw.line([(bx-22, by), (bx+22, by)], fill="#ff4444", width=2)
            draw.line([(bx, by-22), (bx, by+22)], fill="#ff4444", width=2)

        self.canvas.delete("all")
        self._off_x = (self.CANVAS_W - dw) // 2
        self._off_y = (self.CANVAS_H - dh) // 2
        self.tk_img = ImageTk.PhotoImage(disp)
        self.canvas.create_image(self._off_x, self._off_y,
                                 anchor="nw", image=self.tk_img)

    # ── CANVAS EVENTS ──────────────────────────────────────────────────────

    def _canvas_to_orig(self, cx, cy):
        """Convert canvas pixel → original image pixel. Returns (ix, iy) or None."""
        if self.orig_img is None:
            return None
        ix = (cx - self._off_x) * self.scale_x
        iy = (cy - self._off_y) * self.scale_y
        if 0 <= ix <= self.orig_img.width and 0 <= iy <= self.orig_img.height:
            return int(ix), int(iy)
        return None

    def _on_click(self, event):
        if self.orig_img is None:
            messagebox.showinfo("No image", "Load an image first.")
            return
        pt = self._canvas_to_orig(event.x, event.y)
        if pt is None:
            return
        ix, iy = pt

        if self.click_mode.get() == self.MODE_TARGET:
            self.target_px, self.target_py = ix, iy
            self.v_tx.set(str(ix))
            self.v_ty.set(str(iy))
            self.status_var.set(
                f"TARGET pixel set → X: {ix}   Y: {iy}   "
                f"| Switch to ● BLAST mode and click the blast car.")
        else:
            self.blast_cx, self.blast_cy = ix, iy
            self.v_cx.set(str(ix))
            self.v_cy.set(str(iy))
            self.status_var.set(
                f"BLAST pixel set → X: {ix}   Y: {iy}   "
                f"| Click ▶ COMPUTE to get lat/lon + elevation.")

        self._render()

    def _on_move(self, event):
        if self.orig_img is None:
            return
        pt = self._canvas_to_orig(event.x, event.y)
        if pt:
            ix, iy = pt
            mode = "TARGET" if self.click_mode.get() == self.MODE_TARGET else "BLAST"
            self.status_var.set(f"[{mode}]  Cursor → X: {ix}   Y: {iy}")

    # ── LOAD IMAGE ─────────────────────────────────────────────────────────

    def _load_image(self):
        path = filedialog.askopenfilename(
            title="Select scene image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("All", "*.*")])
        if not path:
            return
        self.orig_img  = Image.open(path)
        self.target_px = None
        self.target_py = None
        self.blast_cx  = None
        self.blast_cy  = None
        self._render()
        self.status_var.set(
            f"Loaded: {path.split('/')[-1]}  |  "
            f"{self.orig_img.width}×{self.orig_img.height}  |  "
            f"Mode = TARGET — click the target car first.")

    # ── LOAD DEM ───────────────────────────────────────────────────────────

    def _load_dem(self):
        path = filedialog.askopenfilename(
            title="Select DEM raster (.tif)",
            filetypes=[("GeoTIFF", "*.tif *.tiff"), ("All", "*.*")])
        if not path:
            return
        err = load_dem(path)
        if err:
            self.v_dem.set("ERROR")
            self.dem_status.set(f"Load failed: {err}")
            messagebox.showerror("DEM error", err)
        else:
            self.v_dem.set(path.split("/")[-1])
            b = _dem_src.bounds
            self.dem_status.set(
                f"✔ Loaded  |  Bounds: [{b.bottom:.3f}N – {b.top:.3f}N, "
                f"{b.left:.3f}E – {b.right:.3f}E]")

    # ── CLEAR ──────────────────────────────────────────────────────────────

    def _clear_all(self):
        self.target_px = self.target_py = None
        self.blast_cx  = self.blast_cy  = None
        for sv in [self.v_tx, self.v_ty, self.v_cx, self.v_cy]:
            sv.set("—")
        for v in self.result_vars.values():
            v.set("—")
        for v in self.dem_vars.values():
            v.set("—")
        if self.orig_img:
            self._render()
        self.status_var.set("Cleared. Click TARGET car first, then BLAST car.")

    # ── COMPUTE ────────────────────────────────────────────────────────────

    def _compute(self):
        # validate GPS / altitude
        try:
            drone_lat  = float(self.v_dlat.get())
            drone_lon  = float(self.v_dlon.get())
            center_lat = float(self.v_clat.get())
            center_lon = float(self.v_clon.get())
            altitude_m = float(self.v_alt.get())
        except ValueError:
            messagebox.showerror("Input error", "GPS / altitude fields must be numeric.")
            return

        # validate target pixel
        try:
            tpx = int(self.v_tx.get())
            tpy = int(self.v_ty.get())
        except ValueError:
            messagebox.showerror("No target pixel",
                                 "Click the TARGET car on the image first\n"
                                 "(mode = ● TARGET), or type X/Y manually.")
            return

        # validate blast pixel
        try:
            bpx = int(self.v_cx.get())
            bpy = int(self.v_cy.get())
        except ValueError:
            messagebox.showerror("No blast pixel",
                                 "Click the BLAST car on the image first\n"
                                 "(mode = ● BLAST), or type X/Y manually.")
            return

        if self.orig_img is None:
            messagebox.showerror("No image", "Load an image first.")
            return

        ow, oh = self.orig_img.width, self.orig_img.height

        mpp_x, mpp_y = compute_mpp(ow, oh,
                                    drone_lat, drone_lon,
                                    center_lat, center_lon,
                                    altitude_m)

        blast_lat, blast_lon, dx_m, dy_m, dist_m = pixel_to_latlon(
            bpx, bpy, tpx, tpy,
            mpp_x, mpp_y, center_lat, center_lon)

        # DEM elevation
        z_center = get_elevation(center_lat, center_lon)
        z_blast  = get_elevation(blast_lat,  blast_lon)

        if z_center is not None and z_blast is not None:
            z_center_s = f"{z_center:.2f}"
            z_blast_s  = f"{z_blast:.2f}"
            z_offset_s = f"{(z_blast - z_center):+.2f}"
        elif _dem_src is None:
            z_center_s = z_blast_s = z_offset_s = "No DEM"
        else:
            z_center_s = f"{z_center:.2f}" if z_center is not None else "Out of bounds"
            z_blast_s  = f"{z_blast:.2f}"  if z_blast  is not None else "Out of bounds"
            z_offset_s = "N/A"

        # update GEO bar
        self.result_vars["Blast Lat"].set(f"{blast_lat:.6f}")
        self.result_vars["Blast Lon"].set(f"{blast_lon:.6f}")
        self.result_vars["Dist (m)"].set(f"{dist_m:.2f}")
        self.result_vars["ΔX (m)"].set(f"{dx_m:+.2f}")
        self.result_vars["ΔY (m)"].set(f"{dy_m:+.2f}")

        # update DEM bar
        self.dem_vars["Z Center (m)"].set(z_center_s)
        self.dem_vars["Z Blast (m)"].set(z_blast_s)
        self.dem_vars["Z Offset (m)"].set(z_offset_s)

        self.status_var.set(
            f"✔  Blast → {blast_lat:.6f}, {blast_lon:.6f}  |  "
            f"Dist: {dist_m:.2f} m  |  "
            f"Z Center: {z_center_s} m   Z Blast: {z_blast_s} m   Z Offset: {z_offset_s} m"
        )

        # terminal dump
        print("\n" + "=" * 75)
        print("  BLAST GEOLOCATION + ELEVATION RESULT")
        print("=" * 75)
        print(f"  Drone GPS      : {drone_lat:.6f}, {drone_lon:.6f}")
        print(f"  Target GPS     : {center_lat:.6f}, {center_lon:.6f}")
        print(f"  Target pixel   : ({tpx}, {tpy})")
        print(f"  Altitude AGL   : {altitude_m:.2f} m")
        print(f"  mpp_x / mpp_y  : {mpp_x:.6f} / {mpp_y:.6f} m/px")
        print(f"  Blast pixel    : ({bpx}, {bpy})")
        print(f"  ΔX / ΔY        : {dx_m:+.2f} m / {dy_m:+.2f} m")
        print(f"  Distance       : {dist_m:.2f} m")
        print(f"\n  ► Blast Lat    : {blast_lat:.6f}")
        print(f"  ► Blast Lon    : {blast_lon:.6f}")
        print(f"\n  ── ELEVATION (DEM) ──────────────────────")
        print(f"  Z Target       : {z_center_s} m")
        print(f"  Z Blast        : {z_blast_s} m")
        print(f"  Z Offset       : {z_offset_s} m  (blast − target)")
        print("=" * 75)


if __name__ == "__main__":
    app = BlastGeoApp()
    app.mainloop()
