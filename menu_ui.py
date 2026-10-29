"""Selection screen (fighter cards + pencil icons) and the stat editor screen."""
import math
import os
import sys

import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT, CENTER_X, CENTER_Y, STRIP_WIDTH
import stat_editor as se

GOLD = (255, 205, 40)
BLUE = (50, 180, 220)
RED = (220, 50, 80)
TEAM = [BLUE, RED]
TEXT = (235, 238, 250)
MUTED = (140, 148, 175)
PANEL = (16, 18, 34)

F_TITLE = pygame.font.SysFont("Impact", 44)
F_HEAD = pygame.font.SysFont("Impact", 30)
F_NAME = pygame.font.SysFont("Impact", 24)
F_BTN = pygame.font.SysFont("Impact", 28)
F_ROW = pygame.font.SysFont("Arial", 17, bold=True)
F_SMALL = pygame.font.SysFont("Arial", 14, bold=True)
F_TINY = pygame.font.SysFont("Arial", 12, bold=True)

# Detect if the game is running in a web browser
IS_WEB = sys.platform == "emscripten"

# ---------------------------------------------------------------- helpers
def lighten(c, a):
    return tuple(min(255, int(v + (255 - v) * a)) for v in c)

def rrect(screen, rect, color, radius=12, border=None, bw=0):
    surf = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(surf, color, surf.get_rect(), border_radius=radius)
    if border:
        pygame.draw.rect(surf, border, surf.get_rect(), bw, border_radius=radius)
    screen.blit(surf, rect.topleft)

def text(screen, font, s, color, align, pos, shadow=True, alpha=255):
    img = font.render(s, True, color)
    rect = img.get_rect(**{align: pos})
    if shadow:
        sh = font.render(s, True, (0, 0, 0))
        if alpha < 255:
            sh.set_alpha(alpha)
        screen.blit(sh, rect.move(2, 2))
    if alpha < 255:
        img.set_alpha(alpha)
    screen.blit(img, rect)
    return rect

def fit(font, s, width):
    if font.size(s)[0] <= width:
        return s
    while s and font.size(s + "...")[0] > width:
        s = s[:-1]
    return s + "..."

def draw_pencil(screen, cx, cy, size, outline=(30, 24, 10)):
    """A small pencil pointing down-left."""
    L = size * 1.6
    d = (0.7071, -0.7071)
    n = (0.7071, 0.7071)
    tx, ty = cx - d[0] * L / 2, cy - d[1] * L / 2
    w = size * 0.28

    def P(t, off):
        return (tx + d[0] * L * t + n[0] * off, ty + d[1] * L * t + n[1] * off)

    parts = (
        ([P(0.24, -w), P(0.80, -w), P(0.80, w), P(0.24, w)], (255, 200, 40)),
        ([P(0.24, -w * 0.2), P(0.80, -w * 0.2), P(0.80, w * 0.2), P(0.24, w * 0.2)], (255, 232, 130)),
        ([P(0.00, 0), P(0.24, -w), P(0.24, w)], (240, 205, 160)),
        ([P(0.00, 0), P(0.09, -w * 0.38), P(0.09, w * 0.38)], (60, 60, 70)),
        ([P(0.80, -w), P(0.88, -w), P(0.88, w), P(0.80, w)], (170, 175, 190)),
        ([P(0.88, -w), P(1.00, -w), P(1.00, w), P(0.88, w)], (240, 120, 150)),
    )
    for pts, col in parts:
        pygame.draw.polygon(screen, col, pts)
    pygame.draw.polygon(screen, outline, [P(0, 0), P(0.24, -w), P(1.0, -w), P(1.0, w), P(0.24, w)], 1)

def draw_button(screen, label, rect, base, hover_col, hovered, font=None):
    font = font or F_BTN
    col = hover_col if hovered else base
    pygame.draw.rect(screen, (0, 0, 0), rect.move(0, 4), border_radius=12)
    pygame.draw.rect(screen, col, rect, border_radius=12)
    pygame.draw.rect(screen, lighten(col, 0.45), pygame.Rect(rect.x + 4, rect.y + 3, rect.w - 8, max(3, rect.h // 4)),
                     border_radius=8)
    pygame.draw.rect(screen, (255, 255, 255), rect, 3, border_radius=12)
    img = font.render(label, True, (255, 255, 255))
    sh = font.render(label, True, (0, 0, 0))
    r = img.get_rect(center=rect.center)
    screen.blit(sh, r.move(2, 2))
    screen.blit(img, r)


# ---------------------------------------------------------------- selection screen
class SelectScreen:
    def __init__(self, roster_info, roster_classes, get_avatar, editors):
        self.info = roster_info
        self.classes = roster_classes
        self.get_avatar = get_avatar
        self.editors = editors
        self.p1 = 0
        self.p2 = 1 if len(roster_info) > 1 else 0
        self.active = 0            # which slot the next click on a fighter fills
        self.t = 0
        self._av = {}
        self.scroll = 0            # scroll position of the fighter list (pixels)

    # ----- data
    def _avatar(self, idx, r):
        key = (idx, r)
        if key not in self._av:
            self._av[key] = self.get_avatar(self.info[idx], r)
        return self._av[key]

    def _stats(self, idx):
        return sys.modules[self.classes[idx].__module__].STATS

    def _picked(self, slot):
        return self.p1 if slot == 0 else self.p2

    # ----- layout
    def layout(self):
        W = max(420, min(STRIP_WIDTH, SCREEN_WIDTH - 20))
        left = CENTER_X - W // 2
        top = max(12, CENTER_Y - 350)
        gap = 10
        sw = (W - 12) // 2
        slots = [pygame.Rect(left, top + 80, sw, 235), pygame.Rect(left + sw + 12, top + 80, sw, 235)]
        cols = 3
        cw = (W - 2 * gap) // cols
        ch = 118
        n = len(self.info)
        rows = (n + cols - 1) // cols
        bw, bh = 250, 62
        side = SCREEN_WIDTH - (left + W) >= bw + 50      # room to the right of the menu -> button goes on the side
        list_top = top + 372
        if side:
            list_bottom = SCREEN_HEIGHT - 12
        else:                                            # narrow screen: the button sits under the (scrolling) list
            list_bottom = SCREEN_HEIGHT - 12 - bh - 12
        view = pygame.Rect(left - 4, list_top - 6, W + 8, max(ch, list_bottom - list_top + 6))
        content_h = rows * (ch + gap) - gap
        max_scroll = max(0, content_h - (view.h - 6))
        self.scroll = max(0, min(max_scroll, self.scroll))
        cards = []
        for i in range(n):
            r, c = divmod(i, cols)
            cards.append(pygame.Rect(left + c * (cw + gap), list_top + r * (ch + gap) - self.scroll, cw, ch))
        if side:
            brawl = pygame.Rect(left + W + 25 + (SCREEN_WIDTH - (left + W) - 25 - bw) // 2, CENTER_Y - bh // 2, bw, bh)
        else:
            brawl = pygame.Rect(CENTER_X - bw // 2, SCREEN_HEIGHT - bh - 12, bw, bh)
        return {"W": W, "left": left, "top": top, "slots": slots, "cards": cards, "brawl": brawl, "view": view, "max_scroll": max_scroll}

    @staticmethod
    def _pencil(rect, pad, rad):
        return (rect.right - pad, rect.top + pad), rad

    # ----- input
    def handle_scroll(self, dy):
        """Mouse wheel / arrow keys: dy > 0 scrolls up, dy < 0 scrolls down."""
        L = self.layout()
        self.scroll = max(0, min(L["max_scroll"], self.scroll - dy * 60))

    def handle_click(self, pos):
        """Returns ('brawl',), ('edit', index) or None."""
        L = self.layout()
        for slot, rect in enumerate(L["slots"]):
            (cx, cy), rad = self._pencil(rect, 26, 18)
            if math.hypot(pos[0] - cx, pos[1] - cy) <= rad:
                return ("edit", self._picked(slot))
        in_view = L["view"].collidepoint(pos)            # cards scrolled out of the list can't be clicked
        for i, rect in enumerate(L["cards"]):
            (cx, cy), rad = self._pencil(rect, 20, 15)
            if in_view and math.hypot(pos[0] - cx, pos[1] - cy) <= rad:
                return ("edit", i)
        for i, rect in enumerate(L["cards"]):
            if in_view and rect.collidepoint(pos):
                if self.active == 0:
                    self.p1 = i
                else:
                    self.p2 = i
                self.active = 1 - self.active
                return None
        for slot, rect in enumerate(L["slots"]):
            if rect.collidepoint(pos):
                self.active = slot
                return None
        if L["brawl"].collidepoint(pos):
            return ("brawl",)
        return None

    # ----- drawing
    def _bars(self, screen, idx, x, y, w, color):
        n = len(self.info)
        rows = (("HP", "max_hp"), ("SPEED", "speed_mult"), ("TOUCH", "contact_damage"))
        for r, (label, key) in enumerate(rows):
            vmax = max(1e-9, max(self._stats(i).get(key, 0) for i in range(n)))
            v = self._stats(idx).get(key, 0)
            yy = y + r * 17
            text(screen, F_TINY, label, MUTED, "topleft", (x, yy), shadow=False)
            bar = pygame.Rect(x + 52, yy + 2, w - 52 - 54, 9)
            pygame.draw.rect(screen, (30, 32, 52), bar, border_radius=5)
            fw = int(bar.w * max(0.0, min(1.0, v / vmax)))
            if fw > 0:
                pygame.draw.rect(screen, color, pygame.Rect(bar.x, bar.y, fw, bar.h), border_radius=5)
            text(screen, F_TINY, se.fmt(v), TEXT, "topright", (x + w, yy), shadow=False)

    def _draw_pencil_btn(self, screen, center, rad, mouse, dirty):
        hov = math.hypot(mouse[0] - center[0], mouse[1] - center[1]) <= rad
        pygame.draw.circle(screen, (0, 0, 0), (center[0], center[1] + 2), rad)
        pygame.draw.circle(screen, (70, 80, 130) if hov else (38, 42, 74), center, rad)
        pygame.draw.circle(screen, GOLD if hov else (200, 205, 230), center, rad, 2)
        draw_pencil(screen, center[0], center[1], rad * 1.15)
        if dirty:
            pygame.draw.circle(screen, GOLD, (center[0] + rad - 3, center[1] - rad + 3), 5)
            pygame.draw.circle(screen, (0, 0, 0), (center[0] + rad - 3, center[1] - rad + 3), 5, 1)

    def draw(self, screen, mouse):
        self.t += 1
        L = self.layout()
        top = L["top"]
        pulse = 0.5 + 0.5 * math.sin(self.t * 0.1)

        text(screen, F_TITLE, "SELECT BRAWLERS", GOLD, "center", (CENTER_X, top + 24))
        text(screen, F_TINY, "Pick a fighter for the glowing slot  -  pencil edits stats  -  mouse wheel scrolls the list",
             MUTED, "center", (CENTER_X, top + 56), shadow=False)

        # --- the two player slots
        for slot, rect in enumerate(L["slots"]):
            idx = self._picked(slot)
            team = TEAM[slot]
            active = (self.active == slot)
            if active:
                rrect(screen, rect.inflate(10 + int(8 * pulse), 10 + int(8 * pulse)), (*team, int(35 + 45 * pulse)), 22)
            rrect(screen, rect, (18, 20, 38, 238), 18, (*team, 255), 4 if active else 2)
            tag = pygame.Rect(rect.x + 12, rect.y + 12, 92, 24)
            rrect(screen, tag, (*team, 255), 12)
            text(screen, F_TINY, f"PLAYER {slot + 1}", (255, 255, 255), "center", tag.center, shadow=False)

            av_r = 44
            c = (rect.centerx, rect.y + 96)
            pygame.draw.circle(screen, (*[int(v * 0.35) for v in team],), c, av_r + 9)
            pygame.draw.circle(screen, team, c, av_r + 6, 4)
            screen.blit(self._avatar(idx, av_r), (c[0] - av_r, c[1] - av_r))
            text(screen, F_NAME, self.info[idx]["name"], (255, 255, 255), "center", (rect.centerx, rect.y + 168))
            self._bars(screen, idx, rect.x + 16, rect.y + 184, rect.w - 32, team)
            
            if not IS_WEB:
                pc, pr = self._pencil(rect, 26, 18)
                self._draw_pencil_btn(screen, pc, pr, mouse, self.editors[idx].any_dirty())

        # --- roster
        text(screen, F_SMALL, "FIGHTERS", MUTED, "topleft", (L["left"] + 4, top + 340), shadow=False)
        view = L["view"]
        screen.set_clip(view)
        for i, rect in enumerate(L["cards"]):
            if rect.bottom < view.top or rect.top > view.bottom:
                continue
            hov = rect.collidepoint(mouse) and view.collidepoint(mouse)
            r = rect.move(0, -3) if hov else rect
            picks = [s for s in (0, 1) if self._picked(s) == i]
            border = (70, 76, 112)
            bw = 2
            if picks:
                border, bw = TEAM[picks[0]], 3
            rrect(screen, r, (34, 38, 66, 240) if hov else (22, 25, 46, 238), 14, (*border, 255), bw)
            av_r = 32
            screen.blit(self._avatar(i, av_r), (r.centerx - av_r, r.y + 14))
            pygame.draw.circle(screen, border, (r.centerx, r.y + 14 + av_r), av_r + 2, 2)
            text(screen, F_SMALL, fit(F_SMALL, self.info[i]["name"], r.w - 12), (255, 255, 255), "center",
                 (r.centerx, r.bottom - 17), shadow=True)
            for n_, s in enumerate(picks):                      # "1" / "2" badges show who picked this fighter
                b = (r.x + 16 + n_ * 26, r.y + 16)
                pygame.draw.circle(screen, TEAM[s], b, 11)
                pygame.draw.circle(screen, (255, 255, 255), b, 11, 2)
                text(screen, F_TINY, str(s + 1), (255, 255, 255), "center", b, shadow=False)
            
            if not IS_WEB:
                pc, pr = self._pencil(r, 20, 15)
                self._draw_pencil_btn(screen, pc, pr, mouse if view.collidepoint(mouse) else (-999, -999),
                                      self.editors[i].any_dirty())
        screen.set_clip(None)

        if L["max_scroll"] > 0:                            # scrollbar for the fighter list
            track = pygame.Rect(view.right - 5, view.top + 6, 4, view.h - 6)
            pygame.draw.rect(screen, (30, 33, 58), track, border_radius=2)
            th = max(30, int(track.h * (view.h - 6) / (view.h - 6 + L["max_scroll"])))
            ty = track.y + int((track.h - th) * self.scroll / L["max_scroll"])
            pygame.draw.rect(screen, (150, 158, 210), pygame.Rect(track.x, ty, track.w, th), border_radius=2)
            if self.scroll < L["max_scroll"]:
                text(screen, F_TINY, "scroll for more", MUTED, "midbottom", (view.centerx, view.bottom - 2), shadow=False)

        draw_button(screen, "BRAWL!", L["brawl"], (220, 150, 0), (255, 180, 0), L["brawl"].collidepoint(mouse))


# ---------------------------------------------------------------- stat editor screen
class StatEditorScreen:
    ROW_H = 52

    def __init__(self, roster_info, roster_classes, editors, get_avatar):
        self.info = roster_info
        self.classes = roster_classes
        self.editors = editors
        self.get_avatar = get_avatar
        self.idx = 0
        self.ed = editors[0]
        self.tab = 0
        self.scroll = 0
        self.edit = None           # (group, key, text) while typing a value
        self.hold = None           # +/- button being held: {"g","k","dir","t"}
        self.toast = ("", TEXT, 0)
        self.t = 0

    def open(self, idx):
        self.idx = idx
        self.ed = self.editors[idx]
        self.tab = 0
        self.scroll = 0
        self.edit = None
        self.hold = None
        self.toast = ("", TEXT, 0)

    # ----- layout
    def _layout(self):
        pw = min(SCREEN_WIDTH - 40, 780)
        ph = min(SCREEN_HEIGHT - 40, 860)
        panel = pygame.Rect(0, 0, pw, ph)
        panel.center = (CENTER_X, CENTER_Y)
        x0, maxx = panel.left + 20, panel.right - 20
        x, y = x0, panel.top + 96
        tabs = []
        for i, (g, _) in enumerate(self.ed.groups):
            w = F_SMALL.size(se.pretty(g))[0] + 34
            if x + w > maxx:
                x, y = x0, y + 36
            tabs.append((i, pygame.Rect(x, y, w, 30)))
            x += w + 8
        tabs_bottom = y + 30
        footer = pygame.Rect(panel.left + 20, panel.bottom - 70, pw - 40, 56)
        lst = pygame.Rect(panel.left + 20, tabs_bottom + 14, pw - 40, footer.top - 12 - (tabs_bottom + 14))
        entries = self.ed.groups[self.tab][1] if self.ed.groups else []
        max_scroll = max(0, len(entries) * self.ROW_H - lst.h)
        self.scroll = max(0, min(max_scroll, self.scroll))
        return {
            "panel": panel, "tabs": tabs, "list": lst, "footer": footer, "entries": entries, "max_scroll": max_scroll,
            "back": pygame.Rect(footer.left, footer.top + 6, 130, 44),
            "reset": pygame.Rect(footer.left + 142, footer.top + 6, 130, 44),
            "save": pygame.Rect(footer.right - 220, footer.top + 6, 220, 44),
        }

    def _row_rects(self, L, i):
        lst = L["list"]
        row = pygame.Rect(lst.left, lst.top + i * self.ROW_H - self.scroll, lst.w - 10, self.ROW_H - 6)
        plus = pygame.Rect(row.right - 12 - 34, row.centery - 17, 34, 34)
        box = pygame.Rect(plus.left - 6 - 130, row.centery - 17, 130, 34)
        minus = pygame.Rect(box.left - 6 - 34, row.centery - 17, 34, 34)
        switch = pygame.Rect(row.right - 12 - 74, row.centery - 15, 74, 30)
        return row, minus, box, plus, switch

    # ----- value changes
    def _nudge(self, g, k, direction):
        v = self.ed.get(g, k)
        if isinstance(v, bool):
            self.ed.set(g, k, not v)
            return
        nv = v + direction * se.step_for(v)
        if v >= 0:
            nv = max(0, nv)
        self.ed.set(g, k, int(round(nv)) if isinstance(v, int) else round(nv, 6))

    def _commit(self):
        if not self.edit:
            return
        g, k, s = self.edit
        self.edit = None
        try:
            self.ed.set(g, k, se.parse_value(s, self.ed.get(g, k)))
        except ValueError:
            self.toast = ("That is not a number - value unchanged", (255, 120, 120), 120)

    def _say(self, msg, color=(120, 255, 160)):
        self.toast = (msg, color, 150)

    # ----- input
    def handle_event(self, ev):
        """Returns 'close' when the editor should be left."""
        L = self._layout()
        if ev.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(L["max_scroll"], self.scroll - ev.y * 46))
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.hold = None
        elif ev.type == pygame.KEYDOWN:
            if self.edit:
                g, k, s = self.edit
                if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._commit()
                elif ev.key == pygame.K_ESCAPE:
                    self.edit = None
                elif ev.key == pygame.K_BACKSPACE:
                    self.edit = (g, k, s[:-1])
                elif ev.unicode and ev.unicode in "0123456789.-," and len(s) < 12:
                    self.edit = (g, k, s + ev.unicode.replace(",", "."))
            elif ev.key == pygame.K_ESCAPE:
                return "close"
            elif ev.key == pygame.K_DOWN:
                self.scroll = min(L["max_scroll"], self.scroll + 46)
            elif ev.key == pygame.K_UP:
                self.scroll = max(0, self.scroll - 46)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            return self._click(ev.pos, L)
        return None

    def _click(self, pos, L):
        if self.edit:                                   # clicking anywhere else finishes typing
            g, k, _ = self.edit
            keep = None
            for i, e in enumerate(L["entries"]):
                if (e.group, e.key) == (g, k) and self._row_rects(L, i)[2].collidepoint(pos):
                    keep = True
            if not keep:
                self._commit()

        if L["back"].collidepoint(pos):
            return "close"
        if L["reset"].collidepoint(pos):
            self.ed.reset()
            self.edit = None
            self._say("Back to the values saved in the file", (255, 220, 120))
            return None
        if L["save"].collidepoint(pos):
            try:
                n = self.ed.save()
                name = os.path.basename(self.ed.path or "file")
                self._say(f"Saved {n} change{'s' if n != 1 else ''} to {name}" if n else "Nothing to save - no changes")
            except OSError as e:
                self._say(f"Could not save: {e}", (255, 120, 120))
            return None
        for i, rect in L["tabs"]:
            if rect.collidepoint(pos):
                self.tab, self.scroll, self.edit = i, 0, None
                return None
        if L["list"].collidepoint(pos):
            for i, e in enumerate(L["entries"]):
                row, minus, box, plus, switch = self._row_rects(L, i)
                if not row.collidepoint(pos):
                    continue
                v = self.ed.get(e.group, e.key)
                if isinstance(v, bool):
                    if switch.collidepoint(pos):
                        self._nudge(e.group, e.key, 1)
                elif minus.collidepoint(pos):
                    self._nudge(e.group, e.key, -1)
                    self.hold = {"g": e.group, "k": e.key, "dir": -1, "t": 0}
                elif plus.collidepoint(pos):
                    self._nudge(e.group, e.key, 1)
                    self.hold = {"g": e.group, "k": e.key, "dir": 1, "t": 0}
                elif box.collidepoint(pos):
                    raw = repr(v) if isinstance(v, float) else str(v)
                    self.edit = (e.group, e.key, raw[:-2] if raw.endswith(".0") else raw)
                break
        return None

    # ----- drawing
    def draw(self, screen, mouse):
        self.t += 1
        L = self._layout()
        panel, lst, footer = L["panel"], L["list"], L["footer"]

        if self.hold:                                   # hold + / - to keep changing the value
            self.hold["t"] += 1
            if self.hold["t"] > 18 and self.hold["t"] % 3 == 0:
                self._nudge(self.hold["g"], self.hold["k"], self.hold["dir"])

        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 175))
        screen.blit(dim, (0, 0))

        pygame.draw.rect(screen, (0, 0, 0), panel.move(0, 6), border_radius=22)
        pygame.draw.rect(screen, PANEL, panel, border_radius=22)
        head = pygame.Rect(panel.x, panel.y, panel.w, 84)
        pygame.draw.rect(screen, (26, 30, 58), head, border_top_left_radius=22, border_top_right_radius=22)
        pygame.draw.line(screen, (60, 66, 108), (panel.x + 14, head.bottom), (panel.right - 14, head.bottom), 2)
        pygame.draw.rect(screen, GOLD, panel, 3, border_radius=22)

        # header: avatar + name
        av_r = 30
        c = (panel.x + 56, panel.y + 42)
        pygame.draw.circle(screen, GOLD, c, av_r + 4)
        screen.blit(self.get_avatar(self.info[self.idx], av_r), (c[0] - av_r, c[1] - av_r))
        text(screen, F_HEAD, f"{self.ed.title}  -  EDIT STATS", (255, 255, 255), "topleft", (panel.x + 108, panel.y + 14))
        fname = os.path.basename(self.ed.path or "")
        text(screen, F_TINY, f"Changes work right away in the next fight.  SAVE writes them into {fname}.",
             MUTED, "topleft", (panel.x + 108, panel.y + 52), shadow=False)

        # tabs
        for i, rect in L["tabs"]:
            g = self.ed.groups[i][0]
            sel = (i == self.tab)
            hov = rect.collidepoint(mouse)
            col = GOLD if sel else ((70, 76, 120) if hov else (36, 40, 72))
            pygame.draw.rect(screen, col, rect, border_radius=15)
            text(screen, F_SMALL, se.pretty(g), (20, 20, 30) if sel else TEXT, "center", rect.center, shadow=False)
            if any(self.ed.is_dirty(e.group, e.key) for e in self.ed.groups[i][1]):
                pygame.draw.circle(screen, (255, 120, 60) if sel else GOLD, (rect.right - 8, rect.top + 7), 4)

        # rows (clipped to the list area)
        screen.set_clip(lst)
        for i, e in enumerate(L["entries"]):
            row, minus, box, plus, switch = self._row_rects(L, i)
            if row.bottom < lst.top or row.top > lst.bottom:
                continue
            v = self.ed.get(e.group, e.key)
            dirty = self.ed.is_dirty(e.group, e.key)
            hov = row.collidepoint(mouse)
            rrect(screen, row, (34, 38, 68, 255) if hov else (24, 27, 50, 255) if i % 2 == 0 else (21, 23, 44, 255), 12)
            if dirty:
                pygame.draw.rect(screen, GOLD, pygame.Rect(row.x, row.y + 6, 4, row.h - 12), border_radius=2)
            text_w = minus.left - row.x - 30 if not isinstance(v, bool) else switch.left - row.x - 30
            text(screen, F_ROW, e.label, TEXT, "topleft", (row.x + 16, row.y + 7), shadow=False)
            if e.comment:
                text(screen, F_TINY, fit(F_TINY, e.comment, text_w), MUTED, "topleft", (row.x + 16, row.y + 28), shadow=False)

            if isinstance(v, bool):
                on = bool(v)
                pygame.draw.rect(screen, (60, 190, 100) if on else (80, 84, 110), switch, border_radius=15)
                kx = switch.right - 15 if on else switch.left + 15
                pygame.draw.circle(screen, (255, 255, 255), (kx, switch.centery), 11)
                text(screen, F_TINY, "ON" if on else "OFF", (255, 255, 255), "center",
                     (switch.left + 22, switch.centery) if on else (switch.right - 24, switch.centery), shadow=False)
            else:
                for rect, label in ((minus, "-"), (plus, "+")):
                    h = rect.collidepoint(mouse)
                    pygame.draw.rect(screen, (90, 100, 170) if h else (52, 58, 104), rect, border_radius=9)
                    pygame.draw.rect(screen, (170, 178, 220), rect, 2, border_radius=9)
                    text(screen, F_BTN, label, (255, 255, 255), "center", (rect.centerx, rect.centery - 1), shadow=False)
                editing = self.edit and (self.edit[0], self.edit[1]) == (e.group, e.key)
                pygame.draw.rect(screen, (12, 14, 28), box, border_radius=9)
                pygame.draw.rect(screen, GOLD if editing else ((120, 128, 190) if box.collidepoint(mouse) else (70, 76, 120)),
                                 box, 2, border_radius=9)
                if editing:
                    s = self.edit[2] + ("|" if (self.t // 25) % 2 == 0 else " ")
                    text(screen, F_ROW, s, GOLD, "center", box.center, shadow=False)
                else:
                    text(screen, F_ROW, se.fmt(v), GOLD if dirty else (255, 255, 255), "center", box.center, shadow=False)
        screen.set_clip(None)

        if L["max_scroll"] > 0:                           # scrollbar
            track = pygame.Rect(lst.right - 6, lst.top, 5, lst.h)
            pygame.draw.rect(screen, (30, 33, 58), track, border_radius=3)
            th = max(30, int(track.h * lst.h / (lst.h + L["max_scroll"])))
            ty = track.y + int((track.h - th) * self.scroll / L["max_scroll"])
            pygame.draw.rect(screen, (150, 158, 210), pygame.Rect(track.x, ty, track.w, th), border_radius=3)

        # footer
        n = self.ed.dirty_count()
        status = f"{n} unsaved change{'s' if n != 1 else ''}" if n else "All changes saved"
        text(screen, F_TINY, status, GOLD if n else MUTED, "midtop", (footer.centerx + 40, footer.top - 2), shadow=False)
        draw_button(screen, "BACK", L["back"], (70, 76, 120), (96, 104, 160), L["back"].collidepoint(mouse), F_NAME)
        draw_button(screen, "RESET", L["reset"], (150, 90, 40), (190, 120, 50), L["reset"].collidepoint(mouse), F_NAME)
        draw_button(screen, "SAVE TO FILE", L["save"], (40, 150, 70), (60, 190, 95), L["save"].collidepoint(mouse), F_NAME)

        msg, col, frames = self.toast
        if frames > 0:
            self.toast = (msg, col, frames - 1)
            alpha = int(255 * min(1.0, frames / 30))
            box = pygame.Rect(0, 0, F_ROW.size(msg)[0] + 40, 38)
            box.center = (panel.centerx, lst.bottom - 24)
            rrect(screen, box, (10, 12, 24, min(235, alpha)), 12, (*col, alpha), 2)
            text(screen, F_ROW, msg, col, "center", box.center, shadow=False, alpha=alpha)