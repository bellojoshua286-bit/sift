import ctypes
import os
import sys
import threading
import time
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from cleaner import delete_selected
from engine import find_duplicates

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

RISKY_EXTENSIONS = {".exe", ".dll", ".sys", ".msi", ".bat", ".ini", ".lnk"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"}

PREVIEW_W, PREVIEW_H = 280, 150

BLUE = ("#3B8ED0", "#1F6AA5")
BLUE_HOVER = ("#36719F", "#144870")
RED = "#c0392b"
RED_HOVER = "#962d22"
GREY = ("gray70", "gray30")
BORDER = ("gray75", "gray30")
INFO_BG = ("#e3eef9", "#1c3550")
BADGE_BG = ("#dbe9f6", "#1f3a52")
BADGE_FG = ("#1f6aa5", "#8ec1ea")


def resource_path(name):
    """Find a bundled file, both when running from source and from the .exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def format_size(num_bytes):
    """Turn a byte count into readable text like '15.0 KB'."""
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def count_text(number, one, many):
    """'1 file' or '3 files'."""
    return f"{number} {one if number == 1 else many}"


def get_details(path):
    """Return (size text, modified-date text) for a file."""
    try:
        size_text = format_size(os.path.getsize(path))
        date_text = datetime.fromtimestamp(os.path.getmtime(path)).strftime(
            "%d %b %Y, %H:%M"
        )
    except OSError:
        return "unknown size", "unknown date"
    return size_text, date_text


def load_preview(path):
    """Return (preview image, (width, height)) for picture files,
    or (None, None) when the file has no preview."""
    if os.path.splitext(path)[1].lower() not in IMAGE_EXTENSIONS:
        return None, None
    try:
        with Image.open(path) as img:
            full_size = img.size
            img.draft("RGB", (PREVIEW_W * 2, PREVIEW_H * 2))
            thumb = img.convert("RGBA")
        thumb.thumbnail((PREVIEW_W, PREVIEW_H))
        image = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=thumb.size)
        return image, full_size
    except Exception:
        return None, None


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sift - Duplicate Finder")
        self.geometry("980x760")
        self.minsize(900, 600)

        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "duplicatefinder.app"
            )
        except Exception:
            pass
        self.after(300, self.set_icon)

        self.folder = None

        self.scan_done = False
        self.scan_result = None
        self.scan_error = None
        self.scan_started = 0
        self.last_scan_time = 0

        self.matches = []          # all duplicate sets found by the scan
        self.index = 0             # which match is on screen
        self.current_group = []    # files shown on screen right now
        self.card_items = []       # one entry per card: box, path, card, note
        self.image_refs = []       # keeps preview images alive

        self.removed_count = 0
        self.freed_bytes = 0
        self.kept_count = 0

        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=20, pady=(20, 10))

        self.browse_button = ctk.CTkButton(
            top, text="Browse folder", command=self.browse
        )
        self.browse_button.pack(side="left", padx=10, pady=10)

        self.scan_button = ctk.CTkButton(
            top, text="Scan", command=self.scan, state="disabled"
        )
        self.scan_button.pack(side="right", padx=10, pady=10)

        self.folder_label = ctk.CTkLabel(top, text="No folder selected", anchor="w")
        self.folder_label.pack(side="left", padx=10, fill="x", expand=True)

        self.status_label = ctk.CTkLabel(self, text="Choose a folder to begin")
        self.status_label.pack(pady=(0, 5))

        self.review = ctk.CTkFrame(self, fg_color="transparent")
        self.review.pack(fill="both", expand=True, padx=20, pady=(5, 15))

        self.show_message("Choose a folder, then click Scan to look for duplicates.")

    # ---------- window icon ----------

    def set_icon(self):
        """Replace CustomTkinter's default window icon with ours."""
        try:
            self.iconbitmap(resource_path("app_icon.ico"))
        except Exception:
            pass

    # ---------- folder + scan ----------

    def browse(self):
        chosen = filedialog.askdirectory(title="Choose a folder to scan")
        if chosen:
            self.folder = chosen
            self.folder_label.configure(text=chosen)
            self.scan_button.configure(state="normal")
            self.status_label.configure(text="Ready to scan")

    def scan(self):
        self.browse_button.configure(state="disabled")
        self.scan_button.configure(state="disabled")
        self.status_label.configure(text="Scanning... 0 s")
        self.show_message("Scanning, please wait...")

        self.removed_count = 0
        self.freed_bytes = 0
        self.kept_count = 0

        self.scan_done = False
        self.scan_result = None
        self.scan_error = None
        self.scan_started = time.time()

        worker = threading.Thread(target=self.run_scan, daemon=True)
        worker.start()
        self.after(500, self.check_scan)

    def run_scan(self):
        """Runs on the background thread. Never touches the window."""
        try:
            self.scan_result = find_duplicates(self.folder)
        except Exception as error:
            self.scan_error = str(error)
        self.scan_done = True

    def check_scan(self):
        """Runs on the window thread twice a second until the scan is done."""
        if not self.scan_done:
            elapsed = int(time.time() - self.scan_started)
            self.status_label.configure(text=f"Scanning... {elapsed} s")
            self.after(500, self.check_scan)
            return

        self.last_scan_time = time.time() - self.scan_started
        self.browse_button.configure(state="normal")
        self.scan_button.configure(state="normal")

        if self.scan_error:
            self.status_label.configure(text=f"Scan failed: {self.scan_error}")
            self.show_message("The scan failed.")
            return

        self.matches = self.scan_result
        self.index = 0

        if not self.matches:
            self.status_label.configure(
                text=f"No duplicates found ({self.last_scan_time:.1f} s)"
            )
            self.show_message("No duplicates found in this folder.")
            return

        self.status_label.configure(
            text=f"Found {count_text(len(self.matches), 'match', 'matches')} "
                 f"({self.last_scan_time:.1f} s)"
        )
        self.show_match()

    # ---------- review screen ----------

    def clear_review(self):
        for widget in self.review.winfo_children():
            widget.destroy()
        self.card_items = []
        self.image_refs = []

    def show_message(self, text):
        self.clear_review()
        ctk.CTkLabel(
            self.review, text=text, text_color="gray", font=ctk.CTkFont(size=15)
        ).pack(expand=True)

    def show_match(self):
        # Skip matches where files have disappeared since the scan
        while self.index < len(self.matches):
            group = [p for p in self.matches[self.index] if os.path.exists(p)]
            if len(group) >= 2:
                break
            self.index += 1
        else:
            self.show_summary()
            return

        self.current_group = group
        self.clear_review()

        header = ctk.CTkFrame(self.review, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkLabel(
            header,
            text="Review duplicates",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left")
        ctk.CTkLabel(
            header,
            text=f"Match {self.index + 1} of {len(self.matches)}",
            text_color="gray",
        ).pack(side="right")

        banner = ctk.CTkFrame(self.review, corner_radius=8, fg_color=INFO_BG)
        banner.pack(fill="x", pady=(10, 10))
        ctk.CTkLabel(
            banner,
            text="These files are identical. Nothing is ticked, so every copy "
                 "is kept unless you choose otherwise.",
            anchor="w",
            justify="left",
            wraplength=860,
        ).pack(fill="x", padx=12, pady=8)

        # Buttons are packed to the bottom first, so they never get cut off
        buttons = ctk.CTkFrame(self.review, fg_color="transparent")
        buttons.pack(side="bottom", pady=(4, 0))

        self.message_label = ctk.CTkLabel(self.review, text="", text_color=RED)
        self.message_label.pack(side="bottom", pady=(8, 0))

        self.primary_button = ctk.CTkButton(
            buttons,
            text="Keep all and continue",
            width=250,
            command=self.primary_clicked,
        )
        self.primary_button.pack(side="left", padx=5)

        ctk.CTkButton(
            buttons,
            text="Skip",
            width=90,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            command=self.skip,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            buttons,
            text="Open folder",
            width=110,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            command=self.open_folder,
        ).pack(side="left", padx=5)

        cards = ctk.CTkScrollableFrame(
            self.review, orientation="horizontal", fg_color="transparent"
        )
        cards.pack(fill="both", expand=True)
        for path in group:
            self.add_card(cards, path)

        self.update_actions()

    def add_card(self, parent, path):
        extension = os.path.splitext(path)[1].lower()
        size_text, date_text = get_details(path)
        image, full_size = load_preview(path)

        card = ctk.CTkFrame(
            parent, corner_radius=12, border_width=1, border_color=BORDER
        )
        card.pack(side="left", padx=6, pady=4, anchor="n")

        # Preview (a picture, or a placeholder for other file types)
        if image:
            self.image_refs.append(image)
            preview = ctk.CTkLabel(
                card,
                text="",
                image=image,
                width=PREVIEW_W,
                height=PREVIEW_H,
                fg_color=("gray88", "gray20"),
                corner_radius=8,
            )
        else:
            label = extension[1:].upper() if extension else "FILE"
            preview = ctk.CTkLabel(
                card,
                text=f"{label}\nNo preview",
                width=PREVIEW_W,
                height=PREVIEW_H,
                fg_color=("gray88", "gray20"),
                text_color="gray",
                corner_radius=8,
                font=ctk.CTkFont(size=16, weight="bold"),
            )
        preview.pack(padx=10, pady=(10, 8))

        # The Remove checkbox sits in the top-left corner, over the preview
        chip = ctk.CTkFrame(
            card,
            corner_radius=6,
            border_width=0.5,
            border_color=("gray60", "gray40"),
            fg_color=("white", "gray17"),
        )
        box = ctk.CTkCheckBox(
            chip,
            text = "",
            width= 0,
            checkbox_width=20,
            checkbox_height=20,
            command=self.update_actions,
        )
        box.pack(padx=(8, 6), pady=5)
        chip.place(x=18, y=18)

        # File type badge, name, and details
        badge_text = extension[1:].upper() if extension else "FILE"
        ctk.CTkLabel(
            card,
            text=f"  {badge_text}  ",
            fg_color=BADGE_BG,
            text_color=BADGE_FG,
            corner_radius=6,
            height=22,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=12)

        ctk.CTkLabel(
            card,
            text=os.path.basename(path),
            font=ctk.CTkFont(weight="bold"),
            wraplength=270,
            justify="left",
            anchor="w",
        ).pack(anchor="w", padx=12, pady=(4, 0))

        first_line = size_text
        if full_size:
            first_line += f"  |  {full_size[0]} x {full_size[1]}"
        facts = f"{first_line}\nModified {date_text}\n{os.path.dirname(path)}"
        ctk.CTkLabel(
            card,
            text=facts,
            text_color="gray",
            font=ctk.CTkFont(size=12),
            wraplength=270,
            justify="left",
            anchor="w",
        ).pack(anchor="w", padx=12, pady=(2, 4))

        if extension in RISKY_EXTENSIONS:
            ctk.CTkLabel(
                card,
                text="Program/system file - be careful",
                text_color="orange",
                anchor="w",
            ).pack(anchor="w", padx=12)

        note = ctk.CTkLabel(card, text="", text_color=RED, anchor="w", height=20)
        note.pack(anchor="w", padx=12, pady=(0, 10))

        self.card_items.append(
            {"box": box, "path": path, "card": card, "note": note}
        )

    def update_actions(self):
        """Refresh the cards and the main button after every tick or untick."""
        total = len(self.card_items)
        ticked = 0

        for item in self.card_items:
            on = item["box"].get() == 1
            ticked += on
            item["note"].configure(
                text="Will be moved to the Recycle Bin" if on else ""
            )
            item["card"].configure(border_color=RED if on else BORDER)

        self.message_label.configure(text="")

        if ticked == 0:
            self.primary_button.configure(
                text="Keep all and continue",
                fg_color=BLUE,
                hover_color=BLUE_HOVER,
                state="normal",
            )
        elif ticked < total:
            self.primary_button.configure(
                text=f"Move {count_text(ticked, 'file', 'files')} to the Recycle Bin",
                fg_color=RED,
                hover_color=RED_HOVER,
                state="normal",
            )
        else:
            self.primary_button.configure(
                text="Keep at least one file", fg_color=GREY, state="disabled"
            )
            self.message_label.configure(
                text="Untick one file. At least one copy has to stay."
            )

    # ---------- actions ----------

    def primary_clicked(self):
        ticked = [item["path"] for item in self.card_items if item["box"].get() == 1]

        if not ticked:
            self.kept_count += 1
            self.next_match()
            return

        if any(os.path.splitext(p)[1].lower() in RISKY_EXTENSIONS for p in ticked):
            if not messagebox.askyesno(
                "Program or system files",
                "Your selection includes program or system files.\n\n"
                "Move them to the Recycle Bin anyway?",
                icon="warning",
            ):
                return

        sizes = {}
        for path in ticked:
            try:
                sizes[path] = os.path.getsize(path)
            except OSError:
                sizes[path] = 0

        try:
            done, failed = delete_selected(self.current_group, ticked)
        except ValueError as error:
            messagebox.showwarning("Nothing was removed", str(error))
            return

        self.removed_count += len(done)
        self.freed_bytes += sum(sizes.get(p, 0) for p in done)

        if failed:
            messagebox.showwarning(
                "Some files were not removed",
                "\n".join(
                    f"{os.path.basename(p)}: {reason}" for p, reason in failed[:10]
                ),
            )

        self.next_match()

    def skip(self):
        self.kept_count += 1
        self.next_match()

    def open_folder(self):
        folders = []
        for path in self.current_group:
            folder = os.path.dirname(path)
            if folder not in folders:
                folders.append(folder)
        for folder in folders[:3]:
            try:
                os.startfile(folder)
            except OSError:
                pass

    def next_match(self):
        self.index += 1
        self.show_match()

    def show_summary(self):
        self.clear_review()
        self.status_label.configure(text="Review finished")

        box = ctk.CTkFrame(self.review, fg_color="transparent")
        box.pack(expand=True)

        ctk.CTkLabel(
            box,
            text="All matches reviewed",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(0, 10))

        if self.removed_count:
            text = (
                f"Moved {count_text(self.removed_count, 'file', 'files')} to the "
                f"Recycle Bin ({format_size(self.freed_bytes)} freed)"
            )
        else:
            text = "No files were removed"
        ctk.CTkLabel(box, text=text, font=ctk.CTkFont(size=15)).pack()

        if self.kept_count:
            ctk.CTkLabel(
                box,
                text=f"{count_text(self.kept_count, 'match', 'matches')} "
                     "kept as they were",
                text_color="gray",
            ).pack(pady=(4, 0))

        ctk.CTkLabel(
            box, text="Click Scan to check the folder again.", text_color="gray"
        ).pack(pady=(14, 0))


if __name__ == "__main__":
    app = App()
    app.mainloop()