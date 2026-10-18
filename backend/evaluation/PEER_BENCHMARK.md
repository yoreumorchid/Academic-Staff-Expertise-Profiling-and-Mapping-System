# UC-16 Peer Benchmark Validation

## Scope

The committed development set is synthetic and contains no real staff or peer-university
records. Its programme hierarchy was informed by public official Computer Science
curriculum pages from Stanford and Oxford, but its wording was independently written for
this project. The external pages are references, not downloaded evaluation fixtures.

The representative test matrix covers:

| Case | Representation | Expected handling |
|---|---|---|
| Normal curriculum | Generated text PDF | Preserve headings and relevant content |
| Word curriculum with a table | Generated DOCX | Preserve table rows as reviewable text |
| Long multi-year programme | Generated text PDF / synthetic text | Token-bounded chunks retain the final section |
| Administration-heavy document | Synthetic repeated page furniture and control sections | Remove repeated furniture and exclude obvious administration by default |
| Extraction-poor scan | Generated blank image-style PDF | Reject with the OCR-not-supported message |

Generated PDF/DOCX files exist only during tests. No copyrighted curriculum document is
committed. Public structural references:

- Stanford CS Bachelor's Program: https://www.cs.stanford.edu/academics-overview/academics-bachelors-program
- Oxford Computer Science course structure: https://www.ox.ac.uk/admissions/undergraduate/courses/course-listing/computer-science

## Method

Each retained peer chunk is embedded once in a batch. Its raw coverage distance is
`1 - cosine_similarity(peer chunk, nearest staff profile)`. The nearest staff member is
shown to preserve niche expertise; the nearest internal cluster and its distance remain
visible as an institutional summary. Every chunk is equally weighted.

Run the provisional calibration from `backend/`:

```powershell
python -m evaluation.scripts.eval_peer_benchmark
```

The generated JSON and Markdown reports record the model, formula, selected boundaries,
per-example distances, predictions, macro F1, and synthetic provenance. These boundaries
are an initial development baseline only. Repeat the procedure with faculty-labelled real
examples before reporting UC-16 accuracy or treating a classification as confirmed.

## UAT record still required

For the supervisor/faculty UAT, record decisions on the result display and confirm that:

- all retained segments remain sortable instead of using a fixed top-N;
- compulsory/elective status, credits, recurrence, accreditation importance, and single
  mentions remain equally weighted until reliable metadata and a stakeholder rule exist;
- wording remains **candidate coverage gap — pending administrator review**;
- the supplied institutional UC-14 syllabus may be used only with its provenance and the
  owner's permission recorded in the local UAT notes.
