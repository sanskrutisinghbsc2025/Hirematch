
from typing import Any, Dict, List, Optional
import uuid

from core.evaluation.criteria_validator import CriteriaValidator
from core.model_lab.models import (
    EvaluationDataset,
    EvaluationDatasetItem,
    RelevanceGrade,
    TaskType,
)
from core.storage.benchmark_repository import EvaluationDatasetRepository
from core.storage.database import Database
from core.utils.logger import logger


class EvaluationDatasetService:

    def __init__(self, db: Database):
        self.db = db
        self.repo = EvaluationDatasetRepository(db)
        self.validator = CriteriaValidator()
        self.ensure_synthetic_benchmark_dataset()

    def create_dataset(
        self,
        name: str,
        version: str = "v1.0",
        task: TaskType = TaskType.SEMANTIC_RETRIEVAL,
        description: str = "",
        rubric_version: str = "rubric-v1.0",
        created_by: str = "Authorized Reviewer",
        items: Optional[List[EvaluationDatasetItem]] = None,
    ) -> EvaluationDataset:
        dataset = EvaluationDataset(
            id=str(uuid.uuid4()),
            name=name,
            version=version,
            task=task,
            description=description,
            rubric_version=rubric_version,
            created_by=created_by,
            is_frozen=False,
            items=items or [],
        )
        return self.repo.create_dataset(dataset)

    def get_dataset(self, dataset_id: str, load_items: bool = True) -> Optional[EvaluationDataset]:
        return self.repo.get_dataset(dataset_id, load_items=load_items)

    def list_datasets(self, task: Optional[TaskType] = None) -> List[EvaluationDataset]:
        return self.repo.list_datasets(task=task)

    def add_item_to_dataset(
        self,
        dataset_id: str,
        query_text: str,
        passage_text: str,
        relevance_grade: RelevanceGrade,
        category: str = "GENERAL",
        reviewer_notes: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvaluationDatasetItem:
        is_valid, reasons = self.validator.validate_criterion(query_text)
        if not is_valid:
            raise ValueError(f"Rubric Violation: Query '{query_text}' is prohibited: {'; '.join(reasons)}")

        item = EvaluationDatasetItem(
            id=str(uuid.uuid4()),
            dataset_id=dataset_id,
            query_text=query_text.strip(),
            passage_text=passage_text.strip(),
            relevance_grade=relevance_grade,
            category=category,
            reviewer_notes=reviewer_notes,
            metadata=metadata or {},
        )
        self.repo.add_items([item])
        return item

    def freeze_dataset(self, dataset_id: str) -> None:
        self.repo.freeze_dataset(dataset_id)

    def is_frozen(self, dataset_id: str) -> bool:
        return self.repo.is_frozen(dataset_id)

    def ensure_synthetic_benchmark_dataset(self) -> EvaluationDataset:
        synthetic_id = "synthetic-benchmark-v1"
        existing = self.repo.get_dataset(synthetic_id, load_items=False)
        if existing:
            return existing

        dataset = EvaluationDataset(
            id=synthetic_id,
            name="Synthetic Criteria & Experience Benchmark",
            version="v1.0",
            task=TaskType.SEMANTIC_RETRIEVAL,
            description=(
                "Curated benchmark test set covering direct synonyms, acronyms, conceptual paraphrases, "
                "non-equivalent distractors, contextual negations, and irrelevant candidate text."
            ),
            rubric_version="job-evidence-rubric-v1.0",
            created_by="HireMatch Evaluation Suite",
            is_frozen=True,
            items=[],
        )

        test_cases = [
            ("PostgreSQL database administration and query tuning", "Extensive experience designing and optimizing Postgres relational schemas.", RelevanceGrade.HIGHLY_RELEVANT, "SYNONYM", "Postgres is standard canonical alias for PostgreSQL."),
            ("Kubernetes container orchestration and Helm charts", "Deployed and managed microservice clusters across multi-region K8s infrastructure.", RelevanceGrade.HIGHLY_RELEVANT, "SYNONYM", "K8s is standard abbreviation for Kubernetes."),
            ("Amazon Web Services cloud architecture", "Migrated legacy on-premise monolith to AWS serverless architecture with Lambda and S3.", RelevanceGrade.HIGHLY_RELEVANT, "SYNONYM", "AWS is acronym for Amazon Web Services."),
            ("TypeScript application development", "Designed typed enterprise web client libraries using TS and React.", RelevanceGrade.HIGHLY_RELEVANT, "SYNONYM", "TS is abbreviation for TypeScript."),
            ("Docker containerization and image builds", "Containerized microservice fleet using multi-stage Dockerfiles.", RelevanceGrade.HIGHLY_RELEVANT, "SYNONYM", "Direct containerization tooling match."),

            ("High-throughput asynchronous messaging and distributed event streaming", "Architected Kafka pub/sub pipelines processing 50M event payloads per second with zero data loss.", RelevanceGrade.HIGHLY_RELEVANT, "PARAPHRASE", "Kafka pub/sub fulfills asynchronous messaging requirements conceptually."),
            ("Automated CI/CD deployment pipelines", "Engineered automated GitHub Actions workflows for linting, test suites, and Docker container delivery.", RelevanceGrade.HIGHLY_RELEVANT, "PARAPHRASE", "GitHub Actions workflows constitute a CI/CD pipeline."),
            ("Infrastructure as Code and cloud provisioning", "Automated multi-account AWS resource provisioning using declarative Terraform modules.", RelevanceGrade.HIGHLY_RELEVANT, "PARAPHRASE", "Terraform represents Infrastructure as Code conceptually."),
            ("Microservice architecture and distributed API gateways", "Designed decoupled independent service endpoints coordinated by an Envoy reverse proxy.", RelevanceGrade.HIGHLY_RELEVANT, "PARAPHRASE", "Decoupled services with reverse proxy represent microservice API gateway architecture."),
            ("Distributed in-memory caching and session management", "Reduced database latency by 80% through an clustered Redis caching layer.", RelevanceGrade.HIGHLY_RELEVANT, "PARAPHRASE", "Redis caching fulfills in-memory caching requirement."),

            ("Python backend web framework experience", "Built automation scripts and web scrapers in Python, with basic exposure to Flask endpoints.", RelevanceGrade.RELEVANT, "PARTIAL", "Partial backend framework exposure."),
            ("Relational database design and SQL optimization", "Wrote standard SQL SELECT and JOIN queries for monthly business analytics reporting.", RelevanceGrade.RELEVANT, "PARTIAL", "Basic SQL usage without advanced schema design or query tuning."),
            ("Machine learning model deployment", "Assisted senior data scientist with data labeling and training pipeline documentation in Jupyter.", RelevanceGrade.RELEVANT, "PARTIAL", "Adjacent data science participation without primary deployment ownership."),

            ("Java enterprise backend application development with Spring Boot", "Built interactive responsive user interfaces and web animations using JavaScript, React, and CSS.", RelevanceGrade.NOT_RELEVANT, "DISTRACTOR", "JavaScript frontend is not Java enterprise backend."),
            ("C++ low-level systems programming and memory management", "Developed web scrapers and automation utility scripts utilizing Python.", RelevanceGrade.NOT_RELEVANT, "DISTRACTOR", "Python scripting is not C++ low-level systems programming."),
            ("Apache Spark large-scale big data batch processing", "Configured and maintained Apache HTTP web server reverse proxy on Ubuntu Linux.", RelevanceGrade.NOT_RELEVANT, "DISTRACTOR", "Apache HTTP web server is not Apache Spark big data processing."),
            ("Deep learning neural networks with PyTorch", "Proficient in basic statistical regression modeling in Excel spreadsheets.", RelevanceGrade.NOT_RELEVANT, "DISTRACTOR", "Spreadsheet regression is not deep neural networks."),

            ("React single-page web application development", "Familiar with Angular and Vue, but no commercial experience with React or Next.js.", RelevanceGrade.NOT_RELEVANT, "NEGATION", "Candidate explicitly negates React commercial experience."),
            ("Kubernetes production cluster administration", "Have not managed Kubernetes clusters in production; worked only with standalone Docker compose.", RelevanceGrade.NOT_RELEVANT, "NEGATION", "Candidate explicitly states lack of production Kubernetes experience."),
            ("Go (Golang) microservice systems programming", "Keen interest in learning Go, but currently zero professional experience with the language.", RelevanceGrade.NOT_RELEVANT, "NEGATION", "Personal learning interest without experience."),
            ("GraphQL API schema design and resolver implementation", "Evaluated GraphQL but chose REST APIs instead; no experience building GraphQL schemas.", RelevanceGrade.NOT_RELEVANT, "NEGATION", "Explicit statement of not building GraphQL schemas."),

            ("Distributed backend systems engineering with Python and AWS", "Cashier and customer service associate responsible for handling cash register and restocking shelves.", RelevanceGrade.NOT_RELEVANT, "IRRELEVANT", "Retail cashier responsibilities have zero relevance to backend engineering."),
            ("Cloud security architecture and compliance auditing", "Managed high-volume kitchen prep and inventory rotation at commercial restaurant.", RelevanceGrade.NOT_RELEVANT, "IRRELEVANT", "Commercial kitchen prep has zero relevance to cloud security."),
            ("Frontend UI performance optimization", "Barista preparing espresso drinks and greeting morning café patrons.", RelevanceGrade.NOT_RELEVANT, "IRRELEVANT", "Food service duties have zero relevance to web performance optimization."),
        ]

        items = []
        for q, p, grade, cat, note in test_cases:
            items.append(
                EvaluationDatasetItem(
                    id=str(uuid.uuid4()),
                    dataset_id=synthetic_id,
                    query_text=q,
                    passage_text=p,
                    relevance_grade=grade,
                    category=cat,
                    reviewer_notes=note,
                )
            )

        dataset.items = items
        dataset.item_count = len(items)
        return self.repo.create_dataset(dataset)
