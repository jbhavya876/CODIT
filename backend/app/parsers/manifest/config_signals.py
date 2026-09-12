"""
Detects frameworks, databases, message queues, and infrastructure signals.

Analyzes docker-compose.yml, Dockerfiles, .env.example, GitHub Actions workflows,
and declared dependencies.
Every emitted signal is strictly tagged with the specific file that evidenced it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from backend.app.ingestion.models import FileEntry
from backend.app.parsers.models import DependencyEntry, TechStackSignal

# Known image / database patterns in docker-compose & Dockerfile
DATABASE_IMAGE_PATTERNS = [
    (r"postgres(?:ql)?(?::.*)?", "PostgreSQL", "database"),
    (r"redis(?::.*)?", "Redis", "cache"),
    (r"mongo(?:db)?(?::.*)?", "MongoDB", "database"),
    (r"mysql(?::.*)?", "MySQL", "database"),
    (r"mariadb(?::.*)?", "MariaDB", "database"),
    (r"kafka(?::.*)?", "Apache Kafka", "message_queue"),
    (r"rabbitmq(?::.*)?", "RabbitMQ", "message_queue"),
    (r"elasticsearch(?::.*)?", "Elasticsearch", "search"),
    (r"opensearch(?::.*)?", "OpenSearch", "search"),
    (r"neo4j(?::.*)?", "Neo4j", "database"),
    (r"clickhouse(?::.*)?", "ClickHouse", "database"),
    (r"cassandra(?::.*)?", "Cassandra", "database"),
]

FRAMEWORK_DEPENDENCY_MAP = {
    # Python
    "fastapi": ("FastAPI", "framework"),
    "flask": ("Flask", "framework"),
    "django": ("Django", "framework"),
    "sqlalchemy": ("SQLAlchemy ORM", "database"),
    "tortoise-orm": ("Tortoise ORM", "database"),
    "celery": ("Celery", "task_queue"),
    "pydantic": ("Pydantic", "library"),
    "neo4j": ("Neo4j Driver", "database"),
    # JavaScript / TypeScript
    "react": ("React", "framework"),
    "next": ("Next.js", "framework"),
    "express": ("Express", "framework"),
    "vue": ("Vue.js", "framework"),
    "svelte": ("Svelte", "framework"),
    "@nestjs/core": ("NestJS", "framework"),
    "tailwindcss": ("Tailwind CSS", "framework"),
    "prisma": ("Prisma ORM", "database"),
    "mongoose": ("Mongoose", "database"),
    "typeorm": ("TypeORM", "database"),
    "ioredis": ("ioredis", "cache"),
}

ENV_VAR_PATTERNS = [
    (r"(?:DATABASE_URL|POSTGRES_|PG_)", "PostgreSQL / SQL Database", "database"),
    (r"(?:REDIS_URL|REDIS_HOST)", "Redis Cache", "cache"),
    (r"(?:MONGODB_URI|MONGO_URL)", "MongoDB", "database"),
    (r"(?:AWS_ACCESS_KEY|AWS_SECRET)", "Amazon Web Services (AWS)", "infra"),
    (r"(?:STRIPE_SECRET|STRIPE_KEY)", "Stripe Payments API", "api"),
    (r"(?:OPENAI_API_KEY)", "OpenAI API", "api"),
    (r"(?:ANTHROPIC_API_KEY)", "Anthropic Claude API", "api"),
    (r"(?:COGNODB_URI|COGNODB_PASSWORD)", "CognoDB Graph Database", "database"),
]


def detect_config_signals(
    files: List[FileEntry],
    dependencies: List[DependencyEntry],
) -> List[TechStackSignal]:
    """
    Scans repository files and dependencies for concrete tech-stack evidence.
    Guarantees that every returned TechStackSignal includes the exact evidencing file.
    """
    signals: List[TechStackSignal] = []
    seen_signals = set()

    def add_signal(category: str, name: str, evidence_file: str, confidence: str = "high", detail: str = ""):
        sig_key = (category, name, evidence_file)
        if sig_key not in seen_signals:
            seen_signals.add(sig_key)
            signals.append(TechStackSignal(
                category=category,
                name=name,
                evidence_file=evidence_file,
                confidence=confidence,
                detail=detail,
            ))

    # 1. Scan declared dependencies for framework and library signals
    for dep in dependencies:
        dep_lower = dep.name.lower()
        if dep_lower in FRAMEWORK_DEPENDENCY_MAP:
            name, cat = FRAMEWORK_DEPENDENCY_MAP[dep_lower]
            add_signal(
                category=cat,
                name=name,
                evidence_file=dep.evidence_file,
                confidence="high",
                detail=f"Declared dependency: {dep.name}=={dep.raw_version}",
            )

    # 2. Scan repository files
    for entry in files:
        p_lower = entry.path.lower()
        filename = Path(entry.path).name.lower()

        # docker-compose
        if "docker-compose" in p_lower and (p_lower.endswith(".yml") or p_lower.endswith(".yaml")):
            for line in entry.content.splitlines():
                line_clean = line.strip()
                if line_clean.startswith("image:"):
                    img = line_clean.split("image:", 1)[1].strip()
                    for pattern, tech_name, cat in DATABASE_IMAGE_PATTERNS:
                        if re.search(pattern, img, re.IGNORECASE):
                            add_signal(
                                category=cat,
                                name=tech_name,
                                evidence_file=entry.path,
                                confidence="high",
                                detail=f"docker-compose service image: {img}",
                            )

        # Dockerfile
        if filename.startswith("dockerfile") or p_lower.endswith(".dockerfile"):
            for line in entry.content.splitlines():
                line_clean = line.strip()
                if line_clean.startswith("FROM "):
                    base_img = line_clean.split("FROM ", 1)[1].strip()
                    add_signal(
                        category="infra",
                        name=f"Docker Container ({base_img})",
                        evidence_file=entry.path,
                        confidence="high",
                        detail=line_clean,
                    )
                elif line_clean.startswith("EXPOSE "):
                    port = line_clean.split("EXPOSE ", 1)[1].strip()
                    add_signal(
                        category="infra",
                        name=f"Exposed Port ({port})",
                        evidence_file=entry.path,
                        confidence="medium",
                        detail=line_clean,
                    )

        # .env.example / .env
        if filename.startswith(".env"):
            for line in entry.content.splitlines():
                line_clean = line.strip()
                if not line_clean or line_clean.startswith("#"):
                    continue
                var_name = line_clean.split("=")[0].strip()
                for pattern, tech_name, cat in ENV_VAR_PATTERNS:
                    if re.search(pattern, var_name, re.IGNORECASE):
                        add_signal(
                            category=cat,
                            name=tech_name,
                            evidence_file=entry.path,
                            confidence="high",
                            detail=f"Environment variable: {var_name}",
                        )

        # GitHub Workflows CI
        if ".github/workflows" in p_lower and (p_lower.endswith(".yml") or p_lower.endswith(".yaml")):
            add_signal(
                category="ci",
                name="GitHub Actions CI/CD",
                evidence_file=entry.path,
                confidence="high",
                detail=f"Workflow definition: {Path(entry.path).name}",
            )
            if "pytest" in entry.content:
                add_signal(
                    category="ci",
                    name="Pytest Automation",
                    evidence_file=entry.path,
                    confidence="high",
                    detail="CI runs pytest",
                )
            if "npm test" in entry.content or "npm run test" in entry.content:
                add_signal(
                    category="ci",
                    name="NPM Test Automation",
                    evidence_file=entry.path,
                    confidence="high",
                    detail="CI runs npm test",
                )

    return signals
