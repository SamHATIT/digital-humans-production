"""Une reprise apres annulation ne doit pas relire la vieille demande (05/11/2026).

Smoke exec 181 : annulation, puis reprise -> 202 « resumed », puis le job
s'annule en 0,3 s : `cancel_requested_at` n'etait jamais efface.
"""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.workers.enqueue import enfiler_execution


class _Base:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def rollback(self):  # pragma: no cover
        pass


class _Pool:
    async def enqueue_job(self, nom, **kwargs):
        return SimpleNamespace(job_id=kwargs["_job_id"])


def _execution(annulee):
    return SimpleNamespace(
        id=181, arq_job_id=None, arq_queue_name=None,
        cancel_requested_at=datetime(2026, 11, 5, 18, 33, tzinfo=timezone.utc) if annulee else None,
    )


def test_un_nouvel_enfilage_efface_la_demande_d_annulation_precedente():
    execution, base = _execution(True), _Base()
    asyncio.run(enfiler_execution(_Pool(), base, execution, "execute_sds_task", execution_id=181))
    assert execution.cancel_requested_at is None
    assert base.commits == 1          # effacement persiste avec le job


def test_controle_negatif_sans_annulation_rien_ne_change():
    execution = _execution(False)
    asyncio.run(enfiler_execution(_Pool(), _Base(), execution, "execute_sds_task", execution_id=181))
    assert execution.cancel_requested_at is None and execution.arq_job_id
