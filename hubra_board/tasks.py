"""Celery task: the board's daily reminders."""

from __future__ import annotations

from hubra.core.modules import per_tenant_job
from hubra.core.tasks import celery_app

from . import services


@celery_app.task(name="hubra_board.tasks.remind")
@per_tenant_job("board")
def remind() -> dict:
    from hubra.core.extensions import db

    done = services.remind()
    db.session.commit()
    return done
