## 4.3 Use Case Description

### **UC-1 register account**

| Description | The system shall allow new users to create a system account by providing personal details, choosing an institutional role, and entering specific identifiers (ORCID or Portfolio). |
| :---- | :---- |
| **Actor(s)** | ACADEMIC STAFF, FACULTY ADMINISTRATOR |
| **Triggering Event** | Actor clicks the “Sign Up” button on the login interface.  |
| **Pre-condition** | Actor does not have an existing active account in the system.  Actor possesses a valid institutional email address.  |
| **Post-condition** | The account is created with a "Pending" status. Actor is restricted from accessing functional modules until administrative approval is granted. |
| **Flow of Events** | Actor accesses the registration interface Actor enters full name and institutional email address. Actor selects their role: Academic Staff or Faculty Administrator. If Academic Staff is selected: Actor must provide their unique 16-digit ORCID ID and department affiliation If Faculty Administrator is selected: Actor must select their specific Portfolio Role from Faculty Manager, Head of Department (HoD), Deputy Dean (Research) or Deputy Dean (Undergraduate/Postgraduate). Actor may optionally provide their 16-digit ORCID ID and department affiliation to enable dual-role profiling. Actor sets a secure password and submits the registration form. System validates the input data (e.g., ORCID format and email uniqueness). System creates the account in a Pending status and notifies Actor to await approval.  |
| **Alternative Flow \- Dynamic Role Input**  | **@Step 3** System interface dynamically updates to show either the ORCID/Department fields or the Portfolio selection dropdown based on the role chosen.  |
| **Alternative Flow \- Dual-Role Registration** | **@Step 5.2** If Actor provides an ORCID ID while registering as an administrator, System shall flag the account as a "Dual-Role" user for automated data harvesting and profile generation.  |
| **Exception Flow \- Email Already Exists** | **@Step 7** If the institutional email is already registered, System prompts Actor to log in. |

### **UC-2 authorize registration**

| Description | The system allows the Faculty Manager (HR) administrator to review pending registration requests and either approve them to activate the account or reject them to remove the request from the system.  |
| :---- | :---- |
| **Actor(s)** | FACULTY MANAGER |
| **Triggering Event** | Actor accesses the "Pending Requests" section within the administrative dashboard.  |
| **Pre-condition** | A new user has successfully submitted a registration form. The user account is currently in a Pending status. Actor is logged in with Faculty Manager (HR) portfolio privileges. |
| **Post-condition** | The account status is updated to Active (if approved) or deleted from the system (if rejected). A system notification email is sent to the registrant informing them of the outcome. |
| **Flow of Events** | Actor accesses the User Management dashboard. System retrieves and displays a list of all registration requests currently in Pending status. Actor selects a specific pending request to review the registrant’s details (Name, Email, Role, and ORCID/Portfolio). Actor chooses to Approve the registration. System updates the account status to “Active” in the database. System triggers UC-5 to send an approval notification email to the user. |
| **Alternative Flow \- Rejection of Registration** | **@Step 4** Actor chooses to Reject the registration request: System deletes the pending registration record from the database. System triggers UC-5 to send a rejection notification email to the user. |

### **UC-3 login**

| Description | The system allows activated users to securely access the platform using their registered institutional email and password, subsequently redirecting them to their designated role-based dashboards or management portals. |
| :---- | :---- |
| **Actor(s)** | ACADEMIC STAFF, FACULTY ADMINISTRATOR |
| **Triggering Event** | Actor clicks the “Login” button on the authentication interface.  |
| **Pre-condition** | Actor has a registered account in the system. Actor’s account status has been set to “Active” by a Faculty Manager (HR) administrator. |
| **Post-condition** | Actor is successfully authenticated and a secure session is established. Actor is redirected to their authorized functional module based on their role and portfolio. |
| **Flow of Events** | Actor enters their institutional email and password. Actor click the “Login” button. System validates the credentials against the database records. System identifies the user’s role (Academic Staff or Faculty Administrator) and assigned portfolio. System grants access and redirect Actor to the appropriate interface. |
| **Alternative Flow \- Initial Data Sync** | **@Step 5** If Actor is an Academic Staff member logging in for the first time since account activation, System shall automatically trigger the automated data harvesting module using Actor’s ORCID ID. |
| **Alternative Flow \- Dual-Role First-Time Sync** | **@Step 5** If Actor is a Faculty Administrator logging in for the first time with an optional ORCID provided, System shall trigger the automated data harvesting module.  |
| **Exception Flow \- Invalid Credentials** | **@Step 3** If the email or password does not match the database records, System shall display an “Invalid email or password” error message and prevent authentication. |
| **Exception Flow \- Unauthorized Access (Pending Status)** | **@Step 3** If the account status is still Pending. System shall deny access and inform Actor that the account is awaiting administrative approval. |

### **UC-4 reset password**

| Description | The system allows users to recover access to their account by requesting a password reset link via their registered institutional email address.  |
| :---- | :---- |
| **Actor(s)** | ACADEMIC STAFF, FACULTY ADMINISTRATOR |
| **Triggering Event** | Actor clicks the “Forgot Password” link on the login interface.  |
| **Pre-condition** | Actor has an existing registered account in the system. Actor has access to their institutional email account.  |
| **Post-condition** | Actor’s password is successfully updated in the database.  Actor can log in using the new credentials.  |
| **Flow of Events** | Actor clicks the “Forgot Password” button. Actor enters their registered institutional email address.  System verifies that the email address exists in the database.  System generates a unique, time-sensitive reset token.  System triggers UC-5 to send a password reset email containing the secure link to Actor. Actor clicks the link provided in the email.  Actor enters a new password and confirms it. System validates that both password entries match.  System updates the encrypted password in the database. System displays a success message and redirects Actor to the login page.  |
| **Alternative Flow \- Direct Reset from Profile Management** | **@Step 1** If Actor is already logged in and wishes to change their password: Actor accesses the “Account Settings” in the profile.  Actor enters current password and new password. System validates the current password and updates the record.  |
| **Exception Flow \- Email Not Found** | **@Step 3** If the entered email address is not found in the database, System shall display an error message stating "Email address not recognized" and prevents the reset process. |
| **Exception Flow \- Password Mismatch** | **@Step 8** If the new password and confirmation password do not match, System shall prompt Actor to re-enter the passwords to ensure consistency.  |
| **Exception Flow \- Expired Token** | **@Step 6** If Actor clicks the link after the time limit has expired, System shall inform Actor that the link is no longer valid and prompts them to request a new one.  |

### **UC-5 send notification email**

| Description | The system provides an automated communication service to inform users of critical account activities, including registration outcomes and password reset requests.  |
| :---- | :---- |
| **Actor(s)** | None |
| **Triggering Event** | A system event occurs that requires user notification (e.g., UC-2 account approval/rejection or UC-4 password reset request).  |
| **Pre-condition** | A system trigger has been activated by a related functional module.   The target user has a valid institutional email address stored in the database.  |
| **Post-condition** | An automated email is successfully dispatched to the user's institutional inbox.  |
| **Flow of Events** | System identifies a trigger event from a related module (e.g., account activation or password reset).  System retrieves the corresponding email template based on the event type.   System fetches the recipient's institutional email address and full name from the database.   System populates the email template with specific dynamic data (e.g., approval status or a secure reset link).   System dispatches the notification email via the system mail server. |
| **Alternative Flow- Registration Outcome Notification**  | **@Step 1** If triggered by UC-2, System shall generate a notification specifying whether the registration was "Approved" or "Rejected". |
| **Alternative Flow \- Password Recovery Notification**  | **@Step 1** If triggered by UC-4, System shall generate a notification containing a unique, time-sensitive token link for secure password updates**.** |
| **Exception Flow \- Email Delivery Failure** | **@Step 5** If the mail server returns a delivery error, System shall log the failure and schedule a retry attempt after a predefined interval.  |

### **UC-6 access role-based dashboard**

| Description | The system provides a customized user interface based on Actor’s portfolio. The interface consists of a persistent sidebar for module switching and a central dashboard providing a strategic overview of authorized modules.  |
| :---- | :---- |
| **Actor(s)** | FACULTY ADMINISTRATOR |
| **Triggering Event** | Actor successfully authenticates via the secure login interface. |
| **Pre-condition** | Actor is logged into the system.  Actor has a valid role and portfolio assigned in the database. |
| **Post-condition** | Actor is granted access to the specific functional modules defined by their portfolio.  Unauthorized modules are restricted from Actor's view.  |
| **Flow of Events** | Actor completes the authentication process.  System retrieves Actor's role, portfolio, and dual-role status from the database.  System renders the global layout: System populates sidebar links for authorized modules (e.g., Gap Analytics, Course Mapping). System displays a global search bar and a switch view toggle for dual-role users on header.  System directs Actor to the Dashboard Overview, displaying high-level analytical summaries relevant to the portfolio. |
| **Alternative Flow \- Dual-Role View Switching** | **@Step 4** If Actor  is in Admin View and selects "Switch to Staff View," System renders the Expertise Management Portal for personal profile management. |
| **Alternative Flow \- Return to Admin View**  | **@Step 4** If Actor is in Staff View and selects "Switch to Admin View," System shall redirect the user back to the Strategic Dashboard based on their portfolio.  |
| **Exception Flow \- Unauthorized Module Request** | **@Step 4** If Actor attempts to manually access a URL for a module outside their portfolio, System shall redirect Actor back to their designated dashboard and display a permission error.  |

### **UC-7 consult staff profiles**

| Description | The system allows administrators to identify academic staff via two pathways: a Global Header Search for quick queries and a Dedicated Staff Profiles Page for comprehensive directory browsing and multi-category filtering.  |
| :---- | :---- |
| **Actor(s)** | FACULTY ADMINISTRATOR |
| **Triggering Event** | Actor clicks the "Staff Profiles" link in the sidebar or the search bar in the global header.  |
| **Pre-condition** | Actor is logged into the system.  Academic staff profiles have been processed and stored in the Expertise Knowledge Database.  |
| **Post-condition** | Actor successfully views the comprehensive expertise profile and distilled research tags of the selected academic staff member.  |
| **Flow of Events** | Actor clicks the Staff Profiles link in the navigation sidebar.  System navigates to a dedicated page displaying the faculty-wide staff directory; department is a search filter rather than an authorization boundary so cross-department expertise remains discoverable. Actor applies advanced filters to narrow results by Normalized Expertise Tags or department. System applies the authorized scope and filters in SQL and displays a deterministic, paginated set of matching academic staff cards with the total result count. Actor moves between result pages or selects a specific staff member. System retrieves and renders the full expertise profile, including AI-generated tags and publication history restored from OpenAlex.   |
| **Alternative Flow \- Global Header Search** | **@Step 1** If Actor clicks the integrated search bar in the global header from any page: Actor selects a search category such as Name, Expertise, Publication, or Department from the dropdown. Actor enters keywords and System displays a real-time list of matching staff cards.  Actor selects a specific profile from the results.  System proceeds to Step 6 of the Main Flow to render the full profile.  |
| **Exception Flow \- No Search Term Provided** | **@Step 4** If Actor initiates a search without entering any keyword in the input field, System shall prompt Actor to provide a search term before executing the query.  |
| **Exception Flow \- Zero Matches Found**  | **@Step 5** If no academic staff profiles match Actor's search terms or filter selection:  System shall display a "No matching profiles found" message.   System shall prompt Actor to modify the search criteria or clear the filters.  |

### **UC-8 generate expertise profiles**

| Description | The system automatically harvests publication metadata from external sources and applies a hybrid NLP and LLM pipeline to distill raw text into normalized expertise tags.  |
| :---- | :---- |
| **Actor(s)** | EXTERNAL ACADEMIC DATABASES |
| **Triggering Event** | System detects the first successful login of an approved academic staff member or initiates a scheduled quarterly synchronization.  |
| **Pre-condition** | Academic staff member has a verified 16-digit ORCID ID stored in the system.  Secure connection to ORCID and OpenAlex REST APIs is established.   |
| **Post-condition** | AI-generated normalized expertise tags are successfully stored in the centralized Expertise Knowledge Database.  |
| **Flow of Events** | System initiates a data harvesting request to Actor (ORCID API) using the staff member's ORCID ID. System retrieves the list of Digital Object Identifiers (DOIs) from Actor to establish publication history.  System utilizes the harvested DOIs to request and retrieve publication abstracts from the OpenAlex database.  System deploys the SciBERT NLP model to perform keyword extraction from the retrieved abstract texts.  System processes extracted keywords through a Large Language Model (LLM) for semantic refinement and data normalization.  System maps fragmented technical jargon to broader, standardized expertise domains to resolve terminology gaps.  System stores the final normalized expertise tags in the structured database.  |
| **Alternative Flow** | No alternative flow for this use case. |
| **Exception Flow \- Abstract Retrieval Failure**  | **@Step 3** If OpenAlex does not contain the abstract text for a specific DOI, System flags the entry and triggers UC-9 to allow the staff member to manually supplement the data. |
| **Exception Flow \- API Connection Timeout**  | **@Step 2** If the external academic database fails to respond, System logs the error and schedules a retry attempt after a predefined interval.  |

### **UC-9 supplement abstract**

| Description | The system allows academic staff members to manually provide publication abstracts when the automated harvesting process fails to retrieve them from external databases, ensuring that the NLP pipeline can generate a complete expertise profile.  |
| :---- | :---- |
| **Actor(s)** | ACADEMIC STAFF |
| **Triggering Event** | Actor identifies a publication record with a "Missing Abstract" status in their profile portal. |
| **Pre-condition** | Actor is logged into the Expertise Management Portal.  The automated harvesting process has identified one or more publications without accessible abstracts in OpenAlex.  |
| **Post-condition** | The expertise profile is updated with new normalized tags derived from the manually supplemented abstract. |
| **Flow of Events** | Actor navigates to the publication management section of the Expertise Management Portal.  System displays harvested publication records and flags entries missing abstract metadata.  Actor selects a flagged publication to open the supplement interface.  Actor pastes the abstract text into the provided input field.  Actor submits the entry for processing. System validates the input and stores the abstract in the Expertise Knowledge Database.  System triggers the NLP and LLM pipeline to generate new expertise tags from the provided text.  |
| **Alternative Flow \- Document Upload** | **@Step 4** Actor chooses to upload a PDF or Word document of the publication instead of pasting text:  System utilizes an extraction module to retrieve text from the uploaded file.  System proceeds to Step 6 of the Main Flow.  |
| **Exception Flow \- Insufficient Text Length**  | **@Step 6** If the provided text is too short for meaningful NLP extraction, System shall prompt Actor to provide a more comprehensive abstract to ensure profiling accuracy.  |
| **Exception Flow \- Invalid Format**  | **@Step 6** If the uploaded document is corrupted or in an unsupported format, System shall display an error message and request a valid file or manual text entry.  |

### **UC-10 input academic background**

| Description | The system allows academic staff members to manually input and manage their professional history, including administrative roles, awards, and educational qualifications that are not captured through automated metadata harvesting.  |
| :---- | :---- |
| **Actor(s)** | ACADEMIC STAFF |
| **Triggering Event** | Actor navigates to the "Academic Background" section within the Expertise Management Portal.  |
| **Pre-condition** | Actor is logged into the Expertise Management Portal with an active account.  Actor with dual-role is in the "Staff View" interface.  |
| **Post-condition** | The validated academic and administrative records are successfully stored in the Expertise Knowledge Database and integrated into the user's profile.  |
| **Flow of Events** | Actor accesses the Expertise Management Portal.  Actor selects the specific category for input, such as Administrative Roles, Awards, or Education.  System displays the relevant input forms for the selected category.  Actor enters the required details, including titles, dates, and descriptions of their professional achievements.  Actor clicks the "Save" or "Update" button.  System validates the input data for completeness and correct formatting.  System stores the encrypted records in the Expertise Knowledge Database.  System updates Actor’s expertise profile to reflect the newly added background information.  |
| **Alternative Flow \- Editing Existing Records**  | **@Step 3** If Actor chooses to modify an existing record:  System retrieves the existing data and populates the form.  Actor modifies the necessary fields. System proceeds to Step 5 of the Main Flow.  |
| **Exception Flow\- Missing Mandatory Fields**  | **@Step 6** If mandatory information, such as the start date of an administrative role or the title of an award, is missing:  System highlights the empty fields. System prevents submission and prompts Actor to complete the required data.  |
| **Exception Flow \- Date Validation Error**  | **@Step 6** If Actor enters an end date that precedes the start date:  System identifies the chronological inconsistency.  System displays an error message and requests a correction before saving.  |

### **UC-11 refine expertise tags**

| Description | The system provides an interactive interface for academic staff members to review, validate, and adjust the expertise tags generated by the AI pipeline to ensure the profile accurately reflects their actual research specialization.  |
| :---- | :---- |
| **Actor(s)** | ACADEMIC STAFF |
| **Triggering Event** | Actor navigates to the expertise profile section of the Expertise Management Portal.  |
| **Pre-condition** | Actor is logged into the Expertise Management Portal.  The automated profiling module (UC-8) has successfully generated a baseline set of expertise tags based on publication metadata.  |
| **Post-condition** | The validated and refined expertise tags are updated in the Expertise Knowledge Database and are made available for institutional mapping and analytics.  |
| **Flow of Events** | Actor navigates to the Expertise Profile section.  System retrieves and displays the current set of AI-generated normalized expertise tags from the database.  Actor reviews each tag for semantic accuracy and relevance.  Actor selects unnecessary or incorrect tags for removal from the profile.  Actor confirms the validation of the accurate tags.  Actor clicks the Update Profile button to finalize the refinement.  System saves the refined and validated tag set into the Expertise Knowledge Database.  |
| **Alternative Flow \- Adding Custom Tags**  | **@Step 4** If Actor identifies missing expertise domains that the AI pipeline failed to extract from the available abstracts:   Actor enters a new expertise keyword into the manual input field. System performs a real-time normalization check to suggest existing standardized technical tags.  Actor selects the appropriate tag to add to the profile.  System proceeds to Step 6 of the Main Flow.  |
| **Exception Flow \- Minimum Tag Requirement**  | **@Step 6** If Actor attempts to save a profile with zero expertise tags:  System identifies that the profile contains no expertise data points. System displays a warning message stating that a profile requires at least one tag for institutional visibility.  System prevents the update and prompts Actor to select or add at least one relevant expertise domain.  |

### **UC-12 trigger expertise sync**

| Description | The system allows academic staff and faculty administrators to manually initiate a synchronization process that harvests the latest publication metadata from external databases to update expertise profiles  |
| :---- | :---- |
| **Actor(s)** | ACADEMIC STAFF, FACULTY ADMINISTRATOR |
| **Triggering Event** | Actor clicks the manual update trigger or synchronization button within their respective management portal or dashboard.  |
| **Pre-condition** | Actor is successfully logged into the ExpertiseInsight system.  Target academic staff profiles have valid ORCID IDs associated with their accounts.  |
| **Post-condition** | The Expertise Knowledge Database is updated with the most recent publication records and AI-generated expertise tags.  |
| **Flow of Events** | Actor accesses the synchronization interface. Actor selects the option to manually trigger an expertise data update.  System identifies the target profile(s) for synchronization based on Actor’s selection or portfolio permissions.  System initiates a connection to the ORCID and OpenAlex APIs to check for new publication metadata.  System triggers the automated profiling pipeline (UC-8) to harvest DOIs and reconstruct abstracts.  System processes new data through the NLP and LLM modules to generate refined expertise tags.  System updates the Expertise Knowledge Database and notifies Actor of the successful synchronization.  |
| **Alternative Flow \- Automated Quarterly Sync**  | **@Step 1** System automatically triggers the synchronization process every three months without manual intervention to ensure institutional data remains current.  |
| **Exception Flow \- No New Data Identified**  | **@Step 4** If the external databases indicate that no new publications have been added since the last synchronization:  System terminates the harvesting process.  System informs Actor that the expertise profile is already up to date.  |
| **Exception Flow \- API Connection Failure**  | **@Step 4** If the connection to ORCID or OpenAlex times out or fails:  System logs the error and halts the synchronization.  System displays a notification to Actor explaining the connectivity issue and suggests a retry later.  |

### **UC-13 input course/grant specifications**

| Description | The system provides an interface for faculty administrators to manually enter natural language descriptions or upload documents representing course syllabi or research grant calls to facilitate automated expertise matching. |
| :---- | :---- |
| **Actor(s)** | HEAD OF DEPARTMENT, DEPUTY DEAN (UG/PG), DEPUTY DEAN (RESEARCH) |
| **Triggering Event** | Actor navigates to the Course Mapping or Research Grant Mapping module. |
| **Pre-condition** | Actor is logged into the Strategic Dashboard with an authorized portfolio.  The Expertise Knowledge Database is populated with processed staff profiles.  |
| **Post-condition** | The specifications are successfully ingested and prepared for the semantic matching process.  |
| **Flow of Events** | Actor selects the Course Mapping or Research Grant Mapping module.  System displays the specification input interface featuring a text entry area and a file upload zone.  Actor enters the natural language description of the requirement into the text area.  Actor clicks the submit button to initiate processing.  System validates the input data for sufficient text volume.  System stores the requirement temporarily and triggers the semantic matching module to begin the expertise comparison  |
| **Alternative Flow \- File Upload** | **@Step 3** If Actor chooses to provide requirements via a document: Actor selects and uploads a PDF or Word file containing the syllabus or grant call. System deterministically removes repeated page furniture, detects reviewable sections with a paragraph fallback for unfamiliar structures, and displays the extracted source text. Actor includes or excludes sections before ingestion. System creates token-bounded overlapping chunks, embeds them in a batch, preserves their source provenance, and proceeds to Step 4 of the Main Flow. |
| **Exception Flow\- Missing Specifications**  | **@Step 5** If Actor attempts to submit the form without entering text or uploading a file:  System identifies the empty input fields.  System displays a validation error message and prompts Actor to provide the necessary specifications.  |
| **Exception Flow \- Excessive Analytical Content** | **@Step 3** If selected source text exceeds 4,500 model tokens or produces more than 24 chunks, System prevents ingestion and asks Actor to exclude administrative or less relevant sections. System does not silently truncate the document. |

### **UC-14 match expertise with specifications**

| Description | The system performs semantic matching between the provided course or grant specifications and the institutional expertise database to generate a ranked list of the most suitable academic staff members based on direct and latent relevance. |
| :---- | :---- |
| **Actor(s)** | HEAD OF DEPARTMENT, DEPUTY DEAN (UG/PG), DEPUTY DEAN (RESEARCH) |
| **Triggering Event** | Actor initiates the matching process after providing natural language specifications or uploading a document. |
| **Pre-condition** | Actor is logged in and authorized to access the mapping module based on their portfolio.  Course or grant specifications have been successfully ingested and vectorized.  The Expertise Knowledge Database contains processed faculty profiles with pre-computed embeddings.  |
| **Post-condition** | A ranked matching report is displayed to Actor, detailing recommended staff members and analysis results to support evidence-based resource allocation. |
| **Flow of Events** | System receives the natural language requirement vectors generated from the input course or grant specifications.  System retrieves pre-computed academic staff expertise vectors from the Expertise Knowledge Database.  System calculates the Cosine Similarity between the requirement vectors and staff expertise vectors to determine direct semantic relevance.  System executes the Spreading Activation algorithm on the domain-specific knowledge graph to identify latent experts who possess knowledge in related or foundational fields.  System computes a weighted comprehensive score by aggregating the direct similarity and diffusion activation scores.  System sorts eligible academic staff in descending order based on the final comprehensive weighted score.  System renders the ranked list on the Strategic Dashboard, displaying the staff name, department affiliation, and matching score for administrative decision-making.  |
| **Alternative Flow\- Cross-Department Discovery** | **@Step 3** If the primary department lacks sufficient staff, System identifies "upskilled" or "reskilled" experts from other departments who possess the required technical capabilities to resolve staffing gaps. |
| **Exception Flow\- Insufficient Expertise Match**  | **@Step 3** If no expertise profiles in the database meet the minimum semantic proximity threshold, System displays a message indicating that no suitable matches were identified for the given specifications. |

### **UC-15 view global benchmarking**

| Description | The system allows faculty administrators to review how strongly current internal capability clusters cover prominent computer-science topics in OpenAlex. The result is decision-support evidence for programme planning, staff development, recruitment discussion, and collaboration, not an automatic institutional-gap or emerging-trend claim. |
| :---- | :---- |
| **Actor(s)** | FACULTY MANAGER, HEAD OF DEPARTMENT, DEPUTY DEAN (UG/PG) |
| **Triggering Event** | Actor selects the global benchmarking option within the Gap Analytics module of the Strategic Dashboard.  |
| **Pre-condition** | Actor is logged into the system with an authorized administrative portfolio. Internal faculty expertise centroids have been established by constructing one normalized, confidence-weighted vector per eligible active staff profile from validated or sufficiently confident expertise-tag links, then applying deterministic K-Means clustering. Connection to the OpenAlex REST API is available. |
| **Post-condition** | Actor views an interactive current-topic coverage comparison with OpenAlex topic provenance, research-output counts, nearest internal clusters, raw semantic distances, and an optional LLM-written explanation that does not replace the deterministic evidence. |
| **Flow of Events** | Actor accesses the Gap Analytics module. System constructs one weighted expertise vector per eligible staff member so each clustering observation represents institutional capacity rather than a standalone vocabulary tag. Actor initiates the global topic coverage analysis. System resolves the official OpenAlex Computer Science field and its subfields. For each subfield, System selects the two primary topics with the highest current count of articles, reviews, books, and book chapters. System embeds each topic name and description using the configured embedding model and calculates `1 - max cosine similarity` to the internal staff-cluster centroids. System presents weaker-coverage evidence first while retaining every selected topic, its OpenAlex ID, subfield, source count, update date, nearest internal cluster, and pending administrator-review status. System applies dimensionality reduction for the exploratory visualization and stores the retrieval and formula inputs needed to audit the run. |
| **Alternative Flow\- Administrative Interpretation** | **@Step 5** Actor sorts evidence by weaker coverage, stronger coverage, or computer-science subfield and interprets it alongside programme priorities, staff workload, development opportunities, recruitment plans, and collaboration options. System does not convert semantic distance into an automatic staffing decision. |
| **Exception Flow\- API Connection Timeout**  | **@Step 3** If OpenAlex fails to respond after bounded retries, System returns a service-unavailable error. Previously persisted global runs remain available to the combined-analysis workflow, but the failed request does not fabricate or silently reuse current data. |
| **Exception Flow \- Insufficient Internal Data**  | **@Step 4** If System cannot identify sufficient internal expertise clusters to perform a comparison, it prompts Actor to trigger a manual expertise sync to populate the database.  |

### **UC-16 perform peer benchmarking**

| Description | The system allows faculty administrators to compare internal staff expertise and capability clusters against programme-level peer curricula to surface candidate coverage gaps for administrator review. It does not automatically prove an institutional blind spot. |
| :---- | :---- |
| **Actor(s)** | FACULTY MANAGER, HEAD OF DEPARTMENT, DEPUTY DEAN (UG/PG) |
| **Triggering Event** | Actor selects the peer benchmarking option within the Gap Analytics module of the Strategic Dashboard. |
| **Pre-condition** | Actor is logged into the system with an authorized administrative portfolio. Internal faculty expertise centroids have been established from normalized, confidence-weighted active staff profile vectors via deterministic K-Means clustering. The uploaded peer material represents a programme-level curriculum or a multi-document collection that adequately covers multiple courses in the programme; one isolated module syllabus is not sufficient evidence for an institution-level comparison. |
| **Post-condition** | Sortable candidate coverage evidence is persisted, visualized, and made available to the combined gap analysis. Every result remains pending administrator review. |
| **Flow of Events** | Actor accesses the Gap Analytics module. System constructs one confidence-weighted expertise vector per eligible staff member and clusters those staff vectors into internal capacity centroids. Actor selects the Peer Benchmarking function. Actor uploads PDF or Word documents representing a programme structure or sufficiently broad curriculum collection. System removes repeated page furniture, detects reviewable sections with a paragraph fallback for unfamiliar structures, and displays exact extracted source text grouped by file. Actor includes or excludes sections. System creates token-bounded overlapping chunks, embeds them in one batch, and preserves filename, detected section, and source excerpt. For every retained chunk, System computes cosine distance to the nearest staff profile as the raw coverage signal and separately records the nearest capability cluster and its distance as an institutional summary. System provisionally classifies the segment as covered, partially covered, or a candidate gap using the recorded development-set calibration. System displays every retained segment with its evidence and pending administrator-review status; no LLM determines the score or classification. |
| **Alternative Flow \- Multi-Document Benchmarking**  | **@Step 3** If Actor uploads multiple documents from different peer institutions, the system shall aggregate the extracted domains into a consolidated peer benchmark baseline before performing the comparison.  |
| **Alternative Flow \- Insufficient Programme Coverage** | **@Step 3** If the selected files appear to describe only one course, System warns that a single-course syllabus cannot support an institution-level peer-gap claim and asks Actor to provide or confirm a collection representing the wider programme. |
| **Alternative Flow \- Manual Evidence Review** | **@Step 5** Actor sorts the complete bounded result set by distance or source and reviews the exact excerpt. Compulsory/elective status, credits, recurrence, accreditation importance, and single mentions remain equally weighted until reliable metadata and an approved stakeholder rule exist. |
| **Exception Flow \- Invalid File Format**  | **@Step 3** If the uploaded document is in an unsupported format or is corrupted, the system shall display an error message and prompt Actor to provide a valid PDF or Word file. |
| **Exception Flow \- Extraction Failure**  | **@Step 4** If the system cannot identify meaningful academic domains within the document, the system shall notify Actor and suggest uploading a more detailed programme curriculum, course catalogue, or programme report.  |
| **Exception Flow \- Upload or Analysis Limit** | **@Step 3/4** If Actor selects more than 8 files, any file exceeds 10 MiB, the combined request exceeds 25 MiB, selected source text exceeds 11,000 model tokens, or the representation exceeds 60 chunks, System prevents analysis and asks Actor to reduce the collection or exclude less relevant sections. System does not silently truncate programme content. |

### **UC-17 view gap analysis**

| Description | The system provides a synthesis of institutional expertise coverage compared against current prominent OpenAlex topics and peer curricula. |
| :---- | :---- |
| **Actor(s)** | FACULTY MANAGER, HEAD OF DEPARTMENT, DEPUTY DEAN (UG/PG) |
| **Triggering Event** | Actor selects the generate combined Gap Analysis report option.  |
| **Pre-condition** | Actor is logged into the system with an authorized administrative portfolio.  Internal faculty clusters have been established and external global or peer benchmarking data has been processed. |
| **Post-condition** | Actor views a multi-dimensional, source-balanced review queue that surfaces candidate institutional blind spots for administrator validation and supports evidence-based recruitment and curriculum discussion. It does not prove that a gap exists.  |
| **Flow of Events** | Actor enters the Gap Analytics module. System displays the main benchmarking interface providing access to global-topic and peer-curriculum evidence. Actor chooses to generate the combined Gap Analysis Report. System retrieves the latest persisted coverage evidence from either source. Within each source, System assigns a relative review priority from the ordering of distinct raw coverage distances, applies the provisional UAT weights of 50% global and 50% peer, and creates one review queue. System preserves the raw distance, source provenance, nearest internal staff/cluster evidence, review status, and supporting excerpt rather than inventing an unvalidated match between an OpenAlex topic and a peer-curriculum segment. System synthesizes the evidence into a natural-language decision-support report while preserving the provisional-weight and administrator-review boundaries. The weights determine review order only and are not a probability or gap-severity score. |
| **Alternative Flow \- Single Benchmark Focus**  | **@Step 3** If the Actor requires data from only one source:  Actor selects either Global Benchmarking or Peer Benchmarking. System executes the specific analysis and redirects the Actor to the focused visualization.  |
| **Exception Flow \- Missing Benchmark Data**  | **@Step 4** If neither benchmarking source has been populated, System prevents report generation and prompts Actor to run a benchmark. If exactly one source is missing, System names the missing component, returns the available evidence for limited review, and retains its configured 50% weight rather than silently presenting it as a complete or 100%-weighted cross-source report. |
| **Exception Flow \- Visualization Rendering Error**  | **@Step 7** If the dimensionality reduction algorithm fails to converge:  System logs the technical error.  System displays the raw gap data in a tabular format and provides the LLM-synthesized summary as a fallback.  |

### **UC-18 export customized CV**

| Description | The system allows academic staff to select specific professional achievements, such as validated expertise tags, to generate a concise one-page expertise snapshot for external grant applications or conferences.  |
| :---- | :---- |
| **Actor(s)** | ACADEMIC STAFF |
| **Triggering Event** | Actor selects the "Export Snapshot" option within the Expertise Management Portal.  |
| **Pre-condition** | Actor is logged into the Expertise Management Portal.  Actor has a validated expertise profile containing AI-generated tags and publication history.  |
| **Post-condition** | A customized one-page CV is successfully generated and downloaded to Actor's device in the selected format. |
| **Flow of Events** | Actor accesses the profile export interface within the Expertise Management Portal.  System retrieves and displays the Actor's categorized professional data, including normalized expertise tags, publications, and administrative records.  Actor selects the specific expertise tags and technical skills to be prioritized in the snapshot.  Actor filters and selects publications or academic backgrounds to be included based on the application type.  Actor selects the desired export format such as PDF or Word.  Actor clicks the Generate button to initiate the distillation process. System assembles the selected data points into a standardized one-page template.  System initiates the file download process to Actor's device.  |
| **Alternative Flow \- Default Template Export**  | **@Step 3** If Actor chooses to use the default settings, the system shall automatically populate the one-page snapshot with the top-ranked expertise tags and the most recent publications before proceeding to Step 6\.  |
| **Exception Flow \- Data Selection Overload**  | **@Step 4** If the selected professional records exceed the space constraints of the one-page layout, the system shall display a warning and prompt Actor to refine the selection to ensure the snapshot remains concise.  |
| **Exception Flow \- Empty Profile Selection**  | **@Step 6** If Actor attempts to generate a CV without selecting any expertise tags or publications, the system shall prevent the export and prompt the Actor to include at least one data point.  |
