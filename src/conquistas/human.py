"""Comportamentos "humanos": pausas irregulares, digitação e rolagem."""

from __future__ import annotations

import random
import time

from .config import SearchConfig


class Pacer:
    """Controla o ritmo entre buscas, com variação aleatória."""

    def __init__(
        self,
        min_delay_s: float,
        max_delay_s: float,
        rng: random.Random | None = None,
    ) -> None:
        if max_delay_s < min_delay_s:
            raise ValueError("max_delay_s deve ser >= min_delay_s")
        self.min_delay_s = float(min_delay_s)
        self.max_delay_s = float(max_delay_s)
        self._rng = rng or random.Random()

    @classmethod
    def from_config(cls, cfg: SearchConfig, rng: random.Random | None = None) -> Pacer:
        return cls(cfg.min_delay_s, cfg.max_delay_s, rng)

    def next_delay(self) -> float:
        """Intervalo enviesado para o meio da faixa (menos previsível que uniforme)."""
        low, high = self.min_delay_s, self.max_delay_s
        mid = low + (high - low) * 0.55
        value = self._rng.gauss(mid, (high - low) / 4)
        return max(low, min(high, value))

    def wait(self, scale: float = 1.0) -> float:
        delay = self.next_delay() * scale
        time.sleep(delay)
        return delay


def type_text(
    keyboard,
    text: str,
    rng: random.Random | None = None,
    min_char_s: float = 0.04,
    max_char_s: float = 0.16,
    typo_chance: float = 0.015,
) -> None:
    """Digita caractere por caractere, com pausas e hesitações irregulares."""
    rng = rng or random.Random()
    for char in text:
        if char == " " and rng.random() < typo_chance:
            time.sleep(rng.uniform(0.15, 0.45))
        keyboard.type(char)
        time.sleep(rng.uniform(min_char_s, max_char_s))
        if rng.random() < 0.05:
            time.sleep(rng.uniform(0.08, 0.3))


def random_scroll(page, rng: random.Random | None = None, moves: int = 2) -> None:
    """Rolagem e movimento de mouse leves para parecer leitura."""
    rng = rng or random.Random()
    try:
        viewport = page.viewport_size or {"width": 1366, "height": 768}
        width, height = viewport["width"], viewport["height"]
        for _ in range(moves):
            page.mouse.move(
                rng.randint(40, width - 40), rng.randint(80, height - 80), steps=rng.randint(6, 18)
            )
            page.mouse.wheel(0, rng.randint(180, 640))
            time.sleep(rng.uniform(0.4, 1.2))
    except Exception:  # página fechada/navegando: não é motivo para falhar a busca
        return
