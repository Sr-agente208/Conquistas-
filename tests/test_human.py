from __future__ import annotations

import random

import pytest

from conquistas.human import Pacer


def test_pacer_respects_bounds():
    rng = random.Random(3)
    pacer = Pacer(4.0, 9.0, rng)
    delays = [pacer.next_delay() for _ in range(500)]
    assert min(delays) >= 4.0
    assert max(delays) <= 9.0
    assert len(set(delays)) > 100  # não é constante


def test_pacer_rejects_inverted_range():
    with pytest.raises(ValueError):
        Pacer(10.0, 2.0)


def test_pacer_wait_scales(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr("conquistas.human.time.sleep", lambda s: slept.append(s))
    pacer = Pacer(5.0, 5.0, random.Random(0))
    value = pacer.wait(scale=0.5)
    assert value == pytest.approx(2.5)
    assert slept and slept[0] == pytest.approx(2.5)


def test_typing_and_scroll_do_not_raise_with_fake_page():
    class FakeKeyboard:
        def __init__(self):
            self.typed = []

        def type(self, char):
            self.typed.append(char)

    class FakeMouse:
        def move(self, *a, **k):
            return None

        def wheel(self, *a, **k):
            return None

    class FakePage:
        viewport_size = {"width": 800, "height": 600}
        mouse = FakeMouse()

    from conquistas.human import random_scroll, type_text

    keyboard = FakeKeyboard()
    type_text(keyboard, "teste", random.Random(1))
    assert "".join(keyboard.typed) == "teste"
    random_scroll(FakePage(), random.Random(2), moves=1)
