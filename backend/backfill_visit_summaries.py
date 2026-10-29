"""One-time backfill: per-visit patient summaries for pre-0019 visits.

Visits recorded before migration 0019 have no patient_summary. This
script queues mdt.summarize_visit for every visit missing one. Queued
work lands as draft: a clinician still reviews and releases each
summary before patients see it. Safe to re-run: visits that already
have one are skipped.

Run inside the backend container (worker must be running to drain the
queue):

    docker compose exec backend python backfill_visit_summaries.py
"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.mdt.tasks import summarize_visit
from app.patients.models import Visit


def main() -> int:
    with SessionLocal() as db:
        visits = db.scalars(select(Visit).order_by(Visit.visit_date)).all()
        missing = [
            v.id for v in visits if not (v.patient_summary or {}).get("en")
        ]
    print(f"backfill: {len(visits)} visits, {len(missing)} missing a summary")
    queued, failed = 0, 0
    for i, visit_id in enumerate(missing, 1):
        try:
            summarize_visit.delay(visit_id)
            queued += 1
        except Exception as exc:
            failed += 1
            print(f"backfill: queue failed for {visit_id}: {exc}")
        if i % 50 == 0:
            print(f"backfill: {i}/{len(missing)} queued...")
    print(f"backfill: queued {queued}, failed {failed} (worker drafts EN/SW/LG for release)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
