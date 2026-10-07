# UBCHelper eval — full-16576

2026-10-06T22:22:47 · 12 questions · k=4 · judge on

Models: chat=`claude-haiku-4-5`, judge=`google/gemma-4-e4b`, embed=`text-embedding-3-small` · corpus=16576 · retrieval=hybrid_rerank

## Summary

| metric | score |
|--------|-------|
| hit@4 | 0.833 |
| recall@4 | 0.708 |
| MRR | 0.667 |
| faithfulness | 0.903 |
| answer_relevancy | 0.774 |
| context_precision | 0.859 |
| context_recall | 0.792 |
| **hallucination_rate** | **0.097** |

## By category

| category | n | hit@4 | recall@4 | MRR |
|---|---|---|---|---|
| code-lookup | 5 | 0.800 | 0.700 | 0.800 |
| collision | 3 | 1.000 | 1.000 | 0.667 |
| multi-hop | 3 | 0.667 | 0.333 | 0.333 |
| policy | 1 | 1.000 | 1.000 | 1.000 |

Small buckets: one item flipping moves an n=3 category by 0.33. Treat the ordering as real and the decimals as noisy.

## Stage-1 shortlist recall

Recall over the 50-candidate shortlist handed to the reranker, before it reorders anything. The gap between @20 and @50 is the recall that a 20-wide stage 1 would never have shown the reranker at all.

| depth | recall |
|---|---|
| stage-1 recall@20 | 0.750 |
| stage-1 recall@50 | 0.917 |
| final recall@4 (after rerank) | 0.708 |

## Questions

### q001 — hit — gold [10, 182]

**Q:** What are the prerequisites for CPSC 221?

**Reference:** One of CPSC 210 or CPEN 221, and either one of CPSC 121, MATH 220 (or MATH_O 220), or a score of 68% or higher in MATH 226.

**Retrieved:** [182] Computer Science, Faculty of Science [2025/26] · [10] Computer Science, Faculty of Science [2026/27] · [219] Computer Science, Faculty of Science [2025/26] · [232] Computer Science, Faculty of Science [2025/26]

**Answer:** The prerequisites for CPSC 221 are:

One of CPSC 210 or CPEN 221, **and** either:
- (a) one of CPSC 121, MATH 220, or MATH O 220, or
- (b) a score of 68% or higher in MATH 226

Note: The exact course codes have been updated slightly between calendar editions. For the current 2026/27 calendar, the prerequisite refers to CPSC_V 210, CPEN_V 221, and MATH_V 220 (or MATH_O 220).

For the most current and authoritative wording, see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**Scores:** rr 1.00 · faithfulness 0.833 · answer_relevancy 0.864 · context_precision 1.000 · context_recall 1.000

### q002 — hit — gold [24, 197]

**Q:** What are the prerequisites for CPSC 320?

**Reference:** CPSC 221 (or DSCI 221) plus at least 3 credits of MATH or STAT at the 200 level or above (the 2025/26 edition also accepted COMM 291 or BIOL 300 for the second part).

**Retrieved:** [197] Computer Science, Faculty of Science [2025/26] · [42] Computer Science, Faculty of Science [2026/27] · [214] Computer Science, Faculty of Science [2025/26] · [216] Computer Science, Faculty of Science [2025/26]

**Answer:** According to the calendar, the prerequisites for CPSC 320 are:

1. **CPSC 221 or DSCI 221**, AND
2. **At least 3 credits** from: COMM 291, BIOL 300, or MATH or STAT courses at the 200 level or above

For the most current and authoritative wording, see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**Scores:** rr 1.00 · faithfulness 1.000 · answer_relevancy 0.836 · context_precision 1.000 · context_recall 1.000

### q003 — hit — gold [20, 193]

**Q:** What are the prerequisites for CPSC 313?

**Reference:** CPSC 213, and either CPSC 221 or DSCI 221.

**Retrieved:** [20] Computer Science, Faculty of Science [2026/27] · [193] Computer Science, Faculty of Science [2025/26] · [213] Computer Science, Faculty of Science [2025/26] · [212] Computer Science, Faculty of Science [2025/26]

**Answer:** The prerequisites for CPSC 313 (Computer Hardware and Operating Systems) are:

- CPSC 213, **and**
- Either CPSC 221 or DSCI 221

For the most current and authoritative wording, see the Computer Science course descriptions page: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**Scores:** rr 1.00 · faithfulness 1.000 · answer_relevancy 0.846 · context_precision 1.000 · context_recall 1.000

### q004 — hit — gold [580, 2196]

**Q:** Which courses satisfy the prerequisite for MATH 200, Calculus III?

**Reference:** One of MATH 101, MATH 103, MATH 105, MATH 121, SCIE 001, MATH_O 101, or MATH_O 103.

**Retrieved:** [580] Mathematics, Faculty of Science [2026/27] · [2196] Mathematics, Faculty of Science [2025/26] · [2225] Mathematics, Faculty of Science [2025/26] · [609] Mathematics, Faculty of Science [2026/27]

**Answer:** For the 2026/27 calendar, the courses that satisfy the prerequisite for MATH_V 200 (Calculus III) are:

- MATH_V 101
- MATH_V 103
- MATH_V 105
- MATH_V 121
- SCIE_V 001
- MATH_O 101
- MATH_O 103

You need to complete one of these courses before enrolling in MATH_V 200.

For the most current and authoritative information, please see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/mathv

**Scores:** rr 1.00 · faithfulness 0.333 · answer_relevancy 0.773 · context_precision 1.000 · context_recall 1.000

### q005 — miss — gold [5, 177]

**Q:** How many credits is CPSC 110 worth and what does it cover?

**Reference:** CPSC 110 (Computation, Programs, and Programming) is worth 4 credits and covers fundamental program and computation structures.

**Retrieved:** [327] Bachelor of Science — Computer Science [2025/26] · [149] Bachelor of Science — Computer Science [2026/27] · [146] Bachelor of Science — Computer Science [2026/27] · [318] Bachelor of Science — Computer Science [2025/26]

**Answer:** CPSC 110 is worth **4 credits**.

However, the excerpts provided do not contain information about what CPSC 110 covers—they only specify the credit value and mention it as a first-year requirement for Computer Science programs.

For details on course content, I'd recommend checking the course description in the UBC Calendar or contacting the Department of Computer Science directly. You can find current program requirements at https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/computer-science

**Scores:** rr 0.00 · faithfulness 1.000 · answer_relevancy 0.729 · context_precision 1.000 · context_recall 1.000

### q006 — miss — gold [114, 128]

**Q:** Compare the B.A. degree requirements for students who entered the program in 2023/24 with those who entered in 2024/25 or later.

**Reference:** Students entering 2023/24 or earlier must complete seven requirements: Writing and Research, Language, Science, Literature, Outside, Upper-level, and Arts Credit Minimum. Students entering 2024/25 or later complete five: Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum — the separate Language, Science, and Literature requirements are folded into the Ways of Knowing Breadth requirement.

**Retrieved:** [2916] Bachelor of Arts — Second Degree Studies [2025/26] · [1295] Bachelor of Arts — Second Degree Studies [2026/27] · [2589] Dual Degree Program Option: Bachelor of Arts, UBC and Sciences Po [2025/26] · [963] Dual Degree Program Option: Bachelor of Arts, UBC and Sciences Po [2026/27]

**Answer:** I don't have enough information in the provided excerpts to make that comparison. The excerpts mention that second-degree students and dual degree students must fulfill "normal B.A. Degree Requirements for students who entered the program in 2023/24 or earlier or Degree Requirements for students who entered the program in 2024/25 or later," but they don't actually detail what those specific requirements are or how they differ between cohorts.

To see the actual degree requirements for each cohort, you would need to consult the full B.A. Degree Requirements pages in the UBC Calendar:
- https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts (for the current 2026/27 requirements)
- https://archive.calendar.ubc.ca/vancouver/2526/faculties-colleges-and-schools/faculty-arts/bachelor-arts/ (for the 2025/26 requirements)

These pages should contain the detailed requirements for each entry cohort.

**Scores:** rr 0.00 · faithfulness 1.000 · answer_relevancy 0.632 · context_precision 0.000 · context_recall 0.000

### q007 — hit — gold [1646, 1668]

**Q:** How does admission to the Bachelor of Computer Science program differ from B.Sc. admission from secondary school?

**Reference:** Bachelor of Computer Science admission is a competitive selection process evaluating applicants on academic and other criteria (not every qualified applicant is admitted); B.Sc. admission from secondary school requires starting first year in September of the Winter session of admission (January starts are not permitted).

**Retrieved:** [1645] Bachelor of Computer Science [2026/27] · [1646] Bachelor of Computer Science [2026/27] · [1654] Bachelor of Computer Science [2026/27] · [1644] Bachelor of Computer Science [2026/27]

**Answer:** The Bachelor of Computer Science (B.C.S.) program is fundamentally different from a typical B.Sc. program in that it's specifically designed as a **second bachelor's degree** for students who already hold a recognized bachelor's degree in a non-computer science field.

Key differences in admission include:

**B.C.S. Admission Requirements:**
- You must have already completed a recognized bachelor's degree in a field that doesn't overlap with computer science
- You need to meet three prerequisites: BC Principles of Mathematics 12 (or Pre-calculus 12), a communication requirement (3 credits), and computer literacy or equivalent experience
- Admission is highly competitive and based on both academic criteria (overall record, most recent 30-credit average with a minimum B- average required) and non-academic criteria (evaluated through letters of reference, work history self-assessment, and a statement of interest)
- The program Admission Committee may interview selected applicants

**Regular B.Sc. Admission (from secondary school):**
The excerpts provided don't detail standard B.Sc. admission from secondary school, so I cannot make a direct comparison based on these materials.

The B.C.S. is fundamentally a postgraduate program for career-changers or people seeking to add computer science credentials to their existing degree, rather than an undergraduate program for secondary school graduates.

For complete details, see: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-computer-science

**Scores:** rr 0.50 · faithfulness 1.000 · answer_relevancy 0.711 · context_precision 1.000 · context_recall 0.667

### q008 — hit — gold [20, 10]

**Q:** I have finished CPSC 210. What else do I need to complete before I can take CPSC 313?

**Reference:** CPSC 313 requires CPSC 213 and either CPSC 221 or DSCI 221. CPSC 221 in turn requires (beyond CPSC 210) one of CPSC 121, MATH 220, MATH_O 220, or a 68%+ score in MATH 226. So after CPSC 210 you still need CPSC 213 and CPSC 221 (with its discrete-math prerequisite).

**Retrieved:** [193] Computer Science, Faculty of Science [2025/26] · [20] Computer Science, Faculty of Science [2026/27] · [917] Bachelor of Arts — Computer Science [2026/27] · [2540] Bachelor of Arts — Computer Science [2025/26]

**Answer:** Based on the prerequisites for CPSC_V 313, you need to complete:

- **CPSC_V 213**, and
- **Either CPSC_V 221 or DSCI_V 221**

Having finished CPSC_V 210 is good preparation, but it's not a formal prerequisite for CPSC_V 313.

For the authoritative course description and most current prerequisites, see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**Scores:** rr 0.50 · faithfulness 0.667 · answer_relevancy 0.784 · context_precision 1.000 · context_recall 0.333

### q009 — hit — gold [3385]

**Q:** In the 2025/26 calendar, what is the minimum number of credits required for a B.Sc. degree?

**Reference:** A minimum of 120 credits (a major, double major, or General Science option requires at least 120 credits but may require more).

**Retrieved:** [3386] Bachelor of Science — General Degree Requirements [2025/26] · [3385] Bachelor of Science — General Degree Requirements [2025/26] · [3315] Bachelor of Science — Credit at UBC and Elsewhere [2025/26] · [1900] Bachelor of Science — General Degree Requirements [2026/27]

**Answer:** In the 2025/26 calendar, the minimum number of credits required for a B.Sc. degree depends on which degree option you pursue:

- **Major, Combined Major, Double Major, or General Science**: 120 credits minimum
- **Honours or Combined Honours**: 132 credits minimum

For more details, see the official calendar page: https://archive.calendar.ubc.ca/vancouver/2526/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements/index.html

**Scores:** rr 0.50 · faithfulness 1.000 · answer_relevancy 0.781 · context_precision 0.917 · context_recall 1.000

### q010 — hit — gold [1900]

**Q:** According to the current 2026/27 calendar, what is the minimum number of credits required for a B.Sc. degree?

**Reference:** A minimum of 120 credits (a major, double major, or General Science option requires at least 120 credits but may require more).

**Retrieved:** [1900] Bachelor of Science — General Degree Requirements [2026/27] · [1901] Bachelor of Science — General Degree Requirements [2026/27] · [1831] Bachelor of Science — Credit at UBC and Elsewhere [2026/27] · [2051] Bachelor of Science — Recognition of Academic Achievement [2026/27]

**Answer:** According to the current 2026/27 calendar, the minimum number of credits required for a B.Sc. degree is **120 credits**.

This applies to most degree options including a major, combined major, double major, or General Science option. Honours or combined honours options require between 120-132 credits depending on the specific specialization.

For details, see: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements

**Scores:** rr 1.00 · faithfulness 1.000 · answer_relevancy 0.772 · context_precision 1.000 · context_recall 1.000

### q011 — hit — gold [128]

**Q:** Does a B.A. student who entered the program in 2024/25 or later have to complete a language requirement?

**Reference:** No. Their five degree requirements are Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum — there is no separate language requirement (that applies to students who entered in 2023/24 or earlier).

**Retrieved:** [2767] Bachelor of Arts — Linguistics [2025/26] · [128] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27] · [300] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [301] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26]

**Answer:** Based on the excerpts provided, there is no general language requirement for all B.A. students who entered in 2024/25 or later. The five degree requirements for these students are: Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum—none of which specify a language requirement.

However, **if you are majoring in Linguistics specifically**, then yes, you must complete 6 credits of coursework in a single language other than English. This is a program-specific requirement for Linguistics majors, not a general B.A. requirement.

For the most current and complete information on B.A. degree requirements, see: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202425-or-later

For Linguistics-specific requirements: https://archive.calendar.ubc.ca/vancouver/2526/faculties-colleges-and-schools/faculty-arts/bachelor-arts/linguistics/index.html

**Scores:** rr 0.50 · faithfulness 1.000 · answer_relevancy 0.687 · context_precision 0.639 · context_recall 0.500

### q012 — hit — gold [0]

**Q:** What are the three levels of academic standing at UBC?

**Reference:** In Good Standing; On Academic Probation; and Failed, Required to Withdraw. All students are In Good Standing on initial entry to the University.

**Retrieved:** [0] Academic Standing [2026/27] · [431] Course Standings [2026/27] · [430] Course Standings [2026/27] · [13784] Academic Regulations [2026/27]

**Answer:** The three levels of academic standing at UBC are:

1. **In Good Standing**
2. **On Academic Probation**
3. **Failed, Required to Withdraw**

All students enter the University in Good Standing initially. A student's standing may change to On Academic Probation or Failed, Required to Withdraw based on their academic performance.

For the authoritative and most current wording, see: https://vancouver.calendar.ubc.ca/campus-wide-policies-and-regulations/academic-standing

**Scores:** rr 1.00 · faithfulness 1.000 · answer_relevancy 0.876 · context_precision 0.750 · context_recall 1.000

