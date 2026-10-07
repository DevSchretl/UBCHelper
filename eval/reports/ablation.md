# UBCHelper ablation — rag-vs-norag-16576

2026-10-06T22:32:31 · 16 questions (12 specific + 4 general) · k=4

Models: chat=`claude-haiku-4-5`, judge=`google/gemma-4-e4b`, embed=`text-embedding-3-small` · corpus=16576

Groundedness = fraction of the answer's claims supported by the gold excerpt (higher is better). Hallucination = 1 - groundedness. Both arms are judged against the same gold excerpt, so a closed-book answer that gives plausible but *different* requirements still counts as unsupported — which is why general questions are listed separately.

## Summary — RAG vs no-RAG

| set | n | RAG groundedness | no-RAG groundedness | RAG halluc. | no-RAG halluc. | halluc. delta (RAG-noRAG) |
|-----|---|------------------|---------------------|-------------|----------------|---------------------------|
| overall | 16 | 0.700 | 0.332 | 0.300 | 0.668 | -0.368 |
| specific | 12 | 0.764 | 0.335 | 0.236 | 0.665 | -0.429 |
| general | 4 | 0.510 | 0.324 | 0.490 | 0.676 | -0.186 |

## Questions

### q001 — specific — gold [10, 182] Computer Science, Faculty of Science [2026/27] (+1 more)

**Q:** What are the prerequisites for CPSC 221?

**Reference:** One of CPSC 210 or CPEN 221, and either one of CPSC 121, MATH 220 (or MATH_O 220), or a score of 68% or higher in MATH 226.

**RAG answer** — groundedness 1.00 (3/3) claims:

For CPSC 221 in the 2026/27 calendar, the prerequisites are:

- One of CPSC_V 210 or CPEN_V 221, **AND**
- Either (a) one of CPSC_V 121, MATH_V 220, or MATH_O 220, **OR** (b) a score of 68% or higher in MATH_V 226

For the authoritative and most current wording, see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**No-RAG answer** — groundedness 0.67 (2/3) claims:

CPSC 221 (Basic Algorithms and Data Structures) has the following prerequisites:

- **CPSC 210** (Software Construction)
- **One of**: MATH 200, MATH 217, MATH 226, or MATH 253 (a second-year discrete math or linear algebra course)

Some students may have these requirements waived based on equivalent coursework, but these are the standard prerequisites listed in the calendar.

### q002 — specific — gold [24, 197] Computer Science, Faculty of Science [2026/27] (+1 more)

**Q:** What are the prerequisites for CPSC 320?

**Reference:** CPSC 221 (or DSCI 221) plus at least 3 credits of MATH or STAT at the 200 level or above (the 2025/26 edition also accepted COMM 291 or BIOL 300 for the second part).

**RAG answer** — groundedness 0.75 (3/4) claims:

According to the 2025/26 calendar, the prerequisites for CPSC 320 are:

- All of the following:
  - CPSC 221 or DSCI 221
  - At least 3 credits from: COMM 291, BIOL 300, or MATH or STAT at 200 level or above

For the authoritative and most current wording, see: https://archive.calendar.ubc.ca/vancouver/2526/course-descriptions/subject/cpscv/index.html

**No-RAG answer** — groundedness 0.40 (2/5) claims:

# CPSC 320 Prerequisites

**CPSC 320** (Intermediate Algorithm Design and Analysis) requires:

- **CPSC 221** (Basic Algorithms and Data Structures)
- **One of:** MATH 200, MATH 217, MATH 226, or MATH 253 (proof-based mathematics)

Some sections may have additional corequisite requirements for linear algebra, so check your specific course section. CPSC 320 is a core course for computer science majors and assumes solid understanding of data structures and discrete mathematics.

### q003 — specific — gold [20, 193] Computer Science, Faculty of Science [2026/27] (+1 more)

**Q:** What are the prerequisites for CPSC 313?

**Reference:** CPSC 213, and either CPSC 221 or DSCI 221.

**RAG answer** — groundedness 0.67 (2/3) claims:

For CPSC 313 (Computer Hardware and Operating Systems), the prerequisites are:

- CPSC 213, **and**
- Either CPSC 221 or DSCI 221

You can find the authoritative course description at https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**No-RAG answer** — groundedness 0.25 (1/4) claims:

CPSC 313 (Computer Hardware and Operating Systems) has the following prerequisites:

- **CPSC 213** (Introduction to Computer Systems)

This is the main prerequisite. Some sections may also require or recommend concurrent enrollment in a math course, but CPSC 213 is the essential requirement.

### q004 — specific — gold [580, 2196] Mathematics, Faculty of Science [2026/27] (+1 more)

**Q:** Which courses satisfy the prerequisite for MATH 200, Calculus III?

**Reference:** One of MATH 101, MATH 103, MATH 105, MATH 121, SCIE 001, MATH_O 101, or MATH_O 103.

**RAG answer** — groundedness 0.88 (7/8) claims:

For MATH_V 200 (Calculus III) in the 2026/27 calendar, the prerequisite is one of the following courses:

- MATH_V 101
- MATH_V 103
- MATH_V 105
- MATH_V 121
- SCIE_V 001
- MATH_O 101
- MATH_O 103

You need to complete just one of these courses to meet the prerequisite for MATH_V 200.

For the authoritative and most current wording, please consult: https://vancouver.calendar.ubc.ca/course-descriptions/subject/mathv

**No-RAG answer** — groundedness 0.75 (3/4) claims:

# MATH 200 Prerequisites

The prerequisite for MATH 200 (Calculus III) is:

**MATH 101 or MATH 103 or MATH 105 or a score of 64% or higher in MATH 110**

These courses cover the differential calculus content needed for MATH 200, which focuses on multivariable calculus and applications.

### q005 — specific — gold [5, 177] Computer Science, Faculty of Science [2026/27] (+1 more)

**Q:** How many credits is CPSC 110 worth and what does it cover?

**Reference:** CPSC 110 (Computation, Programs, and Programming) is worth 4 credits and covers fundamental program and computation structures.

**RAG answer** — groundedness 1.00 (1/1) claims:

CPSC 110 is worth **4 credits**.

However, the excerpts provided don't contain information about what CPSC 110 covers—they only list it as a required course. For details about the course content and topics, you would need to check the course description in the UBC Course Calendar or the Computer Science department's course listings.

For the most current program requirements, see the official calendar at: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/computer-science

**No-RAG answer** — groundedness 0.22 (2/9) claims:

CPSC 110 is worth **3 credits**.

It covers the fundamentals of computer programming, including:
- Basic programming concepts (variables, data types, control flow)
- Functions and procedures
- Introduction to object-oriented programming
- Problem-solving and algorithm design
- Programming in Java

The course emphasizes practical programming skills and is typically the first computer science course for students new to programming. It's a foundational course required for most CS majors and serves as a prerequisite for many upper-level CS courses.

### q006 — specific — gold [114, 128] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2026/27] (+1 more)

**Q:** Compare the B.A. degree requirements for students who entered the program in 2023/24 with those who entered in 2024/25 or later.

**Reference:** Students entering 2023/24 or earlier must complete seven requirements: Writing and Research, Language, Science, Literature, Outside, Upper-level, and Arts Credit Minimum. Students entering 2024/25 or later complete five: Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum — the separate Language, Science, and Literature requirements are folded into the Ways of Knowing Breadth requirement.

**RAG answer** — groundedness 1.00 (2/2) claims:

I don't have enough information in the provided excerpts to compare the specific degree requirements between these two cohorts. The excerpts reference that there are different "Degree Requirements for students who entered the program in 2023/24 or earlier" versus "Degree Requirements for students who entered the program in 2024/25 or later," but they don't actually detail what those differences are.

To see the specific requirements for each cohort, you would need to consult the full degree requirements pages in the UBC Calendar. For the 2026/27 calendar, you can find this information at:
- https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts

I'd recommend visiting that page and looking for the separate requirement sections for each cohort to compare them directly.

**No-RAG answer** — groundedness 0.08 (1/12) claims:

# B.A. Degree Requirements: 2023/24 vs. 2024/25+

## Core Structure (Largely Unchanged)

Both cohorts require:
- **120 total credit hours**
- **English requirement**: ENGL 112 or equivalent
- **Science requirement**: One course from approved list
- **Breadth requirements** across multiple disciplines

## Key Difference: Writing Requirement

**2023/24 students:**
- Could satisfy writing through various departmental courses or WRDS 150

**2024/25+ students:**
- **WRDS 110** (3 credits) is now the standard requirement
- More structured, institutionalized approach to writing instruction

## Other Potential Changes

- **Elective flexibility** may have been adjusted
- **Upper-level requirements** in major/minor programs may have shifted slightly
- Some departments updated course offerings and prerequisites

## Recommendation

For the most precise comparison, I'd recommend checking the specific **Faculty of Arts calendar pages** for each year, as departments often adjust course selections within breadth requirements. The 120-credit framework remains consistent, but the writing requirement shift is the most significant formal change between these cohorts.

Is there a specific requirement area you want me to clarify further?

### q007 — specific — gold [1646, 1668] Bachelor of Computer Science [2026/27] (+1 more)

**Q:** How does admission to the Bachelor of Computer Science program differ from B.Sc. admission from secondary school?

**Reference:** Bachelor of Computer Science admission is a competitive selection process evaluating applicants on academic and other criteria (not every qualified applicant is admitted); B.Sc. admission from secondary school requires starting first year in September of the Winter session of admission (January starts are not permitted).

**RAG answer** — groundedness 0.56 (5/9) claims:

Based on the calendar information provided, the Bachelor of Computer Science (B.C.S.) program is fundamentally different from a typical B.Sc. program in that it's specifically designed as a **second bachelor's degree** for students who already hold a recognized bachelor's degree in a non-computer science field.

Key differences in admission include:

**B.C.S. Admission:**
- Requires completion of a prior bachelor's degree
- Uses a selective admission process evaluating both academic and non-academic criteria
- Requires a minimum B- (68%) average in the most recent 30 credits
- Assesses non-academic qualities through letters of reference, self-assessment, and statement of interest
- May conduct interviews with selected applicants
- Is a two-year program

**Secondary School Admission (standard B.Sc.):**
The excerpts provided focus on B.C.S. requirements and don't contain detailed information about standard secondary school B.Sc. admission, so I cannot make a complete comparison.

Additionally, note that students newly admitted to the B.C.S. cannot pursue another program concurrently at UBC or elsewhere—they must complete all remaining credits through UBC's Vancouver campus.

For the most current and complete admission requirements, see https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-computer-science

**No-RAG answer** — groundedness 0.14 (2/14) claims:

# BCS vs B.Sc. Admission

**Bachelor of Computer Science (BCS)** has distinct, more competitive admission requirements:

- **Admission average**: Typically 85-90%+ (higher than general B.Sc.)
- **Required courses**: Math 12, Physics 12, English 12 (or equivalents)
- **Capacity-constrained**: Smaller cohort with selective intake
- **Direct entry**: Admitted directly into the CS major

**B.Sc. (General)** admission is less restrictive:

- **Admission average**: Generally 70-75%+
- **Math requirement**: Math 12 minimum (Physics recommended but not required)
- **Higher intake**: Larger program with more spots
- **Flexible major**: Choose your major after first year, including CS if preferred

**Key difference**: BCS guarantees your major from day one but requires higher grades and prerequisites. B.Sc. offers flexibility to explore, but competing for CS as a major after first year is more difficult than direct BCS admission.

If you're a strong Math/Physics student aiming for CS, BCS is the direct path. If you want flexibility or have borderline grades, B.Sc. allows entry with potential to pursue CS later (though transfer standards are competitive).

### q008 — specific — gold [20, 10] Computer Science, Faculty of Science [2026/27] (+1 more)

**Q:** I have finished CPSC 210. What else do I need to complete before I can take CPSC 313?

**Reference:** CPSC 313 requires CPSC 213 and either CPSC 221 or DSCI 221. CPSC 221 in turn requires (beyond CPSC 210) one of CPSC 121, MATH 220, MATH_O 220, or a 68%+ score in MATH 226. So after CPSC 210 you still need CPSC 213 and CPSC 221 (with its discrete-math prerequisite).

**RAG answer** — groundedness 0.67 (2/3) claims:

Based on the prerequisites for CPSC 313, you need to complete:

1. **CPSC 213**, and
2. Either **CPSC 221** or **DSCI 221**

Having completed CPSC 210 is good preparation, but it's not a formal prerequisite for CPSC 313.

For the authoritative and most current wording, see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**No-RAG answer** — groundedness 0.33 (1/3) claims:

# Prerequisites for CPSC 313

To take CPSC 313 (Computer Hardware and Operating Systems), you need:

- **CPSC 210** ✓ (you've completed this)
- **CPSC 221** (Basic Algorithms and Data Structures)

So you still need to complete **CPSC 221** before enrolling in CPSC 313.

### q009 — specific — gold [3385] Bachelor of Science — General Degree Requirements [2025/26]

**Q:** In the 2025/26 calendar, what is the minimum number of credits required for a B.Sc. degree?

**Reference:** A minimum of 120 credits (a major, double major, or General Science option requires at least 120 credits but may require more).

**RAG answer** — groundedness 0.80 (4/5) claims:

In the 2025/26 calendar, the minimum number of credits required for a B.Sc. degree depends on your degree option:

- **Major, Combined Major, Double Major, or General Science**: 120 credits minimum
- **Honours or Combined Honours**: 132 credits minimum

Note that these are minimums; your specific specialization may require more credits.

For the authoritative and most current wording, see: https://archive.calendar.ubc.ca/vancouver/2526/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements/index.html

**No-RAG answer** — groundedness 0.67 (2/3) claims:

The minimum number of credits required for a B.Sc. degree at UBC Vancouver is **120 credits**.

This includes requirements across science courses, breadth requirements, and electives. Specific program requirements vary by major, but 120 credits is the baseline for degree completion.

### q010 — specific — gold [1900] Bachelor of Science — General Degree Requirements [2026/27]

**Q:** According to the current 2026/27 calendar, what is the minimum number of credits required for a B.Sc. degree?

**Reference:** A minimum of 120 credits (a major, double major, or General Science option requires at least 120 credits but may require more).

**RAG answer** — groundedness 1.00 (3/3) claims:

According to the current 2026/27 calendar, the minimum number of credits required for a B.Sc. degree is **120 credits**.

This applies to students pursuing a major, combined major, double major, or General Science option. Students in an honours or combined honours program may need between 120-132 credits depending on their specific specialization.

For authoritative details, see: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements

**No-RAG answer** — groundedness 0.50 (1/2) claims:

The minimum number of credits required for a B.Sc. degree at UBC Vancouver is **120 credits**.

This includes completing degree requirements across sciences courses, electives, and breadth requirements, though the exact distribution varies by program specialization.

### q011 — specific — gold [128] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27]

**Q:** Does a B.A. student who entered the program in 2024/25 or later have to complete a language requirement?

**Reference:** No. Their five degree requirements are Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum — there is no separate language requirement (that applies to students who entered in 2023/24 or earlier).

**RAG answer** — groundedness 0.25 (1/4) claims:

Based on the excerpts provided, the language requirement is specific to **Linguistics majors**, not all B.A. students. 

Linguistics majors are required to complete 6 credits of coursework in a single language other than English. This requirement applies to all Linguistics students and cannot be waived based on existing language competency.

However, the general B.A. degree requirements for students entering in 2024/25 or later do not include a language requirement as one of the five mandatory requirements (Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum).

So the answer depends on your major: if you're a Linguistics major, yes; if you're pursuing a different B.A. major, no.

For the most current information, see:
- https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202425-or-later

**No-RAG answer** — groundedness 0.00 (0/4) claims:

Yes. B.A. students entering in 2024/25 or later must complete a language requirement. You need to demonstrate proficiency in a language other than English, which can be satisfied through:

- Completing a language course (typically 3 credits at the 100-level or higher)
- Passing a proficiency exam
- Providing evidence of prior study or native fluency

The specific language and level of proficiency needed may vary by program, so check your degree audit or faculty requirements for details.

### q012 — specific — gold [0] Academic Standing [2026/27]

**Q:** What are the three levels of academic standing at UBC?

**Reference:** In Good Standing; On Academic Probation; and Failed, Required to Withdraw. All students are In Good Standing on initial entry to the University.

**RAG answer** — groundedness 0.60 (3/5) claims:

The three levels of academic standing at UBC are:

1. **In Good Standing** — the default status for all students upon initial entry to the University
2. **On Academic Probation** — a status a student may move to based on academic performance, which may come with registration restrictions
3. **Failed, Required to Withdraw** — the status assigned when a student's academic performance falls below required standards, resulting in a mandatory 12-month withdrawal from studies

For the authoritative and most current wording, see the Academic Standing page: https://vancouver.calendar.ubc.ca/campus-wide-policies-and-regulations/academic-standing

**No-RAG answer** — groundedness 0.00 (0/6) claims:

The three levels of academic standing at UBC Vancouver are:

1. **Good Standing** – Students meeting satisfactory academic progress requirements
2. **Academic Probation** – Students whose GPA falls below 2.0 or who fail to meet progress standards
3. **Dismissed** – Students who do not improve their standing while on probation and are required to withdraw

Students on probation typically have one term to raise their GPA back to 2.0 or above to return to good standing. Failure to do so results in academic dismissal.

### g001 — general — gold [0] Academic Standing [2026/27]

**Q:** What happens to a UBC student's academic standing, and what standings exist?

**Reference:** There are three levels of academic standing: In Good Standing, On Academic Probation, and Failed, Required to Withdraw. Students enter the University In Good Standing.

**RAG answer** — groundedness 0.92 (11/12) claims:

# Academic Standing at UBC

UBC has three levels of academic standing:

1. **In Good Standing** — All students start in this status when they first enter the University.

2. **On Academic Probation** — A student may be placed on academic probation based on their academic performance. Students on probation may have restrictions placed on their registration (which vary by faculty).

3. **Failed, Required to Withdraw** — Students who don't meet academic requirements will be required to withdraw from their studies for 12 months. However, if a student is already registered in and attending courses when this standing is determined after the last withdrawal date, they may complete those courses.

Students who were previously required to withdraw and successfully appeal for readmission may be placed back on academic probation.

A student who receives a "Failed, Required to Withdraw" standing and wishes to continue their studies immediately must appeal; they cannot register for or attend courses while awaiting the appeal outcome (except if already enrolled as noted above).

Note that specific faculties may have additional or more detailed requirements for academic standing. For example, the Faculty of Forestry and Environmental Stewardship has particular GPA and credit completion thresholds that determine standing.

For the most current and complete information, see the Academic Standing page: https://vancouver.calendar.ubc.ca/campus-wide-policies-and-regulations/academic-standing

**No-RAG answer** — groundedness 0.15 (2/13) claims:

# UBC Academic Standings

UBC uses these academic standings:

## **Good Standing**
Student is in good academic progress with no restrictions.

## **Academic Probation**
- Triggered when GPA falls below 2.0 in a term
- Student remains enrolled but is monitored
- Must improve GPA to 2.0+ by the next grading period

## **Required to Withdraw (RTW)**
- Applied when a student on probation fails to reach 2.0 GPA again
- Student must leave UBC for a minimum period (typically at least one full year)
- Can reapply after the required absence period

## **Suspension**
- Disciplinary action for academic misconduct or serious policy violations
- Temporary removal from the institution

## **Expulsion**
- Permanent removal from UBC
- Reserved for serious or repeated violations

## Key Points:
- **GPA Calculation**: Based on coursework in degree program (some courses excluded)
- **Appeals**: Students can appeal standing decisions through their Faculty
- **International Students**: Academic standing affects study permit validity

Your specific Faculty may have slightly different thresholds or procedures, so check your program-specific regulations in the UBC Calendar if you need details for your situation.

### g002 — general — gold [1900] Bachelor of Science — General Degree Requirements [2026/27]

**Q:** Roughly how many credits does a UBC B.Sc. degree require?

**Reference:** A minimum of 120 credits; some options require more.

**RAG answer** — groundedness 0.75 (3/4) claims:

A UBC B.Sc. degree requires a minimum of **120 credits** for a major, combined major, double major, or General Science option. An honours or combined honours option requires between 120 and 132 credits depending on your specific program.

The degree must be completed within a maximum of 180 attempted credits.

For the most current and detailed requirements, see the official calendar page: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements

**No-RAG answer** — groundedness 1.00 (1/1) claims:

A UBC B.Sc. degree requires **120 credits** to complete.

This typically takes 4 years of full-time study, with students taking around 30 credits per year (usually 5 courses per term, 2 terms per year at 3 credits each).

### g003 — general — gold [5] Computer Science, Faculty of Science [2026/27]

**Q:** What is CPSC 110 at UBC about?

**Reference:** CPSC 110, Computation, Programs, and Programming (4 credits), covers fundamental program and computation structures.

**RAG answer** — groundedness 0.25 (1/4) claims:

Based on the calendar information provided, CPSC_V 110 is a first-year Computer Science course designed for students pursuing Computer Science specializations or who plan to take CPSC_V 210. It's the recommended foundational course for students continuing in Computer Science.

The calendar excerpts don't provide a detailed course description of what topics CPSC_V 110 covers specifically. For more detailed information about the course content, I'd recommend:

1. Consulting the course selection guide at https://www.cs.ubc.ca/students/undergrad/courses/choose-your-first-cour…
2. Visiting the Department of Computer Science's undergraduate website at http://www.cs.ubc.ca/students/undergrad
3. Contacting the Department of Computer Science directly

For the official course description, you can also check the full course descriptions at https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv.

**No-RAG answer** — groundedness 0.14 (1/7) claims:

CPSC 110 is UBC's foundational computer science course focused on **computational thinking and program design**. 

The course teaches students how to:
- Design and write programs using a functional programming approach (typically using languages like Racket or Python)
- Break down problems systematically
- Understand data structures and function design
- Apply design recipes to solve computational problems

It's a 3-credit course that serves as the entry point for most computer science majors and is open to students with no prior programming experience. CPSC 110 emphasizes problem-solving methodology and is a prerequisite for most upper-level CS courses like CPSC 210.

### g004 — general — gold [128, 114] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27] (+1 more)

**Q:** What kinds of requirements does a UBC Bachelor of Arts student have to complete?

**Reference:** B.A. students complete a set of faculty-wide degree requirements — for current entrants (2024/25 or later): Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum; earlier cohorts also had separate Language, Science, and Literature requirements.

**RAG answer** — groundedness 0.12 (1/8) claims:

# Bachelor of Arts Requirements

Based on the calendar, UBC Bachelor of Arts students must complete several key requirements:

## Writing and Research Requirement

This has two components:

**Writing Component:** You must successfully complete 3 credits in research and writing through an approved course such as Arts One, ASTU_V 100, ASTU_V 101, CAP_V 100, ENGL_V 100, or WRDS_V 150/151/350. This must be completed before reaching Year 3 standing. If you're admitted from secondary school, you should attempt it in your first 30 credits and must complete it before reaching 54 credits. Transfer students must attempt it in their first Winter Session.

**Research Component:** (The excerpts provided don't include the full details of this component.)

## Language Requirement

You must satisfy the Language Requirement in one of three ways:
1. Complete a non-English language course at BC Grade 12 level or equivalent while still in secondary school
2. Pass a language proficiency test
3. Complete language coursework at UBC to reach or exceed specified proficiency levels

The excerpts don't provide a complete picture of all degree requirements (such as breadth requirements, electives, and total credit hours). For comprehensive details on all Bachelor of Arts requirements, please consult the official Faculty of Arts calendar pages:
- For students entering 2024/25 or later: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202425-or-later
- For students entering 2023/24 or earlier: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202324-or-earlier

**No-RAG answer** — groundedness 0.00 (0/11) claims:

# UBC Bachelor of Arts Requirements

A UBC BA student must complete **120 credits** total, distributed as follows:

## Core Requirements
- **English Composition (3 credits)**: WRDS 150 or equivalent
- **Breadth Requirements (36 credits minimum)**: Courses across at least 4 of these 5 faculties:
  - Science
  - Social Sciences
  - Arts
  - Applied Science
  - Commerce

## Major/Minor
- **Major (30-36 credits)**: Completion of a chosen discipline
- **Minor (18 credits)**: Optional but common; can substitute with second major or additional electives

## Upper-Level Requirement
- **Minimum 42 upper-level credits** (300-level and above)

## Electives
- Remaining credits to reach 120 can be from any eligible courses

## GPA Requirement
- **2.0 GPA minimum** to graduate

## Key Notes
- Students typically declare their major by end of second year
- Specific major programs have additional prerequisites and course requirements
- Some programs (like combined majors) may have different credit allocations

Would you like details about a specific major or concentration?

