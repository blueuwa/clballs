import math
import random
import pygame
from brawler import BaseBrawler, draw_lightning
from config import ARENA_LEFT, ARENA_RIGHT, ARENA_TOP, ARENA_BOTTOM, SCREEN_WIDTH, SCREEN_HEIGHT

PURPLE = (175, 95, 255)          # main electric purple
PURPLE_LIGHT = (225, 195, 255)   # bright purple-white (bolt cores)
PURPLE_DARK = (110, 50, 190)

# ===================== EDIT STATS HERE =====================
STATS = {
    "name": "BLUE",
    "filename": "3.png",
    "max_hp": 1600,
    "speed_mult": 1.5,        # multiplies the starting speed (speed stays constant)
    "radius": 28,
    "contact_damage": 10,     # damage dealt to the enemy when the balls touch

    "max_super": 100,         # size of the super bar
    "super_per_hit": 15,      # super gained each time the POLEARM hits (nothing else charges it)
    "super_per_contact": 0,   # balls bumping does NOT charge his super
}

POLEARM = {
    "length": 65,             # pixels from the grip to the tip of the blade (at rest)
    "tail": 34,               # how far the shaft sticks out BEHIND the grip
    "side_offset": 33,        # how far from the ball's center the grip sits (a bit more than the radius)
    "thickness": 7,           # hitbox thickness of the blade

    # Combo: STAB (knocks the enemy back) -> pull back -> fire the electric C. Then a long cooldown.
    "damage": 100,            # stab damage (every knockback)
    "knock_speed": 1500.0,     # starting speed of the knockback (pixels/second); it slows down to normal
    "knock_frames": 15,       # how long the knockback lasts
    "stab_distance": 48,      # how far the polearm lunges forward
    "stab_frames": 5,         # frames to thrust out (fast)
    "retract_frames": 12,     # frames to pull back (slower)
    "cast_frames": 14,        # frames spent charging the C before it is fired
    "combo_cooldown": 140,    # frames AFTER the C is fired before the next combo (140 = ~2.3 seconds)
    "alert_extra": 55,        # starts turning toward the enemy this far before it can stab
    "idle_angle": -97,        # degrees at rest (-90 = straight up, slightly tilted outward)
    "idle_turn": 0.08,        # radians/frame it returns to the resting pose
    "aim_turn": 0.30,         # radians/frame it turns toward the enemy
    "cast_turn": 0.45,        # radians/frame it aims at the enemy while charging the C

    "spark_color": PURPLE,
}

# The wide electric "C" that flies out after the stab (slows the enemy)
THUNDER_C = {
    "speed": 15.0,            # pixels per frame
    "radius": 72,             # radius of the C (bigger = wider)
    "span": 150,              # degrees of the arc (360 would be a full ring)
    "thickness": 12,          # hitbox / glow thickness of the arc
    "damage": 150,            # damage when the C hits
    "slow_duration": 120,     # 2 seconds
    "slow_factor": 0.8,       # slowed enemies move at 40% of their speed
    "slow_dps": 25,           # damage per second while slowed
    "flip": False,            # False = the round side leads, True = the opening leads
    "color": PURPLE,
}

# Super: a continuous ray of thunder from the polearm that stuns the enemy
ULTIMATE = {
    "ray_duration": 240,      # 4 seconds total (allows 3 seconds of full cinema)
    "ray_width": 20,          # thickness of the glow around the ray
    "stun_duration": 180,     # 3 seconds
    "stun_dps": 200,          # damage per second while stunned
    "ray_color": PURPLE,
}
# ===========================================================


def _closest_on_segment(px, py, ax, ay, bx, by):
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby or 1.0
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / denom))
    return ax + abx * t, ay + aby * t


def _turn(cur, want, step):
    d = (want - cur + math.pi) % (2 * math.pi) - math.pi
    return cur + max(-step, min(step, d)), d


class Blue(BaseBrawler):
    def __init__(self, space, pos, velocity):
        super().__init__(space, pos, velocity, STATS)
        self.pole_angle = math.radians(POLEARM["idle_angle"])
        self.pole_state = "idle"      # idle -> thrust -> retract -> cast -> idle
        self.thrust = 0.0             # 0 = resting, 1 = fully extended
        self.phase_hit = False        # has the current stab already connected?
        self.cast_t = 0
        self.hit_cooldown = 0
        self.ray_timer = 0
        self.ray_total = 0
        self.ray_geom = None
        self.ray_stunned = False
        self.waves = []               # electric C's currently flying
        self.sway = random.uniform(0, 6.28)
        self.random_bolts = []        # random short lightning sparks on the screen edges

    # ---------- geometry ----------
    def _axis(self):
        """Grip point (held beside the ball) and the unit direction of the shaft."""
        a = self.pole_angle
        dx, dy = math.cos(a), math.sin(a)
        nx, ny = -dy, dx
        off = POLEARM["side_offset"]
        bx = self.body.position.x + nx * off
        by = self.body.position.y + ny * off
        return bx, by, dx, dy

    def _shift(self):
        return self.thrust * POLEARM["stab_distance"]

    def _tip(self):
        bx, by, dx, dy = self._axis()
        d = POLEARM["length"] + self._shift()
        return bx + dx * d, by + dy * d

    def _spark_burst(self, x, y, effects):
        frames = 12
        color = POLEARM["spark_color"]
        angles = [random.uniform(0, math.pi * 2) for _ in range(7)]

        def draw(screen):
            for a in angles:
                ln = random.uniform(22, 40)
                draw_lightning(screen, (x, y), (x + math.cos(a) * ln, y + math.sin(a) * ln), color, 3, 5, 3)
                draw_lightning(screen, (x, y), (x + math.cos(a) * ln * 0.6, y + math.sin(a) * ln * 0.6), PURPLE_LIGHT, 1, 3, 2)

        effects.append({"x": x, "y": y, "sprite": None, "timer": frames, "draw": draw})

    # ---------- super: continuous ray ----------
    def _start_ray(self, effects):
        self.ray_timer = ULTIMATE["ray_duration"]
        self.ray_total = ULTIMATE["ray_duration"]
        self.ray_stunned = False
        self.random_bolts = []        # clear any leftover bolts
        color = ULTIMATE["ray_color"]
        width = ULTIMATE["ray_width"]

        def draw(screen):
            if self.ray_timer <= 0 or not self.ray_geom:
                return
            (ox, oy), (ex, ey) = self.ray_geom
            glow = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            pygame.draw.line(glow, (*color, 70), (ox, oy), (ex, ey), width)
            pygame.draw.line(glow, (*color, 110), (ox, oy), (ex, ey), max(4, width // 2))
            screen.blit(glow, (0, 0))
            for w, col, jit in ((7, color, 9), (4, PURPLE_LIGHT, 6), (2, (255, 245, 255), 4)):
                draw_lightning(screen, (ox, oy), (ex, ey), col, w, jit, 14)
            pygame.draw.circle(screen, (255, 245, 255), (int(ox), int(oy)), 9)
            pygame.draw.circle(screen, color, (int(ox), int(oy)), 15, 3)

        effects.append({"x": self.body.position.x, "y": self.body.position.y, "sprite": None,
                        "timer": ULTIMATE["ray_duration"] + 1, "draw": draw})

    def _update_ray(self, target):
        cx, cy = self.body.position.x, self.body.position.y
        tx, ty = target.body.position.x, target.body.position.y

        # the polearm points at the enemy and is held slightly forward while the ray is on
        self.pole_angle = math.atan2(ty - cy, tx - cx)
        self.pole_state = "idle"
        self.thrust = 0.3

        # the ray leaves from the blade tip
        ox, oy = self._tip()
        dx, dy = tx - ox, ty - oy
        dist = math.hypot(dx, dy)
        if dist < target.radius + 8:          # enemy is on top of the tip: shoot from the ball instead
            ox, oy = cx, cy
            dx, dy = tx - ox, ty - oy
            dist = math.hypot(dx, dy)
        dist = dist or 1.0
        ux, uy = dx / dist, dy / dist

        tmax = 10 ** 6                        # ... and goes on until it hits the arena wall
        if ux > 1e-6:
            tmax = min(tmax, (ARENA_RIGHT - ox) / ux)
        elif ux < -1e-6:
            tmax = min(tmax, (ARENA_LEFT - ox) / ux)
        if uy > 1e-6:
            tmax = min(tmax, (ARENA_BOTTOM - oy) / uy)
        elif uy < -1e-6:
            tmax = min(tmax, (ARENA_TOP - oy) / uy)
        self.ray_geom = ((ox, oy), (ox + ux * tmax, oy + uy * tmax))

        if not self.ray_stunned:              # stun once, when the ray first hits
            self.ray_stunned = True
            target.apply_stun(ULTIMATE["stun_duration"], ULTIMATE["stun_dps"], ULTIMATE["ray_color"])
            target.popups.append(("STUNNED!", PURPLE_LIGHT))

    # ---------- polearm behaviour (idle / stab) ----------
    def _try_hit(self, target, effects):
        bx, by, dx, dy = self._axis()
        shift = self._shift()
        L = POLEARM["length"]
        hx, hy = bx + dx * (L - 40 + shift), by + dy * (L - 40 + shift)    # start of the blade
        tipx, tipy = bx + dx * (L + shift), by + dy * (L + shift)
        tx, ty = target.body.position.x, target.body.position.y
        qx, qy = _closest_on_segment(tx, ty, hx, hy, tipx, tipy)
        if math.hypot(tx - qx, ty - qy) <= target.radius + POLEARM["thickness"] / 2:
            self.phase_hit = True
            target.hp -= POLEARM["damage"]
            self.add_super(self.super_per_hit)          # only the polearm / C charge the super
            self._spark_burst(qx, qy, effects)
            # knock the enemy straight away from Blue
            kx, ky = tx - self.body.position.x, ty - self.body.position.y
            kl = math.hypot(kx, ky) or 1.0
            target.apply_knockback(kx / kl, ky / kl, POLEARM["knock_speed"], POLEARM["knock_frames"])

    def _update_pole(self, target, target_alive, effects):
        P = POLEARM
        idle = math.radians(P["idle_angle"]) + math.sin(self.sway) * 0.04
        self.sway += 0.05
        st = self.pole_state

        if st == "idle":
            want, step = idle, P["idle_turn"]
            if target_alive:
                bx, by, _, _ = self._axis()
                tx, ty = target.body.position.x, target.body.position.y
                dist = math.hypot(tx - bx, ty - by)
                reach = P["length"] + P["stab_distance"] * 0.6 + target.radius
                if dist <= reach + P["alert_extra"]:
                    want, step = math.atan2(ty - by, tx - bx), P["aim_turn"]
                self.pole_angle, diff = _turn(self.pole_angle, want, step)
                if dist <= reach and self.hit_cooldown <= 0 and abs(diff) < 0.25:
                    self.pole_state = "thrust"
                    self.phase_hit = False
            else:
                self.pole_angle, _ = _turn(self.pole_angle, want, step)
            self.thrust = max(0.0, self.thrust - 1.0 / P["retract_frames"])

        elif st == "thrust":
            self.thrust = min(1.0, self.thrust + 1.0 / P["stab_frames"])
            if target_alive and not self.phase_hit and self.thrust >= 0.4:
                self._try_hit(target, effects)
            if self.thrust >= 1.0:
                self.pole_state = "retract"

        elif st == "retract":
            self.thrust = max(0.0, self.thrust - 1.0 / P["retract_frames"])
            if target_alive and not self.phase_hit and self.thrust >= 0.4:
                self._try_hit(target, effects)
            if self.thrust <= 0.0:
                self.pole_state = "cast"
                self.cast_t = 0

        else:  # cast: aim at the enemy, gather energy at the tip, then fire the C
            if not target_alive:
                self.pole_state = "idle"
                return
            bx, by, _, _ = self._axis()
            want = math.atan2(target.body.position.y - by, target.body.position.x - bx)
            self.pole_angle, _ = _turn(self.pole_angle, want, P["cast_turn"])
            self.cast_t += 1
            if self.cast_t >= P["cast_frames"]:
                self._launch_c(target, effects)
                self.thrust = 0.5                     # little recoil lunge as it fires
                self.pole_state = "idle"
                self.hit_cooldown = P["combo_cooldown"]

    # ---------- the electric C ----------
    def _c_points(self, w, steps):
        C = THUNDER_C
        R = C["radius"]
        half = math.radians(C["span"]) / 2
        sgn = -1 if C["flip"] else 1
        ux, uy = w["ux"], w["uy"]
        nx, ny = -uy, ux
        pts = []
        for i in range(steps + 1):
            phi = -half + 2 * half * i / steps
            c, s_ = math.cos(phi) * sgn, math.sin(phi)
            pts.append((w["ox"] + R * (c * ux + s_ * nx), w["oy"] + R * (c * uy + s_ * ny)))
        return pts

    def _launch_c(self, target, effects):
        C = THUNDER_C
        tipx, tipy = self._tip()
        dx, dy = target.body.position.x - tipx, target.body.position.y - tipy
        d = math.hypot(dx, dy)
        if d < 1e-6:
            _, _, dx, dy = self._axis()
            d = 1.0
        ux, uy = dx / d, dy / d
        sgn = -1 if C["flip"] else 1
        w = {"ox": tipx - sgn * ux * C["radius"], "oy": tipy - sgn * uy * C["radius"],
             "ux": ux, "uy": uy, "alive": True}
        self.waves.append(w)
        color = C["color"]
        th = C["thickness"]

        def draw(screen):
            if not w["alive"]:
                return
            pts = self._c_points(w, 28)
            pad = th + 50
            minx = int(min(p[0] for p in pts) - pad)
            miny = int(min(p[1] for p in pts) - pad)
            wd = int(max(p[0] for p in pts) + pad) - minx
            ht = int(max(p[1] for p in pts) + pad) - miny
            layer = pygame.Surface((wd, ht), pygame.SRCALPHA)
            loc = [(x - minx, y - miny) for x, y in pts]
            for x, y in loc:                                   # soft glow
                pygame.draw.circle(layer, (*color, 45), (int(x), int(y)), th + 6)
            for x, y in loc:
                pygame.draw.circle(layer, (*color, 80), (int(x), int(y)), max(3, th // 2 + 2))
            screen.blit(layer, (minx, miny))
            # flickering jagged bolt along the arc: purple body, lavender middle, white core
            for width, col, jit in ((7, color, 5), (4, PURPLE_LIGHT, 4), (2, (255, 245, 255), 3)):
                jag = [(x + random.uniform(-jit, jit), y + random.uniform(-jit, jit)) for x, y in pts]
                pygame.draw.lines(screen, col, False, jag, width)
            # little forks that fly off the outer edge
            for _ in range(4):
                x, y = pts[random.randint(0, len(pts) - 1)]
                ax, ay = x - w["ox"], y - w["oy"]
                al = math.hypot(ax, ay) or 1.0
                ln = random.uniform(14, 30)
                draw_lightning(screen, (x, y), (x + ax / al * ln, y + ay / al * ln), color, 2, 4, 3)

        effects.append({"x": tipx, "y": tipy, "sprite": None, "timer": 400, "draw": draw})

    def _update_waves(self, target, effects):
        C = THUNDER_C
        for w in self.waves:
            w["ox"] += w["ux"] * C["speed"]
            w["oy"] += w["uy"] * C["speed"]
            # gone once the middle of the C reaches the arena wall
            sgn = -1 if C["flip"] else 1
            mx, my = w["ox"] + sgn * w["ux"] * C["radius"], w["oy"] + sgn * w["uy"] * C["radius"]
            if mx < ARENA_LEFT or mx > ARENA_RIGHT or my < ARENA_TOP or my > ARENA_BOTTOM:
                w["alive"] = False
                continue
            if target is not None and target.hp > 0:
                tx, ty = target.body.position.x, target.body.position.y
                lim = target.radius + C["thickness"] / 2
                for px, py in self._c_points(w, 30):
                    if math.hypot(px - tx, py - ty) <= lim:
                        w["alive"] = False
                        target.hp -= C["damage"]
                        self.add_super(self.super_per_hit)
                        target.apply_slow(C["slow_duration"], C["slow_factor"], C["slow_dps"], C["color"])
                        target.popups.append(("SLOWED!", PURPLE_LIGHT))
                        self._spark_burst(tx, ty, effects)
                        break
        self.waves = [w for w in self.waves if w["alive"]]

    # ---------- update ----------
    def update_abilities(self, target, projectiles, scratch_effects):
        if self.hp <= 0:
            return

        self._update_waves(target, scratch_effects)

        if self.hit_cooldown > 0:
            self.hit_cooldown -= 1

        target_alive = target is not None and target.hp > 0

        if self.ray_timer > 0 and target_alive:
            self._update_ray(target)
        else:
            self._update_pole(target, target_alive, scratch_effects)
        if self.ray_timer > 0:
            self.ray_timer -= 1

        # Spawn random short cinematic bolts along the letterbox bars
        if self.ray_timer > 30 and random.random() < 0.3:
            # Pick random start point along the top or bottom bar
            if random.random() < 0.5:
                start_x = random.uniform(ARENA_LEFT, ARENA_RIGHT)
                start_y = SCREEN_HEIGHT * 0.12  # Bottom edge of the top bar
            else:
                start_x = random.uniform(ARENA_LEFT, ARENA_RIGHT)
                start_y = SCREEN_HEIGHT * 0.88  # Top edge of the bottom bar
            
            # Give it a random horizontal length and vertical dip
            end_x = start_x + random.uniform(-150, 150)
            end_y = start_y + random.uniform(-80, 80)
            
            self.random_bolts.append({"sx": start_x, "sy": start_y, "x": end_x, "y": end_y, "timer": random.randint(4, 10)})

        # Tick random bolts
        for b in self.random_bolts:
            b["timer"] -= 1
        self.random_bolts = [b for b in self.random_bolts if b["timer"] > 0]

        # super bar full -> fire the ray
        if self.super_charge >= self.max_super and self.ray_timer <= 0 and target_alive:
            self.super_charge = 0
            self.trigger_super()
            self._start_ray(scratch_effects)
            self._update_ray(target)

    # ---------- drawing ----------
    def _draw_polearm(self, screen):
        bx, by, dx, dy = self._axis()
        nx, ny = -dy, dx
        shift = self._shift()
        L = POLEARM["length"]
        tail = POLEARM["tail"]
        casting = self.pole_state == "cast"
        energized = casting or self.ray_timer > 0
        cast_k = min(1.0, self.cast_t / max(1, POLEARM["cast_frames"])) if casting else 1.0

        def P(s, o=0.0):
            return (bx + dx * (s + shift) + nx * o, by + dy * (s + shift) + ny * o)

        # motion streak while stabbing
        if self.pole_state != "idle" and self.thrust > 0.1:
            streak = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            a = int(90 * self.thrust)
            pygame.draw.polygon(streak, (*PURPLE, a), [P(L - 20 - POLEARM["stab_distance"] * self.thrust, -3),
                                                       P(L, -1), P(L, 1),
                                                       P(L - 20 - POLEARM["stab_distance"] * self.thrust, 3)])
            screen.blit(streak, (0, 0))

        # shaft: slim dark wood with a faint highlight
        pygame.draw.polygon(screen, (52, 40, 54), [P(-tail, -2.2), P(L - 30, -2.2), P(L - 30, 2.2), P(-tail, 2.2)])
        pygame.draw.line(screen, (105, 85, 108), P(-tail, -0.9), P(L - 30, -0.9), 1)
        # leather grip wrap
        pygame.draw.polygon(screen, (30, 24, 36), [P(-14, -2.8), P(22, -2.8), P(22, 2.8), P(-14, 2.8)])
        for s in range(-12, 22, 6):
            pygame.draw.line(screen, (70, 56, 84), P(s, -2.8), P(s + 3, 2.8), 1)
        # butt cap
        pygame.draw.polygon(screen, (120, 125, 150), [P(-tail - 5, -1.6), P(-tail, -2.6), P(-tail, 2.6), P(-tail - 5, 1.6)])

        # purple tassel under the blade
        wob = math.sin(self.sway * 3) * 1.5
        pygame.draw.line(screen, PURPLE_DARK, P(L - 33, 0), P(L - 48, -5 + wob), 2)
        pygame.draw.line(screen, PURPLE, P(L - 33, 0), P(L - 50, 4 + wob), 2)

        # socket / ferrule
        pygame.draw.polygon(screen, (110, 116, 140), [P(L - 36, -3.4), P(L - 27, -3.4), P(L - 27, 3.4), P(L - 36, 3.4)])
        pygame.draw.line(screen, (190, 195, 215), P(L - 36, -3.4), P(L - 27, -3.4), 1)

        # leaf-shaped steel blade, two-tone with a central ridge
        blade = [P(L - 28, -2.5), P(L - 19, -6.0), P(L - 8, -4.6), P(L, 0),
                 P(L - 8, 4.6), P(L - 19, 6.0), P(L - 28, 2.5)]
        pygame.draw.polygon(screen, (196, 202, 222), blade)
        pygame.draw.polygon(screen, (140, 147, 175), [P(L - 28, 0), P(L - 28, -2.5), P(L - 19, -6.0),
                                                      P(L - 8, -4.6), P(L, 0)])
        pygame.draw.line(screen, (240, 242, 252), P(L - 28, 0), P(L - 1, 0), 1)
        pygame.draw.polygon(screen, (85, 90, 118), blade, 1)

        if energized:
            tip = P(L, 0)
            for _ in range(3):
                s1, s2 = random.uniform(L - 70, L - 35), random.uniform(L - 30, L + 8)
                o1, o2 = random.uniform(-12, 12), random.uniform(-12, 12)
                draw_lightning(screen, P(s1, o1), P(s2, o2), PURPLE, 2, 5, 4)
            glow = pygame.Surface((70, 70), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*PURPLE, 80), (35, 35), int(10 + 14 * cast_k))
            pygame.draw.circle(glow, (*PURPLE_LIGHT, 130), (35, 35), int(4 + 5 * cast_k))
            screen.blit(glow, (int(tip[0]) - 35, int(tip[1]) - 35))

    def draw(self, screen):
        if self.hp <= 0:
            return
        super().draw(screen)
        self._draw_polearm(screen)   # held beside the ball

    def draw_overlay(self, screen):
        # Cinematic effect: only runs while the super is active
        if self.ray_timer > 0 and self.ray_geom:
            # 0.5s slide in (30 frames), 3s hold, 0.5s slide out (30 frames)
            if self.ray_timer > self.ray_total - 30:
                k = (self.ray_total - self.ray_timer) / 30.0
            elif self.ray_timer < 30:
                k = self.ray_timer / 30.0
            else:
                k = 1.0

            # 1. Darken the screen completely
            dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            dim.fill((0, 0, 0, int(160 * k)))
            screen.blit(dim, (0, 0))

            # 2. Cinematic Letterbox Bars (Black bars at top and bottom)
            bar_h = int(SCREEN_HEIGHT * 0.12 * k)
            pygame.draw.rect(screen, (0, 0, 0), (0, 0, SCREEN_WIDTH, bar_h))
            pygame.draw.rect(screen, (0, 0, 0), (0, SCREEN_HEIGHT - bar_h, SCREEN_WIDTH, bar_h))

            # 3. ADDITIVE GLOW: Makes BLUE and the beam shine brightly out of the darkness
            glow_layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            (ox, oy), (ex, ey) = self.ray_geom
            
            # Massive white glowing core for the beam
            pygame.draw.line(glow_layer, (255, 255, 255, int(255 * k)), (ox, oy), (ex, ey), 12)
            # Bright purple aura around the beam
            pygame.draw.line(glow_layer, (*PURPLE_LIGHT, int(180 * k)), (ox, oy), (ex, ey), 40)
            # Glow on BLUE himself and his polearm tip
            pygame.draw.circle(glow_layer, (255, 255, 255, int(255 * k)), (int(ox), int(oy)), 25)
            pygame.draw.circle(glow_layer, (*PURPLE, int(150 * k)), (int(self.body.position.x), int(self.body.position.y)), 45)

            # Draw with ADD blending so it looks like pure light
            screen.blit(glow_layer, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

            # 4. Draw the jagged lightning effect ON TOP of the glow
            for w, col, jit in ((10, PURPLE, 14), (6, PURPLE_LIGHT, 10), (3, (255, 255, 255), 6)):
                draw_lightning(screen, (ox, oy), (ex, ey), col, w, jit, 18)

            # 5. Short crackling lightning sparks along the edges of the black bars
            for b in self.random_bolts:
                for w, col, jit in ((4, PURPLE, 6), (2, PURPLE_LIGHT, 4), (1, (255, 255, 255), 2)):
                    draw_lightning(screen, (b["sx"], b["sy"]), (b["x"], b["y"]), col, w, jit, 8)