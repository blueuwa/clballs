import math
import random
import pygame
import sounds

from brawler import BaseBrawler, draw_lightning
from config import ARENA_LEFT, ARENA_RIGHT, ARENA_TOP, ARENA_BOTTOM, find_asset

TAU = math.pi * 2

WIND_C = (70, 230, 120)
FIRE_C = (255, 120, 30)
WATER_C = (70, 160, 255)
ICE_C = (170, 230, 255)
BOLT_C = (255, 235, 90)
BLOOM_C = (240, 110, 190)
THUNDER_C = (175, 95, 255)       # purple: the color of a thunderstorm
STEAM_C = (230, 238, 246)

# ===================== EDIT STATS HERE =====================
STATS = {
    "name": "ALI",
    "filename": "14.png",
    "max_hp": 1800,
    "speed_mult": 1.0,
    "radius": 30,
    "contact_damage": 5,

    "max_super": 100,         # the super bar is just the countdown to the next attack
    "super_per_hit": 0,
    "super_per_contact": 0,
}

# Every `interval` frames ALI casts ONE random element (never the same one twice in a row)
CAST = {
    "interval": 300,          # 300 frames = 5 seconds
    "no_repeat": True,
}

# ---- WIND: a swirl that pulls the enemy + bullets (400 dmg in total) ----
WIND = {
    "duration": 180,
    "radius": 120,
    "pull_range": 300,
    "pull_strength": 0.3,
    "vortex_damage": 200,     # if the enemy stays inside the whole time
    "bullets": 30,
    "bullet_damage": 5,      # 8 x 25 = 200
    "bullet_speed": 6.5,
    "bullet_radius": 7,
    "bullet_gap": 3,
}

# ---- FIRE: the borders burn + 3 pellets ----
FIRE = {
    "duration": 240,
    "ramp": 25,
    "band": 30,
    "burn_dps": 150,
    "burn_frames": 120,
    "pellets": 3,
    "pellet_damage": 100,
    "pellet_speed": 6.5,
    "pellet_radius": 9,
    "pellet_gap": 12,
    "pellet_spread": 0.12,
    "pellet_burn_frames": 60,
}

# ---- WATER: puddles -> WET ----
WATER = {
    "puddles": 8,
    "aimed": 4,
    "aim_scatter": 70,
    "radius": 55,
    "lifetime": 300,
    "throw_frames": 22,
    "throw_gap": 6,
    "wet_frames": 300,
}

# ---- ICE: 5 shards ----
ICE = {
    "shards": 5,
    "damage": 20,
    "speed": 8.0,
    "radius": 9,
    "fan": 0.14,
    "gap": 5,
    "freeze_frames": 90,
    "freeze_damage": 1000,    # wet + shard = FROZEN
}

# ---- THUNDER: 5 strikes ----
LIGHTNING = {
    "strikes": 8,
    "damage": 150,
    "radius": 60,
    "telegraph": 36,
    "gap": 22,
    "aim_chance": 0.6,
    "aim_scatter": 45,
    "bonus_damage": 600,      # wet / burning enemy = ELECTROCUTED (once per thunder)
}

# ---- BLOOM: poisonous fruits ----
BLOOM = {
    "fruits": 5,
    "grow_frames": 40,        # sprouting time (can't be touched yet)
    "lifetime": 600,          # a fruit that nobody touches withers after 10 seconds
    "radius": 15,
    "watered_radius": 21,     # a fruit that got watered grows bigger
    "edge_margin": 70,
    "stacks": 1,              # BLOSSOM stacks the enemy gets from one fruit
    "watered_stacks": 2,
    "dps_per_stack": 10,      # damage per second PER stack, until the match ends
    "max_stacks": 10,
    "heal": 30,               # ALI heals this much when HE touches a fruit
    "watered_heal": 45,
}

# ---- MARKS: symbols next to the enemy's name ----
#   storm    slowed a little                      flame  burning (150 dmg/s)
#   droplet  WET (freeze + electrocute combos)    ice    chilled, slowed more
#   bolt     shocked: +15% dmg from ALI        flower BLOSSOM (stacks; used up when ANY other element hits)
MARKS = {
    "storm_frames": 360,
    "storm_slow": 0.85,
    "frost_frames": 300,
    "frost_slow": 0.80,
    "shock_frames": 360,
    "shock_bonus": 0.15,
}

# ---- REACTIONS ----
REACTIONS = {
    # STORM mark + another element = an ELEMENTAL STORM spawns on the enemy
    #   (the same happens when ALI casts WIND while the enemy has a shock / burn / frost mark)
    "storm_frames": 150,
    "thunder_pull": 1.5,      # THUNDERSTORM (purple): pulls harder...
    "zap_gap": 30,            # ...and zaps the enemy inside it
    "zap_damage": 40,
    "fire_vortex_mult": 1.25, # FIRESTORM: more damage + keeps the enemy burning
    "blizzard_slow": 0.60,    # BLIZZARD: heavy slow + keeps the enemy chilled

    "steam_damage": 120,      # FIRE + WATER: both are used up
    "shatter_damage": 250,    # LIGHTNING hits a chilled / frozen enemy: the ice explodes

    "waterspout_pull": 1.3,   # WIND + WATER: a blue swirl that keeps the enemy wet and slowed
    "waterspout_slow": 0.70,
    "thermal_damage": 200,    # FIRE + ICE: thermal shock, both marks are used up
    "plasma_damage": 400,     # LIGHTNING + FIRE (burning enemy): plasma blast + knockback
    "plasma_knock": 2900.0,
    "plasma_knock_frames": 18,
}

# ---- BLOSSOM is used up by ANY other element. Every element turns it into a different explosion. ----
# (the damage is per stack that was on the enemy)
BLOSSOM_REACT = {
    "wind_damage": 30,        # SPORE CYCLONE: a pink swirl at the enemy...
    "wind_mult": 0.30,        # ...that deals +30% damage per stack
    "fire_damage": 60,        # WILDFIRE: green fire ring on the floor + stronger, longer burn
    "fire_burn_frames": 180,
    "fire_burn_mult": 1.5,
    "fire_zone_frames": 180,
    "fire_zone_radius": 110,
    "water_damage": 40,       # OVERGROWTH: vines root the enemy in place
    "water_root_base": 30,
    "water_root_per_stack": 10,
    "water_root_cap": 90,
    "ice_damage": 50,         # CRYO BLOOM: the flowers freeze solid for a moment
    "ice_freeze_frames": 45,
    "thunder_damage": 70,     # POLLEN BLAST: the pollen explodes and blasts the enemy away
    "thunder_knock": 800.0,
    "thunder_knock_frames": 16,
}
# ===========================================================

# ---- AURA: the energy that gathers around ALI before every cast ----
#   0%  .. 60%  every element has energy orbs around him, they drift back in one by one after a cast
#   60%         he ABSORBS the orbs of the elements that will NOT happen, only the next element is left
#   60% .. 100% the remaining orbs spin faster and faster, the aura gets stronger; then the cast
AURA = {
    "per_element": 1,         # orbs per element
    "absorb_at": 0.6,         # when the unused orbs get absorbed (0.6 = 3 of 5 seconds)
    "slow_spin": 0.035,       # orbit speed (radians per frame) while gathering
    "fast_spin": 0.65,        # extra speed at the very end
    "orbit": 10,              # distance of the orbs from the ball's edge
    "return_span": 0.5,       # the orbs come back one by one during this fraction of the cycle
}

ATTACK_NAMES = ("wind", "fire", "water", "ice", "thunder", "bloom")
ATTACK_COLORS = (WIND_C, FIRE_C, WATER_C, ICE_C, BOLT_C, BLOOM_C)

VORTEX_COLORS = {"wind": WIND_C, "thunder": THUNDER_C, "fire": FIRE_C, "ice": ICE_C, "water": WATER_C, "bloom": BLOOM_C}
STORM_NAMES = {"wind": "TORNADO!", "thunder": "THUNDERSTORM!", "fire": "FIRESTORM!", "ice": "BLIZZARD!",
               "water": "WATERSPOUT!", "bloom": "SPORE CYCLONE!"}
STORM_PARTS = {"thunder": (THUNDER_C, (245, 230, 255)), "fire": (FIRE_C, (255, 220, 80)),
               "ice": (ICE_C, (255, 255, 255)), "water": (WATER_C, (200, 235, 255)),
               "bloom": (BLOOM_C, (255, 225, 90), (150, 255, 100))}


def _clamp(x, y, m=30):
    return (max(ARENA_LEFT + m, min(ARENA_RIGHT - m, x)),
            max(ARENA_TOP + m, min(ARENA_BOTTOM - m, y)))


def _dim(col, k):
    return tuple(max(0, min(255, int(v * k))) for v in col)


def _light(col, k):
    return tuple(int(v + (255 - v) * k) for v in col)


def _burst(explosions, x, y, color, radius=26, frames=14):
    sparks = [(random.uniform(0, TAU), random.uniform(0.5, 1.0), random.uniform(2.5, 5.0)) for _ in range(10)]
    explosions.append({"x": x, "y": y, "radius": radius, "timer": frames, "max": frames,
                       "color": color, "sparks": sparks})


class Shot:
    """A straight bullet (wind bullet, fire pellet, ice shard). Same interface as Projectile."""

    def __init__(self, owner, target, pos, vel, damage, radius, kind, color, on_hit=None):
        self.owner = owner
        self.target = target
        self.x, self.y = pos
        self.vx, self.vy = vel
        self.damage = damage
        self.radius = radius
        self.kind = kind
        self.color = color
        self.on_hit = on_hit
        self.trail = []
        self.active = True

    def update(self, explosions):
        if not self.active:
            return
        self.trail.append((self.x, self.y))
        if len(self.trail) > 10:
            self.trail.pop(0)
        self.x += self.vx
        self.y += self.vy

        if (self.x - self.radius <= ARENA_LEFT or self.x + self.radius >= ARENA_RIGHT or
                self.y - self.radius <= ARENA_TOP or self.y + self.radius >= ARENA_BOTTOM):
            self.active = False
            return

        t = self.target
        if t and t.hp > 0:
            tp = t.body.position
            if math.hypot(self.x - tp.x, self.y - tp.y) <= self.radius + t.radius:
                t.hp -= int(round(self.owner._amp(self.damage)))
                _burst(explosions, self.x, self.y, self.color)
                sounds.play("hit")
                if self.on_hit:
                    self.on_hit(self)
                self.active = False

    def draw(self, screen):
        if not self.active:
            return
        n = len(self.trail)
        for i, (tx, ty) in enumerate(self.trail):
            f = (i + 1) / (n + 1)
            pygame.draw.circle(screen, _dim(self.color, 0.55 * f), (int(tx), int(ty)),
                               max(1, int(self.radius * f * 0.8)))
        x, y, r = int(self.x), int(self.y), self.radius
        if self.kind == "ice":
            a = math.atan2(self.vy, self.vx)
            ca, sa = math.cos(a), math.sin(a)
            pts = [(x + ca * r * 2.4, y + sa * r * 2.4), (x - sa * r * 0.8, y + ca * r * 0.8),
                   (x - ca * r * 1.4, y - sa * r * 1.4), (x + sa * r * 0.8, y - ca * r * 0.8)]
            pygame.draw.polygon(screen, self.color, pts)
            pygame.draw.polygon(screen, (255, 255, 255), pts, 2)
        else:
            pygame.draw.circle(screen, _dim(self.color, 0.6), (x, y), r + 3)
            pygame.draw.circle(screen, self.color, (x, y), r)
            core = (255, 240, 170) if self.kind == "fire" else _light(self.color, 0.8)
            pygame.draw.circle(screen, core, (x, y), max(2, r // 2))


# ---------- HUD mark icons: drawn(screen, cx, cy, radius, frac) ----------
_fonts = {}


def _font(name, size, bold=False):
    key = (name, size, bold)
    f = _fonts.get(key)
    if f is None:
        f = _fonts[key] = pygame.font.SysFont(name, size, bold=bold)
    return f


def _badge(screen, cx, cy, rad, frac, color):
    pygame.draw.circle(screen, (14, 16, 30), (cx, cy), rad)
    pygame.draw.circle(screen, _dim(color, 0.35), (cx, cy), rad, 2)
    if frac > 0:                  # the bright arc shrinks as the mark runs out
        pygame.draw.arc(screen, color, pygame.Rect(cx - rad, cy - rad, rad * 2, rad * 2),
                        math.pi / 2, math.pi / 2 + TAU * min(1.0, frac), 3)


def _poly(cx, cy, u, pts):
    return [(cx + x * u, cy + y * u) for x, y in pts]


def _icon_storm(screen, cx, cy, rad, frac):
    _badge(screen, cx, cy, rad, frac, WIND_C)
    u = (rad - 3) / 8.0
    cloud = (215, 238, 222)
    for ox, oy, rr in ((-3, -2.5, 3), (1, -4, 3.6), (4, -1.5, 2.8)):
        pygame.draw.circle(screen, cloud, (int(cx + ox * u), int(cy + oy * u)), max(1, int(rr * u)))
    pygame.draw.rect(screen, cloud, pygame.Rect(int(cx - 6 * u), int(cy - 2.5 * u), max(2, int(11 * u)), max(1, int(2.5 * u))))
    pts = []
    for i in range(14):
        f = i / 13
        a = f * TAU * 1.3
        rr = 3.4 * u * (1 - f * 0.65)
        pts.append((cx + math.cos(a) * rr, cy + 4.6 * u + math.sin(a) * rr * 0.7))
    pygame.draw.lines(screen, WIND_C, False, pts, 2)


def _icon_fire(screen, cx, cy, rad, frac):
    _badge(screen, cx, cy, rad, frac, FIRE_C)
    u = (rad - 3) / 8.0
    pygame.draw.polygon(screen, FIRE_C, _poly(cx, cy, u, [(0.5, -8), (3, -3), (5, 1), (4, 5), (0, 8), (-4, 5), (-5, 1), (-2, -3), (-1, -5)]))
    pygame.draw.polygon(screen, (255, 225, 90), _poly(cx, cy, u, [(0, -1), (2.5, 3), (0, 6.5), (-2.5, 3)]))


def _icon_water(screen, cx, cy, rad, frac):
    _badge(screen, cx, cy, rad, frac, WATER_C)
    u = (rad - 3) / 8.0
    pygame.draw.polygon(screen, WATER_C, _poly(cx, cy, u, [(0, -8), (4.2, -0.5), (-4.2, -0.5)]))
    pygame.draw.circle(screen, WATER_C, (int(cx), int(cy + 3 * u)), max(2, int(5 * u)))
    pygame.draw.circle(screen, (225, 242, 255), (int(cx - 1.8 * u), int(cy + 2 * u)), max(1, int(1.4 * u)))


def _icon_ice(screen, cx, cy, rad, frac):
    _badge(screen, cx, cy, rad, frac, ICE_C)
    u = (rad - 3) / 8.0
    for k in range(3):
        a = k * math.pi / 3 + math.pi / 6
        ca, sa = math.cos(a), math.sin(a)
        pygame.draw.line(screen, (235, 250, 255), (cx - ca * 7.5 * u, cy - sa * 7.5 * u), (cx + ca * 7.5 * u, cy + sa * 7.5 * u), 2)
        for sgn in (-1, 1):
            bx, by = cx + ca * 4.6 * u * sgn, cy + sa * 4.6 * u * sgn
            for side in (-1, 1):
                pa = a + sgn * side * 0.8
                pygame.draw.line(screen, (235, 250, 255), (bx, by),
                                 (bx + math.cos(pa) * 2.6 * u * sgn, by + math.sin(pa) * 2.6 * u * sgn), 1)


def _icon_shock(screen, cx, cy, rad, frac):
    _badge(screen, cx, cy, rad, frac, BOLT_C)
    u = (rad - 3) / 8.0
    pts = _poly(cx, cy, u, [(2.5, -8), (-4.5, 1), (-0.5, 1), (-2.5, 8), (4.5, -2), (0.5, -2)])
    pygame.draw.polygon(screen, BOLT_C, pts)
    pygame.draw.polygon(screen, (255, 255, 255), pts, 1)


def _icon_bloom(screen, cx, cy, rad, frac, count=1):
    _badge(screen, cx, cy, rad, frac, BLOOM_C)
    u = (rad - 3) / 8.0
    for i in range(5):
        a = -math.pi / 2 + i * TAU / 5
        pygame.draw.circle(screen, BLOOM_C, (int(cx + math.cos(a) * 4.2 * u), int(cy + math.sin(a) * 4.2 * u)), max(2, int(3.2 * u)))
    pygame.draw.circle(screen, (255, 225, 90), (cx, cy), max(2, int(2.6 * u)))
    if count > 1:                                   # stack counter
        font = _font("Arial", max(10, int(rad * 1.1)), True)
        txt, shade = font.render(str(count), True, (255, 255, 255)), font.render(str(count), True, (0, 0, 0))
        pos = txt.get_rect(center=(cx + int(rad * 0.55), cy + int(rad * 0.62)))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            screen.blit(shade, pos.move(dx, dy))
        screen.blit(txt, pos)


# ---------- the avatar (used when there is no 14.png in assets) ----------
_avatar_cache = {}


def _petal(cx, cy, a, dist, length, width):
    pts = []
    for i in range(24):
        th = TAU * i / 24
        ex, ey = length * math.cos(th), width * math.sin(th)
        pts.append((cx + dist * math.cos(a) + ex * math.cos(a) - ey * math.sin(a),
                    cy + dist * math.sin(a) + ex * math.sin(a) + ey * math.cos(a)))
    return pts


def make_avatar(radius):
    """A dark star-sphere with a six-element rosette around a white core."""
    if radius in _avatar_cache:
        return _avatar_cache[radius]
    S = 256
    c = S // 2
    big = pygame.Surface((S, S), pygame.SRCALPHA)
    steps = 48
    for i in range(steps):
        t = i / (steps - 1)
        col = (int(16 + 62 * t), int(12 + 48 * t), int(42 + 125 * t))
        pygame.draw.circle(big, col, (c, c), max(1, int(c * (1 - t * 0.93))))
    n = len(ATTACK_COLORS)
    for k, col in enumerate(ATTACK_COLORS):
        a = -math.pi / 2 + k * TAU / n
        outer = _petal(c, c, a, c * 0.50, c * 0.42, c * 0.16)
        pygame.draw.polygon(big, _dim(col, 0.8), outer)
        pygame.draw.polygon(big, (255, 255, 255), outer, 3)
        inner = _petal(c, c, a, c * 0.52, c * 0.25, c * 0.07)
        pygame.draw.polygon(big, _light(col, 0.55), inner)
    pygame.draw.circle(big, (120, 135, 255), (c, c), int(c * 0.27))
    pygame.draw.circle(big, (200, 215, 255), (c, c), int(c * 0.20))
    pygame.draw.circle(big, (255, 255, 255), (c, c), int(c * 0.12))
    pygame.draw.circle(big, (190, 200, 255), (c, c), c - 3, 6)
    mask = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (c, c), c)
    big.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    out = pygame.transform.smoothscale(big, (radius * 2, radius * 2))
    _avatar_cache[radius] = out
    return out


class Ali(BaseBrawler):
    def __init__(self, space, pos, velocity):
        super().__init__(space, pos, velocity, STATS)
        if not find_asset(STATS["filename"]):         # no 14.png -> use the built-in design
            self.surface = make_avatar(self.radius)
        self.t = 0
        self.spin = 0.0              # angle of the orbiting energy orbs
        self.spin_speed = AURA["slow_spin"]
        self.burst_t = 0             # cast burst animation
        self.burst_col = (255, 255, 255)
        self.charge = 0
        self.last_attack = None
        self.next_attack = random.choice(ATTACK_NAMES)   # decided early so his ring shows what is coming
        self.foe = None
        self._proj = None
        self._registered = False
        self.sched = []              # [frames_left, function]
        self.fx = []                 # short visual effects drawn over the balls

        # marks / status effects on the enemy (tracked here)
        self.wet = 0
        self.burn = 0
        self.burn_acc = 0
        self.freeze = 0
        self.storm = 0
        self.frost = 0
        self.shock = 0
        self.blizzard = 0            # inside a blizzard: heavier slow
        self.bloom = 0               # BLOSSOM stacks (until another element uses them up)
        self.bloom_acc = 0
        self.spout = 0               # inside a waterspout: slowed
        self.root_t = 0              # rooted by vines (OVERGROWTH)
        self.root_total = 1
        self.green_t = 0             # burning with green WILDFIRE flames
        self.cd = {}                 # small cooldowns so a reaction can't fire every single frame
        self.zones = []              # WILDFIRE fire rings on the floor

        # attack state
        self.vortexes = []
        self.fire_t = 0
        self.fire_age = 0
        self.blobs = []
        self.puddles = []
        self.strikes = []
        self.bolt_bonus = False
        self.fruits = []

        W = ARENA_RIGHT - ARENA_LEFT
        H = ARENA_BOTTOM - ARENA_TOP
        b = FIRE["band"]
        self._strips = []
        for (px, py, w, h) in ((ARENA_LEFT, ARENA_TOP, W, b), (ARENA_LEFT, ARENA_BOTTOM - b, W, b),
                               (ARENA_LEFT, ARENA_TOP, b, H), (ARENA_RIGHT - b, ARENA_TOP, b, H)):
            s = pygame.Surface((w, h))
            s.fill(FIRE_C)
            self._strips.append((s, (px, py)))

    # ---------- small helpers ----------
    def _later(self, frames, fn):
        self.sched.append([max(1, frames), fn])

    def _run_schedule(self):
        due = []
        for item in self.sched:
            item[0] -= 1
            if item[0] <= 0:
                due.append(item)
        self.sched = [i for i in self.sched if i[0] > 0]
        for _, fn in due:
            fn()

    def _add_fx(self, frames, fn, tag=None):
        self.fx.append({"t": frames, "max": frames, "fn": fn, "tag": tag})

    def _cool(self, name, frames):
        if self.cd.get(name, 0) > 0:
            return False
        self.cd[name] = frames
        return True

    # ----- big visual effects used by the reactions -----
    def _banner(self, text, color):
        """Big title over the arena: the reaction's name."""
        self.fx = [e for e in self.fx if e.get("tag") != "banner"]
        font = _font("Impact", 46)

        def fn(screen, p):
            cx = (ARENA_LEFT + ARENA_RIGHT) // 2
            y = ARENA_TOP + 90 - int(24 * p)
            pop = 1 + 0.6 * max(0.0, 1 - p * 8)
            a = int(255 * min(1.0, (1 - p) * 3))
            surf, shade = font.render(text, True, color), font.render(text, True, (0, 0, 0))
            w, h = surf.get_size()
            size = (max(1, int(w * pop)), max(1, int(h * pop)))
            surf, shade = pygame.transform.smoothscale(surf, size), pygame.transform.smoothscale(shade, size)
            surf.set_alpha(a)
            shade.set_alpha(a)
            r = surf.get_rect(center=(cx, y))
            for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
                screen.blit(shade, r.move(dx, dy))
            screen.blit(surf, r)
        self._add_fx(70, fn, "banner")

    def _shockwave(self, x, y, color, reach=140, frames=26, width=7):
        def fn(screen, p):
            ease = 1 - (1 - p) ** 3
            r = max(2, int(reach * ease))
            a = 1 - p
            S = (reach + 24) * 2
            surf = pygame.Surface((S, S), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*color, int(55 * a)), (S // 2, S // 2), r)
            pygame.draw.circle(surf, (*color, int(230 * a)), (S // 2, S // 2), r, max(1, int(width * a) + 1))
            pygame.draw.circle(surf, (255, 255, 255, int(200 * a)), (S // 2, S // 2), max(2, r - 4), 2)
            screen.blit(surf, (int(x - S // 2), int(y - S // 2)))
        self._add_fx(frames, fn)

    def _flash(self, color, frames=14, alpha=110):
        W, H = ARENA_RIGHT - ARENA_LEFT, ARENA_BOTTOM - ARENA_TOP

        def fn(screen, p):
            surf = pygame.Surface((W, H), pygame.SRCALPHA)
            surf.fill((*color, int(alpha * (1 - p))))
            screen.blit(surf, (ARENA_LEFT, ARENA_TOP))
        self._add_fx(frames, fn)

    def _pillar(self, x, y, color, frames=20, width=44):
        def fn(screen, p):
            k = 1 - p
            w = max(2, int(width * k))
            h = max(2, int(y - ARENA_TOP))
            surf = pygame.Surface((w * 2, h), pygame.SRCALPHA)
            surf.fill((*color, int(100 * k)))
            core = max(1, w // 3)
            pygame.draw.rect(surf, (255, 255, 255, int(220 * k)), pygame.Rect(w - core, 0, core * 2, h))
            screen.blit(surf, (int(x - w), ARENA_TOP))
        self._add_fx(frames, fn)

    def _particles(self, x, y, colors, n=26, speed=(2.0, 7.0), frames=34, grav=0.0, size=(2, 5)):
        ps = [(random.uniform(0, TAU), random.uniform(*speed), random.randint(*size), random.choice(colors))
              for _ in range(n)]

        def fn(screen, p):
            t = p * frames
            for a, sp, sz, col in ps:
                px = x + math.cos(a) * sp * t * 0.9
                py = y + math.sin(a) * sp * t * 0.9 + grav * t * t / 2
                pygame.draw.circle(screen, _dim(col, 1 - p * 0.8), (int(px), int(py)), max(1, int(sz * (1 - p * 0.6))))
        self._add_fx(frames, fn)

    def _cracks(self, x, y, color=(235, 250, 255), frames=34, reach=70):
        lines = []
        for _ in range(9):
            a = random.uniform(0, TAU)
            pts = [(x, y)]
            d = 0.0
            for _ in range(4):
                d += random.uniform(12, reach / 3)
                aa = a + random.uniform(-0.5, 0.5)
                pts.append((x + math.cos(aa) * d, y + math.sin(aa) * d))
            lines.append(pts)

        def fn(screen, p):
            for pts in lines:
                pygame.draw.lines(screen, _dim(color, 1 - p), False, pts, 2)
        self._add_fx(frames, fn)

    def _react(self, who, text, color, ring=140, flash=None, pillar=False, parts=None, at=None):
        """One call = popup + big banner + shockwave (+ optional screen flash / light pillar / sparks)."""
        x, y = at if at else (who.body.position.x, who.body.position.y)
        who.popups.append((text, color))
        self._banner(text, color)
        if ring:
            self._shockwave(x, y, color, ring)
        if flash:
            self._flash(flash if isinstance(flash, tuple) else color)
        if pillar:
            self._pillar(x, y, color)
        if parts:
            self._particles(x, y, parts)

    def _blast_away(self, foe, speed, frames):
        dx, dy = foe.body.position.x - self.body.position.x, foe.body.position.y - self.body.position.y
        l = math.hypot(dx, dy)
        if l < 1e-6:
            dx, dy, l = 1.0, 0.0, 1.0
        foe.apply_knockback(dx / l, dy / l, speed, frames)

    def _aim(self, foe, off=0.0):
        return math.atan2(foe.body.position.y - self.body.position.y,
                          foe.body.position.x - self.body.position.x) + off

    def _shoot(self, kind, color, damage, radius, speed, angle, on_hit=None):
        foe = self.foe
        if foe is None or foe.hp <= 0 or self.hp <= 0:
            return
        pos = (self.body.position.x, self.body.position.y)
        vel = (math.cos(angle) * speed, math.sin(angle) * speed)
        self._proj.append(Shot(self, foe, pos, vel, damage, radius, kind, color, on_hit))

    def _predict(self, foe, frames, scatter):
        p, v = foe.body.position, foe.body.velocity
        x = p.x + v.x * frames / 60.0 + random.uniform(-scatter, scatter)
        y = p.y + v.y * frames / 60.0 + random.uniform(-scatter, scatter)
        return _clamp(x, y)

    def _amp(self, x):
        """Shocked enemies take extra damage from ALI."""
        return x * (1 + MARKS["shock_bonus"]) if self.shock > 0 else x

    def _hurt(self, foe, amount):
        foe.hp -= int(round(self._amp(amount)))

    # ---------- marks ----------
    def _mark_storm(self, foe):
        if self.storm <= 0:
            if self.bloom > 0:                  # BLOSSOM + WIND
                self._bloom_react(foe, "wind")
            else:
                foe.popups.append(("STORMED!", WIND_C))
        self.storm = MARKS["storm_frames"]

    def _mark_shock(self, foe):
        if self.shock <= 0:
            foe.popups.append(("SHOCKED!", BOLT_C))
        self.shock = MARKS["shock_frames"]

    def _mark_frost(self, foe):
        if self.frost <= 0 and self.freeze <= 0:
            foe.popups.append(("CHILLED!", ICE_C))
        self.frost = MARKS["frost_frames"]

    def _make_wet(self, foe):
        if self.burn > 0:                       # FIRE + WATER
            if self._cool("steam", 30):
                self._steam(foe)
            return
        if self.wet <= 0:
            if self.bloom > 0:                  # BLOSSOM + WATER
                self._bloom_react(foe, "water")
            foe.popups.append(("WET!", WATER_C))
        self.wet = WATER["wet_frames"]

    def _ignite(self, foe, frames=None):
        if self.wet > 0:                        # WATER + FIRE
            if self._cool("steam", 30):
                self._steam(foe)
            return
        if (self.frost > 0 or self.freeze > 0) and self._cool("thermal", 90):     # ICE + FIRE
            self._thermal_shock(foe)
            return
        if self.burn <= 0:
            if self.bloom > 0:                  # BLOSSOM + FIRE
                self._bloom_react(foe, "fire")
            else:
                foe.popups.append(("BURNING!", FIRE_C))
            sounds.play("boom")
        self.burn = max(self.burn, frames or FIRE["burn_frames"])

    def _sync_marks(self, foe):
        """Hands main.py the icons to draw next to the enemy's name."""
        M = MARKS
        marks = []
        for fn, left, total in ((_icon_storm, self.storm, M["storm_frames"]),
                                (_icon_fire, self.burn, FIRE["burn_frames"]),
                                (_icon_water, self.wet, WATER["wet_frames"]),
                                (_icon_ice, max(self.frost, self.freeze), M["frost_frames"]),
                                (_icon_shock, self.shock, M["shock_frames"])):
            if left > 0:
                marks.append({"draw": fn, "frac": min(1.0, left / total)})
        if self.bloom > 0:
            marks.append({"draw": self._bloom_icon(self.bloom), "frac": 1.0})
        foe.hud_marks = marks

    @staticmethod
    def _bloom_icon(count):
        return lambda screen, cx, cy, rad, frac: _icon_bloom(screen, cx, cy, rad, frac, count)

    def _tick_status(self, foe, alive):
        prev_freeze = self.freeze
        for name in ("wet", "freeze", "storm", "frost", "shock", "blizzard", "spout", "root_t", "green_t"):
            if getattr(self, name) > 0:
                setattr(self, name, getattr(self, name) - 1)
        for k in list(self.cd):
            self.cd[k] = max(0, self.cd[k] - 1)
        if alive and prev_freeze > 0 and self.freeze == 0:       # the ice melts away
            self._shard_burst(foe.body.position.x, foe.body.position.y, n=8)

        if self.burn > 0:
            self.burn -= 1
            if alive:
                self.burn_acc += 1
                if self.burn_acc >= 12:
                    self.burn_acc = 0
                    wild = BLOSSOM_REACT["fire_burn_mult"] if self.green_t > 0 else 1.0
                    foe.hp -= round(self._amp(FIRE["burn_dps"] * 12 / 60 * wild))
        else:
            self.burn_acc = 0

        if self.bloom > 0 and alive:                              # BLOSSOM: poison until the match ends
            self.bloom_acc += 1
            if self.bloom_acc >= 12:
                self.bloom_acc = 0
                foe.hp -= round(self._amp(self.bloom * BLOOM["dps_per_stack"] * 12 / 60))

        if alive and foe.stun_timer <= 0:                          # slows (never override a stronger one from someone else)
            cands = []
            if self.storm > 0:
                cands.append((MARKS["storm_slow"], WIND_C))
            if self.frost > 0:
                cands.append((MARKS["frost_slow"], ICE_C))
            if self.blizzard > 0:
                cands.append((REACTIONS["blizzard_slow"], ICE_C))
            if self.spout > 0:
                cands.append((REACTIONS["waterspout_slow"], WATER_C))
            if cands:
                f, col = min(cands)
                if foe.slow_timer <= 3 or foe.slow_color in (WIND_C, ICE_C, WATER_C):
                    foe.apply_slow(2, f, 0, col)

    # ---------- reactions ----------
    def _steam(self, foe):
        """FIRE + WATER: both are used up in a scalding cloud."""
        self.wet = 0
        self.burn = 0
        self._hurt(foe, REACTIONS["steam_damage"])
        self._react(foe, "STEAM!", STEAM_C, ring=120, parts=(STEAM_C, (255, 255, 255), (255, 190, 140)))
        sounds.play("hit")

        puffs = [(random.uniform(-24, 24), random.uniform(-6, 14), random.uniform(9, 17), random.uniform(0.6, 1.4))
                 for _ in range(10)]

        def fn(screen, p):
            x, y = foe.body.position.x, foe.body.position.y
            S = 170
            surf = pygame.Surface((S, S), pygame.SRCALPHA)
            for ox, oy, r, sp in puffs:
                pygame.draw.circle(surf, (*STEAM_C, int(170 * (1 - p))),
                                   (int(S / 2 + ox * (1 + p)), int(S / 2 + oy - 60 * p * sp)), int(r * (1 + 1.2 * p)))
            screen.blit(surf, (int(x - S / 2), int(y - S / 2)))
        self._add_fx(50, fn)

    def _shatter(self, foe):
        """LIGHTNING + ICE: the frost on the enemy explodes."""
        was_frozen = self.freeze > 0
        self.frost = 0
        self.freeze = 0
        self.blizzard = 0
        if was_frozen and foe.stun_timer > 0:
            foe.stun_timer = 1                 # base class restores the mass when it reaches 0
        self._hurt(foe, REACTIONS["shatter_damage"])
        self._react(foe, "SHATTERED!", (235, 250, 255), ring=140, flash=(235, 250, 255))
        sounds.play("boom")
        self._shard_burst(foe.body.position.x, foe.body.position.y, n=18, reach=110)
        self._cracks(foe.body.position.x, foe.body.position.y)

    def _thermal_shock(self, foe):
        """FIRE + ICE: the ice cracks from the heat, both marks are used up."""
        was_frozen = self.freeze > 0
        self.frost = self.freeze = self.blizzard = 0
        self.burn = self.burn_acc = 0
        if was_frozen and foe.stun_timer > 0:
            foe.stun_timer = 1
        self._hurt(foe, REACTIONS["thermal_damage"])
        x, y = foe.body.position.x, foe.body.position.y
        self._react(foe, "THERMAL SHOCK!", (255, 170, 110), ring=150, flash=(255, 190, 150),
                    parts=(FIRE_C, ICE_C, (255, 255, 255)))
        self._shockwave(x, y, ICE_C, 105, 30)
        self._cracks(x, y, (255, 230, 200))
        self._shard_burst(x, y, n=12, reach=80)
        sounds.play("boom")

    def _plasma(self, foe):
        """LIGHTNING + FIRE: the burning enemy is hit by a plasma explosion and blasted away."""
        self.burn = self.burn_acc = 0
        foe.hp -= REACTIONS["plasma_damage"]
        self._blast_away(foe, REACTIONS["plasma_knock"], REACTIONS["plasma_knock_frames"])
        self._react(foe, "PLASMA BLAST!", (255, 205, 150), ring=180, flash=(255, 225, 190), pillar=True,
                    parts=(FIRE_C, BOLT_C, (255, 255, 255)))
        sounds.play("boom")

    def _bloom_react(self, foe, kind):
        """Any other element uses up the BLOSSOM stacks and turns them into its own explosion."""
        n = self.bloom
        if n <= 0 or foe is None or foe.hp <= 0:
            return False
        R = BLOSSOM_REACT
        self.bloom = 0
        self.bloom_acc = 0
        x, y = foe.body.position.x, foe.body.position.y
        sounds.play("boom")
        if kind == "wind":                      # SPORE CYCLONE
            self._hurt(foe, R["wind_damage"] * n)
            self._react(foe, "SPORE CYCLONE!", BLOOM_C, ring=160, parts=STORM_PARTS["bloom"])
            cx, cy = _clamp(x, y, WIND["radius"])
            self._spawn_vortex("bloom", cx, cy, REACTIONS["storm_frames"], False, 1 + R["wind_mult"] * n)
        elif kind == "fire":                    # WILDFIRE
            self._hurt(foe, R["fire_damage"] * n)
            self.green_t = R["fire_burn_frames"] + 60
            self.burn = max(self.burn, R["fire_burn_frames"])
            self.zones.append({"x": x, "y": y, "timer": R["fire_zone_frames"], "max": R["fire_zone_frames"]})
            self._react(foe, "WILDFIRE!", (120, 255, 90), ring=R["fire_zone_radius"] + 40, flash=True, pillar=True,
                        parts=((120, 255, 90), (255, 220, 80), FIRE_C))
        elif kind == "water":                   # OVERGROWTH
            self._hurt(foe, R["water_damage"] * n)
            frames = min(R["water_root_cap"], R["water_root_base"] + R["water_root_per_stack"] * n)
            foe.apply_stun(frames, 0, (110, 230, 110))
            self.root_t = self.root_total = frames
            self._react(foe, "OVERGROWTH!", (100, 230, 110), ring=130, parts=((100, 230, 110), BLOOM_C, (200, 255, 150)))
        elif kind == "ice":                     # CRYO BLOOM
            self._hurt(foe, R["ice_damage"] * n)
            frames = R["ice_freeze_frames"]
            foe.apply_stun(frames, 0, ICE_C)
            self.freeze = max(self.freeze, frames)
            self.frost = MARKS["frost_frames"]
            self._react(foe, "CRYO BLOOM!", (200, 235, 255), ring=140, flash=(200, 235, 255),
                        parts=(ICE_C, BLOOM_C, (255, 255, 255)))
            self._cracks(x, y, BLOOM_C, reach=60)
        else:                                   # thunder: POLLEN BLAST
            self._hurt(foe, R["thunder_damage"] * n)
            self._blast_away(foe, R["thunder_knock"], R["thunder_knock_frames"])
            self._react(foe, "POLLEN BLAST!", (255, 225, 110), ring=180, flash=True, pillar=True,
                        parts=(BLOOM_C, (255, 225, 90), (255, 255, 255)))
        return True

    def _shard_burst(self, x, y, n=10, reach=60):
        shards = [(random.uniform(0, TAU), random.uniform(reach * 0.5, reach)) for _ in range(n)]

        def fn(screen, p):
            for a, d in shards:
                ca, sa = math.cos(a), math.sin(a)
                px, py = x + ca * d * p, y + sa * d * p
                ln = 12 * (1 - p) + 3
                pygame.draw.line(screen, (235, 250, 255), (px, py), (px + ca * ln, py + sa * ln), 3)
                pygame.draw.line(screen, ICE_C, (px, py), (px - ca * ln * 0.6, py - sa * ln * 0.6), 2)
        self._add_fx(24, fn)

    def _electro_fx(self, foe):
        def fn(screen, p):
            x, y, r = foe.body.position.x, foe.body.position.y, foe.radius
            for _ in range(5):
                a = random.uniform(0, TAU)
                ln = random.uniform(28, 60)
                draw_lightning(screen, (x + math.cos(a) * r, y + math.sin(a) * r),
                               (x + math.cos(a) * (r + ln), y + math.sin(a) * (r + ln)), (150, 210, 255), 3, 5, 4)
            pygame.draw.circle(screen, (220, 240, 255), (int(x), int(y)), int(r + 4 + 10 * p), 2)
        self._add_fx(22, fn)

    # ---------- casting ----------
    def _cast(self):
        name = self.next_attack
        self.last_attack = name
        names = [n for n in ATTACK_NAMES if not (CAST["no_repeat"] and n == name)]
        self.next_attack = random.choice(names)
        self.burst_t = 24
        self.burst_col = ATTACK_COLORS[ATTACK_NAMES.index(name)]
        getattr(self, "_cast_" + name)()

    def _storm_kind(self):
        """Which kind of swirl does WIND make right now? A fresh mark on the enemy changes it."""
        best, kind = 0.0, "wind"
        for k, left, total in (("thunder", self.shock, MARKS["shock_frames"]),
                               ("fire", self.burn, FIRE["burn_frames"]),
                               ("ice", self.frost, MARKS["frost_frames"]),
                               ("water", self.wet, WATER["wet_frames"])):
            if left > 0 and left / total > best:
                best, kind = left / total, k
        return kind

    def _spawn_vortex(self, kind, x, y, duration, gives_storm, mult=1.0):
        self.vortexes.append({"x": x, "y": y, "timer": duration, "max": duration, "age": 0, "rot": 0.0,
                              "acc": 0.0, "kind": kind, "zap": REACTIONS["zap_gap"], "storm": gives_storm,
                              "mult": mult})

    def _storm_reaction(self, kind):
        """STORM mark + thunder / fire / ice: an elemental storm spawns right on the enemy."""
        foe = self.foe
        if self.storm <= 0 or foe is None or foe.hp <= 0:
            return
        self.storm = 0
        col = VORTEX_COLORS[kind]
        a = random.uniform(0, TAU)
        d = random.uniform(0, 70)
        x, y = _clamp(foe.body.position.x + math.cos(a) * d, foe.body.position.y + math.sin(a) * d, WIND["radius"])
        mult = 1 + BLOSSOM_REACT["wind_mult"] * self.bloom if kind == "bloom" else 1.0
        self._spawn_vortex(kind, x, y, REACTIONS["storm_frames"], False, mult)
        self._react(foe, STORM_NAMES[kind], col, ring=170, at=(x, y),
                    flash=THUNDER_C if kind == "thunder" else None, pillar=(kind == "thunder"),
                    parts=STORM_PARTS[kind])
        sounds.play("super")

    def _cast_wind(self):
        W = WIND
        foe = self.foe
        kind = self._storm_kind()
        col = VORTEX_COLORS[kind]
        sounds.play("super")
        ang = random.uniform(0, TAU)
        dist = random.uniform(140, 260)
        x, y = _clamp(foe.body.position.x + math.cos(ang) * dist,
                      foe.body.position.y + math.sin(ang) * dist, W["radius"])
        self._spawn_vortex(kind, x, y, W["duration"], True)
        if kind == "wind":
            self.popups.append((STORM_NAMES[kind], col))
        else:                                   # a mark on the enemy changed the swirl: make it obvious
            self._react(self, STORM_NAMES[kind], col, ring=170, at=(x, y),
                        flash=THUNDER_C if kind == "thunder" else None, pillar=(kind == "thunder"),
                        parts=STORM_PARTS[kind])
        for i in range(W["bullets"]):
            self._later(10 + i * W["bullet_gap"], lambda c=col: self._shoot_wind(c))

    def _shoot_wind(self, color):
        if self.foe is None:
            return
        self._shoot("wind", color, WIND["bullet_damage"], WIND["bullet_radius"], WIND["bullet_speed"],
                    self._aim(self.foe, random.uniform(-0.05, 0.05)), self._wind_hit)

    def _wind_hit(self, shot):
        if self.foe is not None and self.foe.hp > 0:
            self._mark_storm(self.foe)

    def _cast_fire(self):
        F = FIRE
        self.popups.append(("INFERNO!", FIRE_C))
        sounds.play("boom")
        self._storm_reaction("fire")
        self.fire_t = F["duration"]
        self.fire_age = 0
        for i in range(F["pellets"]):
            self._later(6 + i * F["pellet_gap"], self._shoot_fire)

    def _shoot_fire(self):
        if self.foe is None:
            return
        self._shoot("fire", FIRE_C, FIRE["pellet_damage"], FIRE["pellet_radius"], FIRE["pellet_speed"],
                    self._aim(self.foe, random.uniform(-FIRE["pellet_spread"], FIRE["pellet_spread"])), self._fire_hit)

    def _fire_hit(self, shot):
        if self.foe is not None and self.foe.hp > 0:
            self._ignite(self.foe, FIRE["pellet_burn_frames"])

    def _cast_water(self):
        W = WATER
        self.popups.append(("FLOOD!", WATER_C))
        self._storm_reaction("water")
        for i in range(W["puddles"]):
            self._later(1 + i * W["throw_gap"], lambda i=i: self._throw_puddle(i))

    def _throw_puddle(self, i):
        foe = self.foe
        if foe is None or foe.hp <= 0:
            return
        W = WATER
        if i < W["aimed"]:
            tx, ty = self._predict(foe, W["throw_frames"], W["aim_scatter"])
        else:
            tx = random.uniform(ARENA_LEFT + 40, ARENA_RIGHT - 40)
            ty = random.uniform(ARENA_TOP + 40, ARENA_BOTTOM - 40)
        self.blobs.append({"sx": self.body.position.x, "sy": self.body.position.y,
                           "tx": tx, "ty": ty, "t": 0})
        sounds.play("bump")

    def _cast_ice(self):
        I = ICE
        self.popups.append(("ICE SHARDS!", ICE_C))
        sounds.play("star")
        self._storm_reaction("ice")
        for i in range(I["shards"]):
            off = (i - (I["shards"] - 1) / 2) * I["fan"]
            self._later(1 + i * I["gap"], lambda off=off: self._shoot_ice(off))

    def _shoot_ice(self, off):
        if self.foe is None:
            return
        I = ICE
        self._shoot("ice", ICE_C, I["damage"], I["radius"], I["speed"], self._aim(self.foe, off), self._ice_hit)

    def _ice_hit(self, shot):
        foe = self.foe
        if foe is None or foe.hp <= 0:
            return
        self._bloom_react(foe, "ice")                      # BLOSSOM + ICE
        if self.burn > 0 and self._cool("thermal", 90):    # FIRE + ICE
            self._thermal_shock(foe)
            return
        if self.wet > 0:                       # wet + ice = frozen solid
            self.wet = 0
            foe.hp -= ICE["freeze_damage"]
            foe.apply_stun(ICE["freeze_frames"], 0, ICE_C)
            self.freeze = ICE["freeze_frames"]
            self.frost = MARKS["frost_frames"]
            self._react(foe, "FROZEN!", ICE_C, ring=120, flash=(200, 235, 255))
            sounds.play("boom")
            self._shard_burst(foe.body.position.x, foe.body.position.y, n=12, reach=70)
            self._cracks(foe.body.position.x, foe.body.position.y, reach=50)
        else:
            self._mark_frost(foe)

    def _cast_thunder(self):
        L = LIGHTNING
        self.popups.append(("THUNDER!", BOLT_C))
        sounds.play("super")
        self._storm_reaction("thunder")
        self.bolt_bonus = True
        for i in range(L["strikes"]):
            self._later(1 + i * L["gap"], self._spawn_strike)

    def _spawn_strike(self):
        foe = self.foe
        if foe is None or foe.hp <= 0:
            return
        L = LIGHTNING
        if random.random() < L["aim_chance"]:
            x, y = self._predict(foe, L["telegraph"], L["aim_scatter"])
        else:
            x = random.uniform(ARENA_LEFT + 40, ARENA_RIGHT - 40)
            y = random.uniform(ARENA_TOP + 40, ARENA_BOTTOM - 40)
        self.strikes.append({"x": x, "y": y, "delay": L["telegraph"], "flash": 0})

    def _cast_bloom(self):
        self.popups.append(("BLOOM!", BLOOM_C))
        sounds.play("heal")
        self._storm_reaction("bloom")
        for i in range(BLOOM["fruits"]):
            self._later(1 + i * 6, self._grow_fruit)

    def _grow_fruit(self):
        B = BLOOM
        m = B["edge_margin"]
        x = y = 0
        for _ in range(15):                    # try to keep fruits apart from each other
            x = random.uniform(ARENA_LEFT + m, ARENA_RIGHT - m)
            y = random.uniform(ARENA_TOP + m, ARENA_BOTTOM - m)
            if all(math.hypot(x - f["x"], y - f["y"]) > 70 for f in self.fruits):
                break
        watered = any(math.hypot(x - p["x"], y - p["y"]) <= WATER["radius"] for p in self.puddles)
        self.fruits.append({"x": x, "y": y, "age": 0, "timer": B["lifetime"], "wet": watered, "done": False})

    # ---------- per-frame updates of the attacks ----------
    def _update_vortexes(self, foe):
        W = WIND
        for v in self.vortexes:
            v["age"] += 1
            v["timer"] -= 1
            v["rot"] += 0.25
            kind = v["kind"]
            fx_, fy_ = foe.body.position.x, foe.body.position.y
            dx, dy = v["x"] - fx_, v["y"] - fy_
            d = math.hypot(dx, dy) or 1.0

            if d <= W["pull_range"] and foe.stun_timer <= 0:      # bend the enemy's path toward the swirl
                vx, vy = foe.body.velocity
                sp = math.hypot(vx, vy)
                if sp > 1e-6:
                    mult_p = {"thunder": REACTIONS["thunder_pull"], "water": REACTIONS["waterspout_pull"]}.get(kind, 1.0)
                    strength = W["pull_strength"] * mult_p
                    s = strength * (0.4 + 0.6 * (1 - d / W["pull_range"]))
                    nx, ny = vx / sp + dx / d * s, vy / sp + dy / d * s
                    nl = math.hypot(nx, ny) or 1.0
                    foe.body.velocity = (nx / nl * sp, ny / nl * sp)

            if d <= W["radius"]:
                if v["storm"]:
                    self._mark_storm(foe)
                if kind == "thunder":
                    self._mark_shock(foe)
                    v["zap"] -= 1
                    if v["zap"] <= 0:
                        v["zap"] = REACTIONS["zap_gap"]
                        self._zap(v, foe)
                elif kind == "fire":
                    self._ignite(foe, FIRE["pellet_burn_frames"])
                elif kind == "ice":
                    self._mark_frost(foe)
                    self.blizzard = 3
                elif kind == "water":
                    self._make_wet(foe)
                    self.spout = 3
                per = W["vortex_damage"] / W["duration"]
                if kind == "fire":
                    per *= REACTIONS["fire_vortex_mult"]
                elif kind == "bloom":
                    per *= v["mult"]
                v["acc"] += self._amp(per)
                whole = int(v["acc"])
                v["acc"] -= whole
                foe.hp -= whole
        self.vortexes = [v for v in self.vortexes if v["timer"] > 0]

    def _zap(self, v, foe):
        self._hurt(foe, REACTIONS["zap_damage"])
        sounds.play("hit")
        x0, y0 = v["x"], v["y"]

        def fn(screen, p):
            tx, ty = foe.body.position.x, foe.body.position.y
            draw_lightning(screen, (x0, y0), (tx, ty), THUNDER_C, 5, 10, 8)
            draw_lightning(screen, (x0, y0), (tx, ty), (245, 230, 255), 2, 6, 8)
        self._add_fx(8, fn)

    def _update_fire(self, foe):
        if self.fire_t <= 0:
            return
        F = FIRE
        self.fire_age += 1
        self.fire_t -= 1
        if self.fire_age < F["ramp"] * 0.8:
            return
        p = foe.body.position
        edge = min(p.x - ARENA_LEFT, ARENA_RIGHT - p.x, p.y - ARENA_TOP, ARENA_BOTTOM - p.y)
        if edge - foe.radius <= F["band"]:
            self._ignite(foe)

    def _update_puddles(self, foe):
        W = WATER
        for b in self.blobs:
            b["t"] += 1
            if b["t"] >= W["throw_frames"]:
                self.puddles.append({"x": b["tx"], "y": b["ty"], "timer": W["lifetime"], "age": 0})
                b["done"] = True
                for f in self.fruits:           # BLOOM + WATER: a watered fruit grows bigger and stronger
                    if not f["wet"] and math.hypot(f["x"] - b["tx"], f["y"] - b["ty"]) <= W["radius"] + BLOOM["radius"]:
                        f["wet"] = True
                        self.popups.append(("GROWTH!", WATER_C))
        self.blobs = [b for b in self.blobs if not b.get("done")]
        for p in self.puddles:
            p["timer"] -= 1
            p["age"] += 1
            if math.hypot(p["x"] - foe.body.position.x, p["y"] - foe.body.position.y) <= W["radius"] + foe.radius * 0.3:
                self._make_wet(foe)
        self.puddles = [p for p in self.puddles if p["timer"] > 0]

    def _land_strike(self, s, foe):
        L = LIGHTNING
        s["flash"] = 14
        sounds.play("boom")
        if math.hypot(s["x"] - foe.body.position.x, s["y"] - foe.body.position.y) <= L["radius"] + foe.radius:
            self._hurt(foe, L["damage"])
            self._bloom_react(foe, "thunder")                            # BLOSSOM + LIGHTNING
            if self.bolt_bonus and self.wet > 0:                         # WATER + LIGHTNING
                self.bolt_bonus = False
                self.wet = 0
                foe.hp -= L["bonus_damage"]
                self._react(foe, "ELECTROCUTED!", BOLT_C, ring=150, flash=(150, 200, 255), pillar=True)
                self._electro_fx(foe)
                self.shock = MARKS["shock_frames"]
            elif self.bolt_bonus and self.burn > 0:                      # FIRE + LIGHTNING
                self.bolt_bonus = False
                self._plasma(foe)
                self.shock = MARKS["shock_frames"]
            self._mark_shock(foe)
            if (self.frost > 0 or self.freeze > 0) and self._cool("shatter", 30):   # ICE + LIGHTNING
                self._shatter(foe)

    def _update_strikes(self, foe):
        for s in self.strikes:
            if s["delay"] > 0:
                s["delay"] -= 1
                if s["delay"] == 0:
                    self._land_strike(s, foe)
            else:
                s["flash"] -= 1
        self.strikes = [s for s in self.strikes if s["delay"] > 0 or s["flash"] > 0]

    def _update_zones(self, foe):
        R = BLOSSOM_REACT["fire_zone_radius"]
        for z in self.zones:
            z["timer"] -= 1
            if math.hypot(z["x"] - foe.body.position.x, z["y"] - foe.body.position.y) <= R + foe.radius * 0.3:
                self.green_t = max(self.green_t, 40)
                self._ignite(foe, FIRE["pellet_burn_frames"])
        self.zones = [z for z in self.zones if z["timer"] > 0]

    def _update_fruits(self, foe):
        B = BLOOM
        for f in self.fruits:
            f["age"] += 1
            f["timer"] -= 1
            if f["age"] < B["grow_frames"]:
                continue
            r = B["watered_radius"] if f["wet"] else B["radius"]
            if math.hypot(f["x"] - foe.body.position.x, f["y"] - foe.body.position.y) <= r + foe.radius:
                f["done"] = True                                         # the enemy touched it: BLOSSOM
                gain = B["watered_stacks"] if f["wet"] else B["stacks"]
                self.bloom = min(B["max_stacks"], self.bloom + gain)
                foe.popups.append((f"BLOSSOM x{self.bloom}!" if self.bloom > 1 else "BLOSSOM!", BLOOM_C))
                sounds.play("bump")
            elif math.hypot(f["x"] - self.body.position.x, f["y"] - self.body.position.y) <= r + self.radius:
                f["done"] = True                                         # ALI ate it: heal
                self.hp = min(self.max_hp, self.hp + (B["watered_heal"] if f["wet"] else B["heal"]))
                self.flash((120, 255, 150), 20)
                sounds.play("heal")
        self.fruits = [f for f in self.fruits if f["timer"] > 0 and not f["done"]]

    def _update_fx(self):
        for e in self.fx:
            e["t"] -= 1
        self.fx = [e for e in self.fx if e["t"] > 0]

    # ---------- main update ----------
    def update_abilities(self, target, projectiles, scratch_effects):
        if self.hp <= 0:
            if self.foe is not None:
                self.foe.hud_marks = []
            return
        self.t += 1
        if self.burst_t > 0:
            self.burst_t -= 1
        if not self._registered:       # ground effects are drawn under the balls through main.py's effect list
            scratch_effects.append({"x": 0, "y": 0, "sprite": None, "timer": 10 ** 9, "draw": self._draw_ground})
            self._registered = True

        self.foe = target
        self._proj = projectiles
        alive = target is not None and target.hp > 0
        self._update_fx()
        self._tick_status(target, alive)
        if target is not None:
            self._sync_marks(target)
        if not alive:
            return

        self._run_schedule()
        self._update_vortexes(target)
        self._update_fire(target)
        self._update_puddles(target)
        self._update_strikes(target)
        self._update_fruits(target)
        self._update_zones(target)

        # the "super" bar is the countdown to the next random attack
        self.charge += self.charge_rate()
        self.super_charge = min(self.max_super, int(self.max_super * self.charge / CAST["interval"]))
        if self.charge >= CAST["interval"]:
            self.charge = 0
            self._cast()

        k = self.charge / CAST["interval"]               # the energy orbs speed up after the absorb moment
        P = AURA["absorb_at"]
        self.spin_speed = AURA["slow_spin"] + (AURA["fast_spin"] * ((k - P) / (1 - P)) ** 2 if k > P else 0.0)
        self.spin += self.spin_speed

    # ---------- drawing ----------
    def _draw_vortex(self, screen, v):
        W = WIND
        kind = v["kind"]
        col = VORTEX_COLORS[kind]
        k = max(0.0, min(1.0, v["age"] / 20, v["timer"] / 20))
        R = W["radius"]
        x, y = v["x"], v["y"]
        disc = pygame.Surface((R * 2, R * 2), pygame.SRCALPHA)
        pygame.draw.circle(disc, (*col, int(55 * k)), (R, R), R)
        pygame.draw.circle(disc, (*col, int(120 * k)), (R, R), R, 2)
        screen.blit(disc, (int(x - R), int(y - R)))
        for arm in range(4):
            for j in range(18):
                f = j / 17
                r = R * f * k
                a = v["rot"] + arm * math.pi / 2 + f * 3.2
                c2 = tuple(int(col[c] * (1 - f * 0.6) + 255 * f * 0.6) for c in range(3))
                pygame.draw.circle(screen, c2, (int(x + math.cos(a) * r), int(y + math.sin(a) * r)),
                                   max(2, int(7 * (1 - f)) + 2))
        if kind == "thunder":                  # crackling arcs inside the purple storm
            for _ in range(2):
                a = random.uniform(0, TAU)
                rr = R * random.uniform(0.4, 1.0) * k
                draw_lightning(screen, (x, y), (x + math.cos(a) * rr, y + math.sin(a) * rr), THUNDER_C, 3, 8, 4)
                draw_lightning(screen, (x, y), (x + math.cos(a) * rr, y + math.sin(a) * rr), (245, 230, 255), 1, 5, 4)
        elif kind == "fire":                   # embers
            for _ in range(7):
                ox, oy = random.uniform(-R, R) * 0.8 * k, random.uniform(-R, R) * 0.7 * k
                pygame.draw.circle(screen, random.choice((FIRE_C, (255, 220, 80))), (int(x + ox), int(y + oy)), random.randint(2, 4))
        elif kind == "ice":                    # snow
            for _ in range(9):
                ox, oy = random.uniform(-R, R) * 0.85 * k, random.uniform(-R, R) * 0.85 * k
                pygame.draw.circle(screen, (240, 252, 255), (int(x + ox), int(y + oy)), random.randint(2, 3))
        elif kind == "water":                  # flying droplets
            for _ in range(10):
                ox, oy = random.uniform(-R, R) * 0.85 * k, random.uniform(-R, R) * 0.85 * k
                pygame.draw.circle(screen, (190, 225, 255), (int(x + ox), int(y + oy)), random.randint(2, 4))
        elif kind == "bloom":                  # petals and pollen
            for _ in range(10):
                ox, oy = random.uniform(-R, R) * 0.85 * k, random.uniform(-R, R) * 0.85 * k
                pygame.draw.circle(screen, random.choice((BLOOM_C, (255, 225, 90), (150, 255, 100))),
                                   (int(x + ox), int(y + oy)), random.randint(2, 4))

    def _draw_fruit(self, screen, f):
        B = BLOOM
        grow = min(1.0, f["age"] / B["grow_frames"])
        base_r = B["watered_radius"] if f["wet"] else B["radius"]
        r = int(base_r * grow)
        if r < 2:
            return
        if f["timer"] < 60 and (f["timer"] // 4) % 2 == 0:       # about to wither: blinks
            return
        x, y = int(f["x"]), int(f["y"])
        pygame.draw.ellipse(screen, (40, 70, 40), pygame.Rect(x - r - 4, y + r - 5, (r + 4) * 2, 10))      # mound
        sway = math.sin(self.t * 0.08 + f["x"]) * 2
        pygame.draw.line(screen, (60, 170, 70), (x, y + r), (x + sway, y - r - 2), 3)                      # stem
        pygame.draw.polygon(screen, (80, 200, 90), [(x + sway, y - r), (x + sway + 11, y - r - 8), (x + sway + 3, y - r + 3)])
        pygame.draw.polygon(screen, (60, 170, 70), [(x + sway, y - r), (x + sway - 10, y - r - 6), (x + sway - 3, y - r + 3)])
        if f["wet"]:
            pygame.draw.circle(screen, WATER_C, (x, y), r + 5, 2)
        pygame.draw.circle(screen, (110, 25, 120), (x, y), r)
        pygame.draw.circle(screen, BLOOM_C, (x, y), r, 2)
        pygame.draw.circle(screen, (255, 200, 240), (x - r // 3, y - r // 3), max(2, r // 4))
        by = y - ((self.t + int(f["x"])) * 0.7) % (r * 2.2)                                                 # poison bubble
        pygame.draw.circle(screen, (140, 255, 100), (int(x + math.sin(self.t * 0.2) * r * 0.6), int(by)), 2)

    def _draw_ground(self, screen):
        if self.hp <= 0:
            return

        for v in self.vortexes:
            self._draw_vortex(screen, v)

        # burning borders
        if self.fire_t > 0:
            F = FIRE
            k = max(0.0, min(1.0, self.fire_age / F["ramp"], self.fire_t / F["ramp"]))
            for surf, pos in self._strips:
                surf.set_alpha(int(110 * k))
                screen.blit(surf, pos)
            L, R_, T, B = ARENA_LEFT, ARENA_RIGHT, ARENA_TOP, ARENA_BOTTOM
            W_, H_ = R_ - L, B - T
            sides = (((L, T), (1, 0), (0, 1), W_), ((L, B), (1, 0), (0, -1), W_),
                     ((L, T), (0, 1), (1, 0), H_), ((R_, T), (0, 1), (-1, 0), H_))
            for (ox, oy), (tx, ty), (nx, ny), length in sides:
                for s in range(0, length, 12):
                    bx, by = ox + tx * s, oy + ty * s
                    h = random.uniform(12, 34) * k + 3
                    w = random.uniform(8, 14)
                    sway = random.uniform(-4, 4)
                    tip = (bx + nx * h + tx * sway, by + ny * h + ty * sway)
                    pygame.draw.polygon(screen, FIRE_C, [(bx - tx * w / 2, by - ty * w / 2), tip,
                                                         (bx + tx * w / 2, by + ty * w / 2)])
                    tip2 = (bx + nx * h * 0.55 + tx * sway * 0.5, by + ny * h * 0.55 + ty * sway * 0.5)
                    pygame.draw.polygon(screen, (255, 220, 80), [(bx - tx * w / 4, by - ty * w / 4), tip2,
                                                                 (bx + tx * w / 4, by + ty * w / 4)])

        # puddles on the ground
        Wt = WATER
        for p in self.puddles:
            k = min(1.0, p["timer"] / 30)
            r = Wt["radius"]
            w, h = r * 2, int(r * 1.5)
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(surf, (*WATER_C, int(120 * k)), surf.get_rect())
            pygame.draw.ellipse(surf, (170, 220, 255, int(200 * k)), surf.get_rect(), 2)
            rr = (p["age"] * 0.8) % r
            if rr > 4:
                pygame.draw.ellipse(surf, (255, 255, 255, int(90 * k * (1 - rr / r))),
                                    pygame.Rect(r - rr, h // 2 - rr * 0.75, rr * 2, rr * 1.5), 1)
            screen.blit(surf, (int(p["x"] - w // 2), int(p["y"] - h // 2)))

        for b in self.blobs:                    # puddles flying through the air
            f = b["t"] / Wt["throw_frames"]
            x = b["sx"] + (b["tx"] - b["sx"]) * f
            y = b["sy"] + (b["ty"] - b["sy"]) * f - math.sin(math.pi * f) * 60
            pygame.draw.circle(screen, WATER_C, (int(x), int(y)), 10)
            pygame.draw.circle(screen, (200, 235, 255), (int(x) - 3, int(y) - 3), 3)

        for f in self.fruits:
            self._draw_fruit(screen, f)

        # WILDFIRE rings on the floor
        for z in self.zones:
            R = BLOSSOM_REACT["fire_zone_radius"]
            k = max(0.0, min(1.0, (z["max"] - z["timer"]) / 10, z["timer"] / 25))
            disc = pygame.Surface((R * 2 + 20, R * 2 + 20), pygame.SRCALPHA)
            pygame.draw.circle(disc, (90, 230, 70, int(70 * k)), (R + 10, R + 10), R)
            pygame.draw.circle(disc, (170, 255, 110, int(200 * k)), (R + 10, R + 10), R, 3)
            screen.blit(disc, (int(z["x"] - R - 10), int(z["y"] - R - 10)))
            for _ in range(26):
                a = random.uniform(0, TAU)
                rr = R * (1 if random.random() < 0.5 else random.uniform(0.2, 0.95))
                bx, by = z["x"] + math.cos(a) * rr, z["y"] + math.sin(a) * rr
                h = random.uniform(10, 30) * k + 2
                pygame.draw.polygon(screen, (90, 230, 70), [(bx - 5, by), (bx + random.uniform(-3, 3), by - h), (bx + 5, by)])
                pygame.draw.polygon(screen, (220, 255, 130), [(bx - 2, by), (bx, by - h * 0.55), (bx + 2, by)])

        L_ = LIGHTNING                          # lightning warning circles
        for s in self.strikes:
            if s["delay"] > 0:
                f = s["delay"] / L_["telegraph"]
                pygame.draw.circle(screen, BOLT_C, (int(s["x"]), int(s["y"])), L_["radius"], 2)
                pygame.draw.circle(screen, (255, 255, 255), (int(s["x"]), int(s["y"])),
                                   max(2, int(L_["radius"] * (1 - f))), 1)

    def _aura_color(self, sel, ab):
        """Rainbow of all elements while gathering; turns into the color of the coming element after the absorb."""
        n = len(ATTACK_COLORS)
        f = (self.t * 0.02) % n
        i = int(f)
        u = f - i
        c1, c2 = ATTACK_COLORS[i], ATTACK_COLORS[(i + 1) % n]
        rb = tuple(int(c1[c] * (1 - u) + c2[c] * u) for c in range(3))
        return tuple(int(rb[c] * (1 - ab) + sel[c] * ab) for c in range(3))

    def draw(self, screen):
        if self.hp <= 0:
            return
        A = AURA
        r = self.radius
        x, y = int(self.body.position.x), int(self.body.position.y)
        k = self.charge / CAST["interval"]
        P = A["absorb_at"]
        nxt = ATTACK_NAMES.index(self.next_attack)
        sel = ATTACK_COLORS[nxt]
        ab = max(0.0, min(1.0, (k - P) / 0.07)) if k >= P else 0.0      # absorb progress
        u = max(0.0, min(1.0, (k - P) / (1 - P))) if k >= P else 0.0    # fast-spin progress
        col = self._aura_color(sel, ab)
        pulse = 0.5 + 0.5 * math.sin(self.t * (0.08 + 0.25 * u))
        inten = 0.45 + 0.35 * k + 0.6 * u * u + 0.5 * math.sin(math.pi * min(1.0, ab))

        H = r + 95
        S = H * 2

        # ---------- aura behind the ball ----------
        aura = pygame.Surface((S, S), pygame.SRCALPHA)
        for i in reversed(range(7)):                       # soft glow
            rr = r + 4 + i * 6
            a = int(min(255, 70 * inten * (1 - i / 7) ** 1.4 * (0.8 + 0.4 * pulse)))
            pygame.draw.circle(aura, (*col, a), (H, H), rr)
        for j in range(16):                                # energy wisps licking around the ball
            ang = j * TAU / 16 + self.spin * 0.4
            ln = (8 + 20 * inten) * (0.7 + 0.5 * math.sin(self.t * 0.22 + j * 1.7))
            sway = 0.25 * math.sin(self.t * 0.1 + j)
            b0, b1 = ang - 0.13, ang + 0.13
            tip = (H + math.cos(ang + sway) * (r + 2 + ln), H + math.sin(ang + sway) * (r + 2 + ln))
            p0 = (H + math.cos(b0) * (r + 1), H + math.sin(b0) * (r + 1))
            p1 = (H + math.cos(b1) * (r + 1), H + math.sin(b1) * (r + 1))
            pygame.draw.polygon(aura, (*col, int(min(255, 120 * inten))), [p0, tip, p1])
            tip2 = (H + math.cos(ang + sway) * (r + 2 + ln * 0.55), H + math.sin(ang + sway) * (r + 2 + ln * 0.55))
            pygame.draw.polygon(aura, (*_light(col, 0.6), int(min(255, 150 * inten))), [p0, tip2, p1])
        if u > 0.25:                                       # fast swirl: bright arcs racing around him
            rr = r + A["orbit"] - 6 * u
            for m in range(3):
                a0 = self.spin * 1.3 + m * TAU / 3
                pygame.draw.arc(aura, (*_light(col, 0.5), int(200 * u)), pygame.Rect(H - rr, H - rr, rr * 2, rr * 2),
                                a0, a0 + 0.9, 3)
        if self.burst_t > 0:                               # the cast: expanding shockwave
            p = 1 - self.burst_t / 24
            pygame.draw.circle(aura, (*self.burst_col, int(110 * (1 - p))), (H, H), int(r + 6 + 80 * p))
            pygame.draw.circle(aura, (255, 255, 255, int(230 * (1 - p))), (H, H), int(r + 6 + 80 * p), max(1, int(5 * (1 - p)) + 1))
        screen.blit(aura, (x - H, y - H))

        super().draw(screen)

        # ---------- energy orbs in front ----------
        orbs = pygame.Surface((S, S), pygame.SRCALPHA)
        per = A["per_element"]
        n = len(ATTACK_COLORS)
        total = n * per
        for j in range(per):
            for i, ecol in enumerate(ATTACK_COLORS):
                idx = j * n + i
                selected = (i == nxt)
                orbit = r + A["orbit"] + 3 * math.sin(self.t * 0.1 + idx)
                ang = self.spin + idx * TAU / total
                size = 4.0
                alpha = 1.0
                app = max(0.0, min(1.0, (k - (idx / total) * A["return_span"]) / 0.08))   # coming back after a cast
                dist = orbit
                if app < 1.0:
                    dist = orbit + (1 - app) ** 2 * 75
                    alpha = app
                if k >= P and not selected:                # absorbed into ALI
                    if ab >= 1.0:
                        continue
                    dist = orbit * (1 - ab) ** 1.5
                    ang += ab * 2.5
                    size *= 1 - 0.6 * ab
                    px, py = H + math.cos(ang) * dist, H + math.sin(ang) * dist
                    pygame.draw.line(orbs, (*ecol, int(170 * (1 - ab))), (px, py), (H, H), 2)
                if selected and u > 0:
                    dist -= 6 * u
                    size += 2.5 * u
                px, py = H + math.cos(ang) * dist, H + math.sin(ang) * dist
                if selected and u > 0.05:                  # speed trail
                    for mm in range(1, 8):
                        a2 = ang - mm * self.spin_speed * 0.9
                        qx, qy = H + math.cos(a2) * dist, H + math.sin(a2) * dist
                        pygame.draw.circle(orbs, (*ecol, int(130 * alpha * (1 - mm / 8))), (int(qx), int(qy)),
                                           max(1, int(size * (1 - mm / 9))))
                a_glow = int(255 * alpha)
                pygame.draw.circle(orbs, (*ecol, int(70 * alpha)), (int(px), int(py)), int(size + 6))
                pygame.draw.circle(orbs, (*ecol, int(150 * alpha)), (int(px), int(py)), int(size + 3))
                pygame.draw.circle(orbs, (*ecol, a_glow), (int(px), int(py)), max(1, int(size)))
                pygame.draw.circle(orbs, (255, 255, 255, a_glow), (int(px), int(py)), max(1, int(size // 2.5)))
        if 0 < ab < 1:                                     # flare while the orbs are swallowed
            pygame.draw.circle(orbs, (255, 255, 255, int(170 * (1 - ab))), (H, H), int(r + 6 + 30 * ab), 3)
        screen.blit(orbs, (x - H, y - H))

    def draw_overlay(self, screen):
        """Called by main.py after the balls are drawn: lightning, reaction effects, marks on the enemy."""
        if self.hp <= 0:
            return
        L = LIGHTNING
        for s in self.strikes:
            if s["delay"] == 0 and s["flash"] > 0:
                a = s["flash"] / 14
                R = L["radius"] + 20
                glow = pygame.Surface((R * 2, R * 2), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*BOLT_C, int(130 * a)), (R, R), R)
                pygame.draw.circle(glow, (255, 255, 255, int(200 * a)), (R, R), L["radius"] // 2)
                screen.blit(glow, (int(s["x"] - R), int(s["y"] - R)))
                for w, col, jit in ((9, BOLT_C, 16), (5, (255, 255, 200), 12), (2, (255, 255, 255), 8)):
                    draw_lightning(screen, (s["x"] + random.uniform(-25, 25), ARENA_TOP), (s["x"], s["y"]),
                                   col, w, jit, 10)

        for e in self.fx:
            e["fn"](screen, 1.0 - e["t"] / e["max"])

        foe = self.foe
        if foe is None or foe.hp <= 0:
            return
        x, y, r = int(foe.body.position.x), int(foe.body.position.y), foe.radius

        if self.wet > 0:
            pygame.draw.circle(screen, WATER_C, (x, y), r + 3, 2)
            for _ in range(5):
                a = random.uniform(0, TAU)
                d = r + random.uniform(0, 10)
                pygame.draw.circle(screen, (150, 210, 255),
                                   (int(x + math.cos(a) * d), int(y + math.sin(a) * d + random.uniform(0, 6))),
                                   random.randint(2, 3))

        if self.burn > 0:
            green = self.green_t > 0                     # WILDFIRE: poison makes the flames green
            for _ in range(6):
                px = x + random.uniform(-r, r) * 0.9
                py = y + random.uniform(-r * 0.3, r * 0.8)
                h = random.uniform(14, 28)
                outer = (90, 230, 70) if green else FIRE_C
                inner = (210, 255, 120) if green else (255, 220, 80)
                pygame.draw.polygon(screen, outer, [(px - 5, py), (px + random.uniform(-3, 3), py - h), (px + 5, py)])
                pygame.draw.polygon(screen, inner, [(px - 2.5, py), (px, py - h * 0.55), (px + 2.5, py)])

        if self.shock > 0:
            for _ in range(2):
                a = random.uniform(0, TAU)
                draw_lightning(screen, (x + math.cos(a) * (r + 2), y + math.sin(a) * (r + 2)),
                               (x + math.cos(a) * (r + 16), y + math.sin(a) * (r + 16)), BOLT_C, 2, 3, 3)

        if self.bloom > 0:                               # petals circling the enemy (more stacks = more petals)
            for i in range(min(8, 2 + self.bloom)):
                a = self.t * 0.05 + i * TAU / min(8, 2 + self.bloom)
                px, py = x + math.cos(a) * (r + 6), y + math.sin(a) * (r + 6)
                pygame.draw.circle(screen, BLOOM_C, (int(px), int(py)), 3)
                pygame.draw.circle(screen, (255, 225, 90), (int(px), int(py)), 1)

        if self.root_t > 0:                              # OVERGROWTH: vines wrap around the enemy
            grow = min(1.0, (self.root_total - self.root_t + 1) / 10)
            for i in range(7):
                a0 = i * TAU / 7 + 0.3
                pts = []
                for j in range(12):
                    f = j / 11 * grow
                    rr = (r + 16) - (r + 14) * f
                    a = a0 + f * 1.7
                    pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
                if len(pts) > 1:
                    pygame.draw.lines(screen, (60, 170, 70), False, pts, 4)
                    pygame.draw.lines(screen, (120, 230, 110), False, pts, 1)
                    lx, ly = pts[len(pts) // 2]
                    pygame.draw.circle(screen, BLOOM_C, (int(lx), int(ly)), 3)
                    pygame.draw.circle(screen, (255, 225, 90), (int(lx), int(ly)), 1)

        if self.freeze > 0 and foe.stun_timer > 0:
            R = r + 14
            ice = pygame.Surface((R * 2, R * 2), pygame.SRCALPHA)
            pygame.draw.circle(ice, (*ICE_C, 120), (R, R), r + 8)
            pygame.draw.circle(ice, (255, 255, 255, 220), (R, R), r + 8, 3)
            screen.blit(ice, (x - R, y - R))
            for i in range(8):
                a = i * TAU / 8 + 0.2
                ca, sa = math.cos(a), math.sin(a)
                base = r + 6
                pygame.draw.polygon(screen, (235, 250, 255),
                                    [(x + ca * base - sa * 4, y + sa * base + ca * 4),
                                     (x + ca * (base + 14), y + sa * (base + 14)),
                                     (x + ca * base + sa * 4, y + sa * base - ca * 4)])