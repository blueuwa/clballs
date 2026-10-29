"""Reads the editable number / on-off settings of a character file and writes changes back into it.

Every character file keeps its settings in dicts like

    STATS = {
        "max_hp": 2400,          # some comment
        ...
    }

This module finds those dicts (module-level dicts written as `NAME = {` on their own line), lists every
number / True-False entry together with its comment, changes the LIVE values (so the next battle uses them)
and can save them into the .py file itself, keeping the formatting and the comments.
"""
import ast
import math
import os
import re
import shutil

_DICT_START = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=\s*\{\s*(#.*)?$")
_KEY_LINE = re.compile(r'^\s*"([^"]+)"\s*:\s*(.*)$')


def pretty(name):
    return name.replace("_", " ").title()


def fmt(v):
    if isinstance(v, bool):
        return "ON" if v else "OFF"
    if isinstance(v, int):
        return str(v)
    return ("%.4f" % v).rstrip("0").rstrip(".") or "0"


def parse_value(text, original):
    """Typed text -> number. Keeps ints as ints unless the user typed a decimal point."""
    text = text.strip().replace(",", ".")
    if text in ("", "-", ".", "-."):
        raise ValueError("empty")
    if isinstance(original, float) or "." in text:
        return float(text)
    return int(text)


def step_for(v):
    """A sensible +/- step: about 10% of the value's size."""
    if isinstance(v, bool):
        return 1
    a = abs(v)
    if isinstance(v, int):
        return max(1, 10 ** (len(str(a)) - 2)) if a >= 10 else 1
    if a == 0:
        return 0.1
    return round(10 ** (math.floor(math.log10(a)) - 1), 6)


def _py_repr(v):
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, float):
        r = repr(float(v))
        return r
    return str(int(v))


class Entry:
    def __init__(self, group, key, comment):
        self.group = group
        self.key = key
        self.comment = comment

    @property
    def label(self):
        return pretty(self.key)


class StatEditor:
    """Editable settings of one character module."""

    def __init__(self, module):
        self.module = module
        self.path = getattr(module, "__file__", None)
        if self.path and self.path.endswith(".pyc"):
            self.path = self.path[:-1]
        self.groups = []            # [(group_name, [Entry, ...])] in file order
        self.baseline = {}          # (group, key) -> value that is in the file right now
        self._backed_up = False
        self._scan()

    # ---------- reading ----------
    def _scan(self):
        self.groups = []
        if not self.path or not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8", newline="") as f:
            lines = f.read().splitlines()
        i = 0
        while i < len(lines):
            m = _DICT_START.match(lines[i])
            if not m:
                i += 1
                continue
            name = m.group(1)
            live = getattr(self.module, name, None)
            i += 1
            entries = []
            while i < len(lines) and not lines[i].startswith("}"):
                km = _KEY_LINE.match(lines[i].partition("#")[0])
                if km and isinstance(live, dict) and km.group(1) in live:
                    key = km.group(1)
                    val = live[key]
                    if isinstance(val, (bool, int, float)):
                        comment = lines[i].partition("#")[2].strip()
                        entries.append(Entry(name, key, comment))
                        self.baseline[(name, key)] = val
                i += 1
            if entries:
                self.groups.append((name, entries))
            i += 1

    @property
    def title(self):
        return getattr(self.module, "STATS", {}).get("name", self.module.__name__)

    # ---------- values ----------
    def get(self, group, key):
        return getattr(self.module, group)[key]

    def set(self, group, key, value):
        """Changes the live value (used by the next battle)."""
        getattr(self.module, group)[key] = value

    def is_dirty(self, group, key):
        return self.get(group, key) != self.baseline[(group, key)]

    def any_dirty(self):
        return any(self.is_dirty(g, e.key) for g, es in self.groups for e in es)

    def dirty_count(self):
        return sum(1 for g, es in self.groups for e in es if self.is_dirty(g, e.key))

    def reset(self):
        """Back to what is saved in the file."""
        for (g, k), v in self.baseline.items():
            self.set(g, k, v)

    # ---------- writing ----------
    def save(self):
        """Writes every changed value into the .py file. Returns the number of changed values."""
        changes = {(g, e.key): self.get(g, e.key) for g, es in self.groups for e in es if self.is_dirty(g, e.key)}
        if not changes:
            return 0
        with open(self.path, "r", encoding="utf-8", newline="") as f:
            text = f.read()
        lines = text.splitlines(keepends=True)
        if not self._backed_up:                       # one safety copy per run
            try:
                shutil.copyfile(self.path, self.path + ".bak")
            except OSError:
                pass
            self._backed_up = True

        cur = None
        for idx, line in enumerate(lines):
            stripped = line.rstrip("\r\n")
            m = _DICT_START.match(stripped)
            if m:
                cur = m.group(1)
                continue
            if cur is None:
                continue
            if stripped.startswith("}"):
                cur = None
                continue
            code, sep, comment = stripped.partition("#")
            km = _KEY_LINE.match(code)
            if not km or (cur, km.group(1)) not in changes:
                continue
            key = km.group(1)
            vm = re.match(r'^(\s*"' + re.escape(key) + r'"\s*:\s*)(.*?)(\s*,?\s*)$', code)
            if not vm:
                continue
            new_code = vm.group(1) + _py_repr(changes[(cur, key)]) + vm.group(3)
            ending = line[len(stripped):]
            lines[idx] = new_code + sep + comment + ending

        with open(self.path, "w", encoding="utf-8", newline="") as f:
            f.write("".join(lines))
        for k, v in changes.items():
            self.baseline[k] = v
        return len(changes)
