import sys
import os
import pygame

pygame.init()

# --- Web vs Local Display Setup ---
if sys.platform == "emscripten":
    # Web browsers need a fixed resolution
    SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
else:
    # Local PC gets your full screen
    info = pygame.display.Info()
    SCREEN_WIDTH, SCREEN_HEIGHT = info.current_w, info.current_h

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
if not os.path.exists(ASSETS_DIR) and os.path.exists(os.path.join(BASE_DIR, "assests")):
    ASSETS_DIR = os.path.join(BASE_DIR, "assests")

# Arena Geometry
ASPECT_W, ASPECT_H = 9, 16        
SIDE_MARGIN = 14                  
HUD_SPACE = 100                   

CENTER_X, CENTER_Y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
STRIP_WIDTH = min(SCREEN_WIDTH, SCREEN_HEIGHT * ASPECT_W // ASPECT_H)
SQUARE_SIZE = min(STRIP_WIDTH - 2 * SIDE_MARGIN, SCREEN_HEIGHT - 2 * HUD_SPACE)

ARENA_LEFT = CENTER_X - (SQUARE_SIZE // 2)
ARENA_RIGHT = CENTER_X + (SQUARE_SIZE // 2)
ARENA_TOP = CENTER_Y - (SQUARE_SIZE // 2)
ARENA_BOTTOM = CENTER_Y + (SQUARE_SIZE // 2)

# Fonts
FONT_TITLE = pygame.font.SysFont("Impact", 64)
FONT_SUBTITLE = pygame.font.SysFont("Impact", 36)
FONT_BTN = pygame.font.SysFont("Impact", 42)
FONT_NAME = pygame.font.SysFont("Impact", 24)
FONT_HP = pygame.font.SysFont("Arial", 13, bold=True)
FONT_SUPER = pygame.font.SysFont("Arial", 11, bold=True)
FONT_VS = pygame.font.SysFont("Impact", 32)
FONT_WINNER = pygame.font.SysFont("Impact", 54)

def find_asset(filename):
    path = os.path.join(ASSETS_DIR, filename)
    return path if os.path.exists(path) else None

def load_sprite(filename, width, height):
    base_name = filename.split('.')[0]
    for ext in [".png", ".jpg", ".jpeg"]:
        path = os.path.join(ASSETS_DIR, base_name + ext)
        if os.path.exists(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                return pygame.transform.smoothscale(img, (width, height))
            except Exception as e:
                print(f"Error loading sprite {filename}: {e}")
    return None

def load_avatar(filename, radius):
    path = os.path.join(ASSETS_DIR, filename)
    if os.path.exists(path):
        try:
            raw_img = pygame.image.load(path).convert_alpha()
            scaled_img = pygame.transform.smoothscale(raw_img, (radius * 2, radius * 2))
            circle_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surface, (255, 255, 255, 255), (radius, radius), radius)
            circle_surface.blit(scaled_img, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            return circle_surface
        except Exception as e:
            print(f"Error loading avatar {filename}: {e}")

    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(surf, (200, 50, 50), (radius, radius), radius)
    return surf

def load_background():
    for filename in ["bg.png", "bg.jpg", "bg.jpeg", "background.png", "background.jpg"]:
        bg_path = os.path.join(ASSETS_DIR, filename)
        if os.path.exists(bg_path):
            try:
                raw_bg = pygame.image.load(bg_path).convert()
                return pygame.transform.smoothscale(raw_bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
            except Exception as e:
                print(f"Error loading background image {filename}: {e}")
    
    fallback_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    fallback_surface.fill((20, 24, 40))
    return fallback_surface
