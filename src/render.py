
import pygame
import random

def present(SCREEN, WINDOW, VIRTUAL_W, VIRTUAL_H):
    """Skaliert die Offscreen-Fläche verlustfrei auf das Fenster und letterboxt."""
    w, h = WINDOW.get_size()
    scale = min(w / VIRTUAL_W, h / VIRTUAL_H)
    sw, sh = int(VIRTUAL_W * scale), int(VIRTUAL_H * scale)
    x, y = (w - sw) // 2, (h - sh) // 2
    frame = pygame.transform.smoothscale(SCREEN, (sw, sh))
    WINDOW.fill((0, 0, 0))
    WINDOW.blit(frame, (x, y))
    pygame.display.flip()

def window_to_virtual(pos, WINDOW, VIRTUAL_W, VIRTUAL_H):
    """Mappt Fensterkoordinaten auf virtuelle 1920x1080-Koordinaten."""
    mx, my = pos
    w, h = WINDOW.get_size()
    scale = min(w / VIRTUAL_W, h / VIRTUAL_H)
    sw, sh = int(VIRTUAL_W * scale), int(VIRTUAL_H * scale)
    ox, oy = (w - sw) // 2, (h - sh) // 2
    inside = (ox <= mx < ox + sw) and (oy <= my < oy + sh)
    vx = (mx - ox) / scale
    vy = (my - oy) / scale
    return int(vx), int(vy), inside

def apply_aspect(mode, compute_window_size):
    """Setzt das Fenster neu im gewünschten Seitenverhältnis."""
    WINDOW_W, WINDOW_H = compute_window_size(mode)
    return pygame.display.set_mode((WINDOW_W, WINDOW_H), pygame.RESIZABLE)

def create_scanline_surface(width, height):
    """Erzeugt Scanline-Overlay für Kamera-Effekt."""
    surf = pygame.Surface((width, height)).convert()
    surf.fill((0, 0, 0))
    for y in range(0, height, 4):
        pygame.draw.line(surf, (10, 10, 10), (0, y), (width, y), 2)
    surf.set_alpha(40)
    return surf

def draw_ui(SCREEN, WIDTH, HEIGHT, night_timer, power, is_door_closed):
    """Zeichnet die Status-UI (Zeit, Türstatus, Power)."""
    ui_font = pygame.font.SysFont("Arial", 26)
    panel = pygame.Surface((280, 100), pygame.SRCALPHA)
    panel.fill((10, 10, 10, 120))
    SCREEN.blit(panel, (WIDTH - 300, 15))
    info_x = WIDTH - 280
    info_y = 25
    timer_text = ui_font.render(f"TIME LEFT: {int(night_timer)}s", True, (220, 220, 220))
    SCREEN.blit(timer_text, (info_x, info_y))
    info_y += 28
    door_text = "CLOSED" if is_door_closed else "OPEN"
    door_color = (255, 60, 60) if door_text == "CLOSED" else (100, 255, 100)
    door_label = ui_font.render(f"DOOR: {door_text}", True, door_color)
    SCREEN.blit(door_label, (info_x, info_y))
    info_y += 28
    power_color = (220, 220, 220) if power > 20 else (255, 50, 50)
    power_label = ui_font.render(f"POWER: {power:.0f}%", True, power_color)
    SCREEN.blit(power_label, (info_x, info_y))

def draw_camera_overlay(surface, WIDTH, HEIGHT, SCANLINE_OVERLAY, camera_name, booting=False):
    """Zeichnet Kamera-Overlay (Scanlines, REC, Booting-Effekt)."""
    surface.blit(SCANLINE_OVERLAY, (0, 0))
    vignette = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(0, 255, 15):
        pygame.draw.rect(vignette, (0, 0, 0, i // 8),
                         (i // 6, i // 6, WIDTH - i // 3, HEIGHT - i // 3), 5)
    surface.blit(vignette, (0, 0))
    rec_font = pygame.font.SysFont("Arial", 28)
    rec_text = rec_font.render("REC", True, (255, 40, 40))
    surface.blit(rec_text, (50, 40))
    pygame.draw.circle(surface, (255, 0, 0), (130, 50), 8)
    if booting:
        signal_font = pygame.font.SysFont("Arial", 38)
        signal_label = signal_font.render("SIGNAL LOST", True, (255, 255, 255))
        surface.blit(signal_label, (WIDTH // 2 - signal_label.get_width() // 2,
                                    HEIGHT // 2 - signal_label.get_height() // 2))
        boot_overlay = pygame.Surface((WIDTH, HEIGHT))
        boot_overlay.fill((0, 0, 0))
        boot_overlay.set_alpha(random.randint(160, 220))
        surface.blit(boot_overlay, (0, 0))


def draw_camera_hover_bar(screen, WIDTH, HEIGHT, camera_active, camera_bar_y, camera_bar_target_y, dt):
    """Zeichnet die Hover-Bar für Kamera unten und toggelt bei Hover."""
    bar_height = 80
    hover_zone = HEIGHT - 120  # Bereich für Hover
    mx, my = pygame.mouse.get_pos()
    # Maus in virtuelle Koordinaten umrechnen (falls nötig)
    hovering = my >= hover_zone
    # Toggle bei Hover
    if hovering:
        camera_active = True
    else:
        camera_active = False

    camera_bar_target_y = HEIGHT - (bar_height if camera_active else 20)
    camera_bar_y += (camera_bar_target_y - camera_bar_y) * min(dt * 10, 1)
    bar_rect = pygame.Rect(0, camera_bar_y, WIDTH, bar_height)
    pygame.draw.rect(screen, (25, 25, 25), bar_rect)
    arrow_y = camera_bar_y + 25
    arrow_color = (255, 80, 80) if camera_active else (220, 220, 220)
    pygame.draw.polygon(screen, arrow_color, [
        (WIDTH // 2 - 35, arrow_y + 20),
        (WIDTH // 2 + 35, arrow_y + 20),
        (WIDTH // 2, arrow_y)
    ])
    return camera_active,


def draw_map_hover_bar(surface, WIDTH, HEIGHT, map_open, map_hover_y):
    """Zeichnet die Hover-Bar für Map rechts."""
    BAR_W = 55
    BAR_H = 200
    bar_rect = pygame.Rect(WIDTH - BAR_W, map_hover_y, BAR_W, BAR_H)
    pygame.draw.rect(surface, (40, 90, 160), bar_rect, border_radius=12)
    pygame.draw.polygon(surface, (220, 240, 255), [
        (bar_rect.left + 12, bar_rect.centery),
        (bar_rect.right - 12, bar_rect.centery - 20),
        (bar_rect.right - 12, bar_rect.centery + 20),
    ])

"""
Render- und UI-Funktionen für FNaF-Style-Spiel.
Beinhaltet Skalierung, Overlays, Scanlines und Hover-Bars.
"""
