#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gui/dialogs/diff_dialog.py - Show the git diff of a single changed file
#
# Lets the user preview exactly what changed in a file before committing and
# triggering a build. Opened by activating a row in the Overview's "Changed
# Files" list.

import subprocess

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gdk
from core.translation_utils import _

# Guard against pathological diffs (huge generated files, accidental binaries
# slipping past the text check) freezing the UI while inserting into the buffer.
_MAX_DIFF_CHARS = 400_000


class DiffDialog(Adw.Window):
    """A window showing the git diff for one file, with +/- coloring."""

    def __init__(self, parent, filepath, status):
        super().__init__()
        self.set_title(filepath)
        self.set_default_size(840, 620)
        self.set_modal(True)
        if parent is not None:
            self.set_transient_for(parent)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title=_("Diff"), subtitle=filepath))
        box.append(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)

        textview = Gtk.TextView()
        textview.set_editable(False)
        textview.set_cursor_visible(False)
        textview.set_monospace(True)
        textview.set_wrap_mode(Gtk.WrapMode.NONE)
        for margin in ("set_left_margin", "set_right_margin",
                       "set_top_margin", "set_bottom_margin"):
            getattr(textview, margin)(8)

        buf = textview.get_buffer()
        buf.create_tag("add", foreground="#2ec27e")    # added line
        buf.create_tag("del", foreground="#e01b24")    # removed line
        buf.create_tag("hunk", foreground="#3584e4")   # @@ hunk header
        buf.create_tag("meta", foreground="#9a9996")   # diff/index/file headers
        self._render(buf, filepath, status)

        scrolled.set_child(textview)
        box.append(scrolled)
        self.set_content(box)

        # Escape closes the window (HeaderBar also provides a close button).
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

    def _on_key(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _render(self, buf, filepath, status):
        text = self._diff_text(filepath, status)
        if not text.strip():
            buf.set_text(_("No textual diff (binary file or no changes)."))
            return
        if len(text) > _MAX_DIFF_CHARS:
            text = text[:_MAX_DIFF_CHARS] + "\n" + _("… diff truncated (too large to display).")

        for line in text.splitlines():
            tag = self._tag_for(line)
            it = buf.get_end_iter()
            if tag:
                buf.insert_with_tags_by_name(it, line + "\n", tag)
            else:
                buf.insert(it, line + "\n")

    @staticmethod
    def _tag_for(line):
        if line.startswith("+") and not line.startswith("+++"):
            return "add"
        if line.startswith("-") and not line.startswith("---"):
            return "del"
        if line.startswith("@@"):
            return "hunk"
        if line.startswith(("diff ", "index ", "+++", "---", "new file",
                            "deleted file", "old mode", "new mode",
                            "similarity", "rename ", "copy ", "Binary ")):
            return "meta"
        return None

    @staticmethod
    def _diff_text(filepath, status):
        # Untracked files have nothing in HEAD to diff against; show the whole
        # file as added via --no-index (which exits non-zero but prints the diff).
        if status.startswith("?"):
            cmd = ["git", "diff", "--no-index", "--", "/dev/null", filepath]
        else:
            cmd = ["git", "diff", "HEAD", "--", filepath]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return result.stdout or ""
        except Exception:
            return ""


def show_file_diff(parent, filepath, status):
    """Open a DiffDialog for *filepath* (status is the porcelain code, e.g. 'M')."""
    DiffDialog(parent, filepath, status).present()
