# UBCHelper eval — full

2026-09-07T23:42:26 · 12 questions · k=4 · judge on

Models: chat=`claude-haiku-4-5`, judge=`google/gemma-4-e4b`, embed=`text-embedding-3-small` · corpus=3770 · retrieval=hybrid_rerank

## Summary

| metric | score |
|--------|-------|
| hit@4 | 0.667 |
| recall@4 | 0.625 |
| MRR | 0.542 |
| faithfulness | 0.906 |
| answer_relevancy | 0.759 |
| context_precision | 0.778 |
| context_recall | 0.714 |
| **hallucination_rate** | **0.094** |

## Questions

### q001 — hit — gold [10, 182]

**Q:** What are the prerequisites for CPSC 221?

**Reference:** One of CPSC 210 or CPEN 221, and either one of CPSC 121, MATH 220 (or MATH_O 220), or a score of 68% or higher in MATH 226.

**Retrieved:** [182] Computer Science, Faculty of Science [2025/26] · [10] Computer Science, Faculty of Science [2026/27] · [232] Computer Science, Faculty of Science [2025/26] · [339] Bachelor of Science — Computer Science [2025/26]

**Answer:** For the current 2026/27 calendar, the prerequisites for CPSC_V 221 are:

One of CPSC_V 210 or CPEN_V 221, **and** either:
- (a) one of CPSC_V 121, MATH_V 220, or MATH_O 220, **or**
- (b) a score of 68% or higher in MATH_V 226

For the most current and authoritative wording, see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**Scores:** rr 1.00 · faithfulness 1.000 · answer_relevancy 0.829 · context_precision 1.000 · context_recall 1.000

### q002 — miss — gold [24, 197]

**Q:** What are the prerequisites for CPSC 320?

**Reference:** CPSC 221 (or DSCI 221) plus at least 3 credits of MATH or STAT at the 200 level or above (the 2025/26 edition also accepted COMM 291 or BIOL 300 for the second part).

**Retrieved:** [42] Computer Science, Faculty of Science [2026/27] · [214] Computer Science, Faculty of Science [2025/26] · [339] Bachelor of Science — Computer Science [2025/26] · [170] Bachelor of Science — Computer Science [2026/27]

**Answer:** Based on the excerpts provided, I don't see the specific prerequisites for CPSC 320 listed directly in the course description section.

However, I can note that the Cognitive Systems program requirements indicate that students must achieve a grade of greater than 72% in their statistics course (STAT 200, 201, or 251) in order to be admitted to CPSC 320, suggesting this is a prerequisite or co-requisite consideration.

For the complete and authoritative prerequisites for CPSC 320, I'd recommend checking the course description page directly:
- https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**Scores:** rr 0.00 · faithfulness 0.500 · answer_relevancy 0.833 · context_precision 0.417 · context_recall 0.400

### q003 — hit — gold [20, 193]

**Q:** What are the prerequisites for CPSC 313?

**Reference:** CPSC 213, and either CPSC 221 or DSCI 221.

**Retrieved:** [20] Computer Science, Faculty of Science [2026/27] · [193] Computer Science, Faculty of Science [2025/26] · [213] Computer Science, Faculty of Science [2025/26] · [212] Computer Science, Faculty of Science [2025/26]

**Answer:** The prerequisites for CPSC 313 (Computer Hardware and Operating Systems) are:

- CPSC 213, **and**
- Either CPSC 221 or DSCI 221

For the current 2026/27 calendar, you can find the official details at https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**Scores:** rr 1.00 · faithfulness 0.500 · answer_relevancy 0.839 · context_precision 1.000 · context_recall 1.000

### q004 — hit — gold [580, 2319]

**Q:** Which courses satisfy the prerequisite for MATH 200, Calculus III?

**Reference:** One of MATH 101, MATH 103, MATH 105, MATH 121, SCIE 001, MATH_O 101, or MATH_O 103.

**Retrieved:** [580] Mathematics, Faculty of Science [2026/27] · [2319] Mathematics, Faculty of Science [2025/26] · [2348] Mathematics, Faculty of Science [2025/26] · [609] Mathematics, Faculty of Science [2026/27]

**Answer:** For MATH_V 200 (Calculus III) in the current 2026/27 calendar, the prerequisite is one of the following courses:

- MATH_V 101
- MATH_V 103
- MATH_V 105
- MATH_V 121
- SCIE_V 001
- MATH_O 101
- MATH_O 103

You need to complete just one of these courses to satisfy the prerequisite for MATH_V 200.

For the authoritative and most current wording, please consult the official calendar at: https://vancouver.calendar.ubc.ca/course-descriptions/subject/mathv

**Scores:** rr 1.00 · faithfulness 0.875 · answer_relevancy 0.814 · context_precision 1.000 · context_recall 1.000

### q005 — miss — gold [5, 177]

**Q:** How many credits is CPSC 110 worth and what does it cover?

**Reference:** CPSC 110 (Computation, Programs, and Programming) is worth 4 credits and covers fundamental program and computation structures.

**Retrieved:** [146] Bachelor of Science — Computer Science [2026/27] · [2082] Bachelor of Science — Mathematics [2026/27] · [160] Bachelor of Science — Computer Science [2026/27] · [3568] Bachelor of Science — Mathematics [2025/26]

**Answer:** Based on the academic calendar, **CPSC 110 is worth 4 credits**.

However, the excerpts provided do not contain information about what CPSC 110 covers—they only specify its credit value and that it's a required or recommended course in various Computer Science programs.

For details about the course content and topics covered, you would need to consult the course description in the UBC Course Calendar or contact the Department of Computer Science directly.

**Scores:** rr 0.00 · faithfulness 1.000 · answer_relevancy 0.764 · context_precision 1.000 · context_recall 0.667

### q006 — miss — gold [114, 128]

**Q:** Compare the B.A. degree requirements for students who entered the program in 2023/24 with those who entered in 2024/25 or later.

**Reference:** Students entering 2023/24 or earlier must complete seven requirements: Writing and Research, Language, Science, Literature, Outside, Upper-level, and Arts Credit Minimum. Students entering 2024/25 or later complete five: Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum — the separate Language, Science, and Literature requirements are folded into the Ways of Knowing Breadth requirement.

**Retrieved:** [3039] Bachelor of Arts — Second Degree Studies [2025/26] · [1295] Bachelor of Arts — Second Degree Studies [2026/27] · [2712] Dual Degree Program Option: Bachelor of Arts, UBC and Sciences Po [2025/26] · [963] Dual Degree Program Option: Bachelor of Arts, UBC and Sciences Po [2026/27]

**Answer:** I don't have enough information in the provided excerpts to compare the specific degree requirements between these two cohorts. The excerpts reference that different requirements exist for students who entered in 2023/24 or earlier versus 2024/25 or later, but they don't include the actual details of those requirements—they only point to them.

To see the specific degree requirements for each cohort, you would need to consult the full B.A. Degree Requirements sections in the UBC Calendar. For the current 2026/27 academic year, you can find this at:
https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts

I'd recommend contacting Arts Academic Advising directly if you need a detailed comparison of how the requirements differ between your cohort and another.

**Scores:** rr 0.00 · faithfulness 1.000 · answer_relevancy 0.522 · context_precision 0.000 · context_recall 0.000

### q007 — hit — gold [1769, 1791]

**Q:** How does admission to the Bachelor of Computer Science program differ from B.Sc. admission from secondary school?

**Reference:** Bachelor of Computer Science admission is a competitive selection process evaluating applicants on academic and other criteria (not every qualified applicant is admitted); B.Sc. admission from secondary school requires starting first year in September of the Winter session of admission (January starts are not permitted).

**Retrieved:** [1768] Bachelor of Computer Science [2026/27] · [1769] Bachelor of Computer Science [2026/27] · [1767] Bachelor of Computer Science [2026/27] · [3275] Bachelor of Science — Admission and Transfer [2025/26]

**Answer:** Based on the excerpts provided, there are several key differences between B.C.S. and B.Sc. admission from secondary school:

**Bachelor of Computer Science (B.C.S.):**
- Requires candidates to have already completed a recognized bachelor's degree in a non-overlapping field
- A two-year program designed as a second bachelor's degree
- Admission is based on a competitive selection process evaluating both academic criteria (overall record and most recent 30-credit average with a minimum B- requirement) and non-academic criteria (motivation, maturity, integrity, etc.)
- Non-academic evaluation involves two letters of reference, a self-assessment of work history, and a statement of interest
- Some applicants may be interviewed before admission decisions

**B.Sc. from Secondary School:**
- Admits students directly from high school with no prior degree requirement
- Students are expected to start in September of the admission year
- Admissibility is based on high school course performance, academic rigor of the program, and evidence of learning/achievements both in and out of school
- Many students are admitted on interim grades

In essence, the B.C.S. is a second-degree program for university graduates, while B.Sc. admission from secondary school is for high school students entering their first bachelor's degree.

For the most current and detailed information, see https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-computer-science

**Scores:** rr 0.50 · faithfulness 1.000 · answer_relevancy 0.774 · context_precision 0.500 · context_recall 1.000

### q008 — miss — gold [20, 10]

**Q:** I have finished CPSC 210. What else do I need to complete before I can take CPSC 313?

**Reference:** CPSC 313 requires CPSC 213 and either CPSC 221 or DSCI 221. CPSC 221 in turn requires (beyond CPSC 210) one of CPSC 121, MATH 220, MATH_O 220, or a 68%+ score in MATH 226. So after CPSC 210 you still need CPSC 213 and CPSC 221 (with its discrete-math prerequisite).

**Retrieved:** [917] Bachelor of Arts — Computer Science [2026/27] · [2663] Bachelor of Arts — Computer Science [2025/26] · [154] Bachelor of Science — Computer Science [2026/27] · [160] Bachelor of Science — Computer Science [2026/27]

**Answer:** I don't have information in the provided excerpts about the prerequisites for CPSC 313. The excerpts only show that CPSC 313 is a required upper-level course in the Computer Science programs, but they don't list what courses must be completed before taking it.

To find the specific prerequisites for CPSC 313, you should check the course description in the UBC Vancouver Academic Calendar at https://vancouver.calendar.ubc.ca/ or contact an academic advisor in the Computer Science program.

**Scores:** rr 0.00 · faithfulness 1.000 · answer_relevancy 0.774 · context_precision 1.000 · context_recall 0.000

### q009 — hit — gold [3508]

**Q:** In the 2025/26 calendar, what is the minimum number of credits required for a B.Sc. degree?

**Reference:** A minimum of 120 credits (a major, double major, or General Science option requires at least 120 credits but may require more).

**Retrieved:** [3509] Bachelor of Science — General Degree Requirements [2025/26] · [3508] Bachelor of Science — General Degree Requirements [2025/26] · [3438] Bachelor of Science — Credit at UBC and Elsewhere [2025/26] · [2023] Bachelor of Science — General Degree Requirements [2026/27]

**Answer:** In the 2025/26 calendar, the minimum number of credits required for a B.Sc. degree depends on which degree option you pursue:

- **Major, Combined Major, Double Major, or General Science option**: 120 credits minimum
- **Honours or Combined Honours option**: 132 credits minimum

Note that these are minimums; your specific specialization may require more credits. Additionally, you must complete your degree within a maximum of 180 attempted credits.

For the authoritative and most current wording, see: https://archive.calendar.ubc.ca/vancouver/2526/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements/index.html

**Scores:** rr 0.50 · faithfulness 1.000 · answer_relevancy 0.767 · context_precision 0.917 · context_recall 1.000

### q010 — hit — gold [2023]

**Q:** According to the current 2026/27 calendar, what is the minimum number of credits required for a B.Sc. degree?

**Reference:** A minimum of 120 credits (a major, double major, or General Science option requires at least 120 credits but may require more).

**Retrieved:** [2023] Bachelor of Science — General Degree Requirements [2026/27] · [2024] Bachelor of Science — General Degree Requirements [2026/27] · [1954] Bachelor of Science — Credit at UBC and Elsewhere [2026/27] · [2174] Bachelor of Science — Recognition of Academic Achievement [2026/27]

**Answer:** According to the 2026/27 calendar, the minimum number of credits required for a B.Sc. degree is **120 credits**.

This applies to a major, combined major, double major, or General Science option. However, some degree options require more:

- **Honours or combined honours** options require 120 to 132 credits (as specified by the department's specialization)
- **Dual degrees** require more than 120 credits, though some combinations may be completed in less than 180 credits

For authoritative and current details, see: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements

**Scores:** rr 1.00 · faithfulness 1.000 · answer_relevancy 0.656 · context_precision 1.000 · context_recall 1.000

### q011 — hit — gold [128]

**Q:** Does a B.A. student who entered the program in 2024/25 or later have to complete a language requirement?

**Reference:** No. Their five degree requirements are Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum — there is no separate language requirement (that applies to students who entered in 2023/24 or earlier).

**Retrieved:** [2890] Bachelor of Arts — Linguistics [2025/26] · [128] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27] · [2903] Bachelor of Arts — Linguistics [2025/26] · [2285] Bachelor of International Economics — Degree Requirements for students who enter the  program in 2024/25 or later [2026/27]

**Answer:** Based on the excerpts provided, I cannot definitively answer this question for a general B.A. student entering in 2024/25 or later.

The excerpts show that the Bachelor of Arts degree has five general requirements (Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum), but they don't specify whether a language requirement is part of those general requirements for all B.A. students.

The language requirement **is** clearly mandatory for students majoring specifically in Linguistics or Speech Sciences, but the excerpts don't clarify whether it applies to all B.A. students or only to those with particular majors.

For the authoritative answer, I'd recommend checking the full Bachelor of Arts degree requirements page for students entering in 2024/25 or later at: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202425-or-later

**Scores:** rr 0.50 · faithfulness 1.000 · answer_relevancy 0.700 · context_precision 0.500 · context_recall 0.500

### q012 — hit — gold [0]

**Q:** What are the three levels of academic standing at UBC?

**Reference:** In Good Standing; On Academic Probation; and Failed, Required to Withdraw. All students are In Good Standing on initial entry to the University.

**Retrieved:** [0] Academic Standing [2026/27] · [431] Course Standings [2026/27] · [430] Course Standings [2026/27] · [3658] Bachelor of Science — Recognition of Academic Achievement [2025/26]

**Answer:** The three levels of academic standing at UBC are:

1. **In Good Standing** — the status all students have when they initially enter the University
2. **On Academic Probation** — a status a student may move to based on academic performance
3. **Failed, Required to Withdraw** — a status indicating the student must withdraw from their studies for 12 months

For authoritative details, see the Academic Standing page: https://vancouver.calendar.ubc.ca/campus-wide-policies-and-regulations/academic-standing

**Scores:** rr 1.00 · faithfulness 1.000 · answer_relevancy 0.834 · context_precision 1.000 · context_recall 1.000

