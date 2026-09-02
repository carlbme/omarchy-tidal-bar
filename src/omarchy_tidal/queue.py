from __future__ import annotations


class PlayQueue:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []
        self.index = -1

    def current(self) -> dict[str, object] | None:
        if 0 <= self.index < len(self.items):
            return self.items[self.index]
        return None

    def replace(self, item: dict[str, object]) -> None:
        self.items = [item]
        self.index = 0

    def append(self, item: dict[str, object]) -> int:
        self.items.append(item)
        if self.index < 0:
            self.index = 0
        return len(self.items) - 1

    def next_index(self) -> int | None:
        candidate = self.index + 1
        if 0 <= candidate < len(self.items):
            return candidate
        return None

    def previous_index(self) -> int | None:
        candidate = self.index - 1
        if candidate >= 0:
            return candidate
        return None

    def snapshot(self) -> dict[str, object]:
        return {
            "queue": list(self.items),
            "index": self.index,
            "length": len(self.items),
        }
