import math
import random
import pygame
import sounds

from brawler import BaseBrawler
from config import ARENA_LEFT, ARENA_RIGHT, ARENA_TOP, ARENA_BOTTOM, find_asset

TAU = math.pi * 2

# ===================== EDIT STATS HERE =====================
STATS = {
    "name": "DYIRIX",
    "filename": "9.png",      # put your picture in the assets folder with this name
    "max_hp": 2500,
    "speed_mult": 0.7,        # multiplies the starting speed (speed stays constant)
    "radius": 30,
    "contact_damage": 5,      # damage when the two balls bump

    "max_super": 100,         # size of the super bar
    "super_per_hit": 10,      # super gained each time the vine hits (4 hits = super)
    "super_per_contact": 5,   # super gained when the balls bump
}

# Main attack: every second a spiked vine shoots out toward the enemy, swings in an arc and pulls back.
# The farther from DYIRIX the vine touches the enemy, the more it hurts.
ABILITY = {
    "swing_cooldown": 50,     # frames between two vine attacks (60 = 1 second)
    "damage_min": 10,         # damage when the enemy is hit close to DYIRIX
    "damage_max": 100,        # damage when the enemy is hit at the very tip of the vine
    "vine_length": 190,       # how far the vine reaches (pixels, measured from the ball's edge)
    "vine_thickness": 14,     # hitbox thickness of the vine
    "extend_frames": 14,      # how long the vine takes to shoot out
    "swing_frames": 20,       # how long the swing takes
    "retract_frames": 12,     # how long the vine takes to pull back
    "swing_arc": 120,         # how wide the swing is (degrees)
    "swing_only_in_range": True,   # OFF = attacks every cooldown no matter what, ON = only when the enemy is within reach
}

# Super: 2 hooks fly out, stick into the enemy and pump poison into it.
# If the enemy has less than "execute_hp" health left when the hooks land, it is split in two and stays at 1 hp,
# then dies when "doom_frames" are over.
ULTIMATE = {
    "hook_count": 5,          # how many hooks
    "appear_frames": 12,      # hooks grow out of DYIRIX over this many frames before they are shot
    "hook_speed": 17.0,       # pixels per frame
    "hook_turn": 0.18,        # how much a flying hook steers toward the enemy (radians per frame)
    "hook_spread": 70,        # angle (degrees) at which the two hooks leave DYIRIX's sides

    "poison_damage": 400,     # total poison damage
    "poison_frames": 60,     # how long the poison lasts (120 = 2 seconds)
    "poison_ticks": 10,       # in how many pieces the poison damage is dealt

    "execute_hp": 400,        # enemy with LESS hp than this when the hooks land is split in two
    "doom_frames": 60,       # frames the split enemy survives at 1 hp before dying (120 = 2 seconds)
}
# ===========================================================

VINE_DARK = (18, 62, 32)
VINE = (66, 186, 78)
VINE_LIGHT = (160, 240, 130)
THORN = (232, 238, 205)
POISON = (120, 255, 70)
HOOK_METAL = (190, 205, 190)

_avatar_cache = {}


def make_avatar(radius):
    """Green thorny ball with slit eyes (used when there is no 9.png)."""
    if radius in _avatar_cache:
        return _avatar_cache[radius]
    S = 256
    c = S // 2
    big = pygame.Surface((S, S), pygame.SRCALPHA)
    for i in range(12):                                   # thorns poking out of the ball
        a = i * TAU / 12
        pts = [(c + math.cos(a - 0.17) * c * 0.78, c + math.sin(a - 0.17) * c * 0.78),
               (c + math.cos(a) * c * 0.99, c + math.sin(a) * c * 0.99),
               (c + math.cos(a + 0.17) * c * 0.78, c + math.sin(a + 0.17) * c * 0.78)]
        pygame.draw.polygon(big, (225, 232, 195), pts)
        pygame.draw.polygon(big, (20, 60, 30), pts, 3)
    body = pygame.Surface((S, S), pygame.SRCALPHA)
    for i in range(40):
        t = i / 39
        col = (int(18 + 90 * t), int(70 + 150 * t), int(30 + 70 * t))
        pygame.draw.circle(body, col, (c, c), max(1, int(c * 0.8 * (1 - t * 0.9))))
    big.blit(body, (0, 0))
    for sx in (-1, 1):
        eye = [(c + sx * c * 0.10, c + c * 0.04), (c + sx * c * 0.46, c - c * 0.14),
               (c + sx * c * 0.40, c + c * 0.10), (c + sx * c * 0.14, c + c * 0.14)]
        pygame.draw.polygon(big, (240, 255, 120), eye)
        pygame.draw.ellipse(big, (10, 30, 14), pygame.Rect(int(c + sx * c * 0.27 - 4), int(c - c * 0.02), 8, int(c * 0.2)))
    out = pygame.transform.smoothscale(big, (radius * 2, radius * 2))
    _avatar_cache[radius] = out
    return out


def _turn(cur, want, step):
    d = (want - cur + math.pi) % TAU - math.pi
    return cur + max(-step, min(step, d))


def _closest_on_segment(px, py, ax, ay, bx, by):
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby or 1.0
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / denom))
    return ax + abx * t, ay + aby * t


def _burst(x, y, radius, frames, color):
    return {"x": x, "y": y, "radius": radius, "timer": frames, "max": frames, "color": color,
            "sparks": [(random.uniform(0, TAU), random.uniform(0.5, 1.0), random.uniform(2.5, 5.0)) for _ in range(10)]}


def _glow_dot(screen, x, y, r, color):
    size = int(r * 4)
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(layer, (*color, 60), (size // 2, size // 2), int(r * 2))
    pygame.draw.circle(layer, (*color, 255), (size // 2, size // 2), max(1, int(r)))
    pygame.draw.circle(layer, (255, 255, 255, 200), (size // 2, size // 2), max(1, int(r * 0.4)))
    screen.blit(layer, (int(x - size // 2), int(y - size // 2)))


def _draw_chain(screen, a, b, t):
    """A thorny vine between two points (the rope of a hook)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / d, dx / d
    n = max(4, int(d / 18))
    pts = []
    for i in range(n + 1):
        s = i / n
        w = math.sin(s * 9 - t * 0.3) * 3 * math.sin(s * math.pi)
        pts.append((a[0] + dx * s + nx * w, a[1] + dy * s + ny * w))
    pygame.draw.lines(screen, VINE_DARK, False, pts, 8)
    pygame.draw.lines(screen, VINE, False, pts, 4)
    for i in range(1, n):
        side = 1 if i % 2 else -1
        px, py = pts[i]
        tip = (px + nx * side * 7 + dx / d * 3, py + ny * side * 7 + dy / d * 3)
        base1 = (px - dx / d * 2, py - dy / d * 2)
        base2 = (px + dx / d * 2, py + dy / d * 2)
        pygame.draw.polygon(screen, THORN, [base1, tip, base2])


def _draw_hook(screen, x, y, angle, scale=1.0):
    ca, sa = math.cos(angle), math.sin(angle)

    def P(f, s):                      # f = forward, s = sideways
        return (x + (ca * f - sa * s) * scale, y + (sa * f + ca * s) * scale)

    tip = P(15, 0)
    barb_l = P(-4, -10)
    barb_r = P(-4, 10)
    pygame.draw.line(screen, (30, 50, 36), P(0, 0), barb_l, 6)
    pygame.draw.line(screen, (30, 50, 36), P(0, 0), barb_r, 6)
    pygame.draw.line(screen, (30, 50, 36), P(0, 0), tip, 6)
    pygame.draw.line(screen, HOOK_METAL, P(0, 0), barb_l, 3)
    pygame.draw.line(screen, HOOK_METAL, P(0, 0), barb_r, 3)
    pygame.draw.line(screen, HOOK_METAL, P(0, 0), tip, 3)
    pygame.draw.circle(screen, (30, 50, 36), (int(x), int(y)), max(2, int(7 * scale)))
    pygame.draw.circle(screen, POISON, (int(x), int(y)), max(1, int(4.5 * scale)))


# ======================================================================
#  SUPER: the poison hooks
# ======================================================================
class Hook:
    def __init__(self, owner, angle_from_target, side):
        self.side = side
        self.angle = angle_from_target
        self.x, self.y = owner.body.position.x, owner.body.position.y
        self.attached = False
        self.off = (0.0, 0.0)
        self.flight = 0
        self.back = 0.0          # 0..1 while the hook is pulled back to DYIRIX at the end


class PoisonHooks:
    """One object that owns the 2 hooks of one super AND the poison / split that follows.
    (It lives in the projectile list, so it keeps working even if DYIRIX gets stunned.)"""

    def __init__(self, owner, target):
        U = ULTIMATE
        self.owner = owner
        self.target = target
        self.t = 0
        self.pt = 0                        # frames inside the current phase
        self.phase = "appear"              # appear -> fly -> poison / doom -> release
        self.active = True
        ox, oy = owner.body.position.x, owner.body.position.y
        base = math.atan2(target.body.position.y - oy, target.body.position.x - ox)
        n = max(1, int(U["hook_count"]))
        self.hooks = []
        for i in range(n):
            side = (i - (n - 1) / 2) * 2 if n > 1 else 1
            side = max(-1, min(1, side))
            self.hooks.append(Hook(owner, base + side * math.radians(U["hook_spread"]), side))
        self.orig_surface = None
        self.halves = None
        self.cut_angle = random.uniform(0, math.pi)

    # ---------- helpers ----------
    def _owner(self):
        return self.owner.body.position.x, self.owner.body.position.y

    def _enter(self, phase):
        self.phase = phase
        self.pt = 0

    def _start_poison(self, explosions):
        U = ULTIMATE
        t = self.target
        tx, ty = t.body.position.x, t.body.position.y
        explosions.append(_burst(tx, ty, 60, 18, POISON))
        sounds.play("super")
        if t.hp < U["execute_hp"]:
            self._enter("doom")
            t.hp = 1
            t.popups.append(("SPLIT!", POISON))
            self.orig_surface = t.surface
            self.halves = self._make_halves(t.surface)
            t.surface = pygame.Surface(t.surface.get_size(), pygame.SRCALPHA)   # hide the whole ball, we draw 2 halves
        else:
            self._enter("poison")
            t.popups.append(("POISONED!", POISON))

    def _make_halves(self, surf):
        w, h = surf.get_size()
        c = (w / 2, h / 2)
        a = self.cut_angle
        u = (math.cos(a), math.sin(a))
        n = (-u[1], u[0])
        K = max(w, h) * 2
        out = []
        for sign in (1, -1):
            half = surf.copy()
            mask = pygame.Surface((w, h), pygame.SRCALPHA)
            pts = [(c[0] + u[0] * K, c[1] + u[1] * K), (c[0] - u[0] * K, c[1] - u[1] * K),
                   (c[0] - u[0] * K + n[0] * sign * K, c[1] - u[1] * K + n[1] * sign * K),
                   (c[0] + u[0] * K + n[0] * sign * K, c[1] + u[1] * K + n[1] * sign * K)]
            pygame.draw.polygon(mask, (255, 255, 255, 255), pts)
            half.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            out.append((half, (n[0] * sign, n[1] * sign)))
        return out

    def _restore(self):
        if self.orig_surface is not None:
            self.target.surface = self.orig_surface
            self.orig_surface = None

    # ---------- per frame ----------
    def update(self, explosions):
        if not self.active:
            return
        U = ULTIMATE
        t = self.target
        self.t += 1
        self.pt += 1
        ox, oy = self._owner()
        tx, ty = t.body.position.x, t.body.position.y

        if self.phase == "appear":
            if self.pt >= U["appear_frames"]:
                self._enter("fly")
                sounds.play("sword")
            else:
                grow = self.pt / max(1, U["appear_frames"])
                for h in self.hooks:
                    a = h.angle
                    h.x = ox + math.cos(a) * (self.owner.radius + 8 + 14 * grow)
                    h.y = oy + math.sin(a) * (self.owner.radius + 8 + 14 * grow)

        elif self.phase == "fly":
            for h in self.hooks:
                if h.attached:
                    h.x, h.y = tx + h.off[0], ty + h.off[1]
                    continue
                h.flight += 1
                want = math.atan2(ty - h.y, tx - h.x)
                h.angle = _turn(h.angle, want, U["hook_turn"])
                h.x += math.cos(h.angle) * U["hook_speed"]
                h.y += math.sin(h.angle) * U["hook_speed"]
                if math.hypot(tx - h.x, ty - h.y) <= t.radius + 4 or h.flight > 150:
                    h.attached = True
                    d = math.hypot(h.x - tx, h.y - ty) or 1.0
                    k = min(1.0, (t.radius - 2) / d)
                    h.off = ((h.x - tx) * k, (h.y - ty) * k)
                    explosions.append(_burst(h.x, h.y, 26, 12, POISON))
                    sounds.play("hit")
            if all(h.attached for h in self.hooks):
                self._start_poison(explosions)

        elif self.phase in ("poison", "doom"):
            for h in self.hooks:
                h.x, h.y = tx + h.off[0], ty + h.off[1]
            if self.phase == "poison":
                if t.hp <= 0:
                    self._enter("release")
                else:
                    every = max(1, U["poison_frames"] // max(1, U["poison_ticks"]))
                    if self.pt % every == 0:
                        t.hp -= U["poison_damage"] / max(1, U["poison_ticks"])
                        explosions.append(_burst(tx, ty, 30, 10, POISON))
                    if self.pt >= U["poison_frames"]:
                        self._enter("release")
            else:                                         # doom: the enemy cannot die until the time is over
                if self.pt < U["doom_frames"]:
                    t.hp = 1
                else:
                    t.hp = 0
                    self._restore()
                    explosions.append(_burst(tx, ty, 80, 22, POISON))
                    sounds.play("boom")
                    self._enter("release")

        elif self.phase == "release":
            for h in self.hooks:
                h.back = min(1.0, h.back + 1 / 12)
                h.x += (ox - h.x) * 0.25
                h.y += (oy - h.y) * 0.25
            if self.pt >= 12:
                self._restore()
                self.active = False

    # ---------- drawing ----------
    def draw(self, screen):
        if not self.active:
            return
        t = self.target
        ox, oy = self._owner()
        tx, ty = int(t.body.position.x), int(t.body.position.y)
        poisoned = self.phase in ("poison", "doom")

        if poisoned and (t.hp > 0 or self.phase == "doom"):
            pulse = 0.5 + 0.5 * math.sin(self.t * 0.25)
            ring = t.radius + 8
            c = ring + 16
            layer = pygame.Surface((c * 2, c * 2), pygame.SRCALPHA)
            pygame.draw.circle(layer, (*POISON, int(50 + 40 * pulse)), (c, c), ring + 6)
            pygame.draw.circle(layer, (*POISON, 200), (c, c), ring, 2)
            screen.blit(layer, (tx - c, ty - c))
            for i in range(6):                              # bubbles rising off the enemy
                k = ((self.t * 0.03) + i / 6) % 1.0
                bx = tx + math.sin(i * 2.3 + self.t * 0.05) * t.radius * 0.8
                by = ty + t.radius - k * t.radius * 2.6
                pygame.draw.circle(screen, POISON, (int(bx), int(by)), max(2, int(5 * (1 - k))), 2)

        if self.phase == "doom" and self.halves:
            g = min(16, 3 + self.pt * 0.3)
            jit = 1.5 if self.pt < ULTIMATE["doom_frames"] - 25 else 3.5
            u = (math.cos(self.cut_angle), math.sin(self.cut_angle))
            r = t.radius + 6
            gap = pygame.Surface((int(r * 2 + 20), int(r * 2 + 20)), pygame.SRCALPHA)
            gc = gap.get_width() // 2
            pygame.draw.line(gap, (*POISON, 200), (gc - u[0] * r, gc - u[1] * r), (gc + u[0] * r, gc + u[1] * r),
                             max(2, int(g * 1.6)))
            screen.blit(gap, (tx - gc, ty - gc))
            for half, nv in self.halves:
                w, h = half.get_size()
                px = tx - w // 2 + nv[0] * g + random.uniform(-jit, jit)
                py = ty - h // 2 + nv[1] * g + random.uniform(-jit, jit)
                screen.blit(half, (int(px), int(py)))

        for h in self.hooks:
            end = (h.x, h.y)
            if self.phase == "appear":
                _draw_hook(screen, h.x, h.y, h.angle, scale=self.pt / max(1, ULTIMATE["appear_frames"]))
                continue
            dx, dy = end[0] - ox, end[1] - oy
            d = math.hypot(dx, dy) or 1.0
            start = (ox + dx / d * (self.owner.radius - 2), oy + dy / d * (self.owner.radius - 2))
            _draw_chain(screen, start, end, self.t)
            if poisoned:                                    # poison drops travelling along the rope into the enemy
                for k in range(4):
                    s = ((self.t * 0.04) + k / 4) % 1.0
                    _glow_dot(screen, start[0] + (end[0] - start[0]) * s, start[1] + (end[1] - start[1]) * s, 4, POISON)
            _draw_hook(screen, h.x, h.y, h.angle)


# ======================================================================
#  DYIRIX himself
# ======================================================================
class Dyirix(BaseBrawler):
    def __init__(self, space, pos, velocity):
        super().__init__(space, pos, velocity, STATS)
        if not find_asset(STATS["filename"]):          # no 9.png -> built-in design
            self.surface = make_avatar(self.radius)
        self.t = 0
        self.vine_cd = 0
        self.vine_state = "idle"     # idle -> extend -> swing -> retract
        self.vine_t = 0
        self.vine_angle = math.atan2(velocity[1], velocity[0])
        self.vine_len = 0.0
        self.vine_bend = 0.0
        self.vine_hit = False
        self.swing_sign = 1          # +1 / -1: the swing direction alternates every time
        self.swing_a0 = 0.0

    # ---------- geometry ----------
    def _vine_points(self):
        cx, cy = self.body.position.x, self.body.position.y
        n = 14
        x = cx + math.cos(self.vine_angle) * (self.radius - 2)
        y = cy + math.sin(self.vine_angle) * (self.radius - 2)
        pts = [(x, y)]
        ds = self.vine_len / n
        for i in range(1, n + 1):
            s = i / n
            h = self.vine_angle - self.swing_sign * self.vine_bend * s + math.sin(s * 8 - self.t * 0.5) * 0.12 * s
            x += math.cos(h) * ds
            y += math.sin(h) * ds
            pts.append((x, y))
        return pts

    def _spark(self, x, y, effects):
        angles = [random.uniform(0, TAU) for _ in range(7)]

        def draw(screen):
            for a in angles:
                ln = random.uniform(16, 32)
                end = (x + math.cos(a) * ln, y + math.sin(a) * ln)
                pygame.draw.line(screen, VINE, (x, y), end, 3)
                pygame.draw.line(screen, (235, 255, 220), (x, y), end, 1)
        effects.append({"x": x, "y": y, "sprite": None, "timer": 12, "draw": draw})

    # ---------- vine ----------
    def _start_vine(self, base):
        A = ABILITY
        self.vine_state = "extend"
        self.vine_t = 0
        self.vine_hit = False
        self.swing_a0 = base - self.swing_sign * math.radians(A["swing_arc"]) / 2
        self.vine_angle = self.swing_a0
        self.vine_cd = A["swing_cooldown"]
        sounds.play("sword")

    def _check_hit(self, target, effects):
        A = ABILITY
        pts = self._vine_points()
        tx, ty = target.body.position.x, target.body.position.y
        best = None
        for i in range(len(pts) - 1):
            qx, qy = _closest_on_segment(tx, ty, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
            d = math.hypot(tx - qx, ty - qy)
            if best is None or d < best[0]:
                best = (d, qx, qy)
        if best and best[0] <= target.radius + A["vine_thickness"] / 2:
            _, qx, qy = best
            far = math.hypot(qx - self.body.position.x, qy - self.body.position.y)      # how far from DYIRIX the vine touched
            lo = self.radius + target.radius                         # closest possible touch = damage_min
            frac = max(0.0, min(1.0, (far - lo) / max(1.0, self.radius + A["vine_length"] - lo)))   # vine tip = damage_max
            dmg = A["damage_min"] + (A["damage_max"] - A["damage_min"]) * frac
            self.vine_hit = True
            target.hp -= dmg
            self.add_super(self.super_per_hit)
            self._spark(qx, qy, effects)
            sounds.play("hit")

    def _update_vine(self, target, effects):
        A = ABILITY
        self.vine_t += 1
        arc = math.radians(A["swing_arc"])
        if self.vine_state == "extend":
            p = min(1.0, self.vine_t / max(1, A["extend_frames"]))
            self.vine_len = A["vine_length"] * (1 - (1 - p) ** 2)
            self.vine_bend = 0.1
            if p >= 1.0:
                self.vine_state, self.vine_t = "swing", 0
        elif self.vine_state == "swing":
            p = min(1.0, self.vine_t / max(1, A["swing_frames"]))
            ease = p * p * (3 - 2 * p)
            self.vine_len = A["vine_length"]
            self.vine_angle = self.swing_a0 + self.swing_sign * arc * ease
            self.vine_bend = 0.15 + 1.0 * 4 * p * (1 - p)           # the tip lags behind the swing like a whip
            if p >= 1.0:
                self.vine_state, self.vine_t = "retract", 0
        elif self.vine_state == "retract":
            p = min(1.0, self.vine_t / max(1, A["retract_frames"]))
            self.vine_len = A["vine_length"] * (1 - p * p)
            self.vine_bend = 0.35 * (1 - p)
            if p >= 1.0:
                self.vine_state = "idle"
                self.vine_len = 0.0
                self.swing_sign = -self.swing_sign
        if target is not None and not self.vine_hit and self.vine_len > 4:
            self._check_hit(target, effects)

    # ---------- super ----------
    def _ultimate(self, target, projectiles):
        projectiles.append(PoisonHooks(self, target))
        sounds.play("super")

    # ---------- update ----------
    def update_abilities(self, target, projectiles, scratch_effects):
        if self.hp <= 0:
            return
        A = ABILITY
        self.t += 1
        alive = target is not None and target.hp > 0

        if self.vine_cd > 0:
            self.vine_cd -= 1

        if self.vine_state != "idle":
            self._update_vine(target if alive else None, scratch_effects)
        else:
            cx, cy = self.body.position.x, self.body.position.y
            if alive:
                base = math.atan2(target.body.position.y - cy, target.body.position.x - cx)
            else:
                vx, vy = self.body.velocity
                base = math.atan2(vy, vx) if (vx or vy) else self.vine_angle
            if self.vine_cd <= 0 and alive:
                reach = self.radius + A["vine_length"] + target.radius
                dist = math.hypot(target.body.position.x - cx, target.body.position.y - cy)
                if dist <= reach or not A["swing_only_in_range"]:
                    self._start_vine(base)

        if alive and self.super_charge >= self.max_super:
            self.super_charge = 0
            self.trigger_super()
            self._ultimate(target, projectiles)

    # ---------- drawing ----------
    def draw(self, screen):
        if self.hp <= 0:
            return
        x, y = self.body.position.x, self.body.position.y
        r = self.radius
        for i in range(10):                              # little thorns around the ball
            a = i * TAU / 10 + self.t * 0.01
            pts = [(x + math.cos(a - 0.14) * (r - 2), y + math.sin(a - 0.14) * (r - 2)),
                   (x + math.cos(a) * (r + 7), y + math.sin(a) * (r + 7)),
                   (x + math.cos(a + 0.14) * (r - 2), y + math.sin(a + 0.14) * (r - 2))]
            pygame.draw.polygon(screen, THORN, pts)
            pygame.draw.polygon(screen, VINE_DARK, pts, 1)
        super().draw(screen)

        if self.vine_len > 1:
            pts = self._vine_points()
            n = len(pts) - 1
            for i in range(n):                           # thick at the base, thin at the tip
                w = max(4, int(11 - 6 * i / n))
                pygame.draw.line(screen, VINE_DARK, pts[i], pts[i + 1], w + 4)
            for i in range(n):
                w = max(4, int(11 - 6 * i / n))
                pygame.draw.line(screen, VINE, pts[i], pts[i + 1], w)
                pygame.draw.line(screen, VINE_LIGHT, pts[i], pts[i + 1], max(1, w // 3))
            for i in range(1, n):                        # spikes, alternating sides
                ax, ay = pts[i - 1]
                bx, by = pts[i + 1]
                d = math.hypot(bx - ax, by - ay) or 1.0
                fx, fy = (bx - ax) / d, (by - ay) / d
                nx, ny = -fy, fx
                side = 1 if i % 2 else -1
                ln = 11 - 5 * i / n
                px, py = pts[i]
                spike = [(px - fx * 3, py - fy * 3), (px + nx * side * ln + fx * 4, py + ny * side * ln + fy * 4),
                         (px + fx * 3, py + fy * 3)]
                pygame.draw.polygon(screen, THORN, spike)
                pygame.draw.polygon(screen, VINE_DARK, spike, 1)
            ex, ey = pts[-1]
            px, py = pts[-2]
            d = math.hypot(ex - px, ey - py) or 1.0
            fx, fy = (ex - px) / d, (ey - py) / d
            tip = [(ex - fy * 4, ey + fx * 4), (ex + fx * 15, ey + fy * 15), (ex + fy * 4, ey - fx * 4)]
            pygame.draw.polygon(screen, THORN, tip)
            pygame.draw.polygon(screen, VINE_DARK, tip, 2)
