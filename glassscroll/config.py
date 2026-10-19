"""User settings, stored as JSON in %APPDATA%/GlassScroll/config.json."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

TRIGGERS = {
    "middle": "Middle click (wheel button)",
    "x1": "Side button 1 (back)",
    "x2": "Side button 2 (forward)",
}


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    path = Path(base) / "GlassScroll"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Config:
    enabled: bool = True
    trigger: str = "middle"          # middle | x1 | x2
    short_ms: int = 150              # hold this long  -> volume mode
    long_ms: int = 600               # hold this long  -> track mode
    volume_step: int = 2             # percent per wheel notch
    skip_cooldown_ms: int = 450      # minimum time between track skips
    invert_scroll: bool = False
    show_overlay: bool = True
    start_with_windows: bool = False

    def clamp(self) -> "Config":
        if self.trigger not in TRIGGERS:
            self.trigger = "middle"
        self.short_ms = int(min(max(self.short_ms, 80), 600))
        self.long_ms = int(min(max(self.long_ms, self.short_ms + 150), 2000))
        self.volume_step = int(min(max(self.volume_step, 1), 10))
        self.skip_cooldown_ms = int(min(max(self.skip_cooldown_ms, 150), 1500))
        return self

    @classmethod
    def load(cls) -> "Config":
        path = config_dir() / "config.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = {f.name for f in fields(cls)}
            return cls(**{k: v for k, v in data.items() if k in known}).clamp()
        except Exception:
            return cls()

    def save(self) -> None:
        try:
            (config_dir() / "config.json").write_text(
                json.dumps(asdict(self.clamp()), indent=2), encoding="utf-8"
            )
        except Exception:
            pass
