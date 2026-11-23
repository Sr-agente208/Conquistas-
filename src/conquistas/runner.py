"""Pipeline de execução compartilhado pela CLI e pelo painel web."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Any

from .config import Config
from .tasks import TaskResult

log = logging.getLogger(__name__)


class SessionExpired(RuntimeError):
    """A sessão salva não vale mais; é preciso fazer login de novo."""


@dataclass
class ExecutionResult:
    points_before: int | None = None
    points_after: int | None = None
    results: list[TaskResult] = field(default_factory=list)
    status: str = "ok"
    notes: str | None = None

    @property
    def gained(self) -> int | None:
        if self.points_before is None or self.points_after is None:
            return None
        return self.points_after - self.points_before

    def by_name(self, name: str) -> TaskResult | None:
        return next((r for r in self.results if r.name == name), None)


def execute(
    cfg: Config,
    *,
    only: str = "all",
    pc: int | None = None,
    mobile: int | None = None,
    dry_run: bool = False,
    rng: random.Random | None = None,
) -> ExecutionResult:
    """Executa buscas e/ou tarefas diárias, registrando no banco local.

    Levanta `SessionExpired` quando a sessão salva não está mais válida.
    """
    from .auth import ensure_signed_in, read_points
    from .browser import Session
    from .storage import Store
    from .tasks import daily as daily_task
    from .tasks import searches

    rng = rng or random.Random()
    pc_target = cfg.searches.pc if pc is None else max(0, int(pc))
    mobile_target = cfg.searches.mobile if mobile is None else max(0, int(mobile))
    results: list[TaskResult] = []

    with Store(cfg.storage.database) as store:
        run_id = store.start_run()
        try:
            with Session(cfg) as session:
                if not ensure_signed_in(session, cfg):
                    raise SessionExpired("Sessão inválida ou expirada. Faça login novamente.")

                points_before = read_points(session)
                if points_before is not None:
                    store.record_points(points_before)

                if only in ("all", "searches") and cfg.searches.enabled:
                    results.extend(
                        searches.run_both(
                            session,
                            cfg,
                            pc_target,
                            mobile_target,
                            dry_run=dry_run,
                            rng=rng,
                        )
                    )
                if only in ("all", "daily") and cfg.daily.enabled:
                    results.append(daily_task.run(session, cfg, dry_run=dry_run, rng=rng))

                points_after = read_points(session)
                if points_after is not None:
                    store.record_points(points_after)
        except Exception as exc:
            store.finish_run(run_id, status="erro", notes=str(exc)[:300])
            raise

        pc_result = next((r for r in results if r.name == "buscas:desktop"), None)
        mobile_result = next((r for r in results if r.name == "buscas:mobile"), None)
        daily_result = next((r for r in results if r.name == "diario"), None)
        store.finish_run(
            run_id,
            points_before=points_before,
            points_after=points_after,
            pc_searches=pc_result.performed if pc_result else 0,
            mobile_searches=mobile_result.performed if mobile_result else 0,
            daily_done=daily_result.performed if daily_result else 0,
            daily_total=daily_result.target if daily_result else 0,
            status="simulacao" if dry_run else "ok",
            notes="; ".join(r.notes for r in results if r.notes) or None,
        )

    summary = ExecutionResult(
        points_before=points_before,
        points_after=points_after,
        results=results,
        status="simulacao" if dry_run else "ok",
    )
    log.info(
        "Execução concluída: %s pontos antes, %s depois",
        points_before,
        points_after,
    )
    return summary


def result_to_dict(result: ExecutionResult) -> dict[str, Any]:
    return {
        "points_before": result.points_before,
        "points_after": result.points_after,
        "gained": result.gained,
        "status": result.status,
        "notes": result.notes,
        "tasks": [
            {
                "name": r.name,
                "performed": r.performed,
                "target": r.target,
                "stopped_early": r.stopped_early,
                "notes": r.notes,
            }
            for r in result.results
        ],
    }
