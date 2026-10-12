"""Report helpers used by the web page, the CSV export and the command line."""
import csv
import io

from models import STATUSES

CSV_FIELDS = ["number", "client", "opened_on", "status", "lawyer", "description"]


def build_summary(repo):
    cases = repo.search()
    active = [c for c in cases if c.status != "Closed"]
    by_status = repo.count_by("status")
    return {
        "total": len(cases),
        "active": len(active),
        "by_status": {s: by_status.get(s, 0) for s in STATUSES},
        "by_lawyer": repo.count_by("lawyer"),
        "oldest_active": max(active, key=lambda c: c.days_open, default=None),
    }


def cases_to_csv(cases):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_FIELDS)
    for case in cases:
        writer.writerow([getattr(case, f) for f in CSV_FIELDS])
    return buffer.getvalue()


if __name__ == "__main__":
    import os
    from database import CaseRepository

    summary = build_summary(CaseRepository(os.getenv("DATABASE", "cases.db")))
    print(f"Total cases: {summary['total']} ({summary['active']} active)")
    for status, count in summary["by_status"].items():
        print(f"  {status:<18}{count}")
    print("By lawyer:")
    for lawyer, count in summary["by_lawyer"].items():
        print(f"  {lawyer:<18}{count}")
