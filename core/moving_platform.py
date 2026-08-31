"""Moving platforms that travel between waypoints defined in the map."""

import pygame

from core.config.constants import MOVING_PLATFORM_SPEED


class MovingPlatform:
    """A platform made of tiles that moves between two waypoints."""

    def __init__(
        self,
        tiles: list[tuple[pygame.Rect, pygame.Surface]],
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> None:
        self.tiles = tiles
        self.images = [img for _, img in tiles]

        if tiles:
            min_x = min(r.x for r, _ in tiles)
            min_y = min(r.y for r, _ in tiles)
            max_x = max(r.right for r, _ in tiles)
            max_y = max(r.bottom for r, _ in tiles)
            self.width = max_x - min_x
            self.height = max_y - min_y
        else:
            min_x, min_y = start
            self.width, self.height = 32, 32

        self.tile_offsets = [(r.x - min_x, r.y - min_y) for r, _ in tiles]

        self.start = pygame.math.Vector2(start)
        self.end = pygame.math.Vector2(end)
        self.pos = pygame.math.Vector2(start)
        self.direction = 1  # 1 = toward end, -1 = toward start

        total = self.end - self.start
        self.distance = total.length() if total.length() > 0 else 1
        self.progress = 0.0  # 0 = at start, 1 = at end

        self.rect = pygame.Rect(int(self.pos.x), int(self.pos.y), self.width, self.height)

    def update(self, dt: float) -> None:
        self.progress += (MOVING_PLATFORM_SPEED * dt / self.distance) * self.direction

        if self.progress >= 1.0:
            self.progress = 1.0
            self.direction = -1
        elif self.progress <= 0.0:
            self.progress = 0.0
            self.direction = 1

        self.pos = self.start.lerp(self.end, self.progress)
        self.rect.x = int(self.pos.x)
        self.rect.y = int(self.pos.y)

    def draw(self, surface: pygame.Surface, camera_offset: tuple[int, int] = (0, 0)) -> None:
        ox, oy = camera_offset
        for (off_x, off_y), img in zip(self.tile_offsets, self.images, strict=True):
            surface.blit(img, (int(self.pos.x + off_x - ox), int(self.pos.y + off_y - oy)))


class MovingPlatformManager:
    """Manages moving platforms that travel between waypoints from the map."""

    def __init__(
        self,
        platform_tiles: list[tuple[pygame.Rect, pygame.Surface]],
        waypoint_rects: list[pygame.Rect],
    ) -> None:
        self.platforms: list[MovingPlatform] = []

        if not platform_tiles or len(waypoint_rects) < 2:
            return

        groups = self._group_tiles(platform_tiles)

        waypoint_pairs = []
        for i in range(0, len(waypoint_rects) - 1, 2):
            wp_start = (waypoint_rects[i].x, waypoint_rects[i].y)
            wp_end = (waypoint_rects[i + 1].x, waypoint_rects[i + 1].y)
            waypoint_pairs.append((wp_start, wp_end))

        for i, group in enumerate(groups):
            if i < len(waypoint_pairs):
                start, end = waypoint_pairs[i]
            else:
                r = group[0][0]
                start = (r.x, r.y)
                end = start
            self.platforms.append(MovingPlatform(group, start, end))

    def _group_tiles(
        self, tiles: list[tuple[pygame.Rect, pygame.Surface]]
    ) -> list[list[tuple[pygame.Rect, pygame.Surface]]]:
        """Group tiles that are adjacent into platforms."""
        if not tiles:
            return []

        tile_h = tiles[0][0].height
        tile_w = tiles[0][0].width
        used = [False] * len(tiles)
        groups: list[list[tuple[pygame.Rect, pygame.Surface]]] = []

        for i in range(len(tiles)):
            if used[i]:
                continue

            group = [tiles[i]]
            used[i] = True

            queue = [i]
            while queue:
                ci = queue.pop(0)
                cr = tiles[ci][0]
                for j, (rect_j, _) in enumerate(tiles):
                    if used[j]:
                        continue
                    dx = abs(cr.x - rect_j.x)
                    dy = abs(cr.y - rect_j.y)
                    if (dx <= tile_w and dy == 0) or (dy <= tile_h and dx == 0):
                        group.append(tiles[j])
                        used[j] = True
                        queue.append(j)

            groups.append(group)

        return groups

    def update(self, dt: float) -> None:
        for p in self.platforms:
            p.update(dt)

    def rects(self) -> list[pygame.Rect]:
        return [p.rect for p in self.platforms]

    def draw(self, surface: pygame.Surface, camera_offset: tuple[int, int] = (0, 0)) -> None:
        for p in self.platforms:
            p.draw(surface, camera_offset)
