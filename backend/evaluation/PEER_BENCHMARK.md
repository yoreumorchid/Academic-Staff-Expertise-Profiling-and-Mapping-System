# UC-16 Peer Curriculum Overview Validation

## Current scope

UC-16 is a descriptive, auditable overview of uploaded curriculum material. It
does not embed Peer sections, retrieve a closest staff member or capability
cluster, classify coverage, or claim a staffing/curriculum gap.

The previous synthetic semantic-distance experiment is superseded. Its files
remain in the repository only as an audit trail and must not be cited as
validation of the current overview or reused as a threshold for future Peer
alignment.

## Representative extraction matrix

The focused tests should cover:

| Case | Representation | Expected handling |
|---|---|---|
| Normal curriculum | Generated text PDF | Preserve academic headings and exact content |
| Word curriculum with a table | Generated DOCX | Preserve table rows as reviewable text |
| Long programme | Synthetic text | Retain the final academic section within configured limits |
| Administration-heavy document | Synthetic text | Exclude dates, examination logistics, marks, and bare references |
| Client reselects excluded content | API selection | Reject the excluded section server-side |
| Extraction-poor scan | Generated image-style PDF | Reject with the OCR-not-supported message |

Generated files exist only during tests. No copyrighted curriculum document is
committed.

## Validation still required

Faculty or supervisor UAT should label representative extracted sections as
academic/relevant or administrative/noise, review false inclusions and false
exclusions, and confirm any additional faculty-specific rules. A single syllabus
may describe that module but must not be presented as representative of an
entire peer institution.

If the supervisor later approves a Peer Curriculum Alignment feature, define a
new evaluation protocol around administrator-confirmed course/module units and
real faculty labels. Do not reactivate the old chunk-to-nearest-staff thresholds.
The outstanding product and research questions are listed in
`SUPERVISOR_MEETING_TALKING_POINTS.md`.
