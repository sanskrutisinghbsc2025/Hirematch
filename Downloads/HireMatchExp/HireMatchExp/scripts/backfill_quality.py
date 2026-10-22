import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.storage.database import Database
from core.services.session_orchestrator import ScreeningOrchestrator

def main():
    db = Database(Path("data/hirematch.db"))
    db.initialize_schema()
    orch = ScreeningOrchestrator(db=db)
    rows = db.execute_query("SELECT id, original_filename FROM candidates;")
    print(f"Total candidates to evaluate: {len(rows)}")
    success = 0
    for r in rows:
        cid = r["id"]
        fname = r["original_filename"]
        try:
            assessment = orch.get_candidate_quality_assessment(cid)
            success += 1
            print(f"[{success}/{len(rows)}] {fname}: score={assessment.overall_score:.1f}, label={assessment.quality_label.value}")
        except Exception as e:
            print(f"FAILED {fname} ({cid}): {e}")

    print(f"\nBackfill finished! Successfully assessed {success}/{len(rows)} candidates.")
    count_row = db.execute_query("SELECT COUNT(*) as cnt FROM resume_quality_assessments;")
    print(f"Total rows in resume_quality_assessments: {count_row[0]['cnt']}")

if __name__ == "__main__":
    main()
