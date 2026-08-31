"""Optional pygame-ce desktop simulator backend."""

from __future__ import annotations

from badge_sdk import Action, InputEvent, RefreshMode


class PygameBackend:
    def __init__(self, width: int = 400, height: int = 300, scale: int = 2) -> None:
        try:
            import pygame
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError("Desktop simulation requires pygame-ce") from exc
        self.pygame = pygame
        self.width = width
        self.height = height
        self.scale = max(1, scale)
        pygame.init()
        self.window = pygame.display.set_mode((width * self.scale, height * self.scale))
        pygame.display.set_caption("BeagleBadge Launcher (CPython experimental)")

    def present(self, image, refresh: RefreshMode = RefreshMode.AUTO, damage=None) -> None:
        rgb = image.convert("RGB")
        surface = self.pygame.image.fromstring(rgb.tobytes(), rgb.size, "RGB")
        if self.scale != 1:
            surface = self.pygame.transform.scale(surface, self.window.get_size())
        self.window.blit(surface, (0, 0))
        self.pygame.display.flip()

    def poll(self) -> list[InputEvent]:
        result: list[InputEvent] = []
        mapping = {
            self.pygame.K_UP: Action.UP,
            self.pygame.K_DOWN: Action.DOWN,
            self.pygame.K_LEFT: Action.LEFT,
            self.pygame.K_RIGHT: Action.RIGHT,
            self.pygame.K_RETURN: Action.SELECT,
            self.pygame.K_KP_ENTER: Action.SELECT,
            self.pygame.K_ESCAPE: Action.BACK,
            self.pygame.K_BACKSPACE: Action.DELETE,
        }
        for event in self.pygame.event.get():
            if event.type == self.pygame.QUIT:
                result.append(InputEvent(Action.QUIT))
            elif event.type == self.pygame.KEYDOWN:
                action = mapping.get(event.key)
                if action:
                    result.append(InputEvent(action, repeat=getattr(event, "repeat", False)))
                elif event.unicode and event.unicode.isprintable():
                    result.append(InputEvent(Action.TEXT, text=event.unicode))
        return result

    def close(self) -> None:
        self.pygame.quit()
