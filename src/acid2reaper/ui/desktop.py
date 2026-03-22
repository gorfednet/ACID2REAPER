"""
Cross-platform desktop UI built on Tkinter + ttk (standard library).

Design goals:
- **Accessible**: comfortable padding, ttk/system theme, keyboard access to primary
  actions, native file dialogs (assistive tech uses the OS dialog APIs). Status text
  carries meaning (not color alone).
- **Scalable**: single window; grid weights let resizing give space to the log.
- **Calm layout**: LabelFrames group related controls; hierarchy stays obvious.

This module is only imported for ``--gui`` or ``acid2reaper-gui`` (ACID2Reaper).
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


def _readable_base_font() -> tuple[str, int]:
    """Slightly bump default text size on HiDPI displays so body copy stays legible."""
    try:
        default = tkfont.nametofont("TkDefaultFont")
        return (default.actual()["family"], max(11, int(default.actual()["size"])))
    except Exception:
        return ("TkDefaultFont", 11)


def run_app() -> int:
    """
    Show the main window and block until the user closes it.

    Returns a process exit code (0 = success, 1 = error surfaced to the user).
    """
    main_window = tk.Tk()
    main_window.title(f"{__app_name__} — {__version_label__}")
    main_window.minsize(520, 360)
    main_window.geometry("640x420")

    font_family, font_size = _readable_base_font()
    style = ttk.Style(main_window)
    try:
        style.theme_use(style.theme_use())
    except Exception:
        pass
    style.configure("TButton", padding=8, font=(font_family, font_size))
    style.configure("TLabel", font=(font_family, font_size))
    style.configure("Header.TLabel", font=(font_family, font_size + 2, "bold"))
    style.configure("Status.TLabel", font=(font_family, font_size - 1))
    default_label_fg = style.lookup("TLabel", "foreground") or ""
    style.configure("Status.TLabel", foreground=default_label_fg)

    outer = ttk.Frame(main_window, padding=20)
    outer.grid(row=0, column=0, sticky="nsew")
    main_window.columnconfigure(0, weight=1)
    main_window.rowconfigure(0, weight=1)
    outer.columnconfigure(0, weight=1)

    ttk.Label(outer, text=__app_name__, style="Header.TLabel").grid(
        row=0, column=0, sticky="w", pady=(0, 8)
    )
    ttk.Label(
        outer,
        text=(
            f"First public beta — {__version_label__}. "
            "Convert Sonic Foundry / Sony / MAGIX ACID projects to Cockos REAPER (.rpp). "
            "All processing stays on this computer (no network use)."
        ),
        wraplength=560,
    ).grid(row=1, column=0, sticky="w", pady=(0, 16))

    acid_path_var = tk.StringVar()
    output_path_var = tk.StringVar()

    def pick_acid_file() -> None:
        chosen = filedialog.askopenfilename(
            title="Open ACID project",
            filetypes=[
                ("ACID project", "*.acd *.acd-zip *.acd-bak"),
                ("All files", "*.*"),
            ],
        )
        if chosen:
            acid_path_var.set(chosen)
            if not output_path_var.get():
                output_path_var.set(str(Path(chosen).with_suffix(".rpp")))

    def pick_output_file() -> None:
        chosen = filedialog.asksaveasfilename(
            title="Save REAPER project",
            defaultextension=".rpp",
            filetypes=[("REAPER project", "*.rpp"), ("All files", "*.*")],
        )
        if chosen:
            output_path_var.set(chosen)

    files_panel = ttk.LabelFrame(outer, text="Project files", padding=(12, 10, 12, 12))
    files_panel.grid(row=2, column=0, sticky="ew", pady=(0, 12))
    files_panel.columnconfigure(1, weight=1)

    ttk.Label(files_panel, text="ACID project").grid(row=0, column=0, sticky="w")
    acid_entry = ttk.Entry(files_panel, textvariable=acid_path_var, width=50, takefocus=1)
    acid_entry.grid(row=0, column=1, sticky="ew", padx=8)
    ttk.Button(files_panel, text="Browse…", command=pick_acid_file).grid(
        row=0, column=2, sticky="e"
    )

    ttk.Label(files_panel, text="Output .rpp").grid(row=1, column=0, sticky="w", pady=(12, 0))
    output_entry = ttk.Entry(files_panel, textvariable=output_path_var, width=50, takefocus=1)
    output_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=(12, 0))
    ttk.Button(files_panel, text="Browse…", command=pick_output_file).grid(
        row=1, column=2, sticky="e", pady=(12, 0)
    )

    status_label = ttk.Label(
        outer,
        text="Status: Ready.",
        style="Status.TLabel",
    )
    status_label.grid(row=3, column=0, sticky="ew", pady=(4, 8))

    log_panel = ttk.LabelFrame(outer, text="Conversion log", padding=(8, 8, 8, 8))
    log_panel.grid(row=4, column=0, sticky="nsew", pady=(0, 12))
    log_panel.columnconfigure(0, weight=1)
    log_panel.rowconfigure(0, weight=1)
    outer.rowconfigure(4, weight=1)

    log_background = main_window.cget("background") or style.lookup("TFrame", "background") or "#ffffff"
    conversion_log = tk.Text(
        log_panel,
        height=8,
        wrap="word",
        font=(font_family, font_size - 1),
        relief="flat",
        background=log_background,
        highlightthickness=0,
    )
    conversion_log.grid(row=0, column=0, sticky="nsew")
    conversion_log.insert(
        "1.0",
        "Choose an .acd / .acd-zip / .acd-bak, set the output path if needed, then Convert.\n",
    )
    conversion_log.configure(state="disabled")

    exit_code = 0

    def append_conversion_log(message: str) -> None:
        conversion_log.configure(state="normal")
        conversion_log.insert("end", message + "\n")
        conversion_log.see("end")
        conversion_log.configure(state="disabled")

    def run_conversion() -> None:
        nonlocal exit_code
        source = acid_path_var.get().strip()
        destination = output_path_var.get().strip()
        if not source:
            messagebox.showwarning("Missing file", "Please choose an ACID project file.")
            return
        status_label.configure(text="Status: Converting…")
        main_window.update_idletasks()
        try:
            written = convert(
                Path(source),
                Path(destination) if destination else None,
                extra_media_dirs=None,
            )
            status_label.configure(text="Status: Finished — output saved.")
            append_conversion_log(f"Saved: {written}")
            exit_code = 0
        except Acid2ReaperError as exc:
            status_label.configure(text="Status: Conversion failed (see log).")
            append_conversion_log(str(exc))
            messagebox.showerror("Conversion failed", str(exc))
            exit_code = 1
        except Exception as exc:
            status_label.configure(text="Status: Unexpected error (see log).")
            append_conversion_log(str(exc))
            messagebox.showerror("Error", str(exc))
            exit_code = 1

    button_row = ttk.Frame(outer)
    button_row.grid(row=5, column=0, sticky="e")
    convert_button = ttk.Button(button_row, text="Convert", command=run_conversion)
    convert_button.pack(side="right", padx=(8, 0))
    ttk.Button(button_row, text="Quit", command=main_window.destroy).pack(side="right")

    main_window.bind("<Return>", lambda _event: run_conversion())
    main_window.bind("<Escape>", lambda _event: main_window.destroy())
    convert_button.focus_set()

    main_window.mainloop()
    return exit_code


def main() -> None:
    """Entry point for ``python -m acid2reaper.ui.desktop``."""
    sys.exit(run_app())
