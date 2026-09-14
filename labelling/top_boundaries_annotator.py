"""
Small standalone Tkinter app for labeling every "pre" (presiding officer) speech
contribution as TOP-opener / not-opener, to validate preprocessing/top_boundaries.py's
rule-based detection at the level it actually operates on.

Reads top_boundaries_annotation_input.csv (exported from
measurement/top_change/top_boundaries_exploration.ipynb): one row
per speech contribution -- consecutive "pre" paragraphs already joined upstream in the
notebook, since a paragraph-position gap means another speaker's turn happened in
between and a gap-free run is one continuous chair utterance.

You can navigate freely with Prev/Next (or the arrow keys) across every contribution,
including ones already labeled -- revisiting one and relabeling it overwrites the
earlier label rather than adding a duplicate row. Labels live in memory and are
rewritten to top_boundaries_opener_labels.csv after every change (the file is small,
so a full rewrite each time is simplest and keeps it always consistent). Restarting
the app reloads existing labels and resumes at the first unlabeled contribution.

Run: norm_env/bin/python labelling/top_boundaries_annotator.py
"""

import csv
import webbrowser
from pathlib import Path

import pandas as pd
import tkinter as tk
from tkinter import messagebox, ttk

APP_DIR = Path(__file__).resolve().parent
INPUT_PATH = APP_DIR / "top_boundaries_annotation_input.csv"
GOLD_PATH = APP_DIR / "top_boundaries_opener_labels.csv"
GOLD_FIELDS = ["protocol_id", "state", "date", "url", "start_pos", "end_pos", "is_opener", "type", "sponsor", "topic", "notes"]


def load_items():
    """Flat list of every contribution, in file order, plus a protocol_id -> list
    lookup used only to render each contribution's surrounding context."""
    df = pd.read_csv(INPUT_PATH, dtype={"protocol_id": str})
    items = df.to_dict("records")
    groups = {}
    for it in items:
        groups.setdefault(it["protocol_id"], []).append(it)
    return items, groups


def load_labels():
    if not GOLD_PATH.exists():
        return {}
    ldf = pd.read_csv(GOLD_PATH, dtype={"protocol_id": str})
    for col in ("type", "sponsor", "topic", "notes"):
        if col not in ldf.columns:
            ldf[col] = ""
    return {
        (row.protocol_id, row.start_pos): {
            "is_opener": int(row.is_opener),
            "type": "" if pd.isna(row.type) else row.type,
            "sponsor": "" if pd.isna(row.sponsor) else row.sponsor,
            "topic": "" if pd.isna(row.topic) else row.topic,
            "notes": "" if pd.isna(row.notes) else row.notes,
        }
        for row in ldf.itertuples()
    }


class AnnotatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TOP opener annotator")
        self.geometry("900x700")

        self.items, self.groups = load_items()
        self.items_by_key = {(it["protocol_id"], it["start_pos"]): it for it in self.items}
        self.index_by_key = {(it["protocol_id"], it["start_pos"]): i for i, it in enumerate(self.items)}
        self.labels = load_labels()
        self.session_edits = {}  # only keys actually (re)labeled THIS run -- see _save_labels

        # resume at the first unlabeled contribution; if everything is labeled, land on the last one
        self.idx = next(
            (i for i, it in enumerate(self.items) if (it["protocol_id"], it["start_pos"]) not in self.labels),
            len(self.items) - 1,
        )

        # unique protocol_ids in the order they first appear, for the jump control
        self.protocol_ids = list(dict.fromkeys(it["protocol_id"] for it in self.items))
        self.first_idx_of_protocol = {}
        for i, it in enumerate(self.items):
            self.first_idx_of_protocol.setdefault(it["protocol_id"], i)

        self.header = tk.Label(self, font=("Helvetica", 13, "bold"), anchor="w", justify="left")
        self.header.pack(fill="x", padx=10, pady=(10, 0))

        # error banner (e.g. "no protocol matching") -- only packed when there's
        # something to show, so it doesn't leave dead blank space otherwise
        self.status_banner = tk.Label(self, font=("Helvetica", 12, "bold"), anchor="w", padx=10, pady=6)

        self.url_var = tk.StringVar()
        url_frame = tk.Frame(self)
        url_frame.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(url_frame, textvariable=self.url_var, fg="blue").pack(side="left")
        tk.Button(url_frame, text="Open PDF", command=self.open_url).pack(side="left", padx=8)

        self.jump_frame = jump_frame = tk.Frame(self)
        jump_frame.pack(fill="x", padx=10, pady=4)
        tk.Label(jump_frame, text="Jump to protocol:").pack(side="left")
        self.jump_var = tk.StringVar()
        self.jump_entry = ttk.Combobox(
            jump_frame, textvariable=self.jump_var, values=self.protocol_ids, width=20, state="readonly",
        )
        self.jump_entry.pack(side="left", padx=(4, 8))
        tk.Button(jump_frame, text="Go", command=self.jump_to_protocol).pack(side="left")
        self.jump_entry.bind("<Return>", lambda e: self.jump_to_protocol())
        tk.Button(jump_frame, text="Jump to first unlabeled",
                  command=self.jump_to_first_unlabeled).pack(side="left", padx=(16, 0))
        self.jump_entry.bind("<<ComboboxSelected>>", lambda e: self.jump_to_protocol())

        search_frame = tk.Frame(self)
        search_frame.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(search_frame, text="Find in this protocol:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side="left", padx=(4, 8))
        tk.Button(search_frame, text="▲ Find prev", command=lambda: self.find_in_protocol(-1)).pack(side="left")
        tk.Button(search_frame, text="Find next ▼", command=lambda: self.find_in_protocol(1)).pack(
            side="left", padx=(4, 0))
        self.search_entry.bind("<Return>", lambda e: self.find_in_protocol(1))
        self.search_status_label = tk.Label(search_frame, fg="#a3333d")
        self.search_status_label.pack(side="left", padx=(8, 0))

        text_frame = tk.Frame(self)
        text_frame.pack(fill="both", expand=True, padx=10, pady=4)
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        self.text = tk.Text(text_frame, wrap="word", yscrollcommand=scrollbar.set,
                             state="disabled", cursor="hand2")
        self.text.tag_config("current", background="#fff3b0")
        self.text.tag_config("opener", background="#c8e6c9")
        self.text.tag_config("notopener", background="#d6d6d6")
        self.text.tag_config("has_topic", background="#bbdefb")
        self.text.tag_config("has_sponsor", background="#e1bee7")
        self.text.tag_config("has_type", background="#ffe0b2")
        # priority (highest last): base label color < has a topic recorded
        # < has a sponsor recorded < has a type recorded < current selection.
        # A block with more than one of these filled in shows whichever is
        # raised last here.
        self.text.tag_raise("has_type")
        self.text.tag_raise("has_sponsor")
        self.text.tag_raise("has_topic")
        self.text.tag_raise("opener")
        self.text.tag_raise("current")
        self.text.pack(fill="both", expand=True)
        scrollbar.config(command=self.text.yview)
        self.text.bind("<Button-1>", self._on_text_click)

        type_sponsor_frame = tk.Frame(self)
        type_sponsor_frame.pack(fill="x", padx=10, pady=(8, 0))
        # Comboboxes, not readonly -- suggest previously-typed values but still free
        # text, since new types/sponsors/topics keep appearing throughout the sample
        tk.Label(type_sponsor_frame, text="Type:").pack(side="left")
        self.type_entry = ttk.Combobox(type_sponsor_frame, width=23)
        self.type_entry.pack(side="left", padx=(4, 16))
        tk.Label(type_sponsor_frame, text="Sponsor:").pack(side="left")
        self.sponsor_entry = ttk.Combobox(type_sponsor_frame, width=23)
        self.sponsor_entry.pack(side="left", padx=(4, 16))
        tk.Label(type_sponsor_frame, text="Topic:").pack(side="left")
        self.topic_entry = ttk.Combobox(type_sponsor_frame, width=23)
        self.topic_entry.pack(side="left", padx=4)

        form = tk.Frame(self)
        form.pack(fill="x", padx=10, pady=8)
        tk.Label(form, text="Notes:").pack(side="left", anchor="n")
        notes_frame = tk.Frame(form)
        notes_frame.pack(side="left", fill="x", expand=True, padx=6)
        notes_scroll = tk.Scrollbar(notes_frame)
        notes_scroll.pack(side="right", fill="y")
        self.notes_entry = tk.Text(notes_frame, height=4, wrap="word", yscrollcommand=notes_scroll.set,
                                    relief="flat", borderwidth=0, highlightthickness=1,
                                    highlightbackground="#c9c9c9", highlightcolor="#2a78d6")
        self.notes_entry.pack(side="left", fill="x", expand=True)
        notes_scroll.config(command=self.notes_entry.yview)

        # nav row (Prev/Next) and label row (Opener/Not opener) share one grid so
        # each button sits directly above its counterpart in the same column.
        controls_frame = tk.Frame(self)
        controls_frame.pack(fill="x", padx=10, pady=(0, 10))
        controls_frame.grid_columnconfigure(0, weight=1, uniform="ctl")
        controls_frame.grid_columnconfigure(1, weight=1, uniform="ctl")
        controls_frame.grid_columnconfigure(2, weight=1)

        tk.Button(controls_frame, text="▲ Prev", command=self.go_prev).grid(
            row=0, column=0, sticky="we", padx=(0, 4), pady=(0, 4))
        tk.Button(controls_frame, text="Next ▼", command=self.go_next).grid(
            row=0, column=1, sticky="we", padx=(4, 0), pady=(0, 4))

        # plain tk.Button ignores custom bg on macOS Aqua (keeps native gray, but
        # still applies fg) -- use a Label styled + bound as a button instead,
        # which does respect colors there.
        self._make_color_button(controls_frame, "Opener (y)", "#c8e6c9", "#0f5132",
                                 lambda: self.label_current(1)).grid(row=1, column=0, sticky="we", padx=(0, 4))

        notopener_frame = tk.Frame(controls_frame)
        notopener_frame.grid(row=1, column=1, sticky="we", padx=(4, 0))
        self._make_color_button(notopener_frame, "Not opener (n)", "#d6d6d6", "#0b0b0b",
                                 lambda: self.label_current(0)).pack(side="left", fill="x", expand=True)
        info_btn = tk.Label(notopener_frame, text="ⓘ", font=("Helvetica", 16, "bold"),
                             fg="#2a78d6", cursor="pointinghand", padx=8)
        info_btn.pack(side="left")
        info_btn.bind("<Button-1>", lambda e: messagebox.showinfo(
            "What counts as an Opener",
            "Opener marks the paragraph where the presiding officer opens a new "
            "debate topic (e.g. Tagesordnungspunkt or lfd. Nr.) -- not just any "
            "procedural remark.",
        ))

        self.progress_label = tk.Label(controls_frame, anchor="ne")
        self.progress_label.grid(row=0, column=2, sticky="ne", padx=(12, 0), pady=(0, 4))

        self._make_color_button(controls_frame, "Close app", "#f8d7da", "#58151c",
                                 self.destroy).grid(row=1, column=2, sticky="e", padx=(12, 0))

        # keyboard shortcuts, but only when the notes field isn't being typed into
        self.bind("y", self._on_key_y)
        self.bind("n", self._on_key_n)
        self.bind("<Left>", self._on_key_left)
        self.bind("<Right>", self._on_key_right)

        self._refresh_dropdown_values()
        self.show_current()

    @staticmethod
    def _make_color_button(parent, text, bg, fg, command):
        lbl = tk.Label(parent, text=text, bg=bg, fg=fg, padx=12, pady=6,
                        relief="raised", cursor="pointinghand")
        lbl.bind("<Button-1>", lambda e: command())
        return lbl

    def _typing_in_notes(self):
        return self.focus_get() in (
            self.notes_entry, self.type_entry, self.sponsor_entry, self.topic_entry,
            self.jump_entry, self.search_entry,
        )

    def _refresh_dropdown_values(self):
        for field, entry in (("type", self.type_entry), ("sponsor", self.sponsor_entry),
                             ("topic", self.topic_entry)):
            values = sorted({lab[field] for lab in self.labels.values() if lab.get(field)})
            entry["values"] = [""] + values  # leading blank entry so "clear" is pickable from the list

    def find_in_protocol(self, direction=1):
        query = self.search_var.get().strip().lower()
        self.search_status_label.config(text="")
        if not query:
            return

        it = self.items[self.idx]
        pid = it["protocol_id"]
        group = self.groups[pid]
        pos_in_group = next(i for i, g in enumerate(group) if g["start_pos"] == it["start_pos"])

        # search forward or backward from just past/before the current position,
        # wrapping around, so repeated presses cycle through every match either way
        n = len(group)
        if direction >= 0:
            order = [(pos_in_group + 1 + k) % n for k in range(n)]
        else:
            order = [(pos_in_group - 1 - k) % n for k in range(n)]
        for i in order:
            if query in group[i]["content"].lower():
                self.idx = self.index_by_key[(pid, group[i]["start_pos"])]
                self.show_current()
                return
        self.search_status_label.config(text=f"No match for {query!r} in this protocol.")

    def jump_to_protocol(self):
        pid = self.jump_var.get().strip()
        if pid in self.first_idx_of_protocol:
            self.idx = self.first_idx_of_protocol[pid]
            self.show_current()
        else:
            self.status_banner.config(
                text=f"No protocol matching {pid!r} in this sample.", bg="#f8d7da", fg="#58151c"
            )
            self.status_banner.pack(fill="x", padx=10, pady=(4, 0), before=self.jump_frame)

    def jump_to_first_unlabeled(self):
        # same rule as the startup resume position, but callable any time --
        # scans from the very start so it finds the actual frontier where
        # labeled turns into not-yet-labeled, not just "the next gap from here"
        self.idx = next(
            (i for i, it in enumerate(self.items) if (it["protocol_id"], it["start_pos"]) not in self.labels),
            len(self.items) - 1,
        )
        self.show_current()

    def _on_key_y(self, event):
        if not self._typing_in_notes():
            self.label_current(1)

    def _on_key_n(self, event):
        if not self._typing_in_notes():
            self.label_current(0)

    def _on_key_left(self, event):
        if not self._typing_in_notes():
            self.go_prev()

    def _on_key_right(self, event):
        if not self._typing_in_notes():
            self.go_next()

    def _on_text_click(self, event):
        click_index = self.text.index(f"@{event.x},{event.y}")
        pid = self.items[self.idx]["protocol_id"]
        for start_index, end_index, start_pos in self._block_bounds:
            if self.text.compare(click_index, ">=", start_index) and self.text.compare(click_index, "<", end_index):
                key = (pid, start_pos)
                if key in self.index_by_key:
                    self.idx = self.index_by_key[key]
                    self.show_current()
                return

    def open_url(self):
        webbrowser.open(self.items[self.idx]["url"])

    def go_prev(self):
        self.idx = max(self.idx - 1, 0)
        self.show_current()

    def go_next(self):
        self.idx = min(self.idx + 1, len(self.items) - 1)
        self.show_current()

    def show_current(self):
        it = self.items[self.idx]
        pid = it["protocol_id"]
        group = self.groups[pid]
        pos_in_group = next(i for i, g in enumerate(group) if g["start_pos"] == it["start_pos"])

        self.header.config(text=f"{pid}  —  {it['state'].upper()} · {it['date']}")
        self.url_var.set(it["url"])

        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        current_start_line = None
        self._block_bounds = []  # (start_index, end_index, start_pos) per displayed block, for click-to-jump
        for i, c in enumerate(group):
            label = f"[{c['start_pos']}]" if c["start_pos"] == c["end_pos"] else f"[{c['start_pos']}-{c['end_pos']}]"
            # "end-1c" (not "end") -- Text widgets keep one permanent invisible
            # trailing newline beyond all real content, so plain "end" is always
            # one row past where content actually ends. Using it here made every
            # highlight land one item late (covering this item's trailing blank
            # line plus the NEXT item's content line, never this item's own).
            start_index = self.text.index("end-1c")
            self.text.insert("end", f"{label} {c['content']}\n\n")
            end_index = self.text.index("end-1c")
            self._block_bounds.append((start_index, end_index, c["start_pos"]))
            block_label = self.labels.get((pid, c["start_pos"]))
            if block_label:
                self.text.tag_add("opener" if block_label["is_opener"] else "notopener", start_index, end_index)
                if block_label.get("topic"):
                    self.text.tag_add("has_topic", start_index, end_index)
                if block_label.get("sponsor"):
                    self.text.tag_add("has_sponsor", start_index, end_index)
                if block_label.get("type"):
                    self.text.tag_add("has_type", start_index, end_index)
            if i == pos_in_group:
                self.text.tag_add("current", start_index, end_index)
                current_start_line = start_index
        self.text.config(state="disabled")
        if current_start_line:
            # see() alone only scrolls the minimum distance needed, which tends to
            # land the target line right at the top/bottom edge of the viewport --
            # so follow it with a bbox-based scroll to actually center the line.
            self.text.see(current_start_line)
            self.text.update_idletasks()
            bbox = self.text.bbox(current_start_line)
            if bbox:
                _, y, _, line_height = bbox
                if line_height:
                    visible_height = self.text.winfo_height()
                    self.text.yview_scroll(int((y - visible_height / 2) / line_height), "units")

        key = (pid, it["start_pos"])
        existing = self.labels.get(key)
        self.notes_entry.delete("1.0", "end")
        self.type_entry.delete(0, "end")
        self.sponsor_entry.delete(0, "end")
        self.topic_entry.delete(0, "end")
        if existing:
            self.notes_entry.insert("1.0", existing["notes"])
            self.type_entry.insert(0, existing["type"])
            self.sponsor_entry.insert(0, existing["sponsor"])
            self.topic_entry.insert(0, existing["topic"])
            if existing["is_opener"]:
                self.status_banner.config(text="✓ ALREADY LABELED: OPENER", bg="#d4edda", fg="#0f5132")
            else:
                self.status_banner.config(text="✓ ALREADY LABELED: not opener", bg="#e2e3e5", fg="#41464b")
        else:
            self.status_banner.config(text="○ NOT YET LABELED", bg="#fff3cd", fg="#664d03")
        self.status_banner.pack(fill="x", padx=10, pady=(4, 0), before=self.jump_frame)

        self.progress_label.config(
            text=f"{self.idx + 1} / {len(self.items)}   ({len(self.labels)} labeled)"
        )

    def label_current(self, is_opener):
        it = self.items[self.idx]
        key = (it["protocol_id"], it["start_pos"])
        entry = {
            "is_opener": is_opener,
            "type": self.type_entry.get().strip(),
            "sponsor": self.sponsor_entry.get().strip(),
            "topic": self.topic_entry.get().strip(),
            "notes": self.notes_entry.get("1.0", "end-1c").strip(),
        }
        self.labels[key] = entry
        self.session_edits[key] = entry
        self._save_labels()
        self._refresh_dropdown_values()
        self.go_next()

    def _save_labels(self):
        # Reconcile with whatever is currently on disk before overwriting --
        # otherwise an external edit (e.g. a script fixing topic values while
        # this app stays open) gets silently clobbered on the next save, since
        # this app would otherwise just dump its own stale in-memory snapshot.
        # Only keys actually (re)labeled THIS session (self.session_edits) win
        # over disk -- self.labels also holds everything loaded at startup, and
        # letting that whole snapshot override disk would clobber external
        # edits made to any row this session never touched, not just genuinely
        # fresh ones.
        on_disk = load_labels()
        on_disk.update(self.session_edits)
        self.labels = on_disk

        with open(GOLD_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=GOLD_FIELDS)
            writer.writeheader()
            for (pid, start_pos), lab in self.labels.items():
                meta = self.items_by_key.get((pid, start_pos))
                if meta is None:
                    continue  # a row from disk that isn't in this session's input file
                writer.writerow({
                    "protocol_id": pid, "state": meta["state"], "date": meta["date"], "url": meta["url"],
                    "start_pos": start_pos, "end_pos": meta["end_pos"],
                    "is_opener": lab["is_opener"], "type": lab["type"], "sponsor": lab["sponsor"],
                    "topic": lab["topic"], "notes": lab["notes"],
                })


if __name__ == "__main__":
    if not INPUT_PATH.exists():
        raise SystemExit(
            f"{INPUT_PATH} not found -- export the contributions CSV from "
            "measurement/top_change/top_boundaries_exploration.ipynb first."
        )
    AnnotatorApp().mainloop()
