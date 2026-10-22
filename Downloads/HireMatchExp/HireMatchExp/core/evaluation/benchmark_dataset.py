
from dataclasses import dataclass
from typing import List


@dataclass
class BenchmarkPair:

    id: str
    category: str
    query: str
    passage: str
    expected_match: bool
    description: str


BENCHMARK_CASES: List[BenchmarkPair] = [
    BenchmarkPair(
        id="syn-1",
        category="SYNONYM",
        query="PostgreSQL database administration and query tuning",
        passage="Extensive experience designing and optimizing Postgres relational schemas.",
        expected_match=True,
        description="Postgres is a canonical alias for PostgreSQL.",
    ),
    BenchmarkPair(
        id="syn-2",
        category="SYNONYM",
        query="Kubernetes container orchestration and Helm charts",
        passage="Deployed and managed microservice clusters across multi-region K8s infrastructure.",
        expected_match=True,
        description="K8s is standard abbreviation for Kubernetes.",
    ),
    BenchmarkPair(
        id="syn-3",
        category="SYNONYM",
        query="Amazon Web Services cloud architecture",
        passage="Migrated legacy on-premise monolith to AWS serverless architecture with Lambda and S3.",
        expected_match=True,
        description="AWS is acronym for Amazon Web Services.",
    ),

    BenchmarkPair(
        id="concept-1",
        category="PARAPHRASE",
        query="High-throughput asynchronous messaging and distributed event streaming",
        passage="Architected Kafka pub/sub pipelines processing 50M event payloads per second with zero data loss.",
        expected_match=True,
        description="Kafka pub/sub fulfills asynchronous messaging requirements conceptually.",
    ),
    BenchmarkPair(
        id="concept-2",
        category="PARAPHRASE",
        query="Automated CI/CD deployment pipelines",
        passage="Engineered automated GitHub Actions workflows for linting, test suites, and Docker container delivery.",
        expected_match=True,
        description="GitHub Actions with automated delivery constitutes a CI/CD pipeline.",
    ),

    BenchmarkPair(
        id="distract-1",
        category="DISTRACTOR",
        query="Java enterprise backend application development with Spring Boot",
        passage="Built interactive responsive user interfaces and web animations using JavaScript, React, and CSS.",
        expected_match=False,
        description="JavaScript frontend is not Java enterprise backend.",
    ),
    BenchmarkPair(
        id="distract-2",
        category="DISTRACTOR",
        query="C++ low-level systems programming and memory management",
        passage="Developed web scrapers and automation utility scripts utilizing Python.",
        expected_match=False,
        description="Python scripting is not C++ low-level systems programming.",
    ),

    BenchmarkPair(
        id="neg-1",
        category="NEGATION",
        query="React single-page web application development",
        passage="Familiar with Angular and Vue, but no commercial experience with React or Next.js.",
        expected_match=False,
        description="Candidate explicitly states lack of React experience.",
    ),

    BenchmarkPair(
        id="irrel-1",
        category="IRRELEVANT",
        query="Machine learning deep neural networks and PyTorch",
        passage="Cashier and customer service associate responsible for handling cash register and restocking shelves.",
        expected_match=False,
        description="Retail cashier responsibilities have zero relevance to machine learning.",
    ),
]
