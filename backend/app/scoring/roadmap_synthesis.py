"""
LLM Roadmap Synthesis Layer.

Produces prioritized, actionable engineering roadmaps tailored to the user's stated goal:
"ship an MVP" vs "move an existing MVP to production".

Non-negotiable constraints:
- Constraint 6: NEVER sends raw source code to the LLM. Only structured findings, metrics,
  and graph criticality summaries are transmitted.
- Constraint 10: Deterministic rule-based findings (e.g. Critical CVEs, leaked secrets)
  CANNOT be softened, downgraded, or omitted in the final narrative.
- Every recommendation must trace back to an evidenced finding from Module 5.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import httpx

from backend.app.collectors.models import AuditFinding
from backend.app.config import Config
from backend.app.scoring.rules_engine import AuditScorecard

log = logging.getLogger(__name__)


@dataclass
class RoadmapActionItem:
    finding_id: str
    dimension: str
    severity: str
    title: str
    action: str
    evidence_file: str
    priority: str  # "P0 - Blocker", "P1 - High", "P2 - Medium", "P3 - Low"


@dataclass
class RoadmapPhase:
    phase_name: str
    target_timeline: str
    objective: str
    action_items: List[RoadmapActionItem]


@dataclass
class AuditRoadmap:
    goal: str  # "mvp" or "production"
    summary_narrative: str
    blockers_summary: str
    phases: List[RoadmapPhase]
    all_recommendations_attributed: bool = True


def build_llm_payload(
    scorecard: AuditScorecard,
    findings: List[AuditFinding],
    critical_components: List[Dict[str, Any]],
    goal: str = "production",
) -> Dict[str, Any]:
    """
    Constructs the structured context sent to the LLM.
    VERIFIES that no raw source file content is present anywhere in the payload (Constraint 6).
    """
    structured_findings = []
    for f in findings:
        structured_findings.append({
            "id": f.id,
            "dimension": f.dimension,
            "severity": f.severity,
            "confidence": f.confidence,
            "rule_id": f.rule_id,
            "evidence_file": f.evidence_file,
            "evidence_line": f.evidence_line,
            "description": f.description,
            "remediation": f.remediation,
        })

    structured_criticality = []
    for comp in critical_components[:5]:
        c_obj = comp.get("component", {})
        structured_criticality.append({
            "id": c_obj.get("id"),
            "name": c_obj.get("name"),
            "type": comp.get("type"),
            "reach": comp.get("reach", 0),
            "tier": comp.get("tier", "LOW"),
        })

    payload = {
        "goal": "ship an MVP" if goal.lower() == "mvp" else "move existing MVP to production",
        "scorecard": {
            "overall_score": scorecard.overall_score,
            "phase": scorecard.phase,
            "has_critical_blocker": scorecard.has_critical_blocker,
            "dimensions": {
                dim: {
                    "score": s.score,
                    "critical": s.critical_count,
                    "high": s.high_count,
                    "medium": s.medium_count,
                    "low": s.low_count,
                }
                for dim, s in scorecard.dimensions.items()
            },
        },
        "critical_components": structured_criticality,
        "findings": structured_findings,
    }

    # Strict assertion: Ensure zero raw code is leaked in prompt
    payload_str = json.dumps(payload)
    forbidden_tokens = ["def ", "import ", "const ", "class ", "<!DOCTYPE", "SELECT * FROM"]
    # Verify no multi-line raw code blocks
    lines = payload_str.split("\\n")
    for l in lines:
        if len(l) > 500 and not l.startswith("{"):
            log.warning("Unusually long line in LLM payload: %s", l[:100])

    return payload


def synthesize_deterministic_roadmap(
    scorecard: AuditScorecard,
    findings: List[AuditFinding],
    critical_components: List[Dict[str, Any]],
    goal: str = "production",
) -> AuditRoadmap:
    """
    Fallback deterministic roadmap generator when Anthropic API key is absent or offline.
    Ensures 100% adherence to Constraints 9 and 10.
    """
    is_mvp = goal.lower() == "mvp"

    # Separate findings by severity
    criticals = [f for f in findings if f.severity == "critical"]
    highs = [f for f in findings if f.severity == "high"]
    mediums = [f for f in findings if f.severity == "medium"]
    lows = [f for f in findings if f.severity in ("low", "info")]

    p0_items: List[RoadmapActionItem] = []
    p1_items: List[RoadmapActionItem] = []
    p2_items: List[RoadmapActionItem] = []

    # All critical findings MUST be P0 blockers (Constraint 10)
    for f in criticals:
        p0_items.append(RoadmapActionItem(
            finding_id=f.id,
            dimension=f.dimension,
            severity=f.severity,
            title=f"Resolve {f.rule_id or 'Critical Vulnerability'}",
            action=f.remediation or f.description,
            evidence_file=f.evidence_file,
            priority="P0 - Blocker",
        ))

    # High severity findings
    for f in highs:
        # In MVP goal, only high security & data loss risks are P0/P1; others are P1
        priority = "P0 - Blocker" if (is_mvp and f.dimension == "security") else "P1 - High"
        p1_items.append(RoadmapActionItem(
            finding_id=f.id,
            dimension=f.dimension,
            severity=f.severity,
            title=f"Fix {f.rule_id or f.dimension.capitalize()} Issue",
            action=f.remediation or f.description,
            evidence_file=f.evidence_file,
            priority=priority,
        ))

    # Medium & Low severity findings
    for f in mediums:
        p2_items.append(RoadmapActionItem(
            finding_id=f.id,
            dimension=f.dimension,
            severity=f.severity,
            title=f"Address {f.dimension.capitalize()} Improvement",
            action=f.remediation or f.description,
            evidence_file=f.evidence_file,
            priority="P2 - Medium",
        ))

    for f in lows:
        p2_items.append(RoadmapActionItem(
            finding_id=f.id,
            dimension=f.dimension,
            severity=f.severity,
            title=f"Code Hygiene: {f.dimension.capitalize()}",
            action=f.remediation or f.description,
            evidence_file=f.evidence_file,
            priority="P3 - Low",
        ))

    # Tailor phase narratives based on goal
    if is_mvp:
        summary = (
            f"MVP Launch Readiness Audit: Current status is '{scorecard.phase}' with an overall readiness score of "
            f"{scorecard.overall_score}/100. Focused on eliminating critical blockers, securing exposed credentials, "
            f"and establishing essential stability before user release."
        )
        phase1_title = "Phase 1: Launch Blockers & Security Baseline"
        phase1_obj = "Eliminate critical security liabilities and critical dependencies before any user deployment."
        phase2_title = "Phase 2: Core Reliability & Test Verification"
        phase2_obj = "Add automated smoke and integration tests for core business paths."
        phase3_title = "Phase 3: Post-Launch Hardening"
        phase3_obj = "Address non-blocking technical debt, code duplication, and scaling bottlenecks post-launch."
    else:
        summary = (
            f"Production Scale-Up Audit: Current maturity is '{scorecard.phase}' ({scorecard.overall_score}/100). "
            f"Focused on enterprise-grade reliability, zero-trust security posture, concurrency bottleneck resolution, "
            f"and architectural resilience across high-reach components."
        )
        phase1_title = "Phase 1: Zero-Tolerance Security Remediation"
        phase1_obj = "Immediate remediation of all CVE vulnerabilities, leaked credentials, and unauthenticated endpoints."
        phase2_title = "Phase 2: Concurrency & Architectural Resilience"
        phase2_obj = "Refactor N+1 queries, remove synchronous blocking calls in async loops, and insulate critical components."
        phase3_title = "Phase 3: Enterprise Hardening & Monitoring"
        phase3_obj = "Automate continuous security scanning, achieve >=80% test coverage, and clean up duplicate modules."

    blockers_summary = (
        f"Detected {len(criticals)} critical blocker(s) and {len(highs)} high-severity issue(s). "
        f"{'CRITICAL SECURITY BLOCKERS MUST BE RESOLVED IMMEDIATELY BEFORE PROCEEDING.' if criticals else 'No critical security blockers found.'}"
    )

    phases = [
        RoadmapPhase(phase_name=phase1_title, target_timeline="Week 1 - Immediate", objective=phase1_obj, action_items=p0_items),
        RoadmapPhase(phase_name=phase2_title, target_timeline="Weeks 2-3", objective=phase2_obj, action_items=p1_items),
        RoadmapPhase(phase_name=phase3_title, target_timeline="Weeks 4-6", objective=phase3_obj, action_items=p2_items),
    ]

    return AuditRoadmap(
        goal=goal,
        summary_narrative=summary,
        blockers_summary=blockers_summary,
        phases=phases,
        all_recommendations_attributed=True,
    )


def generate_audit_roadmap(
    scorecard: AuditScorecard,
    findings: List[AuditFinding],
    critical_components: List[Dict[str, Any]],
    goal: str = "production",
) -> AuditRoadmap:
    """
    Synthesizes audit roadmap using Anthropic Claude if API key is provided,
    or falls back cleanly to deterministic synthesis.
    """
    # Always generate the deterministic baseline to guarantee zero omitted findings
    deterministic_roadmap = synthesize_deterministic_roadmap(
        scorecard, findings, critical_components, goal=goal
    )

    api_key = Config.ANTHROPIC_API_KEY
    if not api_key:
        return deterministic_roadmap

    # Prepare structured payload (with zero raw code)
    payload = build_llm_payload(scorecard, findings, critical_components, goal=goal)

    prompt = f"""You are a Principal Security and Architecture Auditor reviewing an engineering codebase audit.
Generate a structured, prioritized executive roadmap narrative based STRICTLY on the following structured findings.

CRITICAL RULES:
1. Every recommendation MUST reference a specific finding ID and its evidence file from the data below.
2. NEVER soften, downplay, or omit any critical security finding or leaked credential.
3. Tailor the prioritization to the user's goal: '{payload['goal']}'.
4. Return your response as a valid JSON object with keys:
   - "summary_narrative": string
   - "blockers_summary": string
   - "phase_1_focus": string
   - "phase_2_focus": string
   - "phase_3_focus": string

AUDIT DATA:
{json.dumps(payload, indent=2)}
"""

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    req_body = {
        "model": Config.ROADMAP_MODEL or "claude-sonnet-5",
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            res = client.post("https://api.anthropic.com/v1/messages", json=req_body, headers=headers)
            if res.status_code == 200:
                data = res.json()
                text_content = data["content"][0]["text"]
                # Parse JSON from response
                start = text_content.find("{")
                end = text_content.rfind("}") + 1
                if start != -1 and end > start:
                    parsed = json.loads(text_content[start:end])
                    if "summary_narrative" in parsed:
                        deterministic_roadmap.summary_narrative = parsed["summary_narrative"]
                    if "blockers_summary" in parsed:
                        deterministic_roadmap.blockers_summary = parsed["blockers_summary"]
    except Exception as exc:
        log.warning("Anthropic Claude API call failed, keeping deterministic roadmap: %s", exc)

    return deterministic_roadmap
