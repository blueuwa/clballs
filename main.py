import sys
import math
import random
import asyncio
import pygame
import pymunk
import sounds

from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, CENTER_X, CENTER_Y, SQUARE_SIZE,
    ARENA_LEFT, ARENA_RIGHT, ARENA_TOP, ARENA_BOTTOM,
    FONT_TITLE, FONT_SUBTITLE, FONT_BTN, FONT_NAME, FONT_HP, FONT_SUPER, FONT_VS, FONT_WINNER,
    load_background, load_avatar, find_asset
)
from starr_nova import StarrNova
from foxxy import Foxxy, make_avatar as make_foxxy_avatar
from blue import Blue
from saucer import Saucer
from ali import Ali, make_avatar as make_ali_avatar
from shade import Shade, DarkBlade, make_avatar as make_shade_avatar
from spicy import Spicy, make_avatar as make_spicy_avatar
from danger import Danger, make_avatar as make_danger_avatar
from dyirix import Dyirix, make_avatar as make_dyirix_avatar
from termi import Termi, make_avatar as make_termi_avatar
from gallos import Gallos, make_avatar as make_gallos_avatar
from hyper import Hyper, make_avatar as make_hyper_avatar
from theia import Theia, make_avatar as make_theia_avatar
from stat_editor import StatEditor
from menu_ui import SelectScreen, StatEditorScreen

# Detect if the game is running in a web browser
IS_WEB = sys.platform == "emscripten"

# ---------- UI fonts ----------
FONT_HUD_NAME = pygame.font.SysFont("Impact", 19)
FONT_HUD_NUM = pygame.font.SysFont("Arial", 12, bold=True)
FONT_POP = pygame.font.SysFont("Impact", 26)
FONT_POP_BIG = pygame.font.SysFont("Impact", 34)
FONT_POP_SMALL = pygame.font.SysFont("Impact", 19)
FONT_BADGE = pygame.font.SysFont("Impact", 24)

# Register Available Characters
ROSTER_CLASSES = [StarrNova, Foxxy, Blue, Saucer, Ali, Shade, Spicy, Danger, Dyirix, Termi, Gallos, Hyper, Theia]
ROSTER_INFO = [
    {"name": "STARR NOVA", "file": "1.png"},
    {"name": "FOXXY", "file": "2.png", "factory": make_foxxy_avatar},
    {"name": "BLUE", "file": "3.png"},
    {"name": "SAUCER", "file": "12.png"},
    {"name": "ALI", "file": "14.png", "factory": make_ali_avatar},
    {"name": "SHADE", "file": "6.png", "factory": make_shade_avatar},
    {"name": "SPICY", "file": "7.png", "factory": make_spicy_avatar},
    {"name": "DANGER", "file": "8.png", "factory": make_danger_avatar},
    {"name": "DYIRIX", "file": "9.png", "factory": make_dyirix_avatar},
    {"name": "TERMI", "file": "10.png", "factory": make_termi_avatar},
    {"name": "GALLOS", "file": "11.png", "factory": make_gallos_avatar},
    {"name": "HYPER", "file": "13.png", "factory": make_hyper_avatar},
    {"name": "THEIA", "file": "15.png", "factory": make_theia_avatar},
]

def get_avatar(info, size):
    if info.get("factory") and not find_asset(info["file"]):
        return info["factory"](size)
    return load_avatar(info["file"], size)

editors = [StatEditor(sys.modules[cls.__module__]) for cls in ROSTER_CLASSES]
select_screen = SelectScreen(ROSTER_INFO, ROSTER_CLASSES, get_avatar, editors)
edit_screen = StatEditorScreen(ROSTER_INFO, ROSTER_CLASSES, editors, get_avatar)

# CHANGED FULLSCREEN TO RESIZABLE FOR WEB COMPATIBILITY
pygame.display.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Bouncing Physics Arena")
clock = pygame.time.Clock()

background_surface = load_background()

projectiles = []
explosions = []
scratch_effects = []

def check_collision(b1, b2):
    if b1.cooldown > 0:
        b1.cooldown -= 1
    if b2.cooldown > 0:
        b2.cooldown -= 1

    pos1 = b1.body.position
    pos2 = b2.body.position
    dist = math.hypot(pos1.x - pos2.x, pos1.y - pos2.y)
    
    if dist <= (b1.radius + b2.radius) and b1.cooldown == 0 and b2.cooldown == 0:
        if getattr(b1, "invisible_timer", 0) > 0 or getattr(b2, "invisible_timer", 0) > 0:
            return
            
        b1.hp -= b2.contact_damage
        b2.hp -= b1.contact_damage
        b1.add_super(b1.super_per_contact)
        b2.add_super(b2.super_per_contact)
        b1.cooldown = 15
        b2.cooldown = 15

TEAM_COLORS = [(50, 180, 220), (220, 50, 80)]
GOLD = (255, 205, 40)

def lighten(color, amount):
    return tuple(min(255, int(v + (255 - v) * amount)) for v in color)

def draw_alpha_rounded(screen, rect, color, radius, border=None, border_w=0):
    surf = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(surf, color, surf.get_rect(), border_radius=radius)
    if border:
        pygame.draw.rect(surf, border, surf.get_rect(), border_w, border_radius=radius)
    screen.blit(surf, rect.topleft)

def draw_text_outline(screen, font, text, color, align, pos, outline_w=2, alpha=255):
    base = font.render(text, True, color)
    shadow = font.render(text, True, (0, 0, 0))
    if alpha < 255:
        base.set_alpha(alpha)
        shadow.set_alpha(alpha)
    rect = base.get_rect(**{align: pos})
    for dx in (-outline_w, 0, outline_w):
        for dy in (-outline_w, 0, outline_w):
            if dx or dy:
                screen.blit(shadow, rect.move(dx, dy))
    screen.blit(base, rect)

def hp_color(pct):
    if pct > 0.5: return (60, 220, 90)
    if pct > 0.25: return (255, 175, 40)
    return (235, 60, 60)

def draw_bar(screen, x, y, w, h, frac, color, trail_frac=None, from_right=False):
    bg = pygame.Rect(x, y, w, h)
    pygame.draw.rect(screen, (22, 22, 32), bg, border_radius=h // 2)
    def segment(f, col, highlight=True):
        fw = int(w * max(0.0, min(1.0, f)))
        if fw <= 0: return
        r = pygame.Rect(x + (w - fw if from_right else 0), y, fw, h)
        pygame.draw.rect(screen, col, r, border_radius=h // 2)
        if highlight and fw > 8:
            hl = pygame.Rect(r.x + 3, r.y + 2, r.w - 6, max(2, h // 3))
            pygame.draw.rect(screen, lighten(col, 0.45), hl, border_radius=max(1, h // 4))
    if trail_frac is not None and trail_frac > frac:
        segment(trail_frac, (245, 245, 245), highlight=False)
    segment(frac, color)
    pygame.draw.rect(screen, (255, 255, 255), bg, 2, border_radius=h // 2)

def draw_player_panel(screen, b, rect, team_color, mirrored):
    draw_alpha_rounded(screen, rect, (14, 16, 30, 215), 16, team_color, 3)
    ax = rect.right - 38 if mirrored else rect.left + 38
    ay = rect.centery
    pygame.draw.circle(screen, team_color, (ax, ay), 28)
    screen.blit(b.hud_avatar, b.hud_avatar.get_rect(center=(ax, ay)))
    pygame.draw.circle(screen, (255, 255, 255), (ax, ay), 26, 2)

    bar_w = rect.w - 88
    bar_x = rect.left + 12 if mirrored else rect.left + 76

    if mirrored:
        draw_text_outline(screen, FONT_HUD_NAME, b.name, (255, 255, 255), "topright", (bar_x + bar_w, rect.top + 3))
    else:
        draw_text_outline(screen, FONT_HUD_NAME, b.name, (255, 255, 255), "topleft", (bar_x, rect.top + 3))
    if b.super_flash > 0:
        pulse = int(170 + 85 * math.sin(pygame.time.get_ticks() * 0.02))
        pos = (bar_x, rect.top + 4) if mirrored else (bar_x + bar_w, rect.top + 4)
        draw_text_outline(screen, FONT_HUD_NUM, "SUPER!", GOLD, "topleft" if mirrored else "topright", pos, 1, pulse)

    marks = getattr(b, "hud_marks", None)
    if marks:
        name_w = FONT_HUD_NAME.size(b.name)[0]
        gap = 4
        avail = bar_w - name_w - 10
        d = max(14, min(24, avail // len(marks) - gap))
        cy = rect.top + 3 + FONT_HUD_NAME.get_height() // 2
        for i, mk in enumerate(marks):
            if mirrored:
                cx = bar_x + bar_w - name_w - 10 - d // 2 - i * (d + gap)
            else:
                cx = bar_x + name_w + 10 + d // 2 + i * (d + gap)
            mk["draw"](screen, cx, cy, d // 2, mk["frac"])

    pct = max(0.0, b.hp / b.max_hp)
    trail = max(0.0, b.hp_trail / b.max_hp)
    hp_y = rect.top + 27
    draw_bar(screen, bar_x, hp_y, bar_w, 17, pct, hp_color(pct), trail, mirrored)
    draw_text_outline(screen, FONT_HUD_NUM, f"{max(0, int(b.hp))} / {b.max_hp}", (255, 255, 255),
                      "center", (bar_x + bar_w // 2, hp_y + 8), 1)

    sup_y = rect.top + 50
    sup_frac = b.super_charge / b.max_super
    sup_color = GOLD
    if b.super_flash > 0 and (b.super_flash // 5) % 2 == 0:
        sup_color = (255, 255, 255)
        sup_frac = 1.0
    draw_bar(screen, bar_x, sup_y, bar_w, 10, sup_frac, sup_color, None, mirrored)

def draw_top_hud(screen, b1, b2, top_y):
    panel_h = 66
    vs_w = 64
    panel_w = (SQUARE_SIZE - vs_w) // 2
    hud_y = max(10, top_y - panel_h - 14)
    for b in (b1, b2):
        if b.hp_trail > b.hp:
            b.hp_trail = max(b.hp, b.hp_trail - max(1.0, (b.hp_trail - b.hp) * 0.06))
        else:
            b.hp_trail = b.hp
    left = pygame.Rect(ARENA_LEFT, hud_y, panel_w, panel_h)
    right = pygame.Rect(ARENA_RIGHT - panel_w, hud_y, panel_w, panel_h)
    draw_player_panel(screen, b1, left, TEAM_COLORS[0], False)
    draw_player_panel(screen, b2, right, TEAM_COLORS[1], True)

    c = (CENTER_X, hud_y + panel_h // 2)
    pygame.draw.circle(screen, (14, 16, 30), c, 25)
    pygame.draw.circle(screen, GOLD, c, 25, 3)
    draw_text_outline(screen, FONT_BADGE, "VS", GOLD, "center", (c[0], c[1] + 1), 2)

def draw_explosion(screen, ex):
    total = ex.get("max", 15)
    p = 1.0 - ex["timer"] / total
    ease = 1.0 - (1.0 - p) ** 3
    fade = (1.0 - p)
    R = ex["radius"]
    color = ex.get("color", (255, 140, 40))
    size = int(R * 3.2)
    c = size // 2
    def scale(col, k): return tuple(max(0, min(255, int(v * k))) for v in col)
    surf = pygame.Surface((size, size))
    body_r = R * (0.55 + 0.5 * ease)
    bright = fade ** 0.6
    for i in range(14):
        t = i / 13
        col = tuple(int(color[k] * (1 - t ** 1.6) + 255 * (t ** 1.6)) for k in range(3))
        pygame.draw.circle(surf, scale(col, bright * (0.45 + 0.55 * t)), (c, c), max(1, int(body_r * (1 - i / 14))))
    pygame.draw.circle(surf, scale((255, 255, 255), 0.9 * fade + 0.1), (c, c), int(R * (0.3 + 0.75 * ease)), max(1, int(5 * fade) + 1))
    spark_color = scale(lighten(color, 0.5), 1.0 * fade + 0.15)
    for ang, spd, sz in ex.get("sparks", ()):
        dist = R * (0.3 + 0.85 * spd * ease)
        px, py = c + math.cos(ang) * dist, c + math.sin(ang) * dist
        pygame.draw.circle(surf, spark_color, (int(px), int(py)), max(1, int(sz * (0.4 + 0.6 * fade))))
    screen.blit(surf, (int(ex["x"]) - c, int(ex["y"]) - c), special_flags=pygame.BLEND_RGB_ADD)

def spawn_floater(b, text, color, big=False, small=False):
    life = 60 if big else (28 if small else 45)
    font = FONT_POP_BIG if big else (FONT_POP_SMALL if small else FONT_POP)
    x = b.body.position.x + random.uniform(-14, 14)
    x = max(ARENA_LEFT + 25, min(ARENA_RIGHT - 25, x))
    y = max(ARENA_TOP + 22, b.body.position.y - b.radius - 8)
    floaters.append({"x": x, "y": y, "text": text, "color": color, "timer": life, "max": life, "font": font})
    if len(floaters) > 40: floaters.pop(0)

def track_changes(b):
    now, before = max(b.hp, 0), max(b.last_hp, 0)
    if now < before:
        dmg = before - now
        if dmg < 20: spawn_floater(b, f"-{int(dmg)}", (210, 235, 255), small=True)
        else: spawn_floater(b, f"-{int(dmg)}", (255, 255, 255) if dmg < 80 else (255, 90, 90), big=dmg >= 80)
    elif now > before:
        spawn_floater(b, f"+{int(now - before)}", (90, 255, 140), big=True)
    b.last_hp = b.hp
    b.tick_effects()
    for text, color in b.popups: spawn_floater(b, text, color, big=True)
    b.popups.clear()

def draw_floaters(screen):
    for f in floaters[:]:
        f["y"] -= 1.1
        f["timer"] -= 1
        alpha = int(255 * min(1.0, f["timer"] / (f["max"] * 0.5)))
        draw_text_outline(screen, f["font"], f["text"], f["color"], "center", (int(f["x"]), int(f["y"])), 2, alpha)
        if f["timer"] <= 0: floaters.remove(f)

def build_arena_surface(w, h):
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(surf, (6, 8, 20, 150), surf.get_rect(), border_radius=10)
    step = 48
    for gx in range(step, w, step): pygame.draw.line(surf, (255, 255, 255, 14), (gx, 0), (gx, h), 1)
    for gy in range(step, h, step): pygame.draw.line(surf, (255, 255, 255, 14), (0, gy), (w, gy), 1)
    pygame.draw.line(surf, (255, 255, 255, 22), (w // 2, 0), (w // 2, h), 2)
    pygame.draw.circle(surf, (255, 255, 255, 22), (w // 2, h // 2), 70, 2)
    return surf

def draw_button(screen, text, rect, base_color, hover_color, is_hovered):
    color = hover_color if is_hovered else base_color
    pygame.draw.rect(screen, (0, 0, 0), rect.move(0, 5), border_radius=12)
    pygame.draw.rect(screen, color, rect, border_radius=12)
    pygame.draw.rect(screen, (255, 255, 255), rect, 3, border_radius=12)
    txt_surf = FONT_BTN.render(text, True, (255, 255, 255))
    screen.blit(txt_surf, txt_surf.get_rect(center=rect.center))

state = "MAIN_MENU"
p1_idx = 0
p2_idx = 1

space = None
brawler1 = None
brawler2 = None
arena_rect = None
arena_surface = None
winner = None
floaters = []

def start_battle():
    global space, brawler1, brawler2, arena_rect, arena_surface, winner, state, projectiles, explosions, scratch_effects
    projectiles.clear()
    explosions.clear()
    scratch_effects.clear()
    floaters.clear()
    space = pymunk.Space()
    space.gravity = (0, 0)
    walls = [
        [(ARENA_LEFT, ARENA_TOP), (ARENA_RIGHT, ARENA_TOP)],
        [(ARENA_LEFT, ARENA_BOTTOM), (ARENA_RIGHT, ARENA_BOTTOM)],
        [(ARENA_LEFT, ARENA_TOP), (ARENA_LEFT, ARENA_BOTTOM)],
        [(ARENA_RIGHT, ARENA_TOP), (ARENA_RIGHT, ARENA_BOTTOM)]
    ]
    for start_p, end_p in walls:
        segment = pymunk.Segment(space.static_body, start_p, end_p, 5)
        segment.elasticity = 1.0
        segment.friction = 0.0
        space.add(segment)
    arena_rect = pygame.Rect(ARENA_LEFT, ARENA_TOP, ARENA_RIGHT - ARENA_LEFT, ARENA_BOTTOM - ARENA_TOP)
    arena_surface = build_arena_surface(arena_rect.width, arena_rect.height)
    b1_class = ROSTER_CLASSES[select_screen.p1]
    b2_class = ROSTER_CLASSES[select_screen.p2]
    brawler1 = b1_class(space, pos=(CENTER_X - 50, CENTER_Y - 50), velocity=(350, 250))
    brawler2 = b2_class(space, pos=(CENTER_X + 50, CENTER_Y + 50), velocity=(-300, -400))
    for b in (brawler1, brawler2):
        b.hp_trail = b.hp
        b.last_hp = b.hp
        b.hud_avatar = pygame.transform.smoothscale(b.surface, (48, 48))
    winner = None
    state = "GAME"

# ---------------------------------------------------------
# ASYNC WEB LOOP STARTS HERE
# ---------------------------------------------------------
async def main():
    global running, state, winner, p1_idx, p2_idx
    
    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        mouse_clicked = False
        for event in pygame.event.get():
            if state == "EDIT":
                if event.type == pygame.QUIT: running = False
                elif edit_screen.handle_event(event) == "close": state = "SELECT_MENU"
                continue
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.MOUSEWHEEL and state == "SELECT_MENU": select_screen.handle_scroll(event.y)
            elif event.type == pygame.KEYDOWN and state == "SELECT_MENU" and event.key in (pygame.K_UP, pygame.K_DOWN):
                select_screen.handle_scroll(1 if event.key == pygame.K_UP else -1)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if state == "GAME": state = "SELECT_MENU"
                    else: running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: mouse_clicked = True

        screen.blit(background_surface, (0, 0))

        if state == "MAIN_MENU":
            title_surf = FONT_TITLE.render("BOUNCING BRAWL", True, (255, 215, 0))
            title_shadow = FONT_TITLE.render("BOUNCING BRAWL", True, (0, 0, 0))
            title_rect = title_surf.get_rect(center=(CENTER_X, CENTER_Y - 120))
            screen.blit(title_shadow, (title_rect.x + 4, title_rect.y + 4))
            screen.blit(title_surf, title_rect)
            play_rect = pygame.Rect(CENTER_X - 120, CENTER_Y + 20, 240, 65)
            is_hover = play_rect.collidepoint(mouse_pos)
            draw_button(screen, "PLAY", play_rect, (50, 180, 50), (70, 210, 70), is_hover)
            if is_hover and mouse_clicked: state = "SELECT_MENU"

        elif state == "SELECT_MENU":
            if mouse_clicked:
                action = select_screen.handle_click(mouse_pos)
                if action and action[0] == "brawl": 
                    start_battle()
                elif action and action[0] == "edit":
                    if IS_WEB:
                        # Play a UI error sound or just do nothing on web
                        sounds.play("bump") 
                    else:
                        edit_screen.open(action[1])
                        state = "EDIT"
            if state == "SELECT_MENU": 
                select_screen.draw(screen, mouse_pos)

        elif state == "EDIT":
            select_screen.draw(screen, (-999, -999))
            edit_screen.draw(screen, mouse_pos)

        elif state == "GAME":
            if not winner:
                space.step(1 / 60.0)
                brawler1.maintain_speed()
                brawler2.maintain_speed()
                check_collision(brawler1, brawler2)

                if brawler1.can_act(): brawler1.update_abilities(brawler2, projectiles, scratch_effects)
                if brawler2.can_act(): brawler2.update_abilities(brawler1, projectiles, scratch_effects)

                blizzard_active = any(getattr(b, "blizzard_timer", 0) > 0 for b in (brawler1, brawler2))
                
                for p in projectiles:
                    if isinstance(p, dict): continue
                    p_active = getattr(p, "active", True)
                    if not p_active: continue

                    # THEIA PARRY LOGIC
                    for parry_user in (brawler1, brawler2):
                        if getattr(parry_user, "parry_timer", 0) > 0 and getattr(parry_user, "name", "") == "THEIA":
                            px = getattr(p, "x", getattr(p, "ox", getattr(p, "sx", -9999)))
                            py = getattr(p, "y", getattr(p, "oy", getattr(p, "sy", -9999)))
                            if px != -9999:
                                if math.hypot(parry_user.body.position.x - px, parry_user.body.position.y - py) <= parry_user.radius + getattr(p, "radius", 15):
                                    p.active = False
                                    parry_user.hp = min(parry_user.max_hp, parry_user.hp + 10)
                                    parry_user.flash((255, 220, 120), 10)
                                    parry_user.popups.append(("+10", (90, 255, 140)))
                                    sounds.play("heal")
                                    break

                    p_active = getattr(p, "active", True)
                    if not p_active: continue

                    if blizzard_active and not isinstance(p, DarkBlade):
                        if hasattr(p, "vx") and hasattr(p, "vy"):
                            p.x -= p.vx * 0.6
                            p.y -= p.vy * 0.6
                            p.vx *= 0.4
                            p.vy *= 0.4
                        elif hasattr(p, "speed"):
                            p.speed *= 0.4
                    
                    p.update(explosions)

                projectiles = [p for p in projectiles if getattr(p, "active", True) if not isinstance(p, dict)]

                track_changes(brawler1)
                track_changes(brawler2)

                if brawler1.hp <= 0 and brawler2.hp <= 0: winner = "DRAW!"
                elif brawler1.hp <= 0: winner = f"{brawler2.name} WINNER!"
                elif brawler2.hp <= 0: winner = f"{brawler1.name} WINNER!"

            draw_top_hud(screen, brawler1, brawler2, ARENA_TOP)
            screen.blit(arena_surface, arena_rect.topleft)
            pygame.draw.rect(screen, GOLD, arena_rect.inflate(14, 14), 3, border_radius=14)
            pygame.draw.rect(screen, (255, 255, 255), arena_rect, 4, border_radius=8)

            for p in projectiles:
                if not isinstance(p, dict): p.draw(screen)

            for ex in explosions[:]:
                draw_explosion(screen, ex)
                ex["timer"] -= 1
                if ex["timer"] <= 0: explosions.remove(ex)

            for sc in scratch_effects[:]:
                x, y = int(sc["x"]), int(sc["y"])
                if "draw" in sc: sc["draw"](screen)
                elif sc.get("sprite"): screen.blit(sc["sprite"], sc["sprite"].get_rect(center=(x, y)))
                sc["timer"] -= 1
                if sc["timer"] <= 0: scratch_effects.remove(sc)

            brawler1.draw(screen)
            brawler2.draw(screen)
            for b in (brawler1, brawler2):
                for patch in getattr(b, "patches", ()): patch.draw(screen)
                if hasattr(b, "draw_overlay"): b.draw_overlay(screen)

            draw_floaters(screen)

            if winner:
                dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                dim.fill((0, 0, 0, 130))
                screen.blit(dim, (0, 0))
                text_surf = FONT_WINNER.render(winner, True, (255, 215, 0))
                max_w = SQUARE_SIZE - 90
                if text_surf.get_width() > max_w:
                    scale = max_w / text_surf.get_width()
                    text_surf = pygame.transform.smoothscale(text_surf, (max_w, int(text_surf.get_height() * scale)))
                text_rect = text_surf.get_rect(center=(CENTER_X, CENTER_Y - 30))
                text_shadow = text_surf.copy()
                text_shadow.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
                banner = text_rect.inflate(60, 36)
                draw_alpha_rounded(screen, banner, (14, 16, 30, 235), 18, GOLD, 4)
                screen.blit(text_shadow, (text_rect.x + 3, text_rect.y + 3))
                screen.blit(text_surf, text_rect)
                menu_btn_rect = pygame.Rect(CENTER_X - 100, CENTER_Y + 40, 200, 50)
                m_hover = menu_btn_rect.collidepoint(mouse_pos)
                draw_button(screen, "RETRY", menu_btn_rect, (50, 180, 50), (70, 210, 70), m_hover)
                if m_hover and mouse_clicked: state = "SELECT_MENU"

        pygame.display.flip()
        clock.tick(60)
        
        # THIS LINE IS CRITICAL FOR THE BROWSER TO NOT FREEZE
        await asyncio.sleep(0)

# Start the async loop
pygame.display.flip()
if __name__ == "__main__":
    asyncio.run(main())
