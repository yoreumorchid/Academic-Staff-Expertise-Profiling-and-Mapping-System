## Part 0 — Opening (30 seconds)

**[Show terminal starting backend + frontend, then switch to browser]**

"So this is the demo video of my system, Expertise Insight. Let me show you the complete workflow, starting from account registration all the way through expertise tags extraction, then staff profiles consulting and portfolio export."

---

## Part 1 — Registration & Approval (2 minutes)

### 1.1 Landing Page → Register

**[Navigate to http://localhost:5173 — shows login page]**

"This is the login page. Every user must authenticate with a UM email. If you don't have an account yet, you click 'Create account'."

**[Click "Create account"]**

"The registration form supports two roles. If you register as Academic Staff, you must provide your department and ORCID identifier. If you register as a Faculty Administrator, you select a portfolio — Faculty Manager, Head of Department, Deputy Dean Research, or Deputy Dean Undergraduate/Postgraduate."

**[Walk through the form — fill in first name, last name, email, password. Select "Academic Staff", type a department, paste an ORCID. Click submit.]**

"After submitting, the account goes into a pending state. A Faculty Manager must review and approve it before you can log in. There will be a new user record in the database with the PENDING account status.
### 1.2 Admin: Approve Registration

**[Log in as the admin account]**

"Now let me switch to an administrator account that was already approved. I log in with my admin credentials."

**[After login, the admin sees the Dashboard page. Navigate sidebar to "Pending Registrations"]**

"As a Faculty Manager, I see a dedicated admin sidebar. I click 'Pending Registrations' — this is the authorization queue. Every new registration appears here. I can see the applicant's name, email, role, department, ORCID, and portfolio details."

**[Click "Approve" on the test academic staff account]**

"I approve the registration. This triggers an email notification to the user but now it's under development by using email service. The status of the new account become Active. And the user can now log in."

### 1.3 Forgot Password / Reset Password (Optional — mention briefly)

**[If time, quickly show the "Forgot password?" link and explain]**

"The auth flow also includes forgot-password and reset-password. Enter your UM email, receive a reset link, set a new password. That's UC-4."

---

## Part 2 — Dual-Role View Toggle (1 minute)

**[Still logged in as admin, point to the header]**

"At the top of the page you can see a Staff View / Admin View toggle. This is dual-role header. Users who hold both an academic-staff identity and an administrative portfolio can switch between two perspectives without logging out and back in."

**[Click "Staff View"]**

"In Staff View, the sidebar shows academic modules: Profile Overview, Expertise Tag Refinement, Academic Background, Publications & Abstracts, and Export Portfolio Snapshot."

**[Click "Admin View"]**

"In Admin View, you can see the Dashboard, pending registrations, gap analytics, benchmarking, course mapping, research grant mapping, and staff profiles. The same user, one session but with two complete portals."

---

## Part 3 — Academic Staff: Profile & Sync (3 minutes)

### 3.1 Staff Profile Overview

**[Log in as the academic staff user. Navigate to "Profile Overview".]**

"Now let me log in as an academic staff member. The landing page is 'Profile Overview'. On the right, there's a 'Run manual sync' button. Clicking it triggers the full NLP pipeline."

### 3.2 Run Manual Sync (UC-8 + UC-12)

**[Click "Run manual sync" — show the warning toast, wait for sync to complete.]**

"And now we'll wait for manual synchronization to complete. When I click this button, the backend does four things in sequence. First, it resolves ORCID to an OpenAlex author ID. Second, it fetches all publications under this author from OpenAlex. Third, for each new publication it extracts the abstract and runs it through SciBERT to extract candidate keyphrases. Fourth, it sends those keyphrases to an LLM for normalization into general expertise tags."

"The sync is synchronous — the button stays disabled, and the browser warns me not to close the tab while it runs. When it completes, the statistics cards update with the number of expertise tags, validated tags, and publications."

### 3.3 Profile Dashboard

**[Scroll through the profile page after sync.]**

"Below the stats, you can see AI-generated expertise tags — each one with a confidence score and a validated checkbox. I can click through to refine them. Below that, recent publications with venue, year, and DOI. At the bottom, a table of recent sync jobs showing the trigger type, status, publications added, and tags added."

(Open VS Code)

I evaluated my NLP tag-extraction pipeline against 27 hand-curated gold papers. For each paper, I started with the author's own keywords and an initial AI suggestion used as academic expert's perspective, then manually reviewed the abstract to produce a final set of fine-grained and clear tags — like "healthcare interoperability" instead of just "health." I ran two pipelines through these 27 papers: a raw SciBERT keyword extractor and a SciBERT-plus-LLM refinement pipeline. I measured both hard exact-match F1 and a soft semantic F1 using SciBERT cosine similarity at threshold 0.7. The LLM-refined pipeline hit a soft F1 of 0.61. That number is acceptable because my gold tags are intentionally more granular and specific than generic keyword labels — they're built for downstream researcher-to-researcher mapping, where capturing the semantic neighbourhood matters more than exact string overlap.

---

## Part 4 — Tag Refinement (1.5 minutes)

**[Navigate to "Expertise Tag Refinement" in the sidebar.]**

"This is expertise tag refinement. The AI-generated tags are listed with their domain, confidence percentage, and source. I have three actions per tag. I can validate it — meaning I confirm this tag accurately represents  expertise. A green checkmark appears. Or I can mark it for removal — it dims out."

**[Check some validate and remove checkboxes.]**

"Below, I can add custom labels that the AI didn't catch — for example, 'Graph Neural Networks'. I type and press Enter. At the bottom, a live preview shows how many tags will remain after I save.

**[Click "Save changes".]**

"Changes are saved via a single API call. The backend upserts refined tags and creates user-tag links. Embeddings are regenerated for new labels so mapping and benchmarking stay consistent."

---

## Part 5 — Publications & Abstract Supplement (1.5 minutes)

**[Navigate to "Publications & Abstracts".]**

"The table shows every publication harvested from OpenAlex. Some abstracts are marked 'Missing' — this happens when OpenAlex doesn't have the full text for a paper, or the paper is behind a paywall."

**[Click "Supplement" on a row with Missing abstract.]**

"A modal opens. I can either paste the abstract text directly — minimum 200 characters — or upload a PDF or DOCX file. The backend extracts the text locally, stores it, and re-runs the NLP pipeline on that paper alone."

**[If you have a PDF, demonstrate the upload path. Otherwise describe it.]**

"After submission, the paper's abstract status changes to 'OK' and the SciBERT + LLM pipeline re-extracts and normalizes tags from the new abstract. No manual re-sync needed."

---

## Part 6 — Global Staff Search (1 minute)

**[Switch to Admin View. In the header search bar, type a name or department.]**

"This is global search. It's available to administrators in the top header bar. I type a name — or a department — and the backend queries both fields in parallel. Results appear in a dropdown with the staff member's full name, department, email, and their top expertise tags."

**[Click a result.]**

"Clicking a result takes me to that staff member's full profile in the Staff Profiles page."
And you can also do detailed search using the filter here.

---

## Part 7 — Course & Grant Mapping (2 minutes)

**[Navigate to "Course Mapping" in the admin sidebar.]**

"Now the mapping module. This is where an administrator matches a course syllabus or a research grant call to the most qualified academic staff."

### 7.1 Ingest a Specification

**[Fill in the specification ingest form.]**

"I give the specification a title — for example, 'Advanced Machine Learning' — and paste the course description text. The backend ingests this, extracts key concepts, and computes a semantic embedding using the same SciBERT model we used for publications."

**[Click "Ingest text". Show the ingested specification in the list below.]**

"Alternatively, I can upload a PDF or DOCX document — useful for real course syllabi or grant calls."

### 7.2 Run Semantic Match

**[Click "Run match" on the ingested specification.]**

"The result table shows rank, staff name, department, and relevant metrics as evidence.

---
And for the benchmarking module, it's still under development.

---

## Part 9 — Portfolio Snapshot Export (1 minute)

**[Switch to Staff View. Navigate to "Export Portfolio Snapshot".]**

"Then comes to the portfolio snapshot export. A staff member can select which expertise tags, publications, and academic background entries to include, choose PDF or DOCX format, and generate a formatted portfolio document."

**[Walk through the export UI — select some items, choose format, click export.]**

"The output is a clean, publication-ready document suitable for grant applications, or annual reviews."

---

## Part 10 — Closing (30 seconds)

**[Return to the dashboard or profile overview.]**


"The entire stack is production-grade — I use ORCID of staff from our faculty as test case. Thank you for watching."
