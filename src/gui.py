"""
Image Converter Pro - Tkinter GUI
"""
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from pathlib import Path
from typing import List, Optional

import converter as conv

# ── Theme colours ──────────────────────────────────────────────────────────────
BG       = "#1e1e2e"
SURFACE  = "#2a2a3e"
ACCENT   = "#7c6af7"
ACCENT2  = "#a78bfa"
TEXT     = "#e2e8f0"
SUBTEXT  = "#94a3b8"
SUCCESS  = "#34d399"
WARNING  = "#fbbf24"
ERROR    = "#f87171"
BORDER   = "#3f3f5a"


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas)
        self.inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")


class TooltipLabel(tk.Label):
    def __init__(self, parent, text, tooltip="", **kwargs):
        super().__init__(parent, text=text, **kwargs)
        self._tip = tooltip
        self.bind("<Enter>", self._show)
        self.bind("<Leave>", self._hide)
        self._tw = None

    def _show(self, _):
        if not self._tip:
            return
        x, y, _, _ = self.bbox("insert")
        x += self.winfo_rootx() + 25
        y += self.winfo_rooty() + 25
        self._tw = tw = tk.Toplevel(self)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self._tip, bg="#333", fg="white",
                 relief="solid", borderwidth=1, padx=6, pady=4,
                 font=("Segoe UI", 9)).pack()

    def _hide(self, _):
        if self._tw:
            self._tw.destroy()
            self._tw = None


class ImageConverterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Image Converter Pro")
        self.root.geometry("920x700")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        self._apply_styles()

        self.files: List[str] = []
        self.output_dir: Optional[str] = None
        self.bg_color = (255, 255, 255)
        self.cancel_flag = False

        self._build_ui()

    # ── Styles ──────────────────────────────────────────────────────────────
    def _apply_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("TLabelframe", background=SURFACE, foreground=TEXT, bordercolor=BORDER)
        style.configure("TLabelframe.Label", background=SURFACE, foreground=ACCENT2, font=("Segoe UI", 10, "bold"))
        style.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT, bordercolor=BORDER)
        style.configure("TCombobox", fieldbackground=SURFACE, foreground=TEXT, selectbackground=ACCENT)
        style.map("TCombobox", fieldbackground=[("readonly", SURFACE)])
        style.configure("TCheckbutton", background=SURFACE, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", SURFACE)])
        style.configure("Accent.TButton", background=ACCENT, foreground="white", font=("Segoe UI", 10, "bold"), padding=8)
        style.map("Accent.TButton", background=[("active", ACCENT2)])
        style.configure("TButton", background=SURFACE, foreground=TEXT, padding=6)
        style.map("TButton", background=[("active", BORDER)])
        style.configure("TProgressbar", troughcolor=SURFACE, background=ACCENT, thickness=8)
        style.configure("TNotebook", background=BG, tabmargins=[2, 5, 2, 0])
        style.configure("TNotebook.Tab", background=SURFACE, foreground=SUBTEXT, padding=[14, 6])
        style.map("TNotebook.Tab", background=[("selected", BG)], foreground=[("selected", ACCENT2)])

    # ── UI Build ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=SURFACE, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🖼  Image Converter Pro", bg=SURFACE, fg=ACCENT2,
                 font=("Segoe UI", 16, "bold")).pack()
        tk.Label(hdr, text="Convert · Resize · Animate · Export",
                 bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9)).pack()

        # Notebook
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=12, pady=8)

        self._tab_single = ttk.Frame(nb)
        self._tab_batch  = ttk.Frame(nb)
        self._tab_anim   = ttk.Frame(nb)

        nb.add(self._tab_single, text=" Single / Multi ")
        nb.add(self._tab_batch,  text=" Sequence → Frames ")
        nb.add(self._tab_anim,   text=" Frames → Animation ")

        self._build_single_tab(self._tab_single)
        self._build_batch_tab(self._tab_batch)
        self._build_anim_tab(self._tab_anim)

        # Status bar
        bar = tk.Frame(self.root, bg=SURFACE, pady=6)
        bar.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(bar, textvariable=self.status_var, bg=SURFACE, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side="left", padx=12)
        self.progress = ttk.Progressbar(bar, length=200, mode="determinate")
        self.progress.pack(side="right", padx=12)

    # ── Shared widgets helpers ───────────────────────────────────────────────
    def _fmt_row(self, parent, label_text: str, var: tk.StringVar,
                 values: List[str], row: int):
        tk.Label(parent, text=label_text, bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 10)).grid(row=row, column=0, sticky="w", padx=10, pady=4)
        cb = ttk.Combobox(parent, textvariable=var, values=values,
                          state="readonly", width=14)
        cb.grid(row=row, column=1, sticky="w", padx=10, pady=4)
        return cb

    def _size_row(self, parent, w_var, h_var, ratio_var, row_start: int):
        tk.Label(parent, text="Width (px)", bg=SURFACE, fg=TEXT).grid(
            row=row_start, column=0, sticky="w", padx=10, pady=4)
        ttk.Entry(parent, textvariable=w_var, width=8).grid(
            row=row_start, column=1, sticky="w", padx=10)
        tk.Label(parent, text="Height (px)", bg=SURFACE, fg=TEXT).grid(
            row=row_start + 1, column=0, sticky="w", padx=10, pady=4)
        ttk.Entry(parent, textvariable=h_var, width=8).grid(
            row=row_start + 1, column=1, sticky="w", padx=10)
        ttk.Checkbutton(parent, text="Keep aspect ratio", variable=ratio_var).grid(
            row=row_start + 2, column=0, columnspan=2, sticky="w", padx=10)

    def _quality_row(self, parent, q_var, row: int):
        tk.Label(parent, text="Quality (JPEG/WEBP)", bg=SURFACE, fg=TEXT).grid(
            row=row, column=0, sticky="w", padx=10, pady=4)
        fr = tk.Frame(parent, bg=SURFACE)
        fr.grid(row=row, column=1, sticky="w", padx=10)
        tk.Scale(fr, from_=1, to=100, orient="horizontal", variable=q_var,
                 bg=SURFACE, fg=TEXT, highlightthickness=0, length=150).pack(side="left")
        tk.Label(fr, textvariable=q_var, bg=SURFACE, fg=ACCENT2, width=3).pack(side="left")

    def _bg_row(self, parent, row: int, btn_attr: str):
        tk.Label(parent, text="BG colour (α→RGB)", bg=SURFACE, fg=TEXT).grid(
            row=row, column=0, sticky="w", padx=10, pady=4)
        btn = tk.Button(parent, text="  #FFFFFF  ", bg="#ffffff", fg="#000000",
                        relief="flat", cursor="hand2",
                        command=lambda a=btn_attr: self._pick_color(a))
        btn.grid(row=row, column=1, sticky="w", padx=10)
        setattr(self, btn_attr, btn)

    def _pick_color(self, btn_attr: str):
        color = colorchooser.askcolor(color="#ffffff", title="Background colour")
        if color and color[0]:
            rgb = tuple(int(v) for v in color[0])
            hex_ = color[1]
            self.bg_color = rgb
            btn = getattr(self, btn_attr)
            btn.configure(bg=hex_, text=f"  {hex_}  ")

    def _out_dir_row(self, parent, out_var: tk.StringVar, row: int):
        tk.Label(parent, text="Output folder", bg=SURFACE, fg=TEXT).grid(
            row=row, column=0, sticky="w", padx=10, pady=4)
        fr = tk.Frame(parent, bg=SURFACE)
        fr.grid(row=row, column=1, columnspan=2, sticky="ew", padx=10)
        ttk.Entry(fr, textvariable=out_var, width=38).pack(side="left")
        ttk.Button(fr, text="Browse…", command=lambda: self._browse_dir(out_var)).pack(side="left", padx=4)

    def _browse_dir(self, var: tk.StringVar):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            var.set(d)

    # ── Single / Multi tab ──────────────────────────────────────────────────
    def _build_single_tab(self, parent):
        parent.configure(style="TFrame")

        # File list frame
        list_fr = ttk.LabelFrame(parent, text=" Input Files ", padding=8)
        list_fr.pack(fill="both", expand=True, padx=12, pady=(10, 4))

        btn_fr = tk.Frame(list_fr, bg=SURFACE)
        btn_fr.pack(fill="x")
        ttk.Button(btn_fr, text="➕ Add Files",
                   command=self._add_files_single).pack(side="left", padx=4)
        ttk.Button(btn_fr, text="📁 Add Folder",
                   command=self._add_folder_single).pack(side="left", padx=4)
        ttk.Button(btn_fr, text="🗑 Clear",
                   command=self._clear_files_single).pack(side="left", padx=4)
        self._single_info_lbl = tk.Label(btn_fr, text="No files selected",
                                         bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9))
        self._single_info_lbl.pack(side="right", padx=8)

        lb_wrap = tk.Frame(list_fr, bg=BG)
        lb_wrap.pack(fill="both", expand=True, pady=4)
        sb = ttk.Scrollbar(lb_wrap, orient="vertical")
        self._single_lb = tk.Listbox(lb_wrap, bg=BG, fg=TEXT, selectbackground=ACCENT,
                                      yscrollcommand=sb.set, borderwidth=0, highlightthickness=0,
                                      font=("Segoe UI", 9))
        sb.config(command=self._single_lb.yview)
        sb.pack(side="right", fill="y")
        self._single_lb.pack(fill="both", expand=True)
        self._single_lb.bind("<Double-Button-1>", lambda _: self._remove_selected_single())

        # Options
        opts_fr = ttk.LabelFrame(parent, text=" Conversion Options ", padding=8)
        opts_fr.pack(fill="x", padx=12, pady=4)
        opts_fr.columnconfigure(2, weight=1)

        all_fmts = list(conv.OUTPUT_FORMATS.keys())
        self._s_fmt = tk.StringVar(value="PNG")
        self._fmt_row(opts_fr, "Output Format", self._s_fmt, all_fmts, 0)

        self._s_w = tk.StringVar()
        self._s_h = tk.StringVar()
        self._s_ratio = tk.BooleanVar(value=True)
        self._size_row(opts_fr, self._s_w, self._s_h, self._s_ratio, 1)

        self._s_quality = tk.IntVar(value=90)
        self._quality_row(opts_fr, self._s_quality, 4)

        self._bg_row(opts_fr, 5, "_s_bg_btn")

        self._s_out = tk.StringVar()
        self._out_dir_row(opts_fr, self._s_out, 6)

        # Animated source options
        anim_fr = ttk.LabelFrame(parent, text=" Animated Source Options ", padding=8)
        anim_fr.pack(fill="x", padx=12, pady=4)

        self._s_anim_mode = tk.StringVar(value="first_frame")
        modes = [("Extract first frame only", "first_frame"),
                 ("Extract all frames (sequence)", "all_frames"),
                 ("Convert animation → animation", "animation")]
        for i, (lbl, val) in enumerate(modes):
            ttk.Radiobutton(anim_fr, text=lbl, variable=self._s_anim_mode,
                            value=val).grid(row=0, column=i, padx=12, pady=2)

        # Convert button
        ttk.Button(parent, text="🚀  Convert", style="Accent.TButton",
                   command=self._run_single).pack(pady=8)

    def _add_files_single(self):
        exts = " ".join(f"*{e}" for e in conv.INPUT_FORMATS)
        paths = filedialog.askopenfilenames(
            title="Select images",
            filetypes=[("Image files", exts), ("All files", "*.*")]
        )
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self._single_lb.insert("end", Path(p).name)
        self._single_info_lbl.config(text=f"{len(self.files)} file(s)")

    def _add_folder_single(self):
        d = filedialog.askdirectory(title="Select folder")
        if not d:
            return
        for f in Path(d).iterdir():
            if f.suffix.lower() in conv.INPUT_FORMATS and str(f) not in self.files:
                self.files.append(str(f))
                self._single_lb.insert("end", f.name)
        self._single_info_lbl.config(text=f"{len(self.files)} file(s)")

    def _clear_files_single(self):
        self.files.clear()
        self._single_lb.delete(0, "end")
        self._single_info_lbl.config(text="No files selected")

    def _remove_selected_single(self):
        idx = self._single_lb.curselection()
        if idx:
            self._single_lb.delete(idx[0])
            del self.files[idx[0]]
            self._single_info_lbl.config(text=f"{len(self.files)} file(s)")

    def _run_single(self):
        if not self.files:
            messagebox.showwarning("No files", "Please add at least one image file.")
            return
        out_dir = self._s_out.get().strip() or str(Path(self.files[0]).parent / "converted")
        fmt = self._s_fmt.get()
        w = int(self._s_w.get()) if self._s_w.get().strip().isdigit() else None
        h = int(self._s_h.get()) if self._s_h.get().strip().isdigit() else None
        keep_ratio = self._s_ratio.get()
        quality = self._s_quality.get()
        mode = self._s_anim_mode.get()

        os.makedirs(out_dir, exist_ok=True)
        self.cancel_flag = False
        self.progress["maximum"] = len(self.files)
        self.progress["value"] = 0

        def worker():
            errors = []
            for i, src in enumerate(self.files):
                if self.cancel_flag:
                    break
                try:
                    info = conv.get_image_info(src)
                    stem = Path(src).stem
                    ext = conv.OUTPUT_FORMATS.get(fmt, f".{fmt.lower()}")

                    if info["animated"] and mode == "all_frames":
                        frame_dir = os.path.join(out_dir, stem + "_frames")
                        conv.animation_to_frames(src, frame_dir, fmt, w, h, keep_ratio, quality, self.bg_color)
                    elif info["animated"] and mode == "animation" and fmt in conv.ANIM_OUTPUT_FORMATS:
                        dst = os.path.join(out_dir, stem + ext)
                        conv.convert_animated(src, dst, fmt, w, h, keep_ratio, quality, self.bg_color)
                    else:
                        dst = os.path.join(out_dir, stem + ext)
                        conv.convert_single(src, dst, fmt, w, h, keep_ratio, quality, self.bg_color)
                except Exception as e:
                    errors.append(f"{Path(src).name}: {e}")

                self.root.after(0, lambda v=i + 1: self._set_progress(v, len(self.files)))

            self.root.after(0, lambda: self._done("Conversion complete!", errors, out_dir))

        threading.Thread(target=worker, daemon=True).start()

    # ── Sequence → Frames tab ───────────────────────────────────────────────
    def _build_batch_tab(self, parent):
        top = ttk.LabelFrame(parent, text=" Animated Source File(s) ", padding=8)
        top.pack(fill="x", padx=12, pady=(10, 4))

        self._b_files: List[str] = []
        fr = tk.Frame(top, bg=SURFACE)
        fr.pack(fill="x")
        ttk.Button(fr, text="➕ Add animated files",
                   command=self._add_batch_files).pack(side="left", padx=4)
        ttk.Button(fr, text="🗑 Clear",
                   command=self._clear_batch).pack(side="left", padx=4)
        self._b_info = tk.Label(fr, text="No files", bg=SURFACE, fg=SUBTEXT)
        self._b_info.pack(side="right", padx=8)

        lb_wrap = tk.Frame(top, bg=BG)
        lb_wrap.pack(fill="x", pady=4)
        self._b_lb = tk.Listbox(lb_wrap, bg=BG, fg=TEXT, height=5,
                                 selectbackground=ACCENT, borderwidth=0, highlightthickness=0)
        self._b_lb.pack(fill="x")

        opts = ttk.LabelFrame(parent, text=" Options ", padding=8)
        opts.pack(fill="x", padx=12, pady=4)

        all_fmts = [k for k in conv.OUTPUT_FORMATS if k not in ("GIF", "WEBP", "APNG")]
        all_fmts = list(conv.OUTPUT_FORMATS.keys())
        self._b_fmt = tk.StringVar(value="PNG")
        self._fmt_row(opts, "Frame Format", self._b_fmt, all_fmts, 0)

        self._b_w = tk.StringVar()
        self._b_h = tk.StringVar()
        self._b_ratio = tk.BooleanVar(value=True)
        self._size_row(opts, self._b_w, self._b_h, self._b_ratio, 1)

        self._b_quality = tk.IntVar(value=90)
        self._quality_row(opts, self._b_quality, 4)

        self._bg_row(opts, 5, "_b_bg_btn")

        self._b_out = tk.StringVar()
        self._out_dir_row(opts, self._b_out, 6)

        ttk.Button(parent, text="🎞  Extract Frames", style="Accent.TButton",
                   command=self._run_batch).pack(pady=8)

    def _add_batch_files(self):
        exts = " ".join(f"*{e}" for e in conv.INPUT_FORMATS)
        paths = filedialog.askopenfilenames(
            title="Select animated images",
            filetypes=[("Image files", exts), ("All files", "*.*")]
        )
        for p in paths:
            if p not in self._b_files:
                self._b_files.append(p)
                self._b_lb.insert("end", Path(p).name)
        self._b_info.config(text=f"{len(self._b_files)} file(s)")

    def _clear_batch(self):
        self._b_files.clear()
        self._b_lb.delete(0, "end")
        self._b_info.config(text="No files")

    def _run_batch(self):
        if not self._b_files:
            messagebox.showwarning("No files", "Please add source animated images.")
            return
        out_base = self._b_out.get().strip() or str(Path(self._b_files[0]).parent / "frames")
        fmt = self._b_fmt.get()
        w = int(self._b_w.get()) if self._b_w.get().strip().isdigit() else None
        h = int(self._b_h.get()) if self._b_h.get().strip().isdigit() else None
        total = len(self._b_files)
        self.progress["maximum"] = total
        self.progress["value"] = 0

        def worker():
            errors = []
            for i, src in enumerate(self._b_files):
                try:
                    out_dir = os.path.join(out_base, Path(src).stem + "_frames")
                    conv.animation_to_frames(src, out_dir, fmt, w, h, self._b_ratio.get(),
                                             self._b_quality.get(), self.bg_color)
                except Exception as e:
                    errors.append(f"{Path(src).name}: {e}")
                self.root.after(0, lambda v=i + 1: self._set_progress(v, total))
            self.root.after(0, lambda: self._done("Frame extraction complete!", errors, out_base))

        threading.Thread(target=worker, daemon=True).start()

    # ── Frames → Animation tab ──────────────────────────────────────────────
    def _build_anim_tab(self, parent):
        top = ttk.LabelFrame(parent, text=" Frame Images (order matters) ", padding=8)
        top.pack(fill="both", expand=True, padx=12, pady=(10, 4))

        self._a_files: List[str] = []
        fr = tk.Frame(top, bg=SURFACE)
        fr.pack(fill="x")
        ttk.Button(fr, text="➕ Add frames",
                   command=self._add_anim_frames).pack(side="left", padx=4)
        ttk.Button(fr, text="↑ Up", command=self._move_up).pack(side="left", padx=2)
        ttk.Button(fr, text="↓ Down", command=self._move_down).pack(side="left", padx=2)
        ttk.Button(fr, text="🗑 Remove", command=self._remove_anim_frame).pack(side="left", padx=2)
        ttk.Button(fr, text="🗑 Clear all", command=self._clear_anim).pack(side="left", padx=2)
        self._a_info = tk.Label(fr, text="No frames", bg=SURFACE, fg=SUBTEXT)
        self._a_info.pack(side="right", padx=8)

        lb_wrap = tk.Frame(top, bg=BG)
        lb_wrap.pack(fill="both", expand=True, pady=4)
        sb2 = ttk.Scrollbar(lb_wrap, orient="vertical")
        self._a_lb = tk.Listbox(lb_wrap, bg=BG, fg=TEXT, selectbackground=ACCENT,
                                 yscrollcommand=sb2.set, borderwidth=0, highlightthickness=0)
        sb2.config(command=self._a_lb.yview)
        sb2.pack(side="right", fill="y")
        self._a_lb.pack(fill="both", expand=True)

        opts = ttk.LabelFrame(parent, text=" Options ", padding=8)
        opts.pack(fill="x", padx=12, pady=4)

        self._a_fmt = tk.StringVar(value="GIF")
        self._fmt_row(opts, "Output Format", self._a_fmt,
                      list(conv.ANIM_OUTPUT_FORMATS), 0)

        self._a_w = tk.StringVar()
        self._a_h = tk.StringVar()
        self._a_ratio = tk.BooleanVar(value=True)
        self._size_row(opts, self._a_w, self._a_h, self._a_ratio, 1)

        self._a_quality = tk.IntVar(value=90)
        self._quality_row(opts, self._a_quality, 4)

        tk.Label(opts, text="Duration/frame (ms)", bg=SURFACE, fg=TEXT).grid(
            row=5, column=0, sticky="w", padx=10, pady=4)
        self._a_duration = tk.StringVar(value="100")
        ttk.Entry(opts, textvariable=self._a_duration, width=8).grid(
            row=5, column=1, sticky="w", padx=10)

        tk.Label(opts, text="Loop count (0=∞)", bg=SURFACE, fg=TEXT).grid(
            row=6, column=0, sticky="w", padx=10, pady=4)
        self._a_loop = tk.StringVar(value="0")
        ttk.Entry(opts, textvariable=self._a_loop, width=8).grid(
            row=6, column=1, sticky="w", padx=10)

        self._bg_row(opts, 7, "_a_bg_btn")

        self._a_out = tk.StringVar()
        tk.Label(opts, text="Output file", bg=SURFACE, fg=TEXT).grid(
            row=8, column=0, sticky="w", padx=10, pady=4)
        ef = tk.Frame(opts, bg=SURFACE)
        ef.grid(row=8, column=1, columnspan=2, sticky="ew", padx=10)
        ttk.Entry(ef, textvariable=self._a_out, width=38).pack(side="left")
        ttk.Button(ef, text="Browse…",
                   command=self._browse_anim_out).pack(side="left", padx=4)

        ttk.Button(parent, text="🎬  Build Animation", style="Accent.TButton",
                   command=self._run_anim).pack(pady=8)

    def _add_anim_frames(self):
        exts = " ".join(f"*{e}" for e in conv.INPUT_FORMATS)
        paths = filedialog.askopenfilenames(
            title="Select frame images",
            filetypes=[("Image files", exts), ("All files", "*.*")]
        )
        for p in paths:
            self._a_files.append(p)
            self._a_lb.insert("end", Path(p).name)
        self._a_info.config(text=f"{len(self._a_files)} frame(s)")

    def _move_up(self):
        sel = self._a_lb.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        self._a_files[i - 1], self._a_files[i] = self._a_files[i], self._a_files[i - 1]
        name = self._a_lb.get(i)
        self._a_lb.delete(i)
        self._a_lb.insert(i - 1, name)
        self._a_lb.selection_set(i - 1)

    def _move_down(self):
        sel = self._a_lb.curselection()
        if not sel or sel[0] >= len(self._a_files) - 1:
            return
        i = sel[0]
        self._a_files[i], self._a_files[i + 1] = self._a_files[i + 1], self._a_files[i]
        name = self._a_lb.get(i)
        self._a_lb.delete(i)
        self._a_lb.insert(i + 1, name)
        self._a_lb.selection_set(i + 1)

    def _remove_anim_frame(self):
        sel = self._a_lb.curselection()
        if sel:
            self._a_lb.delete(sel[0])
            del self._a_files[sel[0]]
            self._a_info.config(text=f"{len(self._a_files)} frame(s)")

    def _clear_anim(self):
        self._a_files.clear()
        self._a_lb.delete(0, "end")
        self._a_info.config(text="No frames")

    def _browse_anim_out(self):
        fmt = self._a_fmt.get()
        ext = conv.OUTPUT_FORMATS.get(fmt, ".gif")
        path = filedialog.asksaveasfilename(
            title="Save animation as",
            defaultextension=ext,
            filetypes=[(f"{fmt} files", f"*{ext}"), ("All files", "*.*")]
        )
        if path:
            self._a_out.set(path)

    def _run_anim(self):
        if len(self._a_files) < 2:
            messagebox.showwarning("Too few frames", "Add at least 2 frame images.")
            return
        out = self._a_out.get().strip()
        if not out:
            messagebox.showwarning("No output path", "Please specify an output file path.")
            return
        fmt = self._a_fmt.get()
        w = int(self._a_w.get()) if self._a_w.get().strip().isdigit() else None
        h = int(self._a_h.get()) if self._a_h.get().strip().isdigit() else None
        dur = int(self._a_duration.get()) if self._a_duration.get().strip().isdigit() else 100
        loop = int(self._a_loop.get()) if self._a_loop.get().strip().isdigit() else 0
        total = len(self._a_files)
        self.progress["maximum"] = total
        self.progress["value"] = 0

        def worker():
            try:
                conv.frames_to_animation(
                    self._a_files, out, fmt, w, h, self._a_ratio.get(),
                    self._a_quality.get(), dur, self.bg_color, loop,
                    progress_cb=lambda cur, tot: self.root.after(
                        0, lambda: self._set_progress(cur, tot))
                )
                self.root.after(0, lambda: self._done("Animation built!", [], str(Path(out).parent)))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    # ── Shared helpers ────────────────────────────────────────────────────────
    def _set_progress(self, value: int, maximum: int):
        self.progress["maximum"] = maximum
        self.progress["value"] = value
        self.status_var.set(f"Processing {value}/{maximum}…")

    def _done(self, msg: str, errors: List[str], open_dir: str):
        self.progress["value"] = self.progress["maximum"]
        self.status_var.set("Done ✓")
        if errors:
            detail = "\n".join(errors[:10])
            if len(errors) > 10:
                detail += f"\n…and {len(errors) - 10} more"
            messagebox.showwarning(msg, f"Completed with errors:\n\n{detail}")
        else:
            if messagebox.askyesno(msg, f"{msg}\n\nOpen output folder?"):
                import subprocess, platform
                if platform.system() == "Windows":
                    os.startfile(open_dir)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", open_dir])
                else:
                    subprocess.Popen(["xdg-open", open_dir])
