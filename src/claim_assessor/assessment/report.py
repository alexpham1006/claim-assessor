from claim_assessor.assessment.models import (
    AssessmentReport,
    Decision,
    Evidence,
    PolicyVerification,
    ReportDraft,
)


def build_report(evidence: Evidence, decision: Decision, draft: ReportDraft) -> AssessmentReport:
    claim, policy = evidence.claim, evidence.policy
    return AssessmentReport(
        document_review=evidence.documents,
        missing_documents=evidence.missing_documents,
        policy_verification=PolicyVerification(
            policy_id=policy.policy_id,
            status=policy.status,
            member_covered=policy.covers_member(claim.member_id),
            within_coverage_period=policy.covers_date(claim.treatment_date),
            claim_type_included=policy.covers_claim_type(claim.claim_type),
        ),
        medical_necessity=evidence.medical,
        benefit_calculation=evidence.benefit,
        recommendation=decision.recommendation,
        findings=decision.findings,
        reasoning=draft.reasoning,
        policy_citations=sorted(draft.policy_citations),
    )


def render_markdown(report: AssessmentReport) -> str:
    policy = report.policy_verification
    benefit = report.benefit_calculation
    documents = [
        f"- `{doc.document_id}` {doc.document_type}: **{doc.status}**"
        + (f" ({'; '.join(doc.issues)})" if doc.issues else "")
        for doc in report.document_review
    ] + [f"- {kind}: **missing**" for kind in report.missing_documents]
    findings = [
        f"- {finding.message} [`{finding.clause_id or 'no policy clause'}`]"
        for finding in report.findings
    ]
    sections = [
        "# Claim Assessment Report",
        f"## Recommendation\n**{report.recommendation}**\n\n" + "\n".join(findings),
        "## Document Review\n" + "\n".join(documents),
        "## Policy Verification\n"
        f"- Policy `{policy.policy_id}`: {policy.status}\n"
        f"- Member covered: {policy.member_covered}\n"
        f"- Within coverage period: {policy.within_coverage_period}\n"
        f"- Claim type included: {policy.claim_type_included}",
        "## Medical Necessity\n"
        f"- **{report.medical_necessity.status}**: {report.medical_necessity.reason}",
        "## Benefit Calculation\n"
        f"- Submitted: {benefit.submitted_amount}\n"
        f"- Covered: {benefit.covered_amount}\n"
        f"- Coinsurance: {benefit.coinsurance_amount}\n"
        f"- Member responsibility: {benefit.member_responsibility}\n"
        f"- Remaining limit: {benefit.remaining_limit_before} -> "
        f"{benefit.remaining_limit_after_claim}",
        "## Reasoning\n" + "\n".join(f"- {line}" for line in report.reasoning),
        "## Policy Citations\n" + "\n".join(f"- `{clause}`" for clause in report.policy_citations),
    ]
    return "\n\n".join(sections) + "\n"


def validate_draft(evidence: Evidence, decision: Decision, draft: ReportDraft) -> list[str]:
    known = {clause.clause_id for clause in evidence.policy.clauses}
    cited = set(draft.policy_citations)
    errors: list[str] = []
    if unknown := sorted(cited - known):
        errors.append(f"Cited clauses do not exist in the policy: {unknown}")
    if missing := sorted(decision.required_citations - cited):
        errors.append(f"Required clauses are not cited: {missing}")
    return errors
