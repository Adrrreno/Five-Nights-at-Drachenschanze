import pygame
import sys
import random
from dataclasses import dataclass
from typing import List, Tuple
import os
from moviepy.editor import VideoFileClip
from PIL import Image
from animatronic import Animatronic, ANIMATRONIC_PATHS, GameContext
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# --- Compatibility patch for Pillow >= 10 ---
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

frame_index = 0
frame_timer = 0
frame_delay = 0.08

rainer_timer = 0
rainer_alpha = 0

local_static = []   # will be overridden after loading
static_frames = []  # if used

in_menu = True
in_controls_menu = False


# Night clock setup
night_start_time = time.time()
night_length = 450  # 7 minutes 30 seconds
current_hour = "12 AM"


# --- Camera Map Clickable Buttons ---
CAM_MAP_RECTS = []   # list of (pygame.Rect, cam_name)
MAP_UI_RECT = None   # button in camera UI that opens map


hour_offsets = [
    random.uniform(0, 5),  # 12→1 AM delay
    random.uniform(0, 5),  # 1→2 AM
    random.uniform(0, 5),  # ...
    random.uniform(0, 5),
    random.uniform(0, 5),
    random.uniform(0, 5)
]

click_once = False

pygame.init()
pygame.mixer.init()
WIDTH, HEIGHT = 1920, 1080
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Fünf Nächte beim Drachen")

last_mouse_pressed = False

CLOCK = pygame.time.Clock()
FONT = pygame.font.SysFont("Arial", 20)

# ----- Configuration -----
ROOM_SIZE = (320, 240)  # size of each camera viewport for display thumbnails
PLAYER_ROOM = "Office"  # the room that is the player's location


# Load placeholder assets (replace these with your sprites)
def load_placeholder_surface(text, size=(320, 240)):
    surf = pygame.Surface(size)
    surf.fill((30, 30, 30))
    txt = FONT.render(text, True, (230,230,230))
    surf.blit(txt, (10,10))
    return surf

jumpscare_active = False
CAMERA_IMG = load_placeholder_surface("Camera View")
JUMPSCARE_IMG = pygame.Surface((WIDTH, HEIGHT))
JUMPSCARE_IMG.fill((255,0,0))
JUMP_TEXT = FONT.render("JUMPSCARE!", True, (255,255,255))
JUMPSCARE_IMG.blit(JUMP_TEXT, (WIDTH//2 - 60, HEIGHT//2 - 10))
# --- Static animation state ---
STATIC_FRAMES = []
STATIC_FRAME_INDEX = 0
STATIC_FRAME_TIMER = 0.0
office_locked = False  # prevents others from entering after jumpscare starts
REC_FONT = pygame.font.Font("../assets/fonts/pixel_font.ttf", 28)
rec_flash_timer = 0.0
rec_visible = True

# --- Camera Map Button Positions (editable) ---
# These are placeholders — you will adjust them after seeing the map in-game.
CAM_MAP_BUTTON_POS = {
    "Stage":      {"pos": (800, 270), "layer": 0},  
    "Kitchen":    {"pos": (120, 200), "layer": 1},  
    "Hall":       {"pos": (560, 360), "layer": 0},  
    "Backroom":   {"pos": (660, 120), "layer": 0},  
    "HallCorner": {"pos": (490, 650), "layer": 1},  
}




# --- Flicker effect control ---
static_alpha = 0         # current opacity
static_target_alpha = 0  # desired opacity (e.g. 100 when active)
static_fade_speed = 300  # how fast the fade occurs (alpha per second)

def create_scanline_surface(width, height):
    surf = pygame.Surface((width, height)).convert()
    surf.fill((0, 0, 0))
    for y in range(0, height, 4):
        pygame.draw.line(surf, (10, 10, 10), (0, y), (width, y), 2)
    surf.set_alpha(40)
    return surf

SCANLINE_OVERLAY = create_scanline_surface(WIDTH, HEIGHT)


ANIM_IMG = pygame.Surface((48, 48))
ANIM_IMG.fill((200, 50, 50))

# --- Office sprites ---
OFFICE_BASE = pygame.image.load("../assets/rooms/Office/office_base.png").convert()
OFFICE_BASE = pygame.transform.smoothscale(OFFICE_BASE, (1920, 1080))

DOOR_CLOSED_IMG = pygame.image.load("../assets/rooms/Office/door_left_closed.png").convert_alpha()
DOOR_CLOSED_IMG = pygame.transform.smoothscale(DOOR_CLOSED_IMG, (1920, 1080))


# --- Load pre-rendered static animation ---
def load_gif_frames(path):
    """Load all frames from a GIF and return a list of Pygame surfaces with alpha."""
    frames = []
    try:
        gif = Image.open(path)
    except Exception as e:
        print(f"[ERROR] Cannot load GIF {path}: {e}")
        return frames

    for frame_index in range(getattr(gif, "n_frames", 1)):
        gif.seek(frame_index)
        # Convert to RGBA so we can add transparency
        frame = gif.convert("RGBA")
        mode = frame.mode
        size = frame.size
        data = frame.tobytes()
        surface = pygame.image.fromstring(data, size, mode).convert_alpha()
        frames.append(surface)
    print(f"[INFO] Loaded {len(frames)} static frames with alpha.")
    return frames


# Optional: load sounds (place in assets/sounds)
def safe_load_sound(path):
    if not os.path.exists(path):
        print(f"[WARNING] Sound file not found: {path}")
        return None
    try:
        sound = pygame.mixer.Sound(path)
        print(f"[OK] Loaded sound: {path}")
        return sound
    except Exception as e:
        print(f"[ERROR] Could not load sound: {path} ({e})")
        return None

# Load sounds
JUMPSCARE_SOUND = safe_load_sound("../assets/sounds/jumpscare.wav")
BACKGROUND_LOOP = safe_load_sound("../assets/sounds/background_loop.wav")
CAMERA_SWITCH_SOUND = safe_load_sound("../assets/sounds/cam_select.wav")
DOOR_CLOSE_SOUND = safe_load_sound("../assets/sounds/door_close.wav")
DOOR_OPEN_SOUND = safe_load_sound("../assets/sounds/door_open.wav")
MAP_OPEN_SOUND = safe_load_sound("../assets/sounds/map_open.wav")
MAP_CLOSE_SOUND = safe_load_sound("../assets/sounds/map_open.wav")
CAM_OPEN_SOUND = safe_load_sound("../assets/sounds/cam_open.wav")
CAM_CLOSE_SOUND = safe_load_sound("../assets/sounds/cam_close.wav")



CAM_OPEN_CHANNEL = pygame.mixer.Channel(7)   # pick any free channel

# Jumpscare video
RAINER_JUMPSCARE_VIDEO_PATH = "../assets/jumpscares/rainer_jumpscare.mp4"


# --- Ambient sounds ---
AMBIENT_SOUNDS = []
for i in range(1, 10):  # assuming ambient1.wav ... ambient9.wav
    path = f"../assets/sounds/schnaufer_winkler{i}.wav"
    sound = safe_load_sound(path)
    if sound:
        AMBIENT_SOUNDS.append(sound)

if AMBIENT_SOUNDS:
    print(f"[INFO] Loaded {len(AMBIENT_SOUNDS)} ambient sound(s).")


STATIC_FRAMES = load_gif_frames("../assets/effects/static.gif")
STATIC_FRAME_INDEX = 0
STATIC_FRAME_TIMER = 0.0

# ----- Map / Rooms / Waypoints -----
@dataclass
class Room:
    name: str
    view_surface: pygame.Surface
    waypoints: List[Tuple[int, int]]  # coordinates local to room


def load_room_image(path, size=(320, 240)):
    """Safely load a PNG or return a placeholder if missing."""
    if not os.path.exists(path):
        print(f"[WARN] Missing room image: {path}")
        return load_placeholder_surface(os.path.basename(path), size)
    try:
        img = pygame.image.load(path).convert()
        return pygame.transform.smoothscale(img, size)
    except Exception as e:
        print(f"[ERROR] Could not load {path}: {e}")
        return load_placeholder_surface("Error", size)

MAP_TOP = pygame.image.load("../assets/ui/map_top.png").convert_alpha()
MAP_BOTTOM = pygame.image.load("../assets/ui/map_bottom.png").convert_alpha()

# scale to tablet size (same as camera screen)
MAP_TOP = pygame.transform.scale(MAP_TOP, (1280, 720))
MAP_BOTTOM = pygame.transform.scale(MAP_BOTTOM, (1280, 720))


# ----- Room Definitions -----
ROOMS = {
    "Stage": Room(
        "Stage",
        load_room_image("../assets/rooms/stage.png", (320, 240)),
        waypoints=[(160, 30), (160, 210)]
    ),
    "Hall": Room(
        "Hall",
        load_room_image("../assets/rooms/hall.png", (320, 240)),
        waypoints=[(50, 50), (250, 180)]
    ),
    "Kitchen": Room(
        "Kitchen",
        load_room_image("../assets/rooms/kitchen.png", (320, 240)),
        waypoints=[(30, 30), (280, 200)]
    ),
    "HallCorner": Room(
        "HallCorner",
        load_room_image("../assets/rooms/hallcorner.png", (320, 240)),
        waypoints=[(60, 60), (260, 180)]
    ),
    "Backroom": Room(
        "Backroom",
        load_room_image("../assets/rooms/backroom.png", (320, 240)),
        waypoints=[(100, 100), (220, 160)]
    ),
    "Office": Room(
        "Office",
        load_room_image("../assets/rooms/office.png", (320, 240)),
        waypoints=[(0, 0)]
    ),
}
ROOM_CONNECTIONS = {
    "Stage": ["Hall"],
    "Hall": ["Stage", "Backroom", "HallCorner"],
    "Kitchen": ["Backroom"],
    "HallCorner": ["Hall", "Office"],
    "Backroom": ["Hall", "HallCorner"],
    "Office": ["Hall", "HallCorner"]
}



# ----- Door & Power System -----
DOORS = {
    ("Hall", "Office"): {"closed": False}
}

# ----- Camera Order -----
CAMERA_ORDER = ["Stage", "Kitchen", "Hall", "Backroom", "HallCorner", "Office"]

# FNaF-style short labels for each camera
CAM_LABELS = {
    "Stage": "1A",
    "Hall": "2",
    "Kitchen": "1B",
    "Backroom": "3",
    "HallCorner": "4",
    "Office": "—"  # optional (usually not a numbered cam)
}



# Optional: if you don’t want to access the Office via camera view:
VIEWABLE_CAMERAS = [r for r in CAMERA_ORDER if r != "Office"]


# MAP HOVER BAR STATE
map_bar_x = WIDTH
map_bar_target_x = WIDTH - 80
map_bar_width = 80

map_open_hover = False
map_toggle_cooldown = 0
map_hover_timer = 0


MAX_POWER = 100.0
power = MAX_POWER
POWER_DRAIN_IDLE = 0.0025      # slower idle drain
POWER_DRAIN_CAMERA = 0.008     # slower drain when cameras are active
POWER_DRAIN_DOOR = 0.02        # slightly reduced door cost

def draw_map_buttons(surface, x, y):
    global map_layer

    btn_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 32)

    btn_top = pygame.Rect(x, y, 180, 50)
    btn_bottom = pygame.Rect(x + 200, y, 220, 50)

    mx, my = pygame.mouse.get_pos()
    click = pygame.mouse.get_pressed()[0]

    # TOP button
    pygame.draw.rect(surface, (120, 50, 50) if map_layer == 0 else (60, 60, 60), btn_top, border_radius=8)
    label = btn_font.render("TOP", True, (255,255,255))
    surface.blit(label, (btn_top.centerx - label.get_width()//2, btn_top.centery - label.get_height()//2))

    # BOTTOM button
    pygame.draw.rect(surface, (120, 50, 50) if map_layer == 1 else (60, 60, 60), btn_bottom, border_radius=8)
    label = btn_font.render("BOTTOM", True, (255,255,255))
    surface.blit(label, (btn_bottom.centerx - label.get_width()//2, btn_bottom.centery - label.get_height()//2))

    # Click detection
    if click:
        if btn_top.collidepoint(mx, my):
            map_layer = 0
            print("Switched to TOP layer")
        elif btn_bottom.collidepoint(mx, my):
            map_layer = 1
            print("Switched to BOTTOM layer")

def draw_map_camera_buttons(surface, map_x, map_y):
    global CAM_MAP_RECTS, camera_index, map_layer

    CAM_MAP_RECTS = []  # Reset each frame

    btn_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 28)

    for cam_name, data in CAM_MAP_BUTTON_POS.items():
        pos = data["pos"]
        layer = data["layer"]

        # Skip if this camera is NOT on the currently selected layer
        if layer != map_layer:
            continue

        px, py = pos

        # Button rectangle
        rect = pygame.Rect(map_x + px - 25, map_y + py - 25, 50, 50)

        mx, my = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mx, my)
        active_cam = (CAMERA_ORDER[camera_index] == cam_name)

        # Color logic
        if active_cam:
            color = (200, 40, 40)     # active
        elif hovered:
            color = (150, 150, 150)   # hover
        else:
            color = (90, 90, 90)

        pygame.draw.rect(surface, color, rect, border_radius=12)
        pygame.draw.rect(surface, (20, 20, 20), rect, 3, border_radius=12)

        # Label like 1A, 1B, 2, etc.
        label = btn_font.render(CAM_LABELS[cam_name], True, (240, 240, 240))
        surface.blit(label, (
            rect.centerx - label.get_width() // 2,
            rect.centery - label.get_height() // 2
        ))

        CAM_MAP_RECTS.append((rect, cam_name))

def draw_map_overlay(surface):
    """
    Draw the map overlay at centered position and return the three main button rects:
    (top_rect, bottom_rect, close_rect). Also populates global CAM_MAP_RECTS.
    Uses: MAP_TOP, MAP_BOTTOM, CAM_MAP_BUTTON_POS, CAMERA_ORDER, CAM_LABELS
    Assumes map_layer is 0 (bottom) or 1 (top).
    """
    global CAM_MAP_RECTS

    CAM_MAP_RECTS = []

    # --- map position (matches your other code) ---
    map_x = WIDTH // 2 - 640
    map_y = HEIGHT // 2 - 360

    # --- draw correct map image for current layer ---
    if map_layer == 1:
        surface.blit(MAP_TOP, (map_x, map_y))
    else:
        surface.blit(MAP_BOTTOM, (map_x, map_y))

    # --- font for map UI ---
    MAP_FONT = pygame.font.Font("../assets/fonts/pixel_font.ttf", 32)

    # --------------------------------------------------
    # 1) TOP / BOTTOM layer buttons
    # --------------------------------------------------
    top_rect = pygame.Rect(map_x + 50, map_y + 30, 180, 50)
    bottom_rect = pygame.Rect(map_x + 260, map_y + 30, 180, 50)

    # button fill: highlight active layer
    pygame.draw.rect(surface, (120, 50, 50) if map_layer == 1 else (60, 60, 60),
                     top_rect, border_radius=8)
    pygame.draw.rect(surface, (120, 50, 50) if map_layer == 0 else (60, 60, 60),
                     bottom_rect, border_radius=8)

    txt = MAP_FONT.render("TOP", True, (255, 255, 255))
    surface.blit(txt, (top_rect.centerx - txt.get_width() // 2,
                       top_rect.centery - txt.get_height() // 2))

    txt = MAP_FONT.render("BOTTOM", True, (255, 255, 255))
    surface.blit(txt, (bottom_rect.centerx - txt.get_width() // 2,
                       bottom_rect.centery - txt.get_height() // 2))

    # --------------------------------------------------
    # 2) Camera buttons on the map (use CAM_MAP_BUTTON_POS)
    # --------------------------------------------------
    mx, my = pygame.mouse.get_pos()
    btn_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 28)

    for cam_name, data in CAM_MAP_BUTTON_POS.items():
        px, py = data["pos"]
        layer = data["layer"]

        # only draw cameras for the currently visible layer
        if layer != map_layer:
            continue

        # rect positioned relative to map_x/map_y
        rect = pygame.Rect(map_x + px - 25, map_y + py - 25, 50, 50)

        hovered = rect.collidepoint(mx, my)
        # active if the current global camera points to this cam name
        active_cam = (CAMERA_ORDER[camera_index] == cam_name)

        # color logic: active = red, hovered = light grey, default = dark grey
        if active_cam:
            color = (200, 40, 40)
        elif hovered:
            color = (150, 150, 150)
        else:
            color = (90, 90, 90)

        pygame.draw.rect(surface, color, rect, border_radius=12)
        pygame.draw.rect(surface, (20, 20, 20), rect, 3, border_radius=12)

        # label (1A, 1B, 2, etc.) — fallback to short name if missing
        label_text = CAM_LABELS.get(cam_name, cam_name[:2])
        lbl = btn_font.render(label_text, True, (240, 240, 240))
        surface.blit(lbl, (rect.centerx - lbl.get_width() // 2,
                           rect.centery - lbl.get_height() // 2))

        CAM_MAP_RECTS.append((rect, cam_name))

    # --------------------------------------------------
    # 3) MAP close button (reuse camera UI MAP button area)
    # --------------------------------------------------
    close_rect = pygame.Rect(WIDTH - 180, 120, 160, 60)
    pygame.draw.rect(surface, (40, 90, 130), close_rect, border_radius=10)
    pygame.draw.rect(surface, (20, 20, 20), close_rect, 3, border_radius=10)

    close_label = MAP_FONT.render("MAP", True, (255, 255, 255))
    surface.blit(close_label, (close_rect.centerx - close_label.get_width() // 2,
                               close_rect.centery - close_label.get_height() // 2))

    # return rects so your main loop can capture them
    return top_rect, bottom_rect, close_rect

def is_door_closed_between(room_a, room_b):
    key = (room_a, room_b) if (room_a, room_b) in DOORS else (room_b, room_a)
    return DOORS.get(key, {}).get("closed", False)

# --- Build Game Context ---
game = GameContext(
    rooms=ROOMS,
    room_connections=ROOM_CONNECTIONS,
    camera_order=CAMERA_ORDER,
    anim_img=ANIM_IMG,
    player_room="Office",
    door_checker=is_door_closed_between,
    get_power=lambda: power
)

# --- Create Animatronics using the new class ---
rainer = Animatronic(
    "Rainer",
    "Stage",
    game,
    route=ANIMATRONIC_PATHS["Rainer"]
)

fliege = Animatronic(
    "Fliege",
    "Kitchen",
    game,
    route=ANIMATRONIC_PATHS["Fliege"]
)

animatronics = [rainer, fliege]



# ----- Game state -----
camera_index = 0   # which camera the player is viewing
game_over = False
jumpscare_time = 0.0
NIGHT_LENGTH = 450  # 7 minutes 30 seconds like FNaF
night_timer = NIGHT_LENGTH
start_ticks = pygame.time.get_ticks()

# ----- Helper UI -----
def draw_ui():
    """Draw FNaF-style status UI (night timer, door status, power)."""
    try:
        ui_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 26)
    except:
        ui_font = FONT  # fallback if pixel font missing

    # --- Background translucent panel ---
    panel = pygame.Surface((280, 100), pygame.SRCALPHA)
    panel.fill((10, 10, 10, 120))
    SCREEN.blit(panel, (WIDTH - 300, 15))

    info_x = WIDTH - 280
    info_y = 25

    # --- Night timer ---
    timer_text = ui_font.render(f"TIME LEFT: {int(night_timer)}s", True, (220, 220, 220))
    SCREEN.blit(timer_text, (info_x, info_y))
    info_y += 28

    # --- Door status ---
    door_text = "CLOSED" if is_door_closed_between("Hall", "Office") else "OPEN"
    door_color = (255, 60, 60) if door_text == "CLOSED" else (100, 255, 100)
    door_label = ui_font.render(f"DOOR: {door_text}", True, door_color)
    SCREEN.blit(door_label, (info_x, info_y))
    info_y += 28

    # --- Power ---
    if power > 20:
        power_color = (220, 220, 220)
    else:
        power_color = (255, 50, 50)
    power_label = ui_font.render(f"POWER: {power:.0f}%", True, power_color)
    SCREEN.blit(power_label, (info_x, info_y))

    # --- Subtle glow/flicker effect (optional aesthetic) ---
    if random.random() < 0.02:
        flicker_overlay = pygame.Surface((280, 100), pygame.SRCALPHA)
        flicker_overlay.fill((255, 255, 255, random.randint(10, 20)))
        SCREEN.blit(flicker_overlay, (WIDTH - 300, 15))




def draw_camera_hover_bar(screen, mouse_y, dt):
    global camera_active, camera_bar_y, camera_bar_target_y
    global last_hover_state, cam_toggle_cooldown, static_target_alpha

    bar_height = 80
    hover_zone = HEIGHT - 120        # The hover area
    toggle_cooldown_time = 0.4       # Prevent double triggers

    # initialize missing globals
    if "last_hover_state" not in globals():
        last_hover_state = False
    if "cam_toggle_cooldown" not in globals():
        cam_toggle_cooldown = 0.0

    # update cooldown
    if cam_toggle_cooldown > 0:
        cam_toggle_cooldown -= dt

    # detect hover
    hovering = mouse_y >= hover_zone

    # --- FNaF toggle logic ---
    if hovering and not last_hover_state and cam_toggle_cooldown <= 0:
        # Toggle camera
        camera_active = not camera_active
        cam_toggle_cooldown = toggle_cooldown_time

        if camera_active:
            static_target_alpha = 120
            print("[CAM] Monitor OPENED")

            # Play camera open sound on dedicated channel
            if CAM_OPEN_SOUND:
                CAM_OPEN_CHANNEL.play(CAM_OPEN_SOUND)

        else:
            static_target_alpha = 0
            print("[CAM] Monitor CLOSED")

            # Stop open sound immediately
            CAM_OPEN_CHANNEL.stop()

    # update last state
    last_hover_state = hovering

    # slide animation
    camera_bar_target_y = HEIGHT - (bar_height if camera_active else 20)
    camera_bar_y += (camera_bar_target_y - camera_bar_y) * min(dt * 10, 1)

    # draw bar background
    bar_rect = pygame.Rect(0, camera_bar_y, WIDTH, bar_height)
    pygame.draw.rect(screen, (25, 25, 25), bar_rect)

    # draw arrow
    arrow_y = camera_bar_y + 25
    arrow_color = (255, 80, 80) if camera_active else (220, 220, 220)
    pygame.draw.polygon(screen, arrow_color, [
        (WIDTH // 2 - 35, arrow_y + 20),
        (WIDTH // 2 + 35, arrow_y + 20),
        (WIDTH // 2, arrow_y)
    ])

    # glow on hover
    if hovering:
        glow = pygame.Surface((WIDTH, bar_height), pygame.SRCALPHA)
        glow.fill((255, 255, 255, 20))
        screen.blit(glow, (0, camera_bar_y))



def mouse_in_camera_ui(mx, my):
    """Returns True if mouse is over any camera UI that should NOT close the cams."""
    # Bottom hover bar
    if my >= HEIGHT - 80:
        return True

    # Right-side camera panel
    panel_width = 180
    panel_x = WIDTH - panel_width
    panel_y = 120
    panel_height = HEIGHT - panel_y - 50

    if panel_x <= mx <= WIDTH and panel_y <= my <= panel_y + panel_height:
        return True

    return False


def handle_camera_switch(key):
    global camera_index, flicker_timer, camera_booting, camera_boot_timer, current_camera_name

    # Trigger camera boot-up sequence
    camera_booting = True
    camera_boot_timer = 0.8  # seconds of static before feed appears

    # Map numeric keys (1..N) to indices in VIEWABLE_CAMERAS
    key_map = {
        pygame.K_1: 0,
        pygame.K_2: 1,
        pygame.K_3: 2,
        pygame.K_4: 3,
        pygame.K_5: 4,
        pygame.K_6: 5,
        pygame.K_7: 6,  # keep if you later add more
        pygame.K_8: 7,
    }

    if key in key_map:
        view_idx = key_map[key]
        if view_idx < len(VIEWABLE_CAMERAS):
            # The 'camera_index' in your rendering code expects an index into CAMERA_ORDER
            # Find the actual index inside CAMERA_ORDER for the selected viewable camera name:
            selected_name = VIEWABLE_CAMERAS[view_idx]
            camera_index = CAMERA_ORDER.index(selected_name)

            flicker_timer = 0.3  # short flicker when switching cams

            if CAMERA_SWITCH_SOUND:
                CAMERA_SWITCH_SOUND.set_volume(0.3)
                CAMERA_SWITCH_SOUND.play()

            # Display a human label for overlay (e.g., "1: Hall" or just "1")
            current_camera_name = f"{view_idx+1}: {selected_name}"
            print(f"[DEBUG] Switched view key {view_idx+1} -> camera_index {camera_index} ({selected_name})")


def toggle_door_between(room_a, room_b):
    """Toggle the door state if a door exists between two rooms."""
    key = (room_a, room_b) if (room_a, room_b) in DOORS else (room_b, room_a)
    if key in DOORS:
        DOORS[key]["closed"] = not DOORS[key]["closed"]


def drain_power(dt, camera_on):
    """Return new power value after drain."""
    total_drain = POWER_DRAIN_IDLE
    if camera_on:
        total_drain += POWER_DRAIN_CAMERA
    # add drain for each closed door
    for door in DOORS.values():
        if door["closed"]:
            total_drain += POWER_DRAIN_DOOR
    return max(power - total_drain * 60 * dt, 0)


def main_menu():
    # --- Load menu music ---
    menu_music = safe_load_sound("../assets/sounds/menu_theme.wav")
    if menu_music:
        menu_music.set_volume(0.5)
        menu_music.play(-1)

    # --- Fonts ---
    title_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 64)
    button_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 28)
    info_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 32)

    # --- Build STATIC frames ---
    if STATIC_FRAMES:
        static_frames = [
            pygame.transform.scale(f, (WIDTH, HEIGHT)).convert_alpha()
            for f in STATIC_FRAMES
        ]
    else:
        surf = pygame.Surface((WIDTH, HEIGHT))
        surf.fill((20, 20, 20))
        static_frames = [surf]

    frame_index = 0
    frame_timer = 0.0
    frame_delay = 0.04

    # --- Rainer flash effect ---
    try:
        rainer_img = pygame.image.load("../assets/images/rainer_flash.png").convert_alpha()
        rainer_img = pygame.transform.scale(rainer_img, (WIDTH, HEIGHT))
    except:
        rainer_img = None

    rainer_timer = random.uniform(5.0, 12.0)
    rainer_alpha = 0

    # Buttons
    start_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT//2, 300, 80)
    controls_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 120, 300, 80)
    quit_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 240, 300, 80)
    back_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT - 200, 300, 80)

    in_controls_menu = False
    running = True

    # -------- BUTTON DRAW --------
    def draw_button(rect, text, hovered):
        base_color = (40, 30, 30)
        hover_color = (70, 20, 20) if hovered else base_color

        # Color flicker
        flicker = random.randint(-10, 10)
        color = (
            max(0, min(255, hover_color[0] + flicker)),
            max(0, min(255, hover_color[1] + flicker)),
            max(0, min(255, hover_color[2] + flicker)),
        )

        # Button shake when hovered
        offset_x = random.randint(-1, 1) if hovered else 0
        offset_y = random.randint(-1, 1) if hovered else 0

        # Draw main button
        pygame.draw.rect(SCREEN, color, rect, border_radius=12)

        # Glow effect
        if hovered:
            glow = pygame.Surface((rect.width + 10, rect.height + 10), pygame.SRCALPHA)
            pygame.draw.rect(glow, (255, 30, 30, 35), glow.get_rect(), border_radius=12)
            SCREEN.blit(glow, (rect.x - 5, rect.y - 5))

        # Draw label
        label = button_font.render(text, True, (220, 220, 220))
        SCREEN.blit(label, (
            rect.centerx - label.get_width()//2 + offset_x,
            rect.centery - label.get_height()//2 + offset_y
        ))


    # -------- MAIN MENU LOOP --------
    while running:
        dt = CLOCK.tick(60)/1000.0

        # --- static animation ---
        frame_timer += dt
        if frame_timer >= frame_delay:
            frame_timer = 0
            frame_index = (frame_index + 1) % len(static_frames)

        static_surface = static_frames[frame_index].copy()
        static_surface.set_alpha(50)     # 50 = transparent static (old style)
        SCREEN.blit(static_surface, (0, 0))


        # --- dark overlay ---
        dark = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dark.fill((0, 0, 0, 80))
        SCREEN.blit(dark, (0,0))

        # --- scanlines ---
        if 'SCANLINE_OVERLAY' in globals() and SCANLINE_OVERLAY:
            SCREEN.blit(SCANLINE_OVERLAY, (0,0))

        mx, my = pygame.mouse.get_pos()

        # --- Rainer flash ---
        rainer_timer -= dt
        if rainer_img and rainer_timer <= 0:
            rainer_alpha = 255
            rainer_timer = random.uniform(8.0, 14.0)

        if rainer_alpha > 0 and rainer_img:
            rainer_alpha = max(0, rainer_alpha - 300 * dt)
            temp = rainer_img.copy()
            temp.set_alpha(int(rainer_alpha))
            SCREEN.blit(temp, (0,0))

        # -------- CONTROL SCREEN --------
        if in_controls_menu:
            header = title_font.render("Controls", True, (255, 255, 255))
            SCREEN.blit(header, (WIDTH//2 - header.get_width()//2, 120))

            lines = [
                "1-5  : Switch cameras",
                "D    : Toggle Office Door",
                "Hover bottom arrow : Open camera monitor",
                "ESC  : Quit game"
            ]

            y = 300
            for line in lines:
                t = info_font.render(line, True, (220, 220, 220))
                SCREEN.blit(t, (WIDTH//2 - t.get_width()//2, y))
                y += 60

            draw_button(back_rect, "Back", back_rect.collidepoint(mx,my))

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if back_rect.collidepoint(mx,my):
                        in_controls_menu = False

            pygame.display.flip()
            continue

        # -------- MAIN MENU SCREEN --------
        if random.random() < 0.03:
            flicker_color = (
                random.randint(150, 255),
                random.randint(150, 255),
                random.randint(150, 255)
            )
        else:
            flicker_color = (255, 255, 255)


        title = title_font.render("FIVE NIGHTS AT DRACHENSCHANZE", True, flicker_color)
        SCREEN.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//3))

        # Buttons
        draw_button(start_rect, "Start Night", start_rect.collidepoint(mx,my))
        draw_button(controls_rect, "Controls", controls_rect.collidepoint(mx,my))
        draw_button(quit_rect, "Quit", quit_rect.collidepoint(mx,my))

        # --- EVENT HANDLING ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if start_rect.collidepoint(mx,my):
                    running = False
                elif controls_rect.collidepoint(mx,my):
                    in_controls_menu = True
                elif quit_rect.collidepoint(mx,my):
                    pygame.quit(); sys.exit()

        pygame.display.flip()

    if menu_music:
        menu_music.fadeout(1500)


# --- MAP HOVER BAR (FNaF style, same logic as cam bar) ---
map_hover_x = 0
map_hover_target_x = 0
map_open = False
map_cooldown = 0.0
MAP_BAR_WIDTH = 60


def draw_map_hover_bar(surface, mouse_y, dt):
    """
    Right-side map hover bar that works exactly like the bottom camera bar.
    Opens map on first hover.
    Closes ONLY after the player fully leaves the bar, then hovers again.
    """

    global map_open, map_hover_y, map_hover_target_y
    global map_toggle_cooldown, map_hover_state

    BAR_W = 55
    BAR_H = 200
    open_zone_x = WIDTH - 80     # must move mouse here to open
    leave_zone_x = WIDTH - 260   # must leave this far to allow closing
    cooldown_time = 0.35

    mx, my = pygame.mouse.get_pos()

    # ---------- INIT GLOBALS ----------
    if "map_hover_state" not in globals():
        map_hover_state = "idle"  # idle → opened → left → ready_to_close

    if "map_toggle_cooldown" not in globals():
        map_toggle_cooldown = 0

    if "map_hover_y" not in globals():
        map_hover_y = HEIGHT//2 - BAR_H//2

    if "map_hover_target_y" not in globals():
        map_hover_target_y = HEIGHT//2 - BAR_H//2

    # ---------- Cooldown ----------
    if map_toggle_cooldown > 0:
        map_toggle_cooldown -= dt

    bar_rect = pygame.Rect(WIDTH - BAR_W, map_hover_y, BAR_W, BAR_H)
    hovering = bar_rect.collidepoint(mx, my)


    # OPENING LOGIC
    if map_hover_state == "idle":
        if hovering and not map_open and map_toggle_cooldown <= 0:
            map_open = True
            map_hover_state = "opened"
            map_toggle_cooldown = cooldown_time
            print("[MAP] OPEN via hover")

            if MAP_OPEN_SOUND:
                MAP_OPEN_SOUND.play()


    # TRANSITION TO READY-TO-CLOSE
    if map_hover_state == "opened" and mx < leave_zone_x:
        map_hover_state = "left"

    # CLOSING LOGIC
    if map_hover_state == "left":
        if hovering and map_open and map_toggle_cooldown <= 0:
            map_open = False
            map_hover_state = "idle"
            map_toggle_cooldown = cooldown_time
            print("[MAP] CLOSE via re-hover")

            if MAP_CLOSE_SOUND:
                MAP_CLOSE_SOUND.play()

    # ---------- Draw the bar (always while camera is open) ----------
    bar_rect = pygame.Rect(WIDTH - BAR_W, map_hover_y, BAR_W, BAR_H)
    pygame.draw.rect(surface, (40, 90, 160), bar_rect, border_radius=12)

    # arrow pointing left
    pygame.draw.polygon(surface, (220, 240, 255), [
        (bar_rect.left + 12, bar_rect.centery),
        (bar_rect.right - 12, bar_rect.centery - 20),
        (bar_rect.right - 12, bar_rect.centery + 20)
    ])



def show_night_intro(screen, text="Night 1", duration=3.0):
    """Displays 'Night X' text with fade in/out transition before gameplay."""
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("../assets/fonts/pixel_font.ttf", 80)
    label = font.render(text, True, (255, 255, 255))

    fade_surface = pygame.Surface((WIDTH, HEIGHT))
    fade_surface.fill((0, 0, 0))

    fade_in_time = 1.0   # seconds
    hold_time = 1.0      # seconds text stays visible
    fade_out_time = 1.0  # seconds
    total_time = fade_in_time + hold_time + fade_out_time

    timer = 0.0
    running = True

    while running:
        dt = clock.tick(60) / 1000.0
        timer += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        # calculate fade alpha
        if timer < fade_in_time:
            alpha = int(255 - (timer / fade_in_time) * 255)
        elif timer < fade_in_time + hold_time:
            alpha = 0
        elif timer < total_time:
            alpha = int(((timer - fade_in_time - hold_time) / fade_out_time) * 255)
        else:
            running = False
            break

        # draw black background + text
        screen.fill((0, 0, 0))
        text_x = WIDTH // 2 - label.get_width() // 2
        text_y = HEIGHT // 2 - label.get_height() // 2
        screen.blit(label, (text_x, text_y))

        # fade overlay
        fade_surface.set_alpha(alpha)
        screen.blit(fade_surface, (0, 0))

        pygame.display.flip()

    # after fade, transition back to black
    screen.fill((0, 0, 0))
    pygame.display.flip()
    pygame.time.wait(500)

pygame.mixer.set_num_channels(16)
pygame.mixer.music.set_volume(1.0)


# ----- Main loop -----
def main():
    global game_over, camera_bar_y, click_once, camera_bar_target_y, map_open, map_layer, jumpscare_time,night_timer, camera_index, power, STATIC_FRAMES, cam_toggle_cooldown, camera_active, camera_button_rect, STATIC_OVERLAY, cam_show_timer, STATIC_FRAME_TIMER, STATIC_FRAME_INDEX, static_alpha, static_target_alpha, jumpscare_active, office_locked, fade, CAM_BAR_ACTIVE_COLOR, CAM_BAR_COLOR, CAM_BAR_FONT, CAM_BAR_HEIGHT, CAM_BAR_TEXT_COLOR, cam_hovered
    running = True
    last_time = pygame.time.get_ticks()
    flicker_timer = 0.0
    camera_active = False
    static_alpha = 0.0         # current transparency level
    STATIC_FRAME_INDEX = 0
    STATIC_FRAME_TIMER = 0.0
    map_open = False
    map_layer = 0  # 0 = bottom, 1 = top
    camera_button_rect = pygame.Rect(WIDTH - 180, HEIGHT - 100, 160, 60)
    door_closed = False
    ambient_timer = random.uniform(20.0, 30.0)  # initial random delay before first ambient
    # --- Initialize animatronics (before main loop) ---
    camera_booting = False
    camera_boot_timer = 0.0
    cam_toggle_cooldown = 0.0
    current_camera_name = "1A"
    jumpscare_active = False
    office_locked = False
    # --- Camera tablet hover system ---
    CAM_BAR_HEIGHT = 60
    CAM_BAR_COLOR = (10, 10, 10)
    CAM_BAR_ACTIVE_COLOR = (30, 30, 30)
    CAM_BAR_TEXT_COLOR = (200, 255, 200)
    CAM_BAR_FONT = pygame.font.Font("../assets/fonts/pixel_font.ttf", 28)
    cam_hovered = False
    camera_bar_y = HEIGHT - 20          # current Y position of the hover bar
    camera_bar_target_y = HEIGHT - 20   # target Y (moves smoothly)
    cam_show_timer = 0.0    



    def play_jumpscare_video(path):
        """Play the jumpscare video overlayed on the current game frame (greenscreen removed)."""
        from moviepy.editor import VideoFileClip
        from PIL import Image
        import numpy as np
        import pygame
        import tempfile
        import os

        if not hasattr(Image, "ANTIALIAS"):
            Image.ANTIALIAS = Image.LANCZOS

        clip = VideoFileClip(path, audio=True)

        # --- Chroma key function: produce alpha transparency instead of black ---
        def chroma_key_rgba(frame):
            """Return RGBA frame with transparency where green was detected."""
            frame = np.copy(frame).astype(np.uint8)
            r, g, b = frame[..., 0], frame[..., 1], frame[..., 2]
            mask = (g > 1.55 * r) & (g > 1.55 * b) & (g > 40)
            alpha = np.where(mask, 0, 255).astype(np.uint8)
            rgba = np.dstack((r, g, b, alpha))
            return rgba

        clip = clip.fl_image(chroma_key_rgba).resize((WIDTH, HEIGHT))

        # --- Extract and play sound separately ---
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_path = tmp.name
            clip.audio.write_audiofile(audio_path, verbose=False, logger=None)

        jumpscare_sound = pygame.mixer.Sound(audio_path)
        jumpscare_sound.set_volume(3.0)
        jumpscare_sound.play()

        # --- Manual Pygame playback ---
        clock = pygame.time.Clock()
        for frame in clip.iter_frames(fps=30, dtype="uint8"):
            if frame.shape[2] == 3:
                # fallback if no alpha
                surf = pygame.image.frombuffer(frame.tobytes(), clip.size, "RGB").convert()
            else:
                surf = pygame.image.frombuffer(frame.tobytes(), clip.size, "RGBA").convert_alpha()

            # --- Redraw last game frame (Office background) first ---
            office_surface = OFFICE_BASE.copy()
            if is_door_closed_between("Hall", "Office"):
                office_surface.blit(DOOR_CLOSED_IMG, (0, 0))
            office_scaled = pygame.transform.scale(office_surface, (WIDTH, HEIGHT))
            SCREEN.blit(office_scaled, (0, 0))

            # --- Then overlay the jumpscare frame with alpha ---
            SCREEN.blit(surf, (0, 0))
            pygame.display.flip()
            clock.tick(30)

        clip.close()

        # Clean up temp file
        try:
            os.remove(audio_path)
        except:
            pass


    # Optional: slight speed variation
    rainer.speed = random.uniform(45, 65)
    fliege.speed = random.uniform(55, 70)

    # --- Start background ambiance when the night begins (with fade-in) ---
    if BACKGROUND_LOOP:
        BACKGROUND_LOOP.set_volume(0.0)
        BACKGROUND_LOOP.play(-1)
        background_fade_timer = 0.0
        background_target_volume = 0.15  # final volume
    else:
        background_fade_timer = None


    while running:
        now = pygame.time.get_ticks()
        dt = (now - last_time) / 1000.0
        last_time = now
        CLOCK.tick(60)

        # --- Gradually fade in background ambience ---
        if BACKGROUND_LOOP and background_fade_timer is not None:
            background_fade_timer += dt
            fade_duration = 5.0  # seconds for full fade-in
            current_volume = min(background_target_volume * (background_fade_timer / fade_duration),
                                background_target_volume)
            BACKGROUND_LOOP.set_volume(current_volume)
            if current_volume >= background_target_volume:
                background_fade_timer = None  # stop updating after fade-in completes


        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                click_once = True

            elif event.type == pygame.KEYDOWN:
                handle_camera_switch(event.key)

                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_d:
                    toggle_door_between("Office", "Hall")
                    door_closed = not door_closed
                    if door_closed:
                        print("Door Closed")
                        if DOOR_CLOSE_SOUND:
                            DOOR_CLOSE_SOUND.play()
                    else:
                        print("Door Open")
                        if DOOR_OPEN_SOUND:
                            DOOR_OPEN_SOUND.play()


        # --- Ambient noise system ---
       
        ambient_timer -= dt
        first_ambient = True

        # Inside the loop:
        ambient_timer -= dt
        if ambient_timer <= 0 and AMBIENT_SOUNDS:
            sound = random.choice(AMBIENT_SOUNDS)
            channel = sound.play()
            if channel:
                left = random.uniform(0.2, 1.0)
                right = random.uniform(0.2, 1.0)
                channel.set_volume(left, right)

            if first_ambient:
                ambient_timer = random.uniform(15.0, 25.0)
                first_ambient = False
            else:
                ambient_timer = random.uniform(20.0, 30.0)


        #drain power each frame
        camera_on = camera_active  # using camera drains more
        power = drain_power(dt, camera_on)

        if power <= 0:
            for door in DOORS.values():
                door["closed"] = False


        # --- Skip updates if player is already dead or jumpscare is active ---
        if game_over or jumpscare_active:
            continue  # freeze all updates this frame

        # --- Normal gameplay updates ---
        # update night timer
        night_timer -= dt
        if night_timer <= 0:
            # survive the night!
            print("You survived the night!")
            running = False
            
        # Update night clock
        elapsed = time.time() - night_start_time
        progress = elapsed / night_length

        # Convert progress (0.0 → 1.0) to hours
        # 12 AM → 1 AM → 2 AM → ... → 6 AM (6 stages)
        hours = int(progress * 6)

        clock_labels = ["12 AM", "1 AM", "2 AM", "3 AM", "4 AM", "5 AM", "6 AM"]

        if hours < len(clock_labels):
            current_hour = clock_labels[hours]
        else:
            current_hour = "6 AM"  # just to be safe

        # update animatronics
        for a in animatronics:
            a.update(dt)

            # Trigger jumpscare if an anim reached the Office and is in jumpscare state
            if not jumpscare_active and a.current_room == PLAYER_ROOM and a.state == "jumpscare":
                print(f"[AI] {a.name} reached the Office! Triggering jumpscare...")

                # --- Prevent duplicate triggers ---
                jumpscare_active = True
                office_locked = True

                # Stop background ambience
                if BACKGROUND_LOOP:
                    BACKGROUND_LOOP.fadeout(1000)

                # Play the appropriate jumpscare
                if a.name == "Rainer":
                    play_jumpscare_video(RAINER_JUMPSCARE_VIDEO_PATH)
                elif a.name == "Fliege":
                    play_jumpscare_video(RAINER_JUMPSCARE_VIDEO_PATH)  # placeholder for Flieged

                # --- Fade to black AFTER jumpscare video ---
                fade_surface = pygame.Surface((WIDTH, HEIGHT))
                fade_surface.fill((0, 0, 0))
                for alpha in range(0, 255, 8):
                    fade_surface.set_alpha(alpha)
                    SCREEN.blit(fade_surface, (0, 0))
                    pygame.display.flip()
                    pygame.time.wait(20)

                print("GAME OVER - Player jumpscared.")
                game_over = True

                # small delay for final sound tail
                pygame.time.wait(1000)
                running = False
                break


        # --- Smooth fade for static overlay ---
        if static_alpha < static_target_alpha:
            static_alpha = min(static_alpha + static_fade_speed * dt, static_target_alpha)
        elif static_alpha > static_target_alpha:
            static_alpha = max(static_alpha - static_fade_speed * dt, static_target_alpha)


        if camera_active and map_open and click_once:
            mx, my = pygame.mouse.get_pos()

            # Layer switch buttons
            if MAP_TOP_RECT.collidepoint(mx, my):
                map_layer = 1
                click_once = False

            elif MAP_BOTTOM_RECT.collidepoint(mx, my):
                map_layer = 0
                click_once = False

            # Camera switching
            for rect, cam_name in CAM_MAP_RECTS:
                if rect.collidepoint(mx, my):
                    camera_index = CAMERA_ORDER.index(cam_name)
                    current_camera_name = cam_name
                    if CAMERA_SWITCH_SOUND: CAMERA_SWITCH_SOUND.play()
                    click_once = False
                    break



        click_once = False

        # draw .............................................................................................................................................................................
        SCREEN.fill((10,10,10))

        # Center large camera view (base image)
        big_room = ROOMS[CAMERA_ORDER[camera_index]]
        big_view = big_room.view_surface.copy()

        # Ensure STATIC_FRAMES has at least one fallback frame
        if not STATIC_FRAMES:
            # create a subtle fallback static frame so nothing crashes / everything blits
            fallback = pygame.Surface((1280, 720), pygame.SRCALPHA)
            fallback.fill((30, 30, 30))
            STATIC_FRAMES = [fallback]
            STATIC_FRAME_INDEX = 0
            STATIC_FRAME_TIMER = 0.0

        # Update static animation timer (global 1080p static)
        if CAMERA_ORDER[camera_index] != "Office" and STATIC_FRAMES:
            STATIC_FRAME_TIMER += dt
            if STATIC_FRAME_TIMER > 0.05:
                STATIC_FRAME_INDEX = (STATIC_FRAME_INDEX + 1) % len(STATIC_FRAMES)
                STATIC_FRAME_TIMER = 0.0

        # Calculate static alpha target and smooth current
        # (target_alpha is 255 when camera open, 0 when closed — static_alpha is used for overlays)
        target_alpha = 255 if camera_active else 0
        if static_alpha < target_alpha:
            static_alpha = min(static_alpha + 100 * dt, target_alpha)
        elif static_alpha > target_alpha:
            static_alpha = max(static_alpha - 100 * dt, target_alpha)

        # If camera is active, draw camera UI (either map or feed)
        MAP_TOP_RECT = MAP_BOTTOM_RECT = MAP_CLOSE_RECT = None

        # Draw night clock at the top-center of the screen
        font_clock = pygame.font.Font("../assets/fonts/pixel_font.ttf", 48)
        clock_text = font_clock.render(current_hour, True, (255, 255, 255))
        SCREEN.blit(clock_text, (WIDTH // 2 - clock_text.get_width() // 2, 30))


        if camera_active:
            # If map is open: draw the map overlay centered
            if map_open:
                MAP_TOP_RECT, MAP_BOTTOM_RECT, MAP_CLOSE_RECT = draw_map_overlay(SCREEN)
            else:
                # Normal camera feed: render animatronics onto feed before scaling
                drawn_rooms = set()
                if CAMERA_ORDER[camera_index] != "Office":
                    for a in animatronics:
                        if a.current_room == big_room.name and a.visible and a.current_room not in drawn_rooms:
                            anim_img = a.get_room_image()
                            # blit to big_view using same coordinates — you may need to adjust coordinates
                            big_view.blit(anim_img, (0, 0))
                            drawn_rooms.add(a.current_room)

                # Scale and blit camera feed into the "tablet" area
                big_scaled = pygame.transform.scale(big_view, (1280, 720))
                SCREEN.blit(big_scaled, (WIDTH//2 - 640, HEIGHT//2 - 360))

            # Draw static overlay on top of camera/map if any
            try:
                static_frame = pygame.transform.scale(STATIC_FRAMES[STATIC_FRAME_INDEX], (1280, 720)).convert_alpha()
                translucent_static = pygame.Surface(static_frame.get_size(), pygame.SRCALPHA)
                translucent_static.blit(static_frame, (0, 0))
            except Exception:
                # fallback translucent static surface when something's wrong
                translucent_static = pygame.Surface((1280, 720), pygame.SRCALPHA)
                translucent_static.fill((0, 0, 0, 0))

            # Use static_alpha to control opacity (smaller factor for subtle effect)
            # Clamp safe values
            alpha_val = max(0, min(255, int(static_alpha * 0.25)))
            translucent_static.set_alpha(alpha_val)
            SCREEN.blit(translucent_static, (WIDTH // 2 - 640, HEIGHT // 2 - 360))

            # If camera booting, show full-screen static overlay (existing variable STATIC_OVERLAY expected)
            if camera_booting:
                camera_boot_timer -= dt
                if 'STATIC_OVERLAY' in globals() and STATIC_OVERLAY:
                    STATIC_OVERLAY.set_alpha(180)
                    SCREEN.blit(STATIC_OVERLAY, (0, 0))
                if camera_boot_timer <= 0:
                    camera_booting = False
            else:
                # Draw camera overlay HUD (REC, vignette, etc.)
                draw_camera_overlay(SCREEN, current_camera_name, booting=camera_booting)

        else:
            # camera not active: draw office world
            office_surface = OFFICE_BASE.copy()
            if door_closed:
                office_surface.blit(DOOR_CLOSED_IMG, (0, 0))
            """
            for a in animatronics:
                if a.current_room == "Office" and a.visible:
                    a.draw_on_surface(office_surface)
            """
            office_scaled = pygame.transform.scale(office_surface, (WIDTH, HEIGHT))
            SCREEN.blit(office_scaled, (0, 0))




        draw_ui()

        def draw_camera_overlay(surface, camera_name, booting=False):
            """Draw realistic FNaF-style camera overlay on top of the camera feed."""
            global rec_flash_timer, rec_visible

            # --- Base scanline overlay ---
            surface.blit(SCANLINE_OVERLAY, (0, 0))

            # --- Slight vignette ---
            vignette = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            for i in range(0, 255, 15):
                pygame.draw.rect(vignette, (0, 0, 0, i // 8),
                                (i // 6, i // 6, WIDTH - i // 3, HEIGHT - i // 3), 5)
            surface.blit(vignette, (0, 0))

            # --- REC indicator (now top-left) ---
            rec_flash_timer += 1 / 60
            if rec_flash_timer >= 0.5:
                rec_flash_timer = 0
                rec_visible = not rec_visible

            if rec_visible:
                rec_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 28)
                rec_text = rec_font.render("REC", True, (255, 40, 40))
                surface.blit(rec_text, (50, 40))
                pygame.draw.circle(surface, (255, 0, 0), (130, 50), 8)

            # --- Booting effect (signal lost) ---
            if booting:
                signal_font = pygame.font.Font("../assets/fonts/pixel_font.ttf", 38)
                signal_label = signal_font.render("SIGNAL LOST", True, (255, 255, 255))
                surface.blit(signal_label, (WIDTH//2 - signal_label.get_width()//2,
                                            HEIGHT//2 - signal_label.get_height()//2))
                # Black flicker overlay
                boot_overlay = pygame.Surface((WIDTH, HEIGHT))
                boot_overlay.fill((0, 0, 0))
                boot_overlay.set_alpha(random.randint(160, 220))
                surface.blit(boot_overlay, (0, 0))

            # --- Random flicker ---
            if random.random() < 0.02:
                flicker_overlay = pygame.Surface((WIDTH, HEIGHT))
                brightness = random.randint(15, 40)
                flicker_overlay.fill((brightness, brightness, brightness))
                flicker_overlay.set_alpha(random.randint(20, 60))
                surface.blit(flicker_overlay, (0, 0))


        draw_camera_overlay(SCREEN, current_camera_name, booting=camera_booting)

        #blackout
        if power <= 0:
            blackout = pygame.Surface((WIDTH, HEIGHT))
            blackout.set_alpha(180)
            blackout.fill((0, 0, 0))
            SCREEN.blit(blackout, (0, 0))

        if game_over:
            # show jumpscare overlay for a short time
            SCREEN.blit(JUMPSCARE_IMG, (0,0))
            jumpscare_time -= dt
            if jumpscare_time <= 0:
                # end menu / quit
                running = False

        mx, my = pygame.mouse.get_pos()
        draw_camera_hover_bar(SCREEN, my, dt)
        if camera_active:
            draw_map_hover_bar(SCREEN, my, dt)


        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main_menu()
    show_night_intro(SCREEN, "Night 1")
    main()
    
