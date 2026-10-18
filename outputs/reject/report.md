# Claim Assessment Report

## Recommendation
**REJECT**

- Excluded: Elective procedures performed solely for cosmetic or aesthetic purposes are excluded from coverage. [`EXCLUSION-COSMETIC-001`]
- This claim type is not covered by the policy [`EXCLUSION-COSMETIC-001`]

## Document Review
- `DOC-011` medical_report: **complete**
- `DOC-012` hospital_bill: **complete**
- `DOC-013` discharge_summary: **complete**

## Policy Verification
- Policy `POLICY-002`: active
- Member covered: True
- Within coverage period: True
- Claim type included: False

## Medical Necessity
- **needs_review**: The code and procedure labels alone do not establish medical necessity; review the documentation for functional, reconstructive, or other therapeutic indication. In this test case, coverage rejection is based on the policy exclusion, not this rule.

## Benefit Calculation
- Submitted: 65000000
- Covered: 0
- Coinsurance: 0
- Member responsibility: 65000000
- Remaining limit: 0 -> 0

## Reasoning
- Elective procedures performed solely for cosmetic or aesthetic purposes are excluded from coverage according to clause EXCLUSION-COSMETIC-001.
- This claim type is not covered by the policy under clause EXCLUSION-COSMETIC-001.

## Policy Citations
- `EXCLUSION-COSMETIC-001`
