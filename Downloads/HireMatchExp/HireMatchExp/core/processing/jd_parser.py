
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional

from core.processing.cleaner import TextCleaner
from core.processing.skill_normalizer import SkillTaxonomyNormalizer


@dataclass
class StructuredJobDescription:
    title: Optional[str] = None
    domain: str = "general"
    responsibilities: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    min_experience_years: int = 0
    preferred_experience_years: Optional[int] = None
    education_level: str = "Unspecified"
    certifications: List[str] = field(default_factory=list)
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "domain": self.domain,
            "responsibilities": self.responsibilities,
            "required_skills": self.required_skills,
            "preferred_skills": self.preferred_skills,
            "min_experience_years": self.min_experience_years,
            "preferred_experience_years": self.preferred_experience_years,
            "education_level": self.education_level,
            "certifications": self.certifications,
        }


class IJobDescriptionParser(ABC):

    @abstractmethod
    def parse_job_description(self, text: str, fallback_title: Optional[str] = None) -> StructuredJobDescription:
        pass

    def parse(self, text: str) -> Dict[str, Any]:
        return self.parse_job_description(text).to_dict()


class EnhancedJDParser(IJobDescriptionParser):

    def __init__(self, normalizer: Optional[SkillTaxonomyNormalizer] = None):
        self.normalizer = normalizer or SkillTaxonomyNormalizer()

    ROLE_ARCHETYPES = {
        "healthcare": {
            "domain": "healthcare",
            "keywords": ["nurse", "nursing", "physician", "doctor", "medical", "clinical", "patient care", "hospital", "pharmacist", "therapist", "dental", "surgeon", "clinic", "icu", "emergency room", "healthcare"],
            "core_skills": ["Patient Care & Clinical Assessment", "Clinical Protocols & Patient Safety", "Pharmacology & Medication Administration", "Electronic Health Records (EHR)", "Emergency Triage & Vital Signs"],
            "tools": ["Epic Systems", "Cerner EHR", "BLS & ACLS Certification", "Diagnostic Medical Equipment", "HIPAA Compliance"],
            "default_exp": 2,
            "education": "Bachelor of Science in Nursing (BSN), MD, or Accredited Healthcare Degree & State Licensure",
        },
        "culinary": {
            "domain": "culinary",
            "keywords": ["chef", "cook", "kitchen", "culinary", "restaurant", "pastry", "sous chef", "line cook", "food service", "hospitality", "catering", "baker"],
            "core_skills": ["Culinary Technique & Food Preparation", "Menu Design & Recipe Development", "Food Safety & Sanitation (HACCP)", "Kitchen Inventory & Food Cost Control", "Station Management & Expediting"],
            "tools": ["Commercial Kitchen Equipment", "ServSafe Manager Certification", "POS & Kitchen Display Systems", "Knife Skills & Butchery", "Health & Sanitation Compliance"],
            "default_exp": 2,
            "education": "Culinary Arts Degree, Professional Apprenticeship, or equivalent commercial kitchen experience",
        },
        "trades": {
            "domain": "trades",
            "keywords": ["electrician", "plumber", "carpenter", "construction", "welder", "hvac", "technician", "maintenance", "masonry", "machinist", "pipefitter", "facilities"],
            "core_skills": ["Trade Workmanship & Practical Installation", "Blueprint & Schematic Interpretation", "Preventive Maintenance & Diagnostics", "Workplace Safety & OSHA Compliance", "Building Codes & Quality Standards"],
            "tools": ["Hand & Power Tools", "Testing & Multimeter Diagnostic Tools", "Trade Licensure (Journeyman / Master)", "PPE & OSHA Protocols", "Fabrication & Assembly Equipment"],
            "default_exp": 3,
            "education": "Vocational Certification, Trade Apprenticeship, or High School Diploma with Trade License",
        },
        "education": {
            "domain": "education",
            "keywords": ["teacher", "teaching", "educator", "instructor", "professor", "faculty", "classroom", "curriculum", "school", "kindergarten", "tutor", "pedagogy", "special education"],
            "core_skills": ["Curriculum Design & Lesson Planning", "Classroom Instruction & Management", "Student Assessment & Formative Evaluation", "Differentiated Instruction & IEP Accommodation", "Subject Matter Pedagogy"],
            "tools": ["Learning Management Systems (Canvas/Blackboard)", "Educational Technology Platforms", "State Educator Certification", "Classroom Engagement Tools", "Parent & Stakeholder Communication"],
            "default_exp": 2,
            "education": "Bachelor's or Master's Degree in Education or relevant subject + State Educator Credential",
        },
        "legal": {
            "domain": "legal",
            "keywords": ["lawyer", "attorney", "counsel", "legal", "paralegal", "litigation", "solicitor", "compliance officer", "contracts manager", "jurist"],
            "core_skills": ["Legal Research & Case Precedent Analysis", "Contract Drafting, Review & Negotiation", "Regulatory Compliance & Risk Assessment", "Litigation Support & Case Management", "Brief Writing & Statutory Interpretation"],
            "tools": ["Westlaw / LexisNexis", "Legal Practice & Case Management Systems", "State Bar Licensure", "DocuSign & Contract Lifecycle Management (CLM)", "E-Discovery Software"],
            "default_exp": 3,
            "education": "Juris Doctor (J.D.) or LL.M. with active Bar membership or Paralegal Certification",
        },
        "finance": {
            "domain": "finance",
            "keywords": ["accountant", "accounting", "auditor", "financial analyst", "finance", "cpa", "controller", "tax", "bookkeeper", "investment", "treasury", "banking", "payroll"],
            "core_skills": ["Financial Analysis & Forecasting", "General Ledger & Month-End Closing", "Financial Statement Preparation & Reporting", "GAAP & IFRS Accounting Standards", "Budgeting & Variance Analysis"],
            "tools": ["Advanced Excel (Financial Modeling)", "ERP Systems (SAP, NetSuite, Oracle)", "QuickBooks", "Tax Compliance & Audit Systems", "CPA / CFA Certification"],
            "default_exp": 2,
            "education": "Bachelor's degree in Accounting, Finance, Economics, or CPA credential",
        },
        "hr": {
            "domain": "hr",
            "keywords": ["human resources", "hr", "recruiter", "talent acquisition", "people operations", "hr generalist", "hr business partner", "hrbp", "talent partner"],
            "core_skills": ["End-to-End Talent Acquisition", "Employee Relations & Conflict Mediation", "Onboarding & Retention Frameworks", "Compensation, Benefits & Payroll Support", "Labor Laws & Employment Compliance"],
            "tools": ["Applicant Tracking Systems (ATS)", "HRIS Platforms (Workday, BambooHR)", "LinkedIn Talent Insights", "SHRM-CP / PHR Certification", "Performance Evaluation Frameworks"],
            "default_exp": 2,
            "education": "Bachelor's degree in Human Resources, Business Administration, Psychology, or related field",
        },
        "sales": {
            "domain": "sales",
            "keywords": ["sales", "account executive", "business development", "real estate", "realtor", "bdr", "sdr", "sales manager", "client relationship", "broker"],
            "core_skills": ["B2B / B2C Prospecting & Territory Development", "Sales Pipeline Management & Quota Attainment", "Contract Negotiation & Deal Closing", "Client Relationship Building", "Consultative Solution Selling"],
            "tools": ["CRM Systems (Salesforce, HubSpot)", "Sales Engagement Platforms", "Lead Sourcing & Qualification Tools", "Contract & Proposal Software", "Real Estate Licensure (if applicable)"],
            "default_exp": 2,
            "education": "Bachelor's degree in Business, Communications, or proven track record of quota attainment",
        },
        "logistics": {
            "domain": "logistics",
            "keywords": ["logistics", "supply chain", "warehouse", "inventory", "procurement", "freight", "shipping", "distribution", "transportation", "material handler"],
            "core_skills": ["Supply Chain Coordination & Fulfillment", "Inventory Control & Cycle Counting", "Vendor Management & Procurement", "Warehouse Operations & Lean / 5S", "Freight & Carrier Scheduling"],
            "tools": ["Warehouse Management Systems (WMS)", "ERP Platforms (SAP, Oracle)", "Barcode Scanning & RFID Systems", "Forklift & OSHA Safety Certification", "TMS Route Optimization"],
            "default_exp": 2,
            "education": "Associate's or Bachelor's in Supply Chain, Logistics, Business, or equivalent industry experience",
        },
        "engineering": {
            "domain": "engineering",
            "keywords": ["mechanical engineer", "civil engineer", "electrical engineer", "chemical engineer", "structural engineer", "industrial engineer", "manufacturing engineer"],
            "core_skills": ["Engineering Design & Technical Analysis", "CAD Modeling & Drafting", "Quality Assurance & Testing Standards", "Technical Documentation & Specifications", "Root Cause Analysis & Design Validation"],
            "tools": ["AutoCAD / SolidWorks / Revit", "MATLAB & Engineering Simulation", "Engineering Design Codes (ASME, IEEE)", "Testing & Inspection Instruments", "Professional Engineer (PE) / EIT Licensure"],
            "default_exp": 2,
            "education": "Bachelor's degree in Mechanical, Civil, Electrical, or related Engineering discipline",
        },
        "management": {
            "domain": "management",
            "keywords": ["general manager", "operations manager", "store manager", "branch manager", "director", "chief executive", "vp of operations", "supervisor", "team leader"],
            "core_skills": ["Operational Strategy & Execution", "Cross-Functional Team Leadership", "P&L Management & Budgeting", "Process Optimization & Operational Excellence", "Stakeholder & Client Communication"],
            "tools": ["Project Management Tools (Asana, Jira, Monday)", "KPI Dashboards & Business Analytics", "ERP & Financial Tracking Systems", "Continuous Improvement (Lean/Six Sigma)", "Executive Reporting"],
            "default_exp": 4,
            "education": "Bachelor's or Master's degree in Business Administration (MBA) or proven leadership career",
        },
        "data": {
            "domain": "tech",
            "keywords": ["data analyst", "data scientist", "data engineer", "business intelligence", "analytics", "bi analyst", "statistician", "machine learning"],
            "core_skills": ["SQL & Relational Querying", "Data Analysis & Exploration", "Python Programming", "Data Cleaning & Preprocessing", "Statistical Modeling & Hypothesis Testing"],
            "tools": ["Tableau", "Power BI", "Excel", "Data Warehousing", "Interactive Reporting Dashboards"],
            "default_exp": 2,
            "education": "Bachelor's degree in Statistics, Mathematics, Computer Science, Economics, or quantitative field",
        },
        "devops": {
            "domain": "tech",
            "keywords": ["devops", "sre", "cloud engineer", "infrastructure", "systems engineer", "platform engineer", "system administrator"],
            "core_skills": ["Linux System Administration", "Container Orchestration", "CI/CD Pipeline Automation", "Cloud Infrastructure Management", "Site Reliability & Monitoring"],
            "tools": ["Docker", "Kubernetes", "Terraform", "AWS / Azure / GCP", "Git"],
            "default_exp": 3,
            "education": "Bachelor's degree in Computer Science, Information Technology, or practical experience",
        },
        "backend": {
            "domain": "tech",
            "keywords": ["backend", "software engineer", "software developer", "full stack", "api developer", "systems architect", "programmer"],
            "core_skills": ["API Design & Implementation", "Object-Oriented Programming", "Database Schema Modeling", "Distributed Systems Architecture", "Data Structures & Algorithms"],
            "tools": ["Python", "Java", "Docker", "PostgreSQL", "Git"],
            "default_exp": 2,
            "education": "Bachelor's degree in Computer Science, Software Engineering, or related technical field",
        },
        "frontend": {
            "domain": "tech",
            "keywords": ["frontend", "front end", "web developer", "ui developer", "react developer", "javascript developer"],
            "core_skills": ["JavaScript & Modern Web Standards", "TypeScript", "HTML5 & Semantic CSS", "Responsive UI Design", "Frontend State Management"],
            "tools": ["React", "Next.js", "Tailwind CSS", "Build Tooling & Webpack", "Git"],
            "default_exp": 2,
            "education": "Bachelor's degree in Computer Science, Web Development, or equivalent practical experience",
        },
        "product": {
            "domain": "management",
            "keywords": ["product manager", "product owner", "scrum master", "project manager", "program manager", "agile coach"],
            "core_skills": ["Product Strategy & Discovery", "Agile & Scrum Frameworks", "User Research & Customer Interviews", "Product Roadmapping & Prioritization", "Cross-Functional Alignment"],
            "tools": ["Jira", "Confluence", "Analytics & Product Telemetry", "Wireframing Tools", "Release Management"],
            "default_exp": 3,
            "education": "Bachelor's degree in Business, Management, Computer Science, or related field",
        },
        "design": {
            "domain": "creative",
            "keywords": ["ui/ux", "designer", "product designer", "graphic designer", "visual designer", "art director", "illustrator"],
            "core_skills": ["User Experience Design", "Wireframing & Interactive Prototyping", "Design Systems & Component Libraries", "User Research & Usability Testing", "Visual & Graphic Communication"],
            "tools": ["Figma", "Adobe Creative Cloud", "Illustrator", "Photoshop", "Prototyping Software"],
            "default_exp": 2,
            "education": "Degree in Graphic Design, HCI, Fine Arts, or demonstrable design portfolio",
        },
        "marketing": {
            "domain": "marketing",
            "keywords": ["marketing", "growth", "seo", "content strategist", "digital marketing", "social media manager", "copywriter"],
            "core_skills": ["Digital Marketing Strategy", "SEO & Content Marketing", "Campaign Planning & Execution", "Audience Analytics & Conversion Optimization", "Brand Messaging & Copywriting"],
            "tools": ["Google Analytics", "CRM & Marketing Automation", "Email Campaign Software", "Social Media Suites", "CMS Platforms"],
            "default_exp": 2,
            "education": "Bachelor's degree in Marketing, Communications, Business, or related discipline",
        },
    }

    def _infer_archetype(self, title: Optional[str], text: str) -> Optional[Dict[str, Any]]:
        clean_title = (title or "").lower()
        if clean_title:
            for archetype_key, data in self.ROLE_ARCHETYPES.items():
                for kw in data["keywords"]:
                    if re.search(rf"\b{re.escape(kw)}\b", clean_title):
                        return data

        clean_text = text.lower()
        best_archetype = None
        best_matches = 0
        for archetype_key, data in self.ROLE_ARCHETYPES.items():
            matches = sum(1 for kw in data["keywords"] if re.search(rf"\b{re.escape(kw)}\b", clean_text))
            if matches > best_matches:
                best_matches = matches
                best_archetype = data

        return best_archetype if best_matches >= 1 else None

    def _extract_bullet_phrases(self, lines: List[str]) -> List[str]:
        extracted: List[str] = []
        boilerplate = [
            r"^(?:must have|ability to|responsible for|demonstrated capability to|proven experience (?:with|in)?|strong knowledge of|proficient in|hands-on experience (?:with|in)?|familiarity with|knowledge of|experience with|minimum of)\s*",
            r"^(?:excellent|strong|proven|demonstrated|solid)\s+",
        ]
        for line in lines:
            trimmed = line.strip().lstrip("-*•0123456789. ")
            if len(trimmed) < 4 or len(trimmed) > 80:
                continue
            cleaned = trimmed
            for b in boilerplate:
                cleaned = re.sub(b, "", cleaned, flags=re.IGNORECASE).strip()
            words = cleaned.split()
            if 1 <= len(words) <= 7 and not cleaned.endswith(("?", "!")):
                phrase = " ".join(w.capitalize() if not w.isupper() else w for w in words)
                if phrase and phrase not in extracted:
                    extracted.append(phrase)
            if len(extracted) >= 8:
                break
        return extracted

    def parse_job_description(self, text: str, fallback_title: Optional[str] = None) -> StructuredJobDescription:
        cleaned = TextCleaner.clean(text)
        if not cleaned:
            return StructuredJobDescription(title=fallback_title)

        lines = cleaned.split("\n")

        detected_title = fallback_title
        if not detected_title and lines:
            first_line = lines[0].strip()
            if 3 <= len(first_line) <= 50 and not any(k in first_line.lower() for k in ["about", "overview", "company", "description"]):
                detected_title = first_line

        current_section = "GENERAL"
        required_text_lines = []
        preferred_text_lines = []
        responsibilities = []
        certifications = []

        for line in lines:
            ll = line.lower().strip()
            if not ll:
                continue

            if any(k in ll for k in ["required", "requirements", "must have", "minimum qualifications", "what you need", "basic qualifications"]):
                current_section = "REQUIRED"
                continue
            elif any(k in ll for k in ["preferred", "nice to have", "bonus", "plus", "desired qualifications"]):
                current_section = "PREFERRED"
                continue
            elif any(k in ll for k in ["responsibilities", "what you'll do", "role overview", "duties", "what does a"]):
                current_section = "RESPONSIBILITIES"
                continue
            elif any(k in ll for k in ["certifications", "licenses"]):
                current_section = "CERTIFICATIONS"
                continue

            if current_section == "REQUIRED":
                required_text_lines.append(line)
            elif current_section == "PREFERRED":
                preferred_text_lines.append(line)
            elif current_section == "RESPONSIBILITIES":
                if line.startswith(("-", "*", "•")):
                    responsibilities.append(line.lstrip("-*• ").strip())
                elif len(line.strip()) > 15:
                    responsibilities.append(line.strip())
            elif current_section == "CERTIFICATIONS":
                if line.startswith(("-", "*", "•")):
                    certifications.append(line.lstrip("-*• ").strip())

        archetype = self._infer_archetype(detected_title, cleaned)

        min_exp = 0
        pref_exp = None
        exp_patterns = [
            r"(\d+)\+?\s*(?:to|-)\s*(\d+)?\s*years?",
            r"(?:minimum|at least)\s*(\d+)\+?\s*years?",
            r"(\d+)\+?\s*years?(?:\s+of\s+[\w\s]{0,40})?\s*experience",
            r"(\d+)\+?\s*years?",
        ]
        for pattern in exp_patterns:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                try:
                    min_exp = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    pass

        if min_exp == 0:
            if archetype:
                min_exp = archetype.get("default_exp", 2)
            else:
                min_exp = 2

        req_text = "\n".join(required_text_lines)
        pref_text = "\n".join(preferred_text_lines)

        edu_source = req_text if req_text else cleaned
        education_level = "Unspecified"
        if re.search(r"\b(bachelor'?s|b\.s\.|b\.tech|b\.e\.|undergraduate)\b", edu_source, re.IGNORECASE):
            education_level = "Bachelor's Degree"
        elif re.search(r"\b(master'?s|m\.s\.|m\.tech|mba|graduate)\b", edu_source, re.IGNORECASE):
            education_level = "Master's Degree"
        elif re.search(r"\b(ph\.?d|doctorate)\b", edu_source, re.IGNORECASE):
            education_level = "PhD"
        elif re.search(r"\b(degree)\b", edu_source, re.IGNORECASE):
            education_level = "Bachelor's Degree"
        elif re.search(r"\b(bachelor'?s|b\.s\.|b\.tech|b\.e\.|degree)\b", cleaned, re.IGNORECASE):
            education_level = "Bachelor's Degree"
        elif re.search(r"\b(master'?s|m\.s\.|m\.tech|mba)\b", cleaned, re.IGNORECASE):
            education_level = "Master's Degree"
        elif re.search(r"\b(ph\.?d|doctorate)\b", cleaned, re.IGNORECASE):
            education_level = "PhD"

        if education_level == "Unspecified" and archetype:
            education_level = archetype.get("education", "Bachelor's Degree or Equivalent")
        elif education_level == "Unspecified":
            education_level = "Bachelor's Degree or Equivalent"

        req_skills_objs = self.normalizer.extract_and_normalize_skills(req_text if req_text else cleaned)
        pref_skills_objs = self.normalizer.extract_and_normalize_skills(pref_text) if pref_text else []

        required_skills = [s.normalized_skill_name for s in req_skills_objs]
        preferred_skills = [s.normalized_skill_name for s in pref_skills_objs]

        if len(required_skills) < 4:
            bullet_reqs = self._extract_bullet_phrases(required_text_lines if required_text_lines else lines)
            for b in bullet_reqs:
                if b not in required_skills and len(required_skills) < 8:
                    required_skills.append(b)

        if len(required_skills) < 4 and archetype:
            for s in archetype.get("core_skills", []):
                if s not in required_skills:
                    required_skills.append(s)
            for t in archetype.get("tools", []):
                if t not in preferred_skills and t not in required_skills:
                    preferred_skills.append(t)

        for s in required_skills:
            if s in preferred_skills:
                preferred_skills.remove(s)

        domain = archetype.get("domain", "general") if archetype else "general"

        return StructuredJobDescription(
            title=detected_title,
            domain=domain,
            responsibilities=responsibilities,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            min_experience_years=min_exp,
            preferred_experience_years=pref_exp,
            education_level=education_level,
            certifications=certifications,
            raw_text=cleaned,
        )


BaselineJDParser = EnhancedJDParser
