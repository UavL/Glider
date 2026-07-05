#!/usr/bin/env python3
import argparse
import pathlib
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from font_bin import FontBin, FontFormatError


PIXEL_SIZE = 20
GRID_BG = "#f5f5f5"
GRID_LINE = "#c9c9c9"
PIXEL_OFF = "#ffffff"
PIXEL_ON = "#111111"
WIDTH_LINE = "#d64a2f"


def glyph_label(ch):
    codepoint = ord(ch)
    if ch == " ":
        name = "space"
    elif ch == "\t":
        name = "tab"
    else:
        name = ch
    return f"0x{codepoint:02X}  {name}"


class FontEditor(tk.Tk):
    def __init__(self, initial_path=None):
        super().__init__()
        self.title("Glider Font Editor")
        self.geometry("980x680")
        self.minsize(760, 520)

        self.path = None
        self.font = None
        self.current_char = None
        self.dirty = False
        self.rects = {}
        self.width_line = None

        self.status_var = tk.StringVar(value="Open a Glider .bin font file.")
        self.width_var = tk.StringVar()

        self._build_menu()
        self._build_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if initial_path is not None:
            self.open_path(initial_path)

    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Open...", command=self.open_dialog, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self.save, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self.save_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

        self.bind_all("<Control-o>", lambda event: self.open_dialog())
        self.bind_all("<Control-s>", lambda event: self.save())
        self.bind_all("<Control-S>", lambda event: self.save_as())

    def _build_widgets(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(root)
        left.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(left, text="Glyphs").pack(anchor=tk.W)

        list_frame = ttk.Frame(left)
        list_frame.pack(fill=tk.Y, expand=True, pady=(4, 0))
        self.glyph_list = tk.Listbox(list_frame, width=18, exportselection=False)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.glyph_list.yview)
        self.glyph_list.configure(yscrollcommand=scrollbar.set)
        self.glyph_list.pack(side=tk.LEFT, fill=tk.Y, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.glyph_list.bind("<<ListboxSelect>>", self._on_glyph_selected)

        right = ttk.Frame(root, padding=(12, 0, 0, 0))
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(right)
        toolbar.pack(fill=tk.X)

        self.file_label = ttk.Label(toolbar, text="No font loaded")
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(toolbar, text="Width").pack(side=tk.LEFT, padx=(12, 4))
        self.width_spin = ttk.Spinbox(
            toolbar,
            from_=1,
            to=1,
            width=6,
            textvariable=self.width_var,
            command=self.apply_width,
        )
        self.width_spin.pack(side=tk.LEFT)
        self.width_spin.bind("<Return>", lambda event: self.apply_width())
        self.width_spin.bind("<FocusOut>", lambda event: self.apply_width())

        canvas_frame = ttk.Frame(right)
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(canvas_frame, background=GRID_BG, highlightthickness=0)
        xscroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        yscroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        self.canvas.grid(row=0, column=0, sticky=tk.NSEW)
        yscroll.grid(row=0, column=1, sticky=tk.NS)
        xscroll.grid(row=1, column=0, sticky=tk.EW)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        status = ttk.Label(self, textvariable=self.status_var, anchor=tk.W, padding=(10, 4))
        status.pack(side=tk.BOTTOM, fill=tk.X)

    def _set_dirty(self, dirty=True):
        self.dirty = dirty
        marker = "*" if self.dirty else ""
        if self.path is None:
            self.title(f"{marker}Glider Font Editor")
        else:
            self.title(f"{marker}{self.path.name} - Glider Font Editor")

    def _confirm_discard(self):
        if not self.dirty:
            return True
        return messagebox.askyesno(
            "Discard changes?",
            "This font has unsaved changes. Discard them?",
            default=messagebox.NO,
        )

    def open_dialog(self):
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            title="Open Glider font",
            filetypes=(("Glider font", "*.bin"), ("All files", "*")),
        )
        if path:
            self.open_path(path)

    def open_path(self, path):
        path = pathlib.Path(path)
        try:
            font = FontBin.from_file(path)
        except (OSError, FontFormatError) as exc:
            messagebox.showerror("Open failed", str(exc))
            return

        self.path = path
        self.font = font
        self.current_char = None
        self.glyph_list.delete(0, tk.END)
        for ch in font.characters():
            self.glyph_list.insert(tk.END, glyph_label(ch))

        self.width_spin.configure(to=font.max_width)
        self.file_label.configure(
            text=f"{path}  ({font.chars} glyphs, {font.max_width}x{font.height} storage)"
        )
        self.status_var.set(f"Loaded {path}")
        self._set_dirty(False)
        if font.chars:
            self.glyph_list.selection_set(0)
            self.glyph_list.activate(0)
            self._select_index(0)

    def save(self):
        if self.font is None:
            return
        if self.path is None:
            self.save_as()
            return
        try:
            self.font.write_file(self.path)
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.status_var.set(f"Saved {self.path}")
        self._set_dirty(False)

    def save_as(self):
        if self.font is None:
            return
        path = filedialog.asksaveasfilename(
            title="Save Glider font",
            defaultextension=".bin",
            filetypes=(("Glider font", "*.bin"), ("All files", "*")),
        )
        if not path:
            return
        self.path = pathlib.Path(path)
        self.save()

    def _on_close(self):
        if self._confirm_discard():
            self.destroy()

    def _on_glyph_selected(self, event=None):
        selection = self.glyph_list.curselection()
        if selection:
            self._select_index(selection[0])

    def _select_index(self, index):
        if self.font is None:
            return
        self.current_char = chr(self.font.offset + index)
        glyph = self.font.glyph(self.current_char)
        self.width_var.set(str(glyph.width))
        self.status_var.set(f"Editing glyph {glyph_label(self.current_char)}")
        self._draw_grid()

    def _draw_grid(self):
        self.canvas.delete("all")
        self.rects = {}
        self.width_line = None
        if self.font is None or self.current_char is None:
            return

        width = self.font.max_width
        height = self.font.height
        canvas_w = width * PIXEL_SIZE + 1
        canvas_h = height * PIXEL_SIZE + 1
        self.canvas.configure(scrollregion=(0, 0, canvas_w, canvas_h))

        for y in range(height):
            for x in range(width):
                x0 = x * PIXEL_SIZE
                y0 = y * PIXEL_SIZE
                fill = PIXEL_ON if self.font.get_pixel(self.current_char, x, y) else PIXEL_OFF
                rect = self.canvas.create_rectangle(
                    x0,
                    y0,
                    x0 + PIXEL_SIZE,
                    y0 + PIXEL_SIZE,
                    outline=GRID_LINE,
                    fill=fill,
                )
                self.rects[(x, y)] = rect
        self._draw_width_marker()

    def _draw_width_marker(self):
        if self.font is None or self.current_char is None:
            return
        if self.width_line is not None:
            self.canvas.delete(self.width_line)

        glyph = self.font.glyph(self.current_char)
        x = glyph.width * PIXEL_SIZE
        self.width_line = self.canvas.create_line(
            x,
            0,
            x,
            self.font.height * PIXEL_SIZE,
            fill=WIDTH_LINE,
            width=2,
        )

    def _on_canvas_click(self, event):
        if self.font is None or self.current_char is None:
            return
        x = int(self.canvas.canvasx(event.x) // PIXEL_SIZE)
        y = int(self.canvas.canvasy(event.y) // PIXEL_SIZE)
        if x < 0 or x >= self.font.max_width or y < 0 or y >= self.font.height:
            return

        new_value = not self.font.get_pixel(self.current_char, x, y)
        self.font.set_pixel(self.current_char, x, y, new_value)
        self.canvas.itemconfigure(self.rects[(x, y)], fill=PIXEL_ON if new_value else PIXEL_OFF)
        self._set_dirty(True)

    def apply_width(self):
        if self.font is None or self.current_char is None:
            return
        try:
            width = int(self.width_var.get())
            self.font.set_width(self.current_char, width)
        except ValueError as exc:
            messagebox.showerror("Invalid width", str(exc))
            self.width_var.set(str(self.font.glyph(self.current_char).width))
            return
        self._draw_width_marker()
        self._set_dirty(True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Edit Glider 1-bit OSD font binaries.")
    parser.add_argument("font", nargs="?", type=pathlib.Path,
            help="font_quicksand_*.bin file to edit")
    args = parser.parse_args(argv)

    app = FontEditor(args.font)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
