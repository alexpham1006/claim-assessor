from claim_assessor.assessment.models import (
    ClauseType,
    Decision,
    DocumentStatus,
    Evidence,
    Finding,
    MedicalStatus,
    Recommendation,
)


def decide(evidence: Evidence) -> Decision:
    if findings := policy_findings(evidence):
        return Decision(recommendation=Recommendation.REJECT, findings=findings)
    if findings := document_findings(evidence) + medical_findings(evidence):
        return Decision(recommendation=Recommendation.REQUEST_MORE_INFO, findings=findings)
    return Decision(recommendation=Recommendation.APPROVE, findings=approval_findings(evidence))


def policy_findings(evidence: Evidence) -> list[Finding]:
    claim, policy = evidence.claim, evidence.policy
    benefit = policy.benefits.get(claim.claim_type)
    coverage = policy.clause_id(ClauseType.COVERAGE)
    exclusion = policy.clause_id(ClauseType.EXCLUSION)

    findings: list[Finding] = []
    if policy.status.lower() != "active":
        findings.append(Finding(coverage, f"Policy is {policy.status}"))
    if not policy.covers_date(claim.treatment_date):
        findings.append(Finding(coverage, "Treatment is outside coverage period"))
    if not policy.covers_member(claim.member_id):
        findings.append(Finding(coverage, "Member is not on the policy"))
    if not policy.waiting_period.satisfied:
        findings.append(Finding(coverage, "Waiting period is not satisfied"))
    findings.extend(
        Finding(exclusion, f"Excluded: {item.description}")
        for item in policy.exclusions
        if set(claim.procedures) & set(item.applies_to)
    )
    if benefit is None:
        findings.append(Finding(coverage, f"Claim type {claim.claim_type} is not included"))
    elif not benefit.covered:
        findings.append(Finding(exclusion, "This claim type is not covered by the policy"))
    return findings


def document_findings(evidence: Evidence) -> list[Finding]:
    required = evidence.required_documents
    if not required:
        return []
    clause = evidence.policy.clause_id(ClauseType.REQUIRED_DOCUMENTS)

    findings: list[Finding] = []
    for document in evidence.documents:
        if document.status is not DocumentStatus.COMPLETE:
            findings.append(
                Finding(
                    clause,
                    f"{document.document_id} is {document.status}: {'; '.join(document.issues)}",
                )
            )
        if document.document_type not in required:
            findings.append(
                Finding(
                    clause,
                    f"{document.document_id} has type {document.document_type}; "
                    f"expected one of {required}",
                )
            )
    findings.extend(Finding(clause, f"Missing {kind}") for kind in evidence.missing_documents)
    return findings


def medical_findings(evidence: Evidence) -> list[Finding]:
    if evidence.medical.status is MedicalStatus.SUPPORTED:
        return []
    coverage = evidence.policy.clause_id(ClauseType.COVERAGE)
    return [Finding(coverage, f"Clinical review required: {evidence.medical.reason}")]


def approval_findings(evidence: Evidence) -> list[Finding]:
    policy, benefit, currency = evidence.policy, evidence.benefit, evidence.claim.currency
    coverage = policy.clause_id(ClauseType.COVERAGE)
    return [
        Finding(coverage, "Policy active for the treatment date"),
        Finding(coverage, "Member is covered"),
        Finding(coverage, "Treatment is medically necessary"),
        Finding(
            policy.clause_id(ClauseType.BENEFIT_LIMIT),
            f"Covered {benefit.covered_amount} {currency}, "
            f"remaining limit {benefit.remaining_limit_after_claim} {currency}",
        ),
        Finding(
            policy.clause_id(ClauseType.COINSURANCE),
            f"Member responsibility {benefit.member_responsibility} {currency}",
        ),
    ]
