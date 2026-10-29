import math
import random
import pygame
import sounds

from brawler import BaseBrawler
from config import ARENA_LEFT, ARENA_RIGHT, ARENA_TOP, ARENA_BOTTOM, find_asset, load_sprite

TAU = math.pi * 2

# ===================== EDIT STATS HERE =====================
STATS = {
    "name": "SPICY",
    "filename": "7.png",      # put your picture in the assets folder with this name
    "max_hp": 2600,
    "speed_mult": 1.0,        # multiplies the starting speed (speed stays constant)
    "radius": 30,
    "contact_damage": 5,      # damage when the two balls bump

    "max_super": 100,         # size of the super bar
    "super_per_hit": 10,       # super gained by the slice and by every spin tick that hits
    "super_per_contact": 5,   # super gained when the balls bump
}

# Combo: slice -> throw the cosmic sword -> it spins on the spot -> it flies back -> rest -> repeat.
ABILITY = {
    "combo_cooldown": 120,    # frames of rest after the sword is back (120 = 2 seconds)

    "slice_damage": 150,      # damage of the slice (only if the enemy is in range)
    "slice_range": 150,       # how far the slice reaches
    "slice_arc": 160,         # (degrees) size of the swoosh, visual only
    "slice_frames": 14,       # how long the slice lasts before the sword is thrown

    "sword_length": 100,      # size of the sword picture / drawing
    "throw_speed": 15.0,      # pixels per frame going out
    "return_speed": 17.0,     # pixels per frame coming back
    "spin_frames": 120,       # how long the sword spins (120 = 2 seconds)
    "spin_damage_per_sec": 150,  # damage per second while the enemy is touching the spinning sword
    "spin_radius": 60,        # reach of the spinning sword
    "spin_speed": 0.5,        # how fast the sword turns (radians per frame)
    "spin_follow": 1.0,       # pixels per frame the spinning sword drifts toward the enemy (0 = stays put)
    "spin_super_every": 30,   # frames of spin-hitting needed for one super gain
}

# Super: a BIG cosmic slash across the whole arena (after a short warning) that leaves a cosmic line.
ULTIMATE = {
    "warn_frames": 45,        # the warning before the slash lands (60 = 1 second)
    "slash_damage": 1300,     # damage if the enemy touches the line when the slash lands
    "slash_width": 50,        # thickness of the line
    "flash_frames": 12,       # white flash of the slash itself

    "line_duration": 300,     # how long the cosmic line stays (300 = 5 seconds)
    "line_fade_frames": 40,   # the line fades out over this many frames at the end

    "cosmic_super_slow": 0.3, # enemy in the line charges its super this much slower (0.3 = 30%)
    "cosmic_linger": 60,      # the cosmic effect lasts this many frames after leaving the line
}
# ===========================================================

VIOLET = (170, 110, 255)
DEEP = (60, 25, 120)
GLOW = (190, 130, 255)

_avatar_cache = {}
_sprite_cache = {}


def _sword_sprite(length):
    """Optional picture: assets/spicysword.png (sword pointing RIGHT, handle in the middle of the image)."""
    if length not in _sprite_cache:
        _sprite_cache[length] = load_sprite("spicysword", int(length * 2), int(length * 2))
    return _sprite_cache[length]


def make_avatar(radius):
    """Cosmic ball with stars and a little sword (used when there is no 7.png)."""
    if radius in _avatar_cache:
        return _avatar_cache[radius]
    S = 256
    c = S // 2
    big = pygame.Surface((S, S), pygame.SRCALPHA)
    for i in range(40):
        t = i / 39
        col = (int(20 + 90 * (1 - t)), int(8 + 40 * (1 - t)), int(50 + 140 * (1 - t)))
        pygame.draw.circle(big, col, (c, c), max(1, int(c * (1 - t * 0.85))))
    rng = random.Random(7)
    for _ in range(40):
        a, d = rng.uniform(0, TAU), rng.uniform(0, c * 0.95)
        pygame.draw.circle(big, (255, 255, 255), (int(c + math.cos(a) * d), int(c + math.sin(a) * d)), rng.choice((1, 2, 2, 3)))
    pygame.draw.line(big, (235, 215, 255), (c - 70, c + 70), (c + 70, c - 70), 14)
    pygame.draw.line(big, (150, 90, 235), (c - 70, c + 70), (c + 70, c - 70), 8)
    pygame.draw.line(big, (230, 200, 255), (c - 62, c + 30), (c - 30, c + 62), 10)
    mask = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (c, c), c)
    big.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    out = pygame.transform.smoothscale(big, (radius * 2, radius * 2))
    _avatar_cache[radius] = out
    return out


def draw_blade(screen, hx, hy, ang, length, t=0):
    """The cosmic sword. (hx, hy) is the handle, the blade points along `ang`."""
    sprite = _sword_sprite(length)
    if sprite:
        rot = pygame.transform.rotate(sprite, -math.degrees(ang))
        screen.blit(rot, rot.get_rect(center=(int(hx), int(hy))))
        return
    ca, sa = math.cos(ang), math.sin(ang)
    nx, ny = -sa, ca
    w = length * 0.09

    def P(f, off):
        return (hx + ca * length * f + nx * w * off, hy + sa * length * f + ny * w * off)
    pygame.draw.line(screen, (90, 45, 170), P(0.1, 0), P(1.0, 0), max(4, int(w * 3.4)))      # glow
    blade = [P(0.12, -1), P(0.86, -1), P(1.0, 0), P(0.86, 1), P(0.12, 1)]
    pygame.draw.polygon(screen, (120, 65, 215), blade)
    pygame.draw.polygon(screen, (235, 215, 255), blade, 2)
    pygame.draw.line(screen, (255, 255, 255), P(0.14, 0), P(0.94, 0), 2)
    for i in range(5):                                                                        # stars on the blade
        if (t // 5 + i) % 3:
            p = P(0.25 + 0.14 * i, 0.45 if i % 2 else -0.45)
            pygame.draw.circle(screen, (255, 255, 255), (int(p[0]), int(p[1])), 2 if (t // 4 + i) % 2 else 1)
    pygame.draw.line(screen, (230, 200, 255), P(0.1, -2.7), P(0.1, 2.7), 4)                   # guard
    pygame.draw.line(screen, (60, 30, 110), P(-0.16, 0), P(0.1, 0), 5)                        # grip
    pygame.draw.circle(screen, (230, 200, 255), (int(P(-0.19, 0)[0]), int(P(-0.19, 0)[1])), 4)


def _closest_on_segment(px, py, ax, ay, bx, by):
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby or 1.0
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / denom))
    return ax + abx * t, ay + aby * t


def _to_wall(cx, cy, ux, uy):
    tmax = 10 ** 6
    if ux > 1e-6:
        tmax = min(tmax, (ARENA_RIGHT - cx) / ux)
    elif ux < -1e-6:
        tmax = min(tmax, (ARENA_LEFT - cx) / ux)
    if uy > 1e-6:
        tmax = min(tmax, (ARENA_BOTTOM - cy) / uy)
    elif uy < -1e-6:
        tmax = min(tmax, (ARENA_TOP - cy) / uy)
    return cx + ux * tmax, cy + uy * tmax


def _clamp(x, y, m):
    return max(ARENA_LEFT + m, min(ARENA_RIGHT - m, x)), max(ARENA_TOP + m, min(ARENA_BOTTOM - m, y))


class CosmicSword:
    """Thrown sword: flies to where the enemy was, spins there (hurting the enemy), then flies back."""

    def __init__(self, owner, target, pos, angle):
        A = ABILITY
        self.owner = owner
        self.target = target
        self.x, self.y = pos
        tp = target.body.position
        self.dest = _clamp(tp.x, tp.y, A["spin_radius"] * 0.6)
        self.state = "out"            # out -> spin -> back
        self.rot = angle
        self.timer = 0
        self.t = 0
        self.dmg_accum = 0.0
        self.hit_frames = 0
        self.active = True

    def update(self, explosions):
        if not self.active:
            return
        A = ABILITY
        o, t = self.owner, self.target
        if o.hp <= 0:
            self.active = False
            return
        self.t += 1
        alive = t is not None and t.hp > 0

        if self.state == "out":
            self.rot += A["spin_speed"] * 1.5
            dx, dy = self.dest[0] - self.x, self.dest[1] - self.y
            d = math.hypot(dx, dy)
            if d <= A["throw_speed"]:
                self.x, self.y = self.dest
                self.state, self.timer = "spin", A["spin_frames"]
                sounds.play("dash")
            else:
                self.x += dx / d * A["throw_speed"]
                self.y += dy / d * A["throw_speed"]

        elif self.state == "spin":
            self.rot += A["spin_speed"]
            self.timer -= 1
            if alive:
                tp = t.body.position
                dx, dy = tp.x - self.x, tp.y - self.y
                d = math.hypot(dx, dy)
                if d > 1e-6 and A["spin_follow"] > 0:
                    self.x += dx / d * min(d, A["spin_follow"])
                    self.y += dy / d * min(d, A["spin_follow"])
                    self.x, self.y = _clamp(self.x, self.y, A["spin_radius"] * 0.6)
                if math.hypot(tp.x - self.x, tp.y - self.y) <= A["spin_radius"] + t.radius:
                    self.dmg_accum += A["spin_damage_per_sec"] / 60.0
                    whole = int(self.dmg_accum)
                    self.dmg_accum -= whole
                    t.hp -= whole
                    self.hit_frames += 1
                    if self.hit_frames % A["spin_super_every"] == 1:
                        o.add_super(o.super_per_hit)
                        sounds.play("scratch")
            if self.timer <= 0 or not alive:
                self.state = "back"

        else:                                         # back
            self.rot += A["spin_speed"] * 1.5
            ox, oy = o.body.position.x, o.body.position.y
            dx, dy = ox - self.x, oy - self.y
            d = math.hypot(dx, dy) or 1.0
            if d <= o.radius + 20 or d <= A["return_speed"]:
                self.active = False                   # caught
                return
            self.x += dx / d * A["return_speed"]
            self.y += dy / d * A["return_speed"]

    def draw(self, screen):
        if not self.active:
            return
        A = ABILITY
        L = A["sword_length"]
        if self.state == "spin":                      # spinning ring of cosmic light
            R = A["spin_radius"]
            ring = pygame.Surface((R * 2 + 8, R * 2 + 8), pygame.SRCALPHA)
            c = R + 4
            pygame.draw.circle(ring, (*VIOLET, 45), (c, c), R)
            pygame.draw.circle(ring, (*GLOW, 120), (c, c), R, 3)
            screen.blit(ring, (int(self.x - c), int(self.y - c)))
        ca, sa = math.cos(self.rot), math.sin(self.rot)
        draw_blade(screen, self.x - ca * L / 2, self.y - sa * L / 2, self.rot, L, self.t)


class CosmicSlash:
    """Warning -> huge slash across the arena (1000 dmg) -> a cosmic line stays and weakens the enemy's super."""

    def __init__(self, owner, target, pos, angle):
        self.owner = owner
        self.target = target
        cx, cy = pos
        ux, uy = math.cos(angle), math.sin(angle)
        self.a = _to_wall(cx, cy, -ux, -uy)
        self.b = _to_wall(cx, cy, ux, uy)
        self.ux, self.uy = ux, uy
        self.nx, self.ny = -uy, ux
        self.len = math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1]) or 1.0
        self.half = ULTIMATE["slash_width"] / 2
        self.t = 0
        self.landed = False
        self.base = None
        rng = random.Random(random.randint(0, 10 ** 6))
        self.stars = [(rng.uniform(0, self.len), rng.uniform(-0.9, 0.9), rng.uniform(0, TAU), rng.choice((1, 2, 2, 3)))
                      for _ in range(70)]
        self.active = True
        owner.flash(GLOW, ULTIMATE["warn_frames"])

    # ----- geometry -----
    def _quad(self, half, ox=0, oy=0):
        (ax, ay), (bx, by) = self.a, self.b
        nx, ny = self.nx * half, self.ny * half
        return [(ax + nx - ox, ay + ny - oy), (bx + nx - ox, by + ny - oy),
                (bx - nx - ox, by - ny - oy), (ax - nx - ox, ay - ny - oy)]

    def _touching(self, t):
        tp = t.body.position
        qx, qy = _closest_on_segment(tp.x, tp.y, self.a[0], self.a[1], self.b[0], self.b[1])
        return math.hypot(tp.x - qx, tp.y - qy) <= self.half + t.radius

    # ----- logic -----
    def update(self, explosions):
        if not self.active:
            return
        U = ULTIMATE
        self.t += 1
        t = self.target
        alive = t is not None and t.hp > 0

        if not self.landed:
            if self.owner.hp <= 0:
                self.active = False
                return
            if self.t >= U["warn_frames"]:
                self._land(alive)
            return

        if self.t > U["warn_frames"] + U["line_duration"]:
            self.active = False
            return
        if alive and self._touching(t):
            t.apply_cosmic(U["cosmic_linger"], U["cosmic_super_slow"])

    def _land(self, alive):
        U = ULTIMATE
        self.landed = True
        sounds.play("sword")
        sounds.play("boom")
        W, H = ARENA_RIGHT - ARENA_LEFT, ARENA_BOTTOM - ARENA_TOP
        ox, oy = ARENA_LEFT, ARENA_TOP
        base = pygame.Surface((W, H), pygame.SRCALPHA)       # the cosmic line, baked once
        for mult, col in ((1.0, (50, 20, 110, 150)), (0.78, (100, 50, 190, 140)),
                          (0.5, (165, 105, 245, 150)), (0.2, (255, 255, 255, 235))):
            pygame.draw.polygon(base, col, self._quad(self.half * mult, ox, oy))
        self.base = base
        if alive:
            if self._touching(self.target):
                self.target.hp -= U["slash_damage"]
                self.owner.add_super(self.owner.super_per_hit)
                self.target.flash(GLOW, 30)
                sounds.play("hit")

    # ----- drawing -----
    def draw(self, screen):
        if not self.active:
            return
        U = ULTIMATE
        W, H = ARENA_RIGHT - ARENA_LEFT, ARENA_BOTTOM - ARENA_TOP
        ox, oy = ARENA_LEFT, ARENA_TOP

        if not self.landed:                                   # the warning
            k = self.t / U["warn_frames"]
            pulse = 0.5 + 0.5 * math.sin(self.t * (0.35 + 0.5 * k))
            lay = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.polygon(lay, (*VIOLET, int(25 + 55 * k * pulse)), self._quad(self.half, ox, oy))
            for sgn in (-1, 1):                               # dashed edges of the future cut
                n = int(self.len // 28)
                for i in range(0, n, 2):
                    s0, s1 = i * 28, i * 28 + 16
                    p0 = (self.a[0] + self.ux * s0 + self.nx * self.half * sgn - ox, self.a[1] + self.uy * s0 + self.ny * self.half * sgn - oy)
                    p1 = (self.a[0] + self.ux * s1 + self.nx * self.half * sgn - ox, self.a[1] + self.uy * s1 + self.ny * self.half * sgn - oy)
                    pygame.draw.line(lay, (*GLOW, int(140 + 100 * pulse)), p0, p1, 3)
            pygame.draw.line(lay, (255, 255, 255, int(90 + 140 * k)), (self.a[0] - ox, self.a[1] - oy), (self.b[0] - ox, self.b[1] - oy), 2)
            screen.blit(lay, (ox, oy))
            return

        age = self.t - U["warn_frames"]
        remaining = U["line_duration"] - age
        alpha = int(255 * max(0.0, min(1.0, remaining / max(1, U["line_fade_frames"]))))
        self.base.set_alpha(alpha)
        screen.blit(self.base, (ox, oy))

        k = alpha / 255.0                                     # twinkling stars drifting inside the line
        for i, (s, off, ph, sz) in enumerate(self.stars):
            s = (s + age * 0.4 * (1 if i % 2 else -1)) % self.len
            px = self.a[0] + self.ux * s + self.nx * off * self.half
            py = self.a[1] + self.uy * s + self.ny * off * self.half
            if not (ARENA_LEFT < px < ARENA_RIGHT and ARENA_TOP < py < ARENA_BOTTOM):
                continue
            tw = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(age * 0.15 + ph))
            v = int(255 * tw * k)
            pygame.draw.circle(screen, (v, v, v), (int(px), int(py)), sz)

        if age < U["flash_frames"]:                           # the flash of the cut itself
            f = 1.0 - age / U["flash_frames"]
            lay = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.polygon(lay, (255, 255, 255, int(210 * f)), self._quad(self.half * (1.0 + 0.8 * (1 - f)), ox, oy))
            screen.blit(lay, (ox, oy))


class Spicy(BaseBrawler):
    def __init__(self, space, pos, velocity):
        super().__init__(space, pos, velocity, STATS)
        if not find_asset(STATS["filename"]):          # no 7.png -> built-in design
            self.surface = make_avatar(self.radius)
        self.combo_state = None       # None, "slice" or "sword"
        self.state_t = 0
        self.combo_cd = 0
        self.sword = None
        self.tick = 0

    def _slice(self, target, scratch_effects):
        A = ABILITY
        x, y = self.body.position.x, self.body.position.y
        tp = target.body.position
        angle = math.atan2(tp.y - y, tp.x - x)
        sounds.play("sword")
        if math.hypot(tp.x - x, tp.y - y) <= A["slice_range"] + target.radius:
            target.hp -= A["slice_damage"]
            self.add_super(self.super_per_hit)
            sounds.play("hit")

        frames = A["slice_frames"]
        arc = math.radians(A["slice_arc"])
        reach = A["slice_range"]
        a_start = angle - arc / 2
        state = {"t": 0}
        me = self

        def draw(screen):
            px, py = me.body.position.x, me.body.position.y
            progress = min(1.0, state["t"] / max(1, frames - 1))
            state["t"] += 1
            a = a_start + arc * progress
            span = a - a_start
            if span > 0.01:
                steps = max(4, int(span / 0.08))
                outer = [(reach + math.cos(a_start + span * i / steps) * reach,
                          reach + math.sin(a_start + span * i / steps) * reach) for i in range(steps + 1)]
                inner = [(reach + math.cos(a_start + span * i / steps) * reach * 0.45,
                          reach + math.sin(a_start + span * i / steps) * reach * 0.45) for i in range(steps, -1, -1)]
                layer = pygame.Surface((reach * 2, reach * 2), pygame.SRCALPHA)
                pygame.draw.polygon(layer, (*VIOLET, 120), outer + inner)
                screen.blit(layer, (int(px - reach), int(py - reach)))
            draw_blade(screen, px, py, a, reach * 0.95, state["t"])

        scratch_effects.append({"x": x, "y": y, "sprite": None, "timer": frames, "draw": draw})
        self.combo_state = "slice"
        self.state_t = frames

    def _throw(self, target, projectiles):
        x, y = self.body.position.x, self.body.position.y
        angle = math.atan2(target.body.position.y - y, target.body.position.x - x)
        self.sword = CosmicSword(self, target, (x, y), angle)
        projectiles.append(self.sword)
        self.combo_state = "sword"
        sounds.play("star")

    def _ultimate(self, target, projectiles):
        x, y = self.body.position.x, self.body.position.y
        angle = math.atan2(target.body.position.y - y, target.body.position.x - x)
        projectiles.append(CosmicSlash(self, target, (x, y), angle))
        sounds.play("super")

    def update_abilities(self, target, projectiles, scratch_effects):
        if self.hp <= 0:
            return
        alive = target is not None and target.hp > 0
        self.tick += 1

        if self.combo_cd > 0:
            self.combo_cd -= 1

        if self.combo_state == "slice":
            self.state_t -= 1
            if self.state_t <= 0:
                if alive:
                    self._throw(target, projectiles)
                else:
                    self.combo_state = None
                    self.combo_cd = ABILITY["combo_cooldown"]
        elif self.combo_state == "sword":
            if self.sword is None or not self.sword.active:
                self.sword = None
                self.combo_state = None
                self.combo_cd = ABILITY["combo_cooldown"]
        elif alive and self.combo_cd <= 0:
            self._slice(target, scratch_effects)

        if alive and self.super_charge >= self.max_super:
            self.super_charge = 0
            self.trigger_super()
            self._ultimate(target, projectiles)

    def draw(self, screen):
        if self.hp <= 0:
            return
        super().draw(screen)
        if self.combo_state is None:                  # the sword rests at his side
            x, y = int(self.body.position.x), int(self.body.position.y)
            draw_blade(screen, x + self.radius * 0.55, y + self.radius * 0.1, -math.pi / 3, 60, self.tick)
