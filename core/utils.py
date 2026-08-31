from pathlib import Path

import pygame


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(t, 1.0))


def load_spritesheet(
    filepath: Path,
    frame_size: tuple[int, int],
    frame_count: int,
    scale: float = 1.0,
) -> list[pygame.Surface]:
    sheet = pygame.image.load(filepath).convert_alpha()
    frames: list[pygame.Surface] = []
    w, h = frame_size
    scaled = (int(w * scale), int(h * scale))
    for i in range(frame_count):
        frame = sheet.subsurface(pygame.Rect(i * w, 0, w, h))
        frames.append(pygame.transform.scale(frame, scaled))
    return frames


def add_outline(
    surface: pygame.Surface,
    color: tuple[int, int, int] = (255, 255, 255),
) -> pygame.Surface:
    """Add a 1px colored outline around a sprite using its mask."""
    w, h = surface.get_size()
    outlined = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    mask = pygame.mask.from_surface(surface)
    mask_surface = mask.to_surface(setcolor=color, unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        outlined.blit(mask_surface, (1 + dx, 1 + dy))
    outlined.blit(surface, (1, 1))
    return outlined


def group_tiles_by_x(
    tiles: list[tuple[pygame.Rect, pygame.Surface]],
) -> list[list[tuple[pygame.Rect, pygame.Surface]]]:
    """Group tiles into columns by x coordinate."""
    groups: dict[int, list[tuple[pygame.Rect, pygame.Surface]]] = {}
    for rect, img in tiles:
        groups.setdefault(rect.x, []).append((rect, img))
    return list(groups.values())


def link_plates_to_doors(plates: list, doors: list) -> dict[int, int]:
    """Link each plate to the nearest door by Manhattan distance."""
    plate_door_map: dict[int, int] = {}
    for pi, plate in enumerate(plates):
        best_dist = float("inf")
        best_di = 0
        for di, door in enumerate(doors):
            if not door.tiles:
                continue
            door_cx = door.tiles[0][0].centerx
            door_cy = sum(t[0].centery for t in door.tiles) // len(door.tiles)
            dist = abs(plate.rect.centerx - door_cx) + abs(plate.rect.centery - door_cy)
            if dist < best_dist:
                best_dist = dist
                best_di = di
        plate_door_map[pi] = best_di
    return plate_door_map
