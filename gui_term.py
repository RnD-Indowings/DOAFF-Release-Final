import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

import nisha2  # backend file
from PIL import Image, ImageTk

# ── color tokens ──────────────────────────────────────────────────────────────
BG = "#0b0d0f"  # near-black canvas
PANEL = "#12151a"  # slightly lighter panel
BORDER = "#1f2830"  # subtle border lines
AMBER = "#d4a017"  # primary accent – targeting amber
AMBER_DIM = "#7a5c0a"  # muted amber for dividers
GREEN = "#39ff14"  # terminal text (neon green)
RED_ERR = "#ff3c3c"  # error state
WHITE = "#e8eaed"  # primary text
MUTED = "#6b7785"  # secondary / label text
BTN_ACT = "#1a3d1a"  # run-button active bg

FONT_MONO = ("Courier New", 10)
FONT_LABEL = ("Courier New", 10, "bold")
FONT_HEAD = ("Courier New", 14, "bold")
FONT_TITLE = ("Courier New", 18, "bold")
FONT_STATUS = ("Courier New", 11, "bold")


class RedirectText:
    def __init__(self, textbox, logfile_all, logfile_gui):
        self.textbox = textbox
        self.log_all = open(logfile_all, "a")
        self.log_gui = open(logfile_gui, "a")

    def write(self, string):
        self.log_all.write(string)
        self.log_all.flush()
        if string.strip().startswith("DroneLat"):
            self.textbox.insert(tk.END, string)
            self.textbox.see(tk.END)
            self.log_gui.write(string)
            self.log_gui.flush()

    def flush(self):
        self.log_all.flush()
        self.log_gui.flush()

    def close(self):
        self.log_all.close()
        self.log_gui.close()


# ── back-end worker ────────────────────────────────────────────────────────────
def run_code():
    try:
        clat = float(entry_lat.get())
        clon = float(entry_lon.get())
    except ValueError:
        messagebox.showerror("Input Error", "Enter valid numeric coordinates")
        return

    status_var.set("● COMPUTING…")
    status_lbl.config(fg=AMBER)
    run_btn.config(state="disabled", bg=AMBER_DIM, fg=MUTED)

    def worker():
        try:
            nisha2.start_with_coordinates(clat, clon)
            status_var.set("● MISSION COMPLETE")
            status_lbl.config(fg=GREEN)
        except Exception as e:
            messagebox.showerror("Runtime Error", str(e))
            status_var.set("● SYSTEM FAULT")
            status_lbl.config(fg=RED_ERR)
        finally:
            run_btn.config(state="normal", bg=BTN_ACT, fg=GREEN)

    threading.Thread(target=worker, daemon=True).start()


# ── helpers ────────────────────────────────────────────────────────────────────
def separator(parent, color=BORDER, pady=4):
    tk.Frame(parent, bg=color, height=1).pack(fill=tk.X, padx=16, pady=pady)


def section_label(parent, text):
    row = tk.Frame(parent, bg=PANEL)
    row.pack(fill=tk.X, padx=16, pady=(10, 4))
    tk.Label(row, text="▸ " + text, font=FONT_LABEL, bg=PANEL, fg=AMBER).pack(side=tk.LEFT)


# ── root window ───────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("ABDE // Artillery Blast Distance Estimator")
root.geometry("660x640")
root.resizable(False, False)
root.configure(bg=BG)

# ── header strip ──────────────────────────────────────────────────────────────
header = tk.Frame(root, bg=PANEL, pady=0)
header.pack(fill=tk.X)

# top amber rule
tk.Frame(header, bg=AMBER, height=2).pack(fill=tk.X)

title_row = tk.Frame(header, bg=PANEL)
title_row.pack(fill=tk.X, padx=18, pady=(10, 6))

# logo — proper padding + white background so it never looks cut
_logo_path = "/home/nisha-/Downloads/indowings_logo.png"
try:
    _logo_raw = Image.open(_logo_path).convert("RGBA")
    # resize content to max 90x55, keeping aspect ratio
    _logo_raw.thumbnail((90, 55), Image.LANCZOS)
    # add 10px padding on all sides so logo breathes
    _pad = 10
    _canvas_w = _logo_raw.width + _pad * 2
    _canvas_h = _logo_raw.height + _pad * 2
    _white_bg = Image.new("RGBA", (_canvas_w, _canvas_h), (255, 255, 255, 255))
    _white_bg.paste(_logo_raw, (_pad, _pad), mask=_logo_raw.split()[3])
    _logo_photo = ImageTk.PhotoImage(_white_bg.convert("RGB"))
    logo_lbl = tk.Label(title_row, image=_logo_photo, bg=PANEL, bd=0)
    logo_lbl.image = _logo_photo
    logo_lbl.pack(side=tk.LEFT, padx=(0, 12))
except Exception:
    pass

tk.Label(
    title_row, text="Artillery Blast Distance Estimator", font=("Courier New", 15, "bold"), bg=PANEL, fg="#b8860b"
).pack(side=tk.LEFT)

# bottom amber rule
tk.Frame(header, bg=AMBER, height=1).pack(fill=tk.X)

# ── body panel ────────────────────────────────────────────────────────────────
body = tk.Frame(root, bg=BG)
body.pack(fill=tk.BOTH, expand=True)

# ── coordinate input section ──────────────────────────────────────────────────
section_label(body, "TARGET COORDINATES")
separator(body)

coord_frame = tk.Frame(body, bg=PANEL, bd=0, relief=tk.FLAT)
coord_frame.pack(padx=16, pady=4, fill=tk.X)
tk.Frame(coord_frame, bg=BORDER, height=1).pack(fill=tk.X)


def coord_row(parent, label_text, row_n):
    row = tk.Frame(parent, bg=PANEL)
    row.pack(fill=tk.X, padx=0, pady=0)

    tk.Label(row, text=label_text, font=FONT_LABEL, width=20, anchor="w", bg=PANEL, fg=MUTED).pack(
        side=tk.LEFT, padx=(14, 6), pady=10
    )

    entry = tk.Entry(
        row,
        width=22,
        font=FONT_MONO,
        bg=BG,
        fg=GREEN,
        insertbackground=AMBER,
        relief=tk.FLAT,
        bd=4,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=AMBER,
    )
    entry.pack(side=tk.LEFT, padx=(0, 14))
    tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X)
    return entry


entry_lat = coord_row(coord_frame, "CENTER LATITUDE :", 0)
entry_lon = coord_row(coord_frame, "CENTER LONGITUDE :", 1)

# ── run + terminate buttons ───────────────────────────────────────────────────
btn_wrap = tk.Frame(body, bg=BG)
btn_wrap.pack(pady=14)

run_btn = tk.Button(
    btn_wrap,
    text="  ▶  INITIATE COMPUTATION  ",
    bg=BTN_ACT,
    fg=GREEN,
    font=("Courier New", 11, "bold"),
    relief=tk.FLAT,
    bd=0,
    padx=18,
    pady=10,
    cursor="crosshair",
    activebackground=AMBER_DIM,
    activeforeground=WHITE,
    command=run_code,
)
run_btn.pack(side=tk.LEFT, padx=(0, 12))

# hover glow
run_btn.bind("<Enter>", lambda e: run_btn.config(bg="#22502a"))
run_btn.bind("<Leave>", lambda e: run_btn.config(bg=BTN_ACT))


def terminate_code():
    answer = messagebox.askyesno(
        "⚠  TERMINATE",
        "Are you sure you want to terminate the running process?\n\nThis will force-stop execution immediately.",
        icon="warning",
    )
    if answer:
        status_var.set("● TERMINATED")
        status_lbl.config(fg=RED_ERR)
        run_btn.config(state="normal", bg=BTN_ACT, fg=GREEN)
        os._exit(0)  # hard kill — stops everything including threads


term_btn = tk.Button(
    btn_wrap,
    text="  ■  TERMINATE  ",
    bg="#3d0000",
    fg=RED_ERR,
    font=("Courier New", 11, "bold"),
    relief=tk.FLAT,
    bd=0,
    padx=18,
    pady=10,
    cursor="crosshair",
    activebackground="#5a0000",
    activeforeground=WHITE,
    command=terminate_code,
)
term_btn.pack(side=tk.LEFT)

# hover glow
term_btn.bind("<Enter>", lambda e: term_btn.config(bg="#5a0000"))
term_btn.bind("<Leave>", lambda e: term_btn.config(bg="#3d0000"))

# ── status bar ────────────────────────────────────────────────────────────────
separator(body, color=AMBER_DIM)

status_row = tk.Frame(body, bg=BG)
status_row.pack(fill=tk.X, padx=18, pady=2)

tk.Label(status_row, text="STATUS", font=("Courier New", 8, "bold"), bg=BG, fg=MUTED).pack(side=tk.LEFT)

status_var = tk.StringVar(value="● STANDBY")
status_lbl = tk.Label(status_row, textvariable=status_var, font=FONT_STATUS, bg=BG, fg=MUTED)
status_lbl.pack(side=tk.LEFT, padx=14)

separator(body, color=AMBER_DIM)

# ── live output section ───────────────────────────────────────────────────────
section_label(body, "TELEMETRY / LIVE OUTPUT")

terminal_outer = tk.Frame(body, bg=BORDER, bd=1, relief=tk.FLAT)
terminal_outer.pack(padx=16, pady=(2, 12), fill=tk.BOTH, expand=True)

# terminal chrome bar
chrome = tk.Frame(terminal_outer, bg="#181c22", pady=4)
chrome.pack(fill=tk.X)
for col in [RED_ERR, AMBER, GREEN]:
    tk.Label(chrome, text=" ● ", font=("Courier New", 8), bg="#181c22", fg=col).pack(side=tk.LEFT, padx=1)
tk.Label(chrome, text="STREAM ACTIVE", font=("Courier New", 8), bg="#181c22", fg=MUTED).pack(side=tk.LEFT, padx=8)

inner = tk.Frame(terminal_outer, bg=BG)
inner.pack(fill=tk.BOTH, expand=True)

scrollbar = tk.Scrollbar(inner, bg=PANEL, troughcolor=BG, relief=tk.FLAT, bd=0, width=10)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

output_box = tk.Text(
    inner,
    height=14,
    width=68,
    bg="#060809",
    fg=GREEN,
    font=FONT_MONO,
    relief=tk.FLAT,
    bd=8,
    insertbackground=AMBER,
    selectbackground=AMBER_DIM,
    yscrollcommand=scrollbar.set,
    wrap=tk.WORD,
)
output_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.config(command=output_box.yview)
output_box.bind("<MouseWheel>", lambda e: output_box.yview_scroll(int(-1 * (e.delta / 120)), "units"))

# ── terminal background image ─────────────────────────────────────────────────
try:
    _tm_raw = Image.open("/home/nisha-/Downloads/logo_t-01.jpg").convert("RGB")
    # resize to fit terminal width, keep aspect ratio
    _tm_w = 580
    _tm_h = int(_tm_raw.height * _tm_w / _tm_raw.width)
    _tm_raw = _tm_raw.resize((_tm_w, _tm_h), Image.LANCZOS)
    # brighten slightly so logo is visible on dark terminal
    from PIL import ImageEnhance

    _tm_raw = ImageEnhance.Brightness(_tm_raw).enhance(1.8)
    _tm_photo = ImageTk.PhotoImage(_tm_raw)
    output_box._tm_photo = _tm_photo  # keep reference
    output_box.tag_configure("center", justify="center")
    output_box.image_create("1.0", image=_tm_photo)
    output_box.insert("1.0", "\n", "center")
    output_box.insert("2.end", "\n")
    output_box.config(state=tk.DISABLED)

    # re-enable state before each write
    _orig_write = RedirectText.write

    def _patched_write(self, string):
        self.textbox.config(state=tk.NORMAL)
        _orig_write(self, string)

    RedirectText.write = _patched_write
except Exception:
    pass

# ── footer ────────────────────────────────────────────────────────────────────
tk.Frame(root, bg=AMBER, height=2).pack(fill=tk.X, side=tk.BOTTOM)
foot = tk.Frame(root, bg=PANEL)
foot.pack(fill=tk.X, side=tk.BOTTOM)
tk.Label(
    foot, text="RESTRICTED  //  AUTHORIZED PERSONNEL ONLY", font=("Courier New", 7, "bold"), bg=PANEL, fg=AMBER_DIM
).pack(pady=3)

# ── stdout redirect ───────────────────────────────────────────────────────────
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE_ALL = f"/home/nisha-/agra_demo/result_except_gui_{timestamp}.txt"
LOG_FILE_GUI = f"/home/nisha-/agra_demo/result_gui_only_{timestamp}.txt"

redirector = RedirectText(output_box, LOG_FILE_ALL, LOG_FILE_GUI)
sys.stdout = redirector
sys.stderr = redirector


def on_close():
    redirector.close()
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()
