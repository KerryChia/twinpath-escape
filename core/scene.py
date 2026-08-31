import pygame


class Scene:
    def __init__(self, manager: "SceneManager") -> None:
        self.manager = manager

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        pass

    def on_resize(self, width: int, height: int) -> None:
        pass


class SceneManager:
    def __init__(self) -> None:
        self.stack: list[Scene] = []

    def push(self, scene: Scene) -> None:
        self.stack.append(scene)

    def pop(self) -> None:
        if self.stack:
            self.stack.pop()

    def replace(self, scene: Scene) -> None:
        if self.stack:
            self.stack.pop()
        self.stack.append(scene)

    @property
    def current(self) -> Scene | None:
        return self.stack[-1] if self.stack else None

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.current:
            self.current.handle_event(event)

    def update(self, dt: float) -> None:
        if self.current:
            self.current.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        for scene in self.stack:
            scene.draw(surface)

    def notify_resize(self, width: int, height: int) -> None:
        for scene in self.stack:
            scene.on_resize(width, height)
