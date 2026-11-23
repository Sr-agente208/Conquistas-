"""Pacote de tarefas (buscas, conjunto diário)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TaskResult:
    """Resumo de uma tarefa executada."""

    name: str
    performed: int = 0
    target: int = 0
    points_gained: int | None = None
    stopped_early: bool = False
    notes: str | None = None

    @property
    def ok(self) -> bool:
        return self.performed > 0 or self.target == 0
