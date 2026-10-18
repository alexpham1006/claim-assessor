# Claim Assessment Report

## Recommendation
**REQUEST_MORE_INFO**

- Missing discharge_summary [`REQUIRED-DOCUMENTS-001`]
- Clinical review required: No procedure is specified and the synthetic data does not provide sufficient clinical criteria to make a definitive medical-necessity assessment. [`COVERAGE-001`]

## Document Review
- `DOC-021` medical_report: **complete**
- `DOC-022` hospital_bill: **complete**
- discharge_summary: **missing**

## Policy Verification
- Policy `POLICY-003`: active
- Member covered: True
- Within coverage period: True
- Claim type included: True

## Medical Necessity
- **needs_review**: No procedure is specified and the synthetic data does not provide sufficient clinical criteria to make a definitive medical-necessity assessment.

## Benefit Calculation
- Submitted: 28000000
- Covered: 28000000
- Coinsurance: 2800000.00
- Member responsibility: 2800000.00
- Remaining limit: 60000000 -> 34800000.00

## Reasoning
- The hospitalization claim lacks the discharge_summary required by policy clause REQUIRED-DOCUMENTS-001.
- A clinical review is required under policy clause COVERAGE-001 because no procedure is specified and the synthetic data does not provide sufficient clinical criteria to make a definitive medical-necessity assessment.

## Policy Citations
- `COVERAGE-001`
- `REQUIRED-DOCUMENTS-001`
