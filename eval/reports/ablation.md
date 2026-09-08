# UBCHelper ablation — rag-vs-norag

2026-09-07T23:53:49 · 16 questions (12 specific + 4 general) · k=4

Models: chat=`claude-haiku-4-5`, judge=`google/gemma-4-e4b`, embed=`text-embedding-3-small` · corpus=3770

Groundedness = fraction of the answer's claims supported by the gold excerpt (higher is better). Hallucination = 1 - groundedness. Both arms are judged against the same gold excerpt, so a closed-book answer that gives plausible but *different* requirements still counts as unsupported — which is why general questions are listed separately.

## Summary — RAG vs no-RAG

| set | n | RAG groundedness | no-RAG groundedness | RAG halluc. | no-RAG halluc. | halluc. delta (RAG-noRAG) |
|-----|---|------------------|---------------------|-------------|----------------|---------------------------|
| overall | 16 | 0.724 | 0.333 | 0.276 | 0.667 | -0.391 |
| specific | 12 | 0.715 | 0.352 | 0.285 | 0.648 | -0.363 |
| general | 4 | 0.750 | 0.276 | 0.250 | 0.724 | -0.474 |

## Questions

### q001 — specific — gold [10, 182] Computer Science, Faculty of Science [2026/27] (+1 more)

**Q:** What are the prerequisites for CPSC 221?

**Reference:** One of CPSC 210 or CPEN 221, and either one of CPSC 121, MATH 220 (or MATH_O 220), or a score of 68% or higher in MATH 226.

**RAG answer** — groundedness 0.500 (1/2 claims):

For the 2026/27 calendar, the prerequisites for CPSC_V 221 are:

- One of CPSC_V 210 or CPEN_V 221, **and**
- Either (a) one of CPSC_V 121, MATH_V 220, or MATH_O 220, **or** (b) a score of 68% or higher in MATH_V 226

For the most current and authoritative wording, see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**No-RAG answer** — groundedness 0.333 (1/3 claims):

# CPSC 221 Prerequisites

**CPSC 221 (Basic Algorithms and Data Structures)** requires:

- **CPSC 210** (Software Construction)

**Corequisite:**
- **MATH 200** (Calculus III) or equivalent

Some students may also need foundational discrete math knowledge, though MATH 200 or concurrent enrollment typically satisfies this requirement.

### q002 — specific — gold [24, 197] Computer Science, Faculty of Science [2026/27] (+1 more)

**Q:** What are the prerequisites for CPSC 320?

**Reference:** CPSC 221 (or DSCI 221) plus at least 3 credits of MATH or STAT at the 200 level or above (the 2025/26 edition also accepted COMM 291 or BIOL 300 for the second part).

**RAG answer** — groundedness 0.000 (0/3 claims):

Based on the course descriptions provided, I don't have the explicit prerequisites for CPSC 320 listed in these excerpts. The excerpts mention CPSC 320 as a required course in the Cognitive Systems major program and reference a note about grade requirements in a statistics course before admission to CPSC 320, but they don't spell out the full prerequisite course list.

For the authoritative and complete prerequisite information for CPSC 320, I'd recommend checking the course description directly on the UBC Vancouver Academic Calendar at:

https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**No-RAG answer** — groundedness 0.667 (2/3 claims):

# CPSC 320 Prerequisites

**CPSC 320** (Intermediate Algorithm Design and Analysis) requires:

- **CPSC 221** (Basic Algorithms and Data Structures)
- **MATH 200** (Calculus III) or **MATH 217** (Multivariable Calculus for Engineers)

You must have completed these prerequisites before enrolling in CPSC 320.

### q003 — specific — gold [20, 193] Computer Science, Faculty of Science [2026/27] (+1 more)

**Q:** What are the prerequisites for CPSC 313?

**Reference:** CPSC 213, and either CPSC 221 or DSCI 221.

**RAG answer** — groundedness 1.000 (2/2 claims):

The prerequisites for CPSC 313 (Computer Hardware and Operating Systems) are:

- CPSC 213, **and**
- Either CPSC 221 or DSCI 221

For the current 2026/27 calendar, you can find this information at: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**No-RAG answer** — groundedness 1.000 (2/2 claims):

# CPSC 313 Prerequisites

CPSC 313 (Computer Hardware and Operating Systems) requires:

- **CPSC 213** (Introduction to Computer Systems)

This is the primary prerequisite. Students must complete CPSC 213 before enrolling in CPSC 313.

### q004 — specific — gold [580, 2319] Mathematics, Faculty of Science [2026/27] (+1 more)

**Q:** Which courses satisfy the prerequisite for MATH 200, Calculus III?

**Reference:** One of MATH 101, MATH 103, MATH 105, MATH 121, SCIE 001, MATH_O 101, or MATH_O 103.

**RAG answer** — groundedness 1.000 (8/8 claims):

For MATH_V 200 (Calculus III) in 2026/27, the prerequisite is one of the following courses:

- MATH_V 101
- MATH_V 103
- MATH_V 105
- MATH_V 121
- SCIE_V 001
- MATH_O 101
- MATH_O 103

You need to complete just one of these courses to satisfy the prerequisite.

For the authoritative and most current wording, please see the course description at https://vancouver.calendar.ubc.ca/course-descriptions/subject/mathv.

**No-RAG answer** — groundedness 0.000 (0/4 claims):

# MATH 200 Prerequisites

The prerequisite for MATH 200 (Calculus III) is:

**MATH 101 or MATH 103** (or equivalent)

These are the second-year calculus courses covering integration and applications of derivatives. You must complete one of these before enrolling in MATH 200.

Alternatively, a **sufficient score on the AP Calculus exam** or transfer credit from another institution may also satisfy this requirement.

### q005 — specific — gold [5, 177] Computer Science, Faculty of Science [2026/27] (+1 more)

**Q:** How many credits is CPSC 110 worth and what does it cover?

**Reference:** CPSC 110 (Computation, Programs, and Programming) is worth 4 credits and covers fundamental program and computation structures.

**RAG answer** — groundedness 1.000 (1/1 claims):

Based on the calendars provided, **CPSC 110 is worth 4 credits**.

However, the excerpts don't contain information about what the course covers—they only specify the credit value and that it's a required course in the first year of Computer Science programs. For details about the course content, you would need to check the course description in the UBC Vancouver Academic Calendar or the Department of Computer Science course listings.

**No-RAG answer** — groundedness 0.200 (2/10 claims):

**CPSC 110 is worth 3 credits.**

This is UBC's introductory computer science course that covers **fundamentals of programming and computational thinking**. The course typically includes:

- Basic programming concepts (variables, control flow, functions)
- Problem-solving and algorithm design
- Data structures (lists, arrays)
- Introduction to object-oriented programming
- Testing and debugging

The course uses a student-friendly language (often Python or a similar language) and requires no prior programming experience. It's a foundational course for most Computer Science and related programs at UBC.

### q006 — specific — gold [114, 128] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2026/27] (+1 more)

**Q:** Compare the B.A. degree requirements for students who entered the program in 2023/24 with those who entered in 2024/25 or later.

**Reference:** Students entering 2023/24 or earlier must complete seven requirements: Writing and Research, Language, Science, Literature, Outside, Upper-level, and Arts Credit Minimum. Students entering 2024/25 or later complete five: Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum — the separate Language, Science, and Literature requirements are folded into the Ways of Knowing Breadth requirement.

**RAG answer** — groundedness 0.600 (3/5 claims):

I don't have enough information in these excerpts to make that comparison. The excerpts reference the different degree requirements for each cohort but don't actually detail what those requirements are.

To see the specific differences between the B.A. degree requirements for students who entered in 2023/24 versus 2024/25 or later, you'll need to consult the full degree requirements pages in the UBC Calendar:

- For 2026/27: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts
- For 2025/26: https://archive.calendar.ubc.ca/vancouver/2526/faculties-colleges-and-schools/faculty-arts/bachelor-arts/

These pages should have separate sections outlining the requirements for each cohort.

**No-RAG answer** — groundedness 0.100 (1/10 claims):

# B.A. Degree Requirements: 2023/24 vs. 2024/25+

## Key Differences

**2023/24 Cohort:**
- 120 total credits required
- 36 credits in upper-level courses (300-level and above)
- No specified minimum for lower-level breadth
- Writing requirement embedded in discipline courses

**2024/25+ Cohort:**
- 120 total credits required
- 36 credits in upper-level courses (300-level and above)
- Explicit **"Breadth Requirement"**: students must complete courses across multiple disciplinary areas
- Formalized **Writing Across the Curriculum** approach with designated writing-intensive courses
- Greater emphasis on ensuring exposure to diverse subject areas

## Main Change

The primary shift is **structural clarity around breadth**. The 2024/25+ requirements explicitly codify the breadth expectation that was implicit in 2023/24, and formalize writing support across the degree rather than concentrating it in major courses.

Both cohorts maintain the same credit totals and upper-level thresholds, but 2024/25+ students have more defined guidelines about distributing their electives across disciplines.

For your specific major, verify the major-specific requirements, as some programs have their own variations on top of the Faculty-wide B.A. framework.

### q007 — specific — gold [1769, 1791] Bachelor of Computer Science [2026/27] (+1 more)

**Q:** How does admission to the Bachelor of Computer Science program differ from B.Sc. admission from secondary school?

**Reference:** Bachelor of Computer Science admission is a competitive selection process evaluating applicants on academic and other criteria (not every qualified applicant is admitted); B.Sc. admission from secondary school requires starting first year in September of the Winter session of admission (January starts are not permitted).

**RAG answer** — groundedness 0.727 (8/11 claims):

Based on the excerpts provided, here are the key differences:

**Bachelor of Computer Science (B.C.S.):**
- Designed for students with a **previous bachelor's degree** in a non-overlapping field
- A **two-year program** leading to a second bachelor's degree
- Admission is highly selective and based on both academic and non-academic criteria
- Academic evaluation includes overall record and a minimum B- (68%) average on the most recent 30 credits
- Non-academic evaluation includes two letters of reference, self-assessment of work history, and a statement of interest
- Applicants may be interviewed before a decision is made

**B.Sc. from Secondary School:**
- For students entering **directly from high school**
- Admission is based on performance in specific high school courses, overall academic rigor of the program, and evidence of relevant learning both in and out of school
- Students are expected to start in September

In essence, the B.C.S. is a graduate-entry program for career-changers with an existing degree, while B.Sc. admission is for secondary school students.

For the most current and complete information, refer to the official calendar pages:
- B.C.S.: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-computer-science
- B.Sc.: https://archive.calendar.ubc.ca/vancouver/2526/faculties-colleges-and-schools/faculty-science/bachelor-science/admission-and-transfer/index.html

**No-RAG answer** — groundedness 0.091 (1/11 claims):

# BCS vs B.Sc. Admission

**Bachelor of Computer Science (BCS) admission** is more competitive and specialized:

- **Higher entrance requirements**: Typically requires stronger grades in Math and Science than general B.Sc.
- **Direct entry program**: You're admitted specifically to Computer Science, not a general science program
- **Restricted seats**: Limited enrollment in the major itself
- **Math prerequisite emphasis**: Strong performance in Calculus and Physics expected

**B.Sc. admission** (general Bachelor of Science):

- **Lower entrance threshold**: Broader acceptance criteria
- **Open declaration**: You can declare most science majors after first year based on grades in prerequisite courses
- **More flexibility**: Choose your major after experiencing different subjects
- **Easier initial entry**: But you must maintain required GPA in CS prerequisites (typically Math 100-level, CPSC 110/210) to actually declare Computer Science as your major

**Key difference**: BCS guarantees your spot in the program upon admission; with B.Sc., you need to earn your way into the CS major through strong performance in first-year prerequisites.

If you're strong in math/physics and certain about CS, BCS is ideal. If you're exploring options or your grades are borderline, B.Sc. offers a pathway in via first-year performance.

### q008 — specific — gold [20, 10] Computer Science, Faculty of Science [2026/27] (+1 more)

**Q:** I have finished CPSC 210. What else do I need to complete before I can take CPSC 313?

**Reference:** CPSC 313 requires CPSC 213 and either CPSC 221 or DSCI 221. CPSC 221 in turn requires (beyond CPSC 210) one of CPSC 121, MATH 220, MATH_O 220, or a 68%+ score in MATH 226. So after CPSC 210 you still need CPSC 213 and CPSC 221 (with its discrete-math prerequisite).

**RAG answer** — groundedness 0.000 (0/4 claims):

I don't have enough information in the available excerpts to answer this question. The excerpts show that CPSC_V 313 is a required upper-level course in Computer Science programs, but they don't include the course prerequisites or corequisites for CPSC_V 313.

To find the specific prerequisites for CPSC_V 313, you should check the course description in the UBC Vancouver Academic Calendar or consult with an academic advisor. You can also contact the Computer Science department directly for the most accurate and current prerequisite information.

**No-RAG answer** — groundedness 0.667 (4/6 claims):

To take **CPSC 313** (Computer Hardware and Operating Systems), you need:

1. **CPSC 210** ✓ (you've completed this)
2. **CPSC 221** (Basic Algorithms and Data Structures)

CPSC 221 is the key prerequisite you still need to complete. It covers fundamental data structures and algorithmic analysis, which are essential for understanding operating systems and hardware concepts in CPSC 313.

Make sure you also meet the **math corequisite**: MATH 220 or MATH 226 (Linear Algebra).

### q009 — specific — gold [3508] Bachelor of Science — General Degree Requirements [2025/26]

**Q:** In the 2025/26 calendar, what is the minimum number of credits required for a B.Sc. degree?

**Reference:** A minimum of 120 credits (a major, double major, or General Science option requires at least 120 credits but may require more).

**RAG answer** — groundedness 1.000 (2/2 claims):

In the 2025/26 calendar, the minimum number of credits required for a B.Sc. degree depends on which degree option you pursue:

- **Major, Combined Major, Double Major, or General Science**: 120 credits minimum
- **Honours or Combined Honours**: 132 credits minimum

Note that these are minimums—your specific program may require more. For the most current and complete details, see the official calendar page: https://archive.calendar.ubc.ca/vancouver/2526/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements/index.html

**No-RAG answer** — groundedness 0.500 (3/6 claims):

The minimum number of credits required for a B.Sc. degree at UBC Vancouver is **120 credits**.

This typically includes:
- General Education requirements (12 credits)
- Science requirements (varying by program)
- Major/specialization requirements
- Electives to reach the 120-credit minimum

The exact distribution varies by specific program, but 120 credits is the baseline for all B.Sc. degrees.

### q010 — specific — gold [2023] Bachelor of Science — General Degree Requirements [2026/27]

**Q:** According to the current 2026/27 calendar, what is the minimum number of credits required for a B.Sc. degree?

**Reference:** A minimum of 120 credits (a major, double major, or General Science option requires at least 120 credits but may require more).

**RAG answer** — groundedness 1.000 (4/4 claims):

According to the current 2026/27 calendar, the minimum number of credits required for a B.Sc. degree is **120 credits**.

This applies to students pursuing a major, combined major, double major, or General Science option. However, honours or combined honours options require between 120-132 credits, and dual degrees require more than 120 credits (though some combinations may be completed in fewer than 180 credits).

For full details, see the Bachelor of Science General Degree Requirements page: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements

**No-RAG answer** — groundedness 0.667 (2/3 claims):

The minimum number of credits required for a B.Sc. degree at UBC Vancouver is **120 credits**.

This includes general requirements such as breadth requirements across science and non-science disciplines, along with major-specific coursework. However, many programs require more than the minimum, so students should verify their specific program requirements in the calendar.

### q011 — specific — gold [128] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27]

**Q:** Does a B.A. student who entered the program in 2024/25 or later have to complete a language requirement?

**Reference:** No. Their five degree requirements are Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum — there is no separate language requirement (that applies to students who entered in 2023/24 or earlier).

**RAG answer** — groundedness 0.750 (3/4 claims):

Based on the excerpts provided, I can only definitively answer this for Linguistics majors: yes, they must complete 6 credits of coursework in a single language other than English.

However, the excerpts don't contain general B.A. degree requirements that would tell me whether a language requirement applies to all B.A. students who entered in 2024/25 or later. The 2026/27 B.A. degree requirements listed (Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum) don't explicitly mention a language requirement in the excerpts provided.

For the most current and complete information about language requirements for B.A. students entering in 2024/25 or later, I'd recommend checking the full B.A. degree requirements page: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202425-or-later

**No-RAG answer** — groundedness 0.000 (0/3 claims):

Yes. B.A. students entering in 2024/25 or later must complete a language requirement. This typically involves demonstrating proficiency in a language other than English, either through:

- Completing 6 credits of university-level coursework in a single language, or
- Meeting proficiency requirements through placement testing or previous education

The specific language and level of proficiency required can vary by program, so you should check with your specific B.A. program for details on which languages satisfy this requirement and what options are available.

### q012 — specific — gold [0] Academic Standing [2026/27]

**Q:** What are the three levels of academic standing at UBC?

**Reference:** In Good Standing; On Academic Probation; and Failed, Required to Withdraw. All students are In Good Standing on initial entry to the University.

**RAG answer** — groundedness 1.000 (5/5 claims):

The three levels of academic standing at UBC are:

1. **In Good Standing**
2. **On Academic Probation**
3. **Failed, Required to Withdraw**

All students begin in Good Standing when they first enter the University. A student's standing may change to On Academic Probation or Failed, Required to Withdraw based on their academic performance. Students on Academic Probation may have restrictions placed on their registration, while students with Failed, Required to Withdraw status must withdraw from their studies for 12 months.

For the most current and authoritative information, see: https://vancouver.calendar.ubc.ca/campus-wide-policies-and-regulations/academic-standing

**No-RAG answer** — groundedness 0.000 (0/5 claims):

The three levels of academic standing at UBC Vancouver are:

1. **Good Standing** – You're meeting satisfactory academic progress with a GPA of 2.0 or higher.

2. **Academic Probation** – Your GPA has fallen below 2.0, and you're required to improve your academic performance within a specified timeframe.

3. **Dismissal** – You've failed to meet academic requirements while on probation and are no longer permitted to continue studies at UBC.

Students on probation typically have one or two terms to bring their GPA back to 2.0 or above, depending on their faculty's specific policies.

### g001 — general — gold [0] Academic Standing [2026/27]

**Q:** What happens to a UBC student's academic standing, and what standings exist?

**Reference:** There are three levels of academic standing: In Good Standing, On Academic Probation, and Failed, Required to Withdraw. Students enter the University In Good Standing.

**RAG answer** — groundedness 1.000 (9/9 claims):

UBC has three levels of academic standing:

1. **In Good Standing** — This is the default standing for all students upon initial entry to the University.

2. **On Academic Probation** — A student may be placed on Academic Probation as a result of academic performance evaluations. Students on Academic Probation may have restrictions placed on their registration, which vary by Faculty.

3. **Failed, Required to Withdraw** — Students with this standing are required to withdraw from their studies for 12 months. However, if this standing is determined after the last date for withdrawal without a "W" on the transcript, the student may complete any courses they're already attending.

A student's academic standing can change based on their academic performance. If a student who has been required to withdraw later successfully appeals for readmission, they may be placed On Academic Probation.

Additionally, if a student receives a **Failed, Required to Withdraw** standing and wishes to appeal to continue their studies immediately, they cannot register for or attend courses while awaiting the appeal results (except in limited circumstances noted above).

For the authoritative and most current information, see: https://vancouver.calendar.ubc.ca/campus-wide-policies-and-regulations/academic-standing

**No-RAG answer** — groundedness 0.231 (3/13 claims):

# UBC Academic Standing

## Standing Categories

UBC uses these academic standings:

- **Good Standing** – Minimum requirements met (typically 2.0 GPA)
- **Academic Probation** – GPA fell below 2.0; student remains enrolled but under review
- **Dismissal** – Repeated failure to meet minimum standards; student is required to withdraw

## What Happens

**On Probation:**
- You remain enrolled and can continue courses
- Your file is flagged for review
- You may face restrictions (reduced course load, mandatory advising)
- You have one term typically to return to Good Standing

**On Dismissal:**
- You are required to withdraw from the university
- You cannot re-enroll immediately
- Readmission requires demonstrated improvement (usually after sitting out 1+ terms and completing upgrading)

## Key Factors

Academic standing is determined by:
- **Cumulative GPA** (primary measure)
- **Term GPA** (recent performance)
- **Progress toward degree requirements**

Specific thresholds vary slightly by faculty (Engineering, Science, etc. have different standards).

**Bottom line:** Probation is a warning system; dismissal is involuntary withdrawal. Both are designed to ensure students are set up for success.

### g002 — general — gold [2023] Bachelor of Science — General Degree Requirements [2026/27]

**Q:** Roughly how many credits does a UBC B.Sc. degree require?

**Reference:** A minimum of 120 credits; some options require more.

**RAG answer** — groundedness 1.000 (3/3 claims):

A UBC Bachelor of Science degree requires a minimum of **120 credits** for a major, combined major, double major, or General Science option (though some of these may require more). An honours or combined honours option requires between 120 and 132 credits depending on the department's specialization.

The degree must be completed within a maximum of 180 attempted credits.

For full details, see the [General Degree Requirements page](https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements).

**No-RAG answer** — groundedness 0.400 (2/5 claims):

A UBC B.Sc. degree requires **120 credits** to complete.

This typically breaks down as:
- **Lower-level courses** (100-200 level): foundation courses in math, sciences, and breadth requirements
- **Upper-level courses** (300-400 level): major-specific and elective courses
- **General Education Requirements**: breadth across sciences, arts, and other domains

The exact distribution varies by specific program (e.g., Biology vs. Physics vs. Chemistry), but 120 credits is the standard total for the Bachelor of Science degree.

### g003 — general — gold [5] Computer Science, Faculty of Science [2026/27]

**Q:** What is CPSC 110 at UBC about?

**Reference:** CPSC 110, Computation, Programs, and Programming (4 credits), covers fundamental program and computation structures.

**RAG answer** — groundedness 0.714 (5/7 claims):

CPSC 110 (Computation, Programs, and Programming) is a 4-credit course that covers fundamental program and computation structures, introductory programming skills, and computation as a tool for information processing, simulation and modelling, and interacting with the world. The course format is [3-3-0], indicating 3 hours of lecture, 3 hours of lab/seminar, and 0 hours of other instruction per week.

This course is designed for students pursuing Computer Science specializations or who plan to take CPSC 210.

For more details, you can consult the official course descriptions at https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv.

**No-RAG answer** — groundedness 0.222 (2/9 claims):

CPSC 110 is UBC's introductory computer science course focused on **computation, programs, and programming**. It teaches fundamental programming concepts using the Racket language (a Lisp dialect), emphasizing problem-solving and design principles rather than just syntax.

Key topics include:
- Data types and structures
- Functions and recursion
- Lists and trees
- Program design and testing

The course is 3 credits and serves as the foundation for most CS majors. It's designed for students with little to no prior programming experience, though it moves at a rigorous pace. Most CS students take it in their first year.

### g004 — general — gold [128, 114] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27] (+1 more)

**Q:** What kinds of requirements does a UBC Bachelor of Arts student have to complete?

**Reference:** B.A. students complete a set of faculty-wide degree requirements — for current entrants (2024/25 or later): Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum; earlier cohorts also had separate Language, Science, and Literature requirements.

**RAG answer** — groundedness 0.286 (2/7 claims):

Based on the UBC Bachelor of Arts degree requirements, students must complete several types of requirements:

1. **Writing and Research Requirement** — This has two components:
   - **Writing Component**: 3 credits of instruction on research and writing in the disciplines (through courses like Arts One, ASTU_V 100, ASTU_V 101, CAP_V 100, ENGL_V 100, WRDS_V 150, WRDS_V 151, or WRDS_V 350). This must be completed before reaching Year 3 standing.
   - **Research Component**: (Details are referenced but not fully shown in the excerpts provided)

2. **Language Requirement** — Students must satisfy this through one of three methods:
   - Complete a language course (excluding English) at BC Grade 12 level or equivalent prior to admission
   - Pass a proficiency test (with no course credit awarded)
   - Complete language courses at UBC to reach or exceed specified proficiency levels

3. **Ways of Knowing Breadth Requirements** — Referenced in the writing component section, though full details aren't provided in these excerpts.

For the complete and most current details on all Bachelor of Arts requirements, please consult the official UBC Calendar pages:
- For students entering 2024/25 or later: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202425-or-later
- For students entering 2023/24 or earlier: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202324-or-earlier

**No-RAG answer** — groundedness 0.250 (3/12 claims):

# UBC Bachelor of Arts Requirements

A BA student must complete **120 credits** with the following structure:

## Core Requirements
- **English requirement**: One course (typically ENGL 110)
- **Quantitative requirement**: One approved course in math, statistics, or logic
- **Writing requirement**: Demonstrated through coursework

## Program Structure
- **Major(s)**: 30-36 credits in your chosen discipline(s)
- **Minor (optional)**: 18-24 credits if declared
- **Electives**: Fill remaining credits to reach 120

## Breadth Requirements
Courses must span multiple faculties:
- At least one course each from Science, Social Sciences, and Humanities/Arts
- This prevents concentrating too heavily in one area

## Upper-Level Courses
- Minimum **36 credits** at the 300-level or above

## Additional Notes
- Grade requirements vary by major (typically 60% minimum to progress)
- Some programs have additional prerequisites or prerequisites for upper-level courses
- Specific requirements depend on your declared major

I'd recommend checking your specific program requirements in the **UBC Calendar** or speaking with an Academic Advisor in your faculty, as some programs have specialized requirements beyond these general BA guidelines.

