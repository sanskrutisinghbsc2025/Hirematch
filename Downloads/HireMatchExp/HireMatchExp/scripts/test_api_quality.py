import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.app.main import app
from core.storage.database import Database

def test_api():
    client = TestClient(app)
    db = Database(Path("data/hirematch.db"))
    
    sessions = db.execute_query("SELECT id FROM screening_sessions LIMIT 1;")
    if not sessions:
        print("No sessions found in DB!")
        return
    session_id = sessions[0]["id"]
    print(f"Testing with session_id: {session_id}")

    res = client.get(f"/api/sessions/{session_id}/candidates")
    print(f"GET /sessions/{session_id}/candidates status:", res.status_code)
    assert res.status_code == 200, res.text
    data = res.json()
    items = data.get("items", [])
    print(f"Retrieved {len(items)} candidates for session.")
    assert len(items) > 0, "No candidates found in session response"
    
    has_quality_count = 0
    for cand in items:
        q_score = cand.get("resume_quality_score")
        q_label = cand.get("resume_quality_label")
        if q_score is not None:
            has_quality_count += 1
            print(f"  Candidate {cand.get('name')}: score={cand.get('overall_score')}, quality_score={q_score}, quality_label={q_label}")
    
    print(f"Candidates with resume quality: {has_quality_count}/{len(items)}")
    assert has_quality_count == len(items), f"Expected all candidates to have quality scores, got {has_quality_count}/{len(items)}"

    test_cand_id = items[0]["id"]
    res_cand = client.get(f"/api/candidates/{test_cand_id}?session_id={session_id}")
    print(f"GET /candidates/{test_cand_id} status:", res_cand.status_code)
    assert res_cand.status_code == 200, res_cand.text
    cand_data = res_cand.json()
    assert cand_data.get("resume_quality_score") is not None, "Candidate detail missing resume_quality_score"
    assert cand_data.get("resume_quality_label") is not None, "Candidate detail missing resume_quality_label"
    assert cand_data.get("resume_quality") is not None, "Candidate detail missing resume_quality object"
    print("  Candidate detail resume_quality_score:", cand_data.get("resume_quality_score"))
    print("  Candidate detail resume_quality_label:", cand_data.get("resume_quality_label"))
    print("  Criterion results count in resume_quality:", len(cand_data["resume_quality"]["criterion_results"]))

    res_qual = client.get(f"/api/candidates/{test_cand_id}/quality?session_id={session_id}")
    print(f"GET /candidates/{test_cand_id}/quality status:", res_qual.status_code)
    assert res_qual.status_code == 200, res_qual.text
    qual_report = res_qual.json()
    assert qual_report.get("overall_score") is not None
    assert qual_report.get("quality_label") is not None
    assert len(qual_report.get("criterion_results", [])) == 10
    print("  Dedicated Quality Report verified! 10 criteria evaluated.")

    if len(items) >= 2:
        comp_payload = {
            "session_id": session_id,
            "candidate_ids": [items[0]["id"], items[1]["id"]]
        }
        res_comp = client.post("/api/candidates/compare", json=comp_payload)
        print(f"POST /candidates/compare status:", res_comp.status_code)
        assert res_comp.status_code == 200, res_comp.text
        comp_data = res_comp.json()
        for ch in comp_data.get("candidate_headers", []):
            print(f"  Comparison header for {ch.get('original_filename')}: quality_score={ch.get('resume_quality_score')}, quality_label={ch.get('resume_quality_label')}")
            assert ch.get("resume_quality_score") is not None

    print("\nALL API QUALITY ENDPOINT VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_api()
