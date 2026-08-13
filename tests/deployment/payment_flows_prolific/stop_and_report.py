"""Test-only: stop recruitment immediately and report what needs paying."""

from collections import Counter

from dallinger.db import session
from dallinger.prolific import prolific_service_from_config
from dallinger.recruiters import by_name
from sqlalchemy import text

STUDY_ID = "6a7de0a7576dc4ebe02c42bf"

try:
    by_name("prolific").close_recruitment()
    print("CLOSE_RECRUITMENT: ok")
except Exception as e:
    print("CLOSE_RECRUITMENT_FAILED:", type(e).__name__, e)

service = prolific_service_from_config(strict=False)
study = service.get_study(STUDY_ID)
submissions = service.get_submissions(STUDY_ID)
print("STUDY_STATUS:", study.get("status"))
print(
    "SUBMISSION_COUNTS:",
    dict(sorted(Counter(s.get("status") for s in submissions).items())),
)

rows = session.execute(
    text("SELECT id, assignment_id, status, base_pay FROM participant ORDER BY id")
).fetchall()
by_assignment = {s.get("id"): s.get("status") for s in submissions}
print("PARTICIPANTS (psynet_id | local status | base_pay | prolific status):")
for r in rows:
    print(f"  {r[0]} | {r[2]} | {r[3]} | {by_assignment.get(r[1], 'NOT FOUND')}")
