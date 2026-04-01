"""
Image Converter Pro - Tkinter GUI
변경사항:
  - Windows 기본 테마 (시스템 기본 색상, 글씨 잘 보임)
  - 창 크기에 따른 스크롤 지원 (마우스 휠 포함)
  - 동일 파일명 덮어쓰기 경고창
  - 애니메이션 FPS 설정 (ms 대신 FPS 표기, ms 실시간 변환 표시)
  - 알파채널 유지 옵션
"""
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from pathlib import Path
from typing import List, Optional

import converter as conv


# ── FPS ↔ ms ──────────────────────────────────────────────────────────────────
def fps_to_ms(fps: float) -> int:
    if fps <= 0:
        return 100
    return max(1, int(round(1000.0 / fps)))


# ── 스크롤 가능 탭 프레임 ────────────────────────────────────────────────────
class ScrollableTab(tk.Frame):
    """창이 작아져도 세로 스크롤로 모든 옵션을 볼 수 있는 컨테이너"""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self._vsb = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vsb.set)
        self._vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self._canvas)
        self._win = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(
            self._win, width=e.width))
        self._canvas.bind("<Enter>", self._bind_wheel)
        self._canvas.bind("<Leave>", self._unbind_wheel)

    def _bind_wheel(self, _):
        self._canvas.bind_all("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self._canvas.bind_all("<Button-4>",
            lambda e: self._canvas.yview_scroll(-1, "units"))
        self._canvas.bind_all("<Button-5>",
            lambda e: self._canvas.yview_scroll(1, "units"))

    def _unbind_wheel(self, _):
        self._canvas.unbind_all("<MouseWheel>")
        self._canvas.unbind_all("<Button-4>")
        self._canvas.unbind_all("<Button-5>")


# ── 메인 앱 ──────────────────────────────────────────────────────────────────
class ImageConverterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Image Converter Pro")
        self.root.geometry("860x660")
        self.root.minsize(660, 500)
        self.root.resizable(True, True)
        self._apply_styles()
        self.files: List[str] = []
        self.bg_color = (255, 255, 255)
        self.cancel_flag = False
        self._build_ui()

    # ── 스타일 ───────────────────────────────────────────────────────────────
    def _apply_styles(self):
        style = ttk.Style(self.root)
        for theme in ("vista", "winnative", "aqua", "clam", "default"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break
        style.configure(".", font=("Segoe UI", 10))
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("TProgressbar", thickness=8)

    # ── 전체 UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        hdr = ttk.Frame(self.root, padding=(0, 8, 0, 4))
        hdr.pack(fill="x")
        ttk.Label(hdr, text="Image Converter Pro",
                  font=("Segoe UI", 14, "bold")).pack()
        ttk.Label(hdr, text="Convert  Resize  Animate  Export",
                  foreground="gray").pack()
        ttk.Separator(self.root).pack(fill="x")

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=4)

        self._tab_single = ttk.Frame(nb)
        self._tab_batch  = ttk.Frame(nb)
        self._tab_anim   = ttk.Frame(nb)
        nb.add(self._tab_single, text="  변환 / 일괄변환  ")
        nb.add(self._tab_batch,  text="  애니메이션 → 프레임  ")
        nb.add(self._tab_anim,   text="  프레임 → 애니메이션  ")

        self._build_single_tab(self._tab_single)
        self._build_batch_tab(self._tab_batch)
        self._build_anim_tab(self._tab_anim)

        bar = ttk.Frame(self.root, padding=4)
        bar.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="준비")
        ttk.Label(bar, textvariable=self.status_var, foreground="gray").pack(side="left")
        self.progress = ttk.Progressbar(bar, length=220, mode="determinate")
        self.progress.pack(side="right")

    # ── 공통 헬퍼 ────────────────────────────────────────────────────────────
    def _lf(self, parent, text):
        return ttk.LabelFrame(parent, text=f" {text} ", padding=8)

    def _row(self, parent, label, row, col=0):
        ttk.Label(parent, text=label).grid(
            row=row, column=col, sticky="w", padx=8, pady=3)

    def _fmt_combo(self, parent, var, values, row):
        self._row(parent, "출력 형식", row)
        cb = ttk.Combobox(parent, textvariable=var, values=values,
                          state="readonly", width=12)
        cb.grid(row=row, column=1, sticky="w", padx=8, pady=3)
        return cb

    def _size_block(self, parent, wv, hv, rv, row):
        self._row(parent, "너비 (px)", row)
        ttk.Entry(parent, textvariable=wv, width=9).grid(
            row=row, column=1, sticky="w", padx=8, pady=3)
        self._row(parent, "높이 (px)", row+1)
        ttk.Entry(parent, textvariable=hv, width=9).grid(
            row=row+1, column=1, sticky="w", padx=8, pady=3)
        ttk.Checkbutton(parent, text="비율 유지", variable=rv).grid(
            row=row+2, column=0, columnspan=2, sticky="w", padx=8)

    def _quality_block(self, parent, qv, row):
        self._row(parent, "품질 (JPEG/WEBP)", row)
        fr = ttk.Frame(parent)
        fr.grid(row=row, column=1, sticky="w", padx=8, pady=3)
        ttk.Scale(fr, from_=1, to=100, orient="horizontal",
                  variable=qv, length=140).pack(side="left")
        ttk.Label(fr, textvariable=qv, width=3).pack(side="left", padx=4)

    def _alpha_block(self, parent, kav, bg_attr, row):
        """알파채널 유지 체크박스 + 배경색 버튼"""
        ttk.Checkbutton(
            parent,
            text="알파채널(투명도) 유지  [알파 미지원 형식은 자동으로 배경색 합성]",
            variable=kav
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=3)
        self._row(parent, "배경색 (투명→불투명 시)", row+1)
        btn = tk.Button(
            parent, text="  #FFFFFF  ", bg="#ffffff", fg="#000000",
            relief="groove", cursor="hand2",
            command=lambda a=bg_attr: self._pick_color(a)
        )
        btn.grid(row=row+1, column=1, sticky="w", padx=8, pady=3)
        setattr(self, bg_attr, btn)

    def _pick_color(self, attr):
        c = colorchooser.askcolor(color="#ffffff", title="배경색 선택")
        if c and c[0]:
            rgb = tuple(int(v) for v in c[0])
            hex_ = c[1]
            self.bg_color = rgb
            getattr(self, attr).configure(bg=hex_, text=f"  {hex_}  ")

    def _out_dir_block(self, parent, var, row):
        self._row(parent, "출력 폴더", row)
        fr = ttk.Frame(parent)
        fr.grid(row=row, column=1, columnspan=2, sticky="ew", padx=8, pady=3)
        ttk.Entry(fr, textvariable=var).pack(side="left", fill="x", expand=True)
        ttk.Button(fr, text="찾아보기…",
                   command=lambda: self._browse_dir(var)).pack(side="left", padx=4)

    def _browse_dir(self, var):
        d = filedialog.askdirectory(title="출력 폴더 선택")
        if d:
            var.set(d)

    # ── 덮어쓰기 확인 ────────────────────────────────────────────────────────
    def _confirm_overwrite(self, path: str) -> bool:
        if os.path.exists(path):
            return messagebox.askyesno(
                "파일 덮어쓰기 확인",
                f"이미 존재하는 파일입니다:\n\n{path}\n\n덮어쓰시겠습니까?",
                icon="warning")
        return True

    def _check_overwrite_list(self, paths: List[str]) -> bool:
        existing = [p for p in paths if os.path.exists(p)]
        if not existing:
            return True
        names = "\n".join(f"  • {Path(p).name}" for p in existing[:10])
        if len(existing) > 10:
            names += f"\n  … 외 {len(existing)-10}개"
        return messagebox.askyesno(
            "파일 덮어쓰기 확인",
            f"{len(existing)}개 파일이 이미 존재합니다:\n\n{names}\n\n모두 덮어쓰시겠습니까?",
            icon="warning")

    # ══════════════════════════════════════════════════════════════════════════
    # 탭 1 : 변환 / 일괄변환
    # ══════════════════════════════════════════════════════════════════════════
    def _build_single_tab(self, parent):
        tab = ScrollableTab(parent)
        tab.pack(fill="both", expand=True)
        p = tab.inner

        # 파일 목록
        lf = self._lf(p, "입력 파일")
        lf.pack(fill="both", expand=True, padx=10, pady=(8,4))

        br = ttk.Frame(lf)
        br.pack(fill="x", pady=(0,4))
        ttk.Button(br, text="➕ 파일 추가",
                   command=self._add_files_single).pack(side="left", padx=2)
        ttk.Button(br, text="📁 폴더 추가",
                   command=self._add_folder_single).pack(side="left", padx=2)
        ttk.Button(br, text="✕ 선택 제거",
                   command=self._remove_selected_single).pack(side="left", padx=2)
        ttk.Button(br, text="🗑 전체 지우기",
                   command=self._clear_files_single).pack(side="left", padx=2)
        self._s_info = ttk.Label(br, text="선택된 파일 없음", foreground="gray")
        self._s_info.pack(side="right", padx=6)

        lbf = ttk.Frame(lf)
        lbf.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(lbf, orient="vertical")
        self._single_lb = tk.Listbox(lbf, yscrollcommand=sb.set,
                                      selectmode="extended", height=6,
                                      font=("Segoe UI", 9))
        sb.config(command=self._single_lb.yview)
        sb.pack(side="right", fill="y")
        self._single_lb.pack(fill="both", expand=True)

        # 변환 옵션
        lf2 = self._lf(p, "변환 옵션")
        lf2.pack(fill="x", padx=10, pady=4)
        lf2.columnconfigure(2, weight=1)

        self._s_fmt = tk.StringVar(value="PNG")
        self._fmt_combo(lf2, self._s_fmt, list(conv.OUTPUT_FORMATS.keys()), 0)

        self._s_w = tk.StringVar(); self._s_h = tk.StringVar()
        self._s_ratio = tk.BooleanVar(value=True)
        self._size_block(lf2, self._s_w, self._s_h, self._s_ratio, 1)

        self._s_quality = tk.IntVar(value=90)
        self._quality_block(lf2, self._s_quality, 4)

        self._s_keep_alpha = tk.BooleanVar(value=True)
        self._alpha_block(lf2, self._s_keep_alpha, "_s_bg_btn", 5)

        # 출력
        lf3 = self._lf(p, "출력 설정")
        lf3.pack(fill="x", padx=10, pady=4)
        lf3.columnconfigure(2, weight=1)
        self._s_out = tk.StringVar()
        self._out_dir_block(lf3, self._s_out, 0)

        # 애니 소스 처리
        lf4 = self._lf(p, "애니메이션 소스 처리 방식")
        lf4.pack(fill="x", padx=10, pady=4)
        self._s_anim_mode = tk.StringVar(value="first_frame")
        for col, (lbl, val) in enumerate([
            ("첫 번째 프레임만 추출", "first_frame"),
            ("모든 프레임을 개별 파일로", "all_frames"),
            ("애니메이션 → 애니메이션", "animation"),
        ]):
            ttk.Radiobutton(lf4, text=lbl,
                            variable=self._s_anim_mode, value=val).grid(
                row=0, column=col, padx=10, pady=4, sticky="w")

        ttk.Button(p, text="🚀  변환 시작", style="Accent.TButton",
                   command=self._run_single).pack(pady=10)

    def _add_files_single(self):
        exts = " ".join(f"*{e}" for e in conv.INPUT_FORMATS)
        for p in filedialog.askopenfilenames(
                title="이미지 파일 선택",
                filetypes=[("이미지 파일", exts), ("모든 파일", "*.*")]):
            if p not in self.files:
                self.files.append(p)
                self._single_lb.insert("end", Path(p).name)
        self._s_info.config(text=f"{len(self.files)}개 선택됨")

    def _add_folder_single(self):
        d = filedialog.askdirectory(title="폴더 선택")
        if not d:
            return
        for f in sorted(Path(d).iterdir()):
            if f.suffix.lower() in conv.INPUT_FORMATS and str(f) not in self.files:
                self.files.append(str(f))
                self._single_lb.insert("end", f.name)
        self._s_info.config(text=f"{len(self.files)}개 선택됨")

    def _clear_files_single(self):
        self.files.clear()
        self._single_lb.delete(0, "end")
        self._s_info.config(text="선택된 파일 없음")

    def _remove_selected_single(self):
        for idx in reversed(self._single_lb.curselection()):
            self._single_lb.delete(idx)
            del self.files[idx]
        self._s_info.config(text=f"{len(self.files)}개 선택됨")

    def _run_single(self):
        if not self.files:
            messagebox.showwarning("파일 없음", "파일을 하나 이상 추가해 주세요.")
            return
        out_dir = self._s_out.get().strip() or str(
            Path(self.files[0]).parent / "converted")
        fmt        = self._s_fmt.get()
        w          = int(self._s_w.get()) if self._s_w.get().strip().isdigit() else None
        h          = int(self._s_h.get()) if self._s_h.get().strip().isdigit() else None
        keep_ratio = self._s_ratio.get()
        quality    = self._s_quality.get()
        keep_alpha = self._s_keep_alpha.get()
        mode       = self._s_anim_mode.get()
        ext        = conv.OUTPUT_FORMATS.get(fmt, f".{fmt.lower()}")
        os.makedirs(out_dir, exist_ok=True)

        # 덮어쓰기 검사 (animation→frames 제외하고 단일 파일만)
        single_dsts = []
        for src in self.files:
            if not (mode == "all_frames"):
                single_dsts.append(os.path.join(out_dir, Path(src).stem + ext))
        if not self._check_overwrite_list(single_dsts):
            return

        self.cancel_flag = False
        self.progress["maximum"] = len(self.files)
        self.progress["value"]   = 0

        def worker():
            errors = []
            for i, src in enumerate(self.files):
                if self.cancel_flag:
                    break
                try:
                    info = conv.get_image_info(src)
                    stem = Path(src).stem
                    if info["animated"] and mode == "all_frames":
                        conv.animation_to_frames(
                            src, os.path.join(out_dir, stem+"_frames"),
                            fmt, w, h, keep_ratio, quality, self.bg_color,
                            keep_alpha=keep_alpha)
                    elif info["animated"] and mode == "animation" \
                            and fmt in conv.ANIM_OUTPUT_FORMATS:
                        conv.convert_animated(
                            src, os.path.join(out_dir, stem+ext),
                            fmt, w, h, keep_ratio, quality, self.bg_color,
                            keep_alpha=keep_alpha)
                    else:
                        conv.convert_single(
                            src, os.path.join(out_dir, stem+ext),
                            fmt, w, h, keep_ratio, quality, self.bg_color,
                            keep_alpha=keep_alpha)
                except Exception as e:
                    errors.append(f"{Path(src).name}: {e}")
                self.root.after(0, lambda v=i+1: self._set_progress(v, len(self.files)))
            self.root.after(0, lambda: self._done("변환 완료!", errors, out_dir))

        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # 탭 2 : 애니메이션 → 프레임
    # ══════════════════════════════════════════════════════════════════════════
    def _build_batch_tab(self, parent):
        tab = ScrollableTab(parent)
        tab.pack(fill="both", expand=True)
        p = tab.inner

        lf = self._lf(p, "애니메이션 파일")
        lf.pack(fill="both", expand=True, padx=10, pady=(8,4))

        self._b_files: List[str] = []
        br = ttk.Frame(lf)
        br.pack(fill="x", pady=(0,4))
        ttk.Button(br, text="➕ 파일 추가",
                   command=self._add_batch_files).pack(side="left", padx=2)
        ttk.Button(br, text="🗑 전체 지우기",
                   command=self._clear_batch).pack(side="left", padx=2)
        self._b_info = ttk.Label(br, text="선택된 파일 없음", foreground="gray")
        self._b_info.pack(side="right", padx=6)

        lbf = ttk.Frame(lf)
        lbf.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(lbf, orient="vertical")
        self._b_lb = tk.Listbox(lbf, yscrollcommand=sb.set, height=5,
                                 font=("Segoe UI", 9))
        sb.config(command=self._b_lb.yview)
        sb.pack(side="right", fill="y")
        self._b_lb.pack(fill="both", expand=True)

        lf2 = self._lf(p, "옵션")
        lf2.pack(fill="x", padx=10, pady=4)
        lf2.columnconfigure(2, weight=1)

        self._b_fmt = tk.StringVar(value="PNG")
        self._fmt_combo(lf2, self._b_fmt, list(conv.OUTPUT_FORMATS.keys()), 0)

        self._b_w = tk.StringVar(); self._b_h = tk.StringVar()
        self._b_ratio = tk.BooleanVar(value=True)
        self._size_block(lf2, self._b_w, self._b_h, self._b_ratio, 1)

        self._b_quality = tk.IntVar(value=90)
        self._quality_block(lf2, self._b_quality, 4)

        self._b_keep_alpha = tk.BooleanVar(value=True)
        self._alpha_block(lf2, self._b_keep_alpha, "_b_bg_btn", 5)

        lf3 = self._lf(p, "출력 폴더")
        lf3.pack(fill="x", padx=10, pady=4)
        lf3.columnconfigure(2, weight=1)
        self._b_out = tk.StringVar()
        self._out_dir_block(lf3, self._b_out, 0)

        ttk.Button(p, text="🎞  프레임 추출 시작", style="Accent.TButton",
                   command=self._run_batch).pack(pady=10)

    def _add_batch_files(self):
        exts = " ".join(f"*{e}" for e in conv.INPUT_FORMATS)
        for p in filedialog.askopenfilenames(
                title="애니메이션 파일 선택",
                filetypes=[("이미지 파일", exts), ("모든 파일", "*.*")]):
            if p not in self._b_files:
                self._b_files.append(p)
                self._b_lb.insert("end", Path(p).name)
        self._b_info.config(text=f"{len(self._b_files)}개 파일")

    def _clear_batch(self):
        self._b_files.clear()
        self._b_lb.delete(0, "end")
        self._b_info.config(text="선택된 파일 없음")

    def _run_batch(self):
        if not self._b_files:
            messagebox.showwarning("파일 없음", "애니메이션 파일을 추가해 주세요.")
            return
        out_base   = self._b_out.get().strip() or str(
            Path(self._b_files[0]).parent / "frames")
        fmt        = self._b_fmt.get()
        w          = int(self._b_w.get()) if self._b_w.get().strip().isdigit() else None
        h          = int(self._b_h.get()) if self._b_h.get().strip().isdigit() else None
        keep_alpha = self._b_keep_alpha.get()
        total      = len(self._b_files)
        self.progress["maximum"] = total
        self.progress["value"]   = 0

        def worker():
            errors = []
            for i, src in enumerate(self._b_files):
                try:
                    conv.animation_to_frames(
                        src, os.path.join(out_base, Path(src).stem+"_frames"),
                        fmt, w, h, self._b_ratio.get(),
                        self._b_quality.get(), self.bg_color,
                        keep_alpha=keep_alpha)
                except Exception as e:
                    errors.append(f"{Path(src).name}: {e}")
                self.root.after(0, lambda v=i+1: self._set_progress(v, total))
            self.root.after(0, lambda: self._done("프레임 추출 완료!", errors, out_base))

        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # 탭 3 : 프레임 → 애니메이션
    # ══════════════════════════════════════════════════════════════════════════
    def _build_anim_tab(self, parent):
        tab = ScrollableTab(parent)
        tab.pack(fill="both", expand=True)
        p = tab.inner

        lf = self._lf(p, "프레임 이미지 (순서가 중요합니다)")
        lf.pack(fill="both", expand=True, padx=10, pady=(8,4))

        self._a_files: List[str] = []
        br = ttk.Frame(lf)
        br.pack(fill="x", pady=(0,4))
        ttk.Button(br, text="➕ 추가",
                   command=self._add_anim_frames).pack(side="left", padx=2)
        ttk.Button(br, text="↑ 위로",  command=self._move_up).pack(side="left", padx=2)
        ttk.Button(br, text="↓ 아래로", command=self._move_down).pack(side="left", padx=2)
        ttk.Button(br, text="✕ 제거",  command=self._remove_anim_frame).pack(side="left", padx=2)
        ttk.Button(br, text="🗑 전체 지우기", command=self._clear_anim).pack(side="left", padx=2)
        self._a_info = ttk.Label(br, text="프레임 없음", foreground="gray")
        self._a_info.pack(side="right", padx=6)

        lbf = ttk.Frame(lf)
        lbf.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(lbf, orient="vertical")
        self._a_lb = tk.Listbox(lbf, yscrollcommand=sb.set, height=6,
                                 font=("Segoe UI", 9))
        sb.config(command=self._a_lb.yview)
        sb.pack(side="right", fill="y")
        self._a_lb.pack(fill="both", expand=True)

        lf2 = self._lf(p, "옵션")
        lf2.pack(fill="x", padx=10, pady=4)
        lf2.columnconfigure(2, weight=1)

        self._a_fmt = tk.StringVar(value="GIF")
        self._fmt_combo(lf2, self._a_fmt, list(conv.ANIM_OUTPUT_FORMATS), 0)

        self._a_w = tk.StringVar(); self._a_h = tk.StringVar()
        self._a_ratio = tk.BooleanVar(value=True)
        self._size_block(lf2, self._a_w, self._a_h, self._a_ratio, 1)

        self._a_quality = tk.IntVar(value=90)
        self._quality_block(lf2, self._a_quality, 4)

        ttk.Separator(lf2, orient="horizontal").grid(
            row=5, column=0, columnspan=3, sticky="ew", padx=4, pady=6)

        # FPS 입력
        self._row(lf2, "프레임 속도 (FPS)", 6)
        fps_fr = ttk.Frame(lf2)
        fps_fr.grid(row=6, column=1, sticky="w", padx=8, pady=3)
        self._a_fps = tk.DoubleVar(value=10.0)
        ttk.Spinbox(fps_fr, textvariable=self._a_fps,
                    from_=0.1, to=120.0, increment=1.0,
                    width=7, format="%.1f").pack(side="left")
        ttk.Label(fps_fr, text=" FPS").pack(side="left")
        self._fps_ms_lbl = ttk.Label(fps_fr, text="= 100 ms/frame", foreground="gray")
        self._fps_ms_lbl.pack(side="left", padx=8)

        def _upd(*_):
            try:
                ms = fps_to_ms(float(self._a_fps.get()))
                self._fps_ms_lbl.config(text=f"= {ms} ms/frame")
            except Exception:
                pass
        self._a_fps.trace_add("write", _upd)

        # 루프
        self._row(lf2, "반복 횟수 (0 = 무한)", 7)
        self._a_loop = tk.StringVar(value="0")
        ttk.Entry(lf2, textvariable=self._a_loop, width=7).grid(
            row=7, column=1, sticky="w", padx=8, pady=3)

        # 알파
        self._a_keep_alpha = tk.BooleanVar(value=True)
        self._alpha_block(lf2, self._a_keep_alpha, "_a_bg_btn", 8)

        # 출력 파일
        lf3 = self._lf(p, "출력 파일")
        lf3.pack(fill="x", padx=10, pady=4)
        lf3.columnconfigure(2, weight=1)
        self._row(lf3, "저장 경로", 0)
        ef = ttk.Frame(lf3)
        ef.grid(row=0, column=1, columnspan=2, sticky="ew", padx=8, pady=3)
        self._a_out = tk.StringVar()
        ttk.Entry(ef, textvariable=self._a_out).pack(side="left", fill="x", expand=True)
        ttk.Button(ef, text="찾아보기…",
                   command=self._browse_anim_out).pack(side="left", padx=4)

        ttk.Button(p, text="🎬  애니메이션 생성", style="Accent.TButton",
                   command=self._run_anim).pack(pady=10)

    def _add_anim_frames(self):
        exts = " ".join(f"*{e}" for e in conv.INPUT_FORMATS)
        for p in filedialog.askopenfilenames(
                title="프레임 이미지 선택",
                filetypes=[("이미지 파일", exts), ("모든 파일", "*.*")]):
            self._a_files.append(p)
            self._a_lb.insert("end", Path(p).name)
        self._a_info.config(text=f"{len(self._a_files)} 프레임")

    def _move_up(self):
        sel = self._a_lb.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        self._a_files[i-1], self._a_files[i] = self._a_files[i], self._a_files[i-1]
        name = self._a_lb.get(i); self._a_lb.delete(i); self._a_lb.insert(i-1, name)
        self._a_lb.selection_set(i-1)

    def _move_down(self):
        sel = self._a_lb.curselection()
        if not sel or sel[0] >= len(self._a_files)-1:
            return
        i = sel[0]
        self._a_files[i], self._a_files[i+1] = self._a_files[i+1], self._a_files[i]
        name = self._a_lb.get(i); self._a_lb.delete(i); self._a_lb.insert(i+1, name)
        self._a_lb.selection_set(i+1)

    def _remove_anim_frame(self):
        sel = self._a_lb.curselection()
        if sel:
            self._a_lb.delete(sel[0]); del self._a_files[sel[0]]
            self._a_info.config(text=f"{len(self._a_files)} 프레임")

    def _clear_anim(self):
        self._a_files.clear(); self._a_lb.delete(0, "end")
        self._a_info.config(text="프레임 없음")

    def _browse_anim_out(self):
        fmt = self._a_fmt.get()
        ext = conv.OUTPUT_FORMATS.get(fmt, ".gif")
        path = filedialog.asksaveasfilename(
            title="애니메이션 저장",
            defaultextension=ext,
            filetypes=[(f"{fmt} 파일", f"*{ext}"), ("모든 파일", "*.*")])
        if path:
            self._a_out.set(path)

    def _run_anim(self):
        if len(self._a_files) < 2:
            messagebox.showwarning("프레임 부족", "프레임 이미지를 2개 이상 추가해 주세요.")
            return
        out = self._a_out.get().strip()
        if not out:
            messagebox.showwarning("경로 없음", "출력 파일 경로를 지정해 주세요.")
            return
        if not self._confirm_overwrite(out):
            return

        fmt        = self._a_fmt.get()
        w          = int(self._a_w.get()) if self._a_w.get().strip().isdigit() else None
        h          = int(self._a_h.get()) if self._a_h.get().strip().isdigit() else None
        keep_alpha = self._a_keep_alpha.get()
        loop       = int(self._a_loop.get()) if self._a_loop.get().strip().isdigit() else 0
        try:
            dur_ms = fps_to_ms(float(self._a_fps.get()))
        except Exception:
            dur_ms = 100

        total = len(self._a_files)
        self.progress["maximum"] = total
        self.progress["value"]   = 0

        def worker():
            try:
                conv.frames_to_animation(
                    self._a_files, out, fmt, w, h, self._a_ratio.get(),
                    self._a_quality.get(), dur_ms, self.bg_color, loop,
                    keep_alpha=keep_alpha,
                    progress_cb=lambda c, t: self.root.after(
                        0, lambda: self._set_progress(c, t)))
                self.root.after(0, lambda: self._done(
                    "애니메이션 생성 완료!", [], str(Path(out).parent)))
            except Exception as e:
                self.root.after(0, lambda err=e: messagebox.showerror("오류", str(err)))

        threading.Thread(target=worker, daemon=True).start()

    # ── 공통 진행/완료 ────────────────────────────────────────────────────────
    def _set_progress(self, value, maximum):
        self.progress["maximum"] = maximum
        self.progress["value"]   = value
        self.status_var.set(f"처리 중 {value}/{maximum}…")

    def _done(self, msg, errors, open_dir):
        self.progress["value"] = self.progress["maximum"]
        self.status_var.set("완료 ✓")
        if errors:
            detail = "\n".join(errors[:10])
            if len(errors) > 10:
                detail += f"\n… 외 {len(errors)-10}개"
            messagebox.showwarning(msg, f"일부 오류 발생:\n\n{detail}")
        else:
            if messagebox.askyesno(msg, f"{msg}\n\n출력 폴더를 여시겠습니까?"):
                import subprocess, platform
                if platform.system() == "Windows":
                    os.startfile(open_dir)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", open_dir])
                else:
                    subprocess.Popen(["xdg-open", open_dir])
