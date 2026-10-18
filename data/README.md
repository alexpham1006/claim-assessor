# Reference data

The JSON files remain strict JSON so the application can validate them at
startup. Field notes live here instead of inline `//` comments, which would
make the runtime files invalid JSON.

## `policies.json`

- `policies`: all policy records.
- `policy_id`: stable policy identifier, for example `POLICY-001`.
- `policyholder.member_id`: member covered by the policy.
- `policyholder.name`: display name of the fictional member.
- `status`: whether the policy is active.
- `coverage_period`: start and end dates for coverage.
- `claim_requirements`: required document types keyed by claim type.
- `benefits`: coverage rules keyed by claim type.
- `benefits.*.covered`: whether that claim type is covered.
- `benefits.*.annual_limit`: annual benefit limit.
- `benefits.*.remaining_limit_before_claim`: available limit before this claim.
- `benefits.*.per_claim_limit`: maximum payable amount for one claim.
- `benefits.*.coinsurance_rate`: member share as a decimal, for example `0.1`.
- `waiting_period`: waiting-period configuration.
- `exclusions`: procedures or conditions excluded by the policy.
- `clauses`: policy clauses available for report citations.

## `documents.json`

- `documents`: all document records.
- `document_id`: stable document identifier, for example `DOC-001`.
- `document_type`: document category, such as `medical_report`.
- `status`: document completeness status.
- `issues`: problems found during document verification.
- `extracted_data`: fields extracted from the document content.

## `medical_rules.json`

- `version`: version of the synthetic rule set.
- `description`: scope and limitations of the rule set.
- `rules`: diagnosis and procedure matching rules.
- `rules.*.rule_id`: stable rule identifier.
- `rules.*.diagnosis`: human-readable diagnosis.
- `rules.*.diagnosis_code`: diagnosis code used for lookup.
- `rules.*.procedures`: human-readable procedure names.
- `rules.*.procedure_codes`: procedure codes checked against a claim.
- `rules.*.result`: `supported` or `needs_review`.
- `rules.*.reason`: explanation returned in the assessment.
- `fallback`: result used when no exact rule matches.

## Identifier convention

```text
CLAIM-001
POLICY-001
MEMBER-001
DOC-001
```
