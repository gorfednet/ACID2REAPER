"""
Cross-platform desktop UI built on Tkinter + ttk (standard library).

Design goals:
- **Accessible**: large default padding, system theme via ttk, keyboard focus
  on primary actions, native file dialogs (screen readers hook into OS APIs).
- **Scalable**: single window; layout uses grid weights so resizing distributes space.
- **Premium feel**: calm spacing, clear hierarchy, status feedback without clutter.

This module is only imported when the user runs ``--gui`` or ``acid2reaper-gui`` (ACID2Reaper).
"""

from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import __app_name__, __version_label__
from ..cli import convert
from ..exceptions import Acid2ReaperError


def _base_font() -> tuple[str, int]:
    """Prefer a readable default size on HiDPI displays."""
    try:
        default = tkfont.nametofont("TkDefaultFont")
        return (default.actual()["family"], max(11, int(default.actual()["size"])))
    except Exception:
        return ("TkDefaultFont", 11)


def run_app() -> int:
    """
    Show the main window and block until the user closes it.

    Returns a process exit code (0 = success, 1 = error shown to user).
    """
    root = tk.Tk()
    root.title(f"{__app_name__} — {__version_label__}")
    root.minsize(520, 320)
    root.geometry("640x400")

    family, size = _base_font()
    style = ttk.Style()
    try:
        style.theme_use(style.theme_use())
    except Exception:
        pass
    style.configure("TButton", padding=8, font=(family, size))
    style.configure("TLabel", font=(family, size))
    style.configure("Header.TLabel", font=(family, size + 2, "bold"))
    style.configure("Status.TLabel", font=(family, size - 1))

    main = ttk.Frame(root, padding=20)
    main.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    main.columnconfigure(1, weight=1)

    ttk.Label(main, text=__app_name__, style="Header.TLabel").grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 16)
    )
    ttk.Label(
        main,
        text=(
            f"First public beta — {__version_label__}. "
            "Convert Sonic Foundry / Sony / MAGIX ACID projects to Cockos REAPER (.rpp)."
        ),
        wraplength=560,
    ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 20))

    in_path: tk.StringVar = tk.StringVar()
    out_path: tk.StringVar = tk.StringVar()

    def browse_in() -> None:
        p = filedialog.askopenfilename(
            title="Open ACID project",
            filetypes=[
                ("ACID project", "*.acd *.acd-zip *.acd-bak"),
                ("All files", "*.*"),
            ],
        )
        if p:
            in_path.set(p)
            if not out_path.get():
                out_path.set(str(Path(p).with_suffix(".rpp")))

    def browse_out() -> None:
        p = filedialog.asksaveasfilename(
            title="Save REAPER project",
            defaultextension=".rpp",
            filetypes=[("REAPER project", "*.rpp"), ("All files", "*.*")],
        )
        if p:
            out_path.set(p)

    ttk.Label(main, text="ACID project").grid(row=2, column=0, sticky="w")
    ttk.Entry(main, textvariable=in_path, width=50).grid(row=2, column=1, sticky="ew", padx=8)
    ttk.Button(main, text="Browse…", command=browse_in).grid(row=2, column=2, sticky="e")

    ttk.Label(main, text="Output .rpp").grid(row=3, column=0, sticky="w", pady=(12, 0))
    ttk.Entry(main, textvariable=out_path, width=50).grid(row=3, column=1, sticky="ew", padx=8, pady=(12, 0))
    ttk.Button(main, text="Browse…", command=browse_out).grid(row=3, column=2, sticky="e", pady=(12, 0))

    status = ttk.Label(main, text="Ready.", style="Status.TLabel", foreground="#333")
    status.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(24, 8))

    log = tk.Text(main, height=8, wrap="word", font=(family, size - 1), relief="flat", background="#f8f8f8")
    log.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=(0, 12))
    log.insert("1.0", "Tips: choose your .acd or .acd-zip, then Convert. Output defaults next to the source file.\n")
    log.configure(state="disabled")
    main.rowconfigure(5, weight=1)

    exit_code = 0

    def append_log(msg: str) -> None:
        log.configure(state="normal")
        log.insert("end", msg + "\n")
        log.see("end")
        log.configure(state="disabled")

    def do_convert() -> None:
        nonlocal exit_code
        src = in_path.get().strip()
        dst = out_path.get().strip()
        if not src:
            messagebox.showwarning("Missing file", "Please choose an ACID project file.")
            return
        status.configure(text="Converting…", foreground="#0a5")
        root.update_idletasks()
        try:
            out = convert(Path(src), Path(dst) if dst else None, extra_media_dirs=None)
            status.configure(text="Done.", foreground="#060")
            append_log(f"Saved: {out}")
            exit_code = 0
        except Acid2ReaperError as exc:
            status.configure(text="Could not convert.", foreground="#a30")
            append_log(str(exc))
            messagebox.showerror("Conversion failed", str(exc))
            exit_code = 1
        except Exception as exc:
            status.configure(text="Unexpected error.", foreground="#a30")
            append_log(str(exc))
            messagebox.showerror("Error", str(exc))
            exit_code = 1

    btn_frame = ttk.Frame(main)
    btn_frame.grid(row=6, column=0, columnspan=3, sticky="e")
    convert_btn = ttk.Button(btn_frame, text="Convert", command=do_convert)
    convert_btn.pack(side="right", padx=(8, 0))
    ttk.Button(btn_frame, text="Quit", command=root.destroy).pack(side="right")

    root.bind("<Return>", lambda e: do_convert())
    root.bind("<Escape>", lambda e: root.destroy())
    convert_btn.focus_set()

    root.mainloop()
    return exit_code


def main() -> None:
    """Entry point for ``python -m acid2reaper.ui.desktop``."""
    sys.exit(run_app())
