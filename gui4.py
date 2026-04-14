#pre-final-gui.py

import tkinter as tk
from tkinter import messagebox
import threading
import sys
import experiment  #backend file
from datetime import datetime

class RedirectText:
    def __init__(self, textbox, logfile_all, logfile_gui):
        self.textbox = textbox
        self.log_all = open(logfile_all, "a")
        self.log_gui = open(logfile_gui, "a")

    def write(self, string):
        self.log_all.write(string)
        self.log_all.flush()

        # If GUI-visible line
        if string.strip().startswith("DroneLat"):
            self.textbox.insert(tk.END, string)
            self.textbox.see(tk.END)

            # Save ONLY GUI lines
            self.log_gui.write(string)
            self.log_gui.flush()

    def flush(self):
        self.log_all.flush()
        self.log_gui.flush()

    def close(self):
        self.log_all.close()
        self.log_gui.close()

#bACKEND
def run_code():
    try:
        clat = float(entry_lat.get())
        clon = float(entry_lon.get())
    except ValueError:
        messagebox.showerror("Input Error", "Enter valid numeric coordinates")
        return

    status_var.set("Running...")
    run_btn.config(state="disabled")

    def worker():
        try:
            experiment.start_with_coordinates(clat, clon)
            status_var.set("Completed ✔")

        except Exception as e:
            messagebox.showerror("Runtime Error", str(e))
            status_var.set("Error ❌")

        finally:
            run_btn.config(state="normal")

    threading.Thread(target=worker, daemon=True).start()


# GUI WINDOW
root = tk.Tk()
root.title("Drone Coordinate System")
root.geometry("550x560")
root.resizable(False, False)

tk.Label(
    root,
    text="Target Coordinate Input",
    font=("Arial",14,"bold")
).pack(pady=10)


frame = tk.Frame(root)
frame.pack(pady=10)

tk.Label(frame, text="Center Latitude", font=("Arial",11)).grid(row=0,column=0,padx=10,pady=6)
entry_lat = tk.Entry(frame, width=25)
entry_lat.grid(row=0,column=1)

tk.Label(frame, text="Center Longitude", font=("Arial",11)).grid(row=1,column=0,padx=10,pady=6)
entry_lon = tk.Entry(frame, width=25)
entry_lon.grid(row=1,column=1)

run_btn = tk.Button(
    root,
    text="RUN",
    bg="green",
    fg="white",
    font=("Arial",12,"bold"),
    width=22,
    command=run_code
)
run_btn.pack(pady=15)
status_var = tk.StringVar(value="Idle")

tk.Label(
    root,
    textvariable=status_var,
    font=("Arial",11,"bold"),
    fg="purple"
).pack()


# TERMINAL OUTPUT 
tk.Label(root, text="Live Output", font=("Arial",12,"bold")).pack(pady=8)

terminal_frame = tk.Frame(root)
terminal_frame.pack(padx=10, pady=5)

scrollbar = tk.Scrollbar(terminal_frame)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

output_box = tk.Text(
    terminal_frame,
    height=18,
    width=70,
    bg="black",
    fg="lime",
    font=("Courier",10),
    yscrollcommand=scrollbar.set
)
output_box.pack(side=tk.LEFT, fill=tk.BOTH)
scrollbar.config(command=output_box.yview)
output_box.bind("<MouseWheel>", lambda e: output_box.yview_scroll(int(-1*(e.delta/120)), "units"))

#  PRINTS 
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