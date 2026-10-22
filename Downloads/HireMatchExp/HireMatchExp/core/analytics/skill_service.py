
import json
from typing import Any, Dict, List, Optional, Set, Tuple

from core.analytics.models import GapStatus, SkillCoverageItem
from core.processing.skill_normalizer import SkillTaxonomyNormalizer
from core.storage.database import Database
from core.storage.repositories import CandidateRepository, JobRepository, SessionRepository
from core.utils.logger import logger


class SkillCoverageAnalyticsService:

    def __init__(self, db: Database, normalizer: Optional[SkillTaxonomyNormalizer] = None):
        self.db = db
        self.normalizer = normalizer or SkillTaxonomyNormalizer()
        self.session_repo = SessionRepository(db)
        self.job_repo = JobRepository(db)
        self.candidate_repo = CandidateRepository(db)

    def analyze_session_skills(self, session_id: str) -> List[SkillCoverageItem]:
        session = self.session_repo.get(session_id)
        if not session:
            raise ValueError(f"Screening Session '{session_id}' not found.")

        job = self.job_repo.get(session.job_id)
        if not job:
            return []

        job_skills: Dict[str, Dict[str, Any]] = {}

        query_crit = """
        SELECT criterion_name, criterion_type, description
        FROM evaluation_criteria
        WHERE job_id = ? AND is_enabled = 1;
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(query_crit, (job.id,))
            crit_rows = cursor.fetchall()

        for cr in crit_rows:
            raw_name = cr["criterion_name"]
            c_type = cr["criterion_type"]
            canonical, category = self.normalizer.normalize(raw_name)
            key = canonical.lower()
            if key not in job_skills:
                job_skills[key] = {
                    "raw_skill_name": raw_name,
                    "canonical_name": canonical,
                    "category": category,
                    "requirement_type": c_type,
                }

        raw_reqs: List[str] = []
        if hasattr(job, "requirements") and job.requirements:
            raw_reqs.extend([r for r in job.requirements if isinstance(r, str)])
        if hasattr(job, "parsed_requirements") and isinstance(job.parsed_requirements, dict):
            raw_reqs.extend([r for r in job.parsed_requirements.get("requirements", []) if isinstance(r, str)])
            for sk in job.parsed_requirements.get("skills", []):
                if isinstance(sk, dict) and "name" in sk:
                    raw_reqs.append(sk["name"])
                elif isinstance(sk, str):
                    raw_reqs.append(sk)

        for req in raw_reqs:
            if req.strip():
                canonical, category = self.normalizer.normalize(req)
                key = canonical.lower()
                if key not in job_skills:
                    job_skills[key] = {
                        "raw_skill_name": req,
                        "canonical_name": canonical,
                        "category": category,
                        "requirement_type": "REQUIRED",
                    }

        if not job_skills:
            query_cc = """
            SELECT criterion_contributions FROM candidate_scoring_records
            WHERE session_id = ? LIMIT 5;
            """
            with self.db.get_connection() as conn:
                cursor = conn.execute(query_cc, (session_id,))
                for row in cursor.fetchall():
                    try:
                        contribs = json.loads(row["criterion_contributions"])
                        for cc in contribs:
                            c_name = cc.get("criterion_name", "")
                            c_type = cc.get("criterion_type", "REQUIRED")
                            canonical, category = self.normalizer.normalize(c_name)
                            key = canonical.lower()
                            if key not in job_skills:
                                job_skills[key] = {
                                    "raw_skill_name": c_name,
                                    "canonical_name": canonical,
                                    "category": category,
                                    "requirement_type": c_type,
                                }
                    except Exception:
                        pass

        enrolled_candidates = self.candidate_repo.list_by_session(session_id)
        total_candidates = len(enrolled_candidates)
        if total_candidates == 0 or not job_skills:
            return []

        cand_ids = [c["candidate"].id for c in enrolled_candidates]

        placeholders = ",".join("?" for _ in cand_ids)
        query_skills = f"""
        SELECT candidate_id, skill_name, normalized_skill_name, evidence_text
        FROM extracted_skills
        WHERE candidate_id IN ({placeholders});
        """
        cand_skill_map: Dict[str, Set[str]] = {cid: set() for cid in cand_ids}
        skill_evidence_snippets: Dict[str, List[str]] = {}

        with self.db.get_connection() as conn:
            cursor = conn.execute(query_skills, tuple(cand_ids))
            for row in cursor.fetchall():
                cid = row["candidate_id"]
                s_name = row["normalized_skill_name"] or row["skill_name"]
                ev_text = row["evidence_text"]
                canonical, _ = self.normalizer.normalize(s_name)
                c_key = canonical.lower()
                cand_skill_map[cid].add(c_key)
                if ev_text:
                    if c_key not in skill_evidence_snippets:
                        skill_evidence_snippets[c_key] = []
                    if len(skill_evidence_snippets[c_key]) < 2 and ev_text not in skill_evidence_snippets[c_key]:
                        skill_evidence_snippets[c_key].append(ev_text)

        missing_cids = [item["candidate"].id for item in enrolled_candidates if not cand_skill_map.get(item["candidate"].id)]
        if missing_cids:
            placeholders_m = ",".join("?" for _ in missing_cids)
            q_struct = f"SELECT id, structured_data FROM candidates WHERE id IN ({placeholders_m}) AND structured_data IS NOT NULL;"
            with self.db.get_connection() as conn:
                cursor = conn.execute(q_struct, tuple(missing_cids))
                for s_row in cursor.fetchall():
                    cid = s_row["id"]
                    try:
                        raw_s = s_row["structured_data"]
                        struct = json.loads(raw_s) if isinstance(raw_s, str) else (raw_s or {})
                        for s_item in struct.get("skills", []):
                            s_name = s_item.get("normalized_name") or s_item.get("name") if isinstance(s_item, dict) else str(s_item)
                            canonical, _ = self.normalizer.normalize(s_name)
                            c_key = canonical.lower()
                            cand_skill_map[cid].add(c_key)
                    except Exception:
                        pass

        query_cc_all = f"""
        SELECT candidate_id, criterion_contributions
        FROM candidate_scoring_records
        WHERE session_id = ?;
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(query_cc_all, (session_id,))
            for row in cursor.fetchall():
                cid = row["candidate_id"]
                if cid not in cand_skill_map:
                    cand_skill_map[cid] = set()
                try:
                    contribs = json.loads(row["criterion_contributions"])
                    for cc in contribs:
                        stat = cc.get("match_status", "")
                        if stat in ("SUPPORTED", "PARTIALLY_SUPPORTED"):
                            c_name = cc.get("criterion_name", "")
                            canonical, _ = self.normalizer.normalize(c_name)
                            cand_skill_map[cid].add(canonical.lower())
                            note = cc.get("notes", "")
                            if note and canonical.lower() not in skill_evidence_snippets:
                                skill_evidence_snippets[canonical.lower()] = [note]
                except Exception:
                    pass

        results: List[SkillCoverageItem] = []
        for key, info in job_skills.items():
            matched_candidates_count = sum(1 for cid in cand_ids if key in cand_skill_map.get(cid, set()))
            coverage_pct = round((matched_candidates_count / total_candidates) * 100.0, 1)

            if coverage_pct >= 70.0:
                status = GapStatus.WELL_COVERED
            elif coverage_pct >= 40.0:
                status = GapStatus.MODERATE_COVERAGE
            else:
                status = GapStatus.ACUTE_GAP

            snippets = skill_evidence_snippets.get(key, [])

            results.append(
                SkillCoverageItem(
                    raw_skill_name=info["raw_skill_name"],
                    canonical_name=info["canonical_name"],
                    category=info["category"],
                    requirement_type=info["requirement_type"],
                    candidate_evidence_count=matched_candidates_count,
                    total_candidates=total_candidates,
                    pool_coverage_percentage=coverage_pct,
                    gap_status=status,
                    sample_evidence_snippets=snippets,
                )
            )

        results.sort(key=lambda x: (x.requirement_type != "REQUIRED", x.pool_coverage_percentage))
        return results
