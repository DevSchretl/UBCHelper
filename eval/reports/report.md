# UBCHelper eval — expanded-defaults

2026-09-12T13:53:16 · 12 questions · k=4 · judge off

Models: chat=`claude-haiku-4-5`, judge=`google/gemma-4-e4b`, embed=`text-embedding-3-small` · corpus=16576 · retrieval=hybrid_rerank

## Summary

| metric | score |
|--------|-------|
| hit@4 | 0.833 |
| recall@4 | 0.708 |
| MRR | 0.667 |

## Questions

### q001 — hit — gold [10, 182]

**Q:** What are the prerequisites for CPSC 221?

**Reference:** One of CPSC 210 or CPEN 221, and either one of CPSC 121, MATH 220 (or MATH_O 220), or a score of 68% or higher in MATH 226.

**Retrieved:** [182] Computer Science, Faculty of Science [2025/26] · [10] Computer Science, Faculty of Science [2026/27] · [219] Computer Science, Faculty of Science [2025/26] · [232] Computer Science, Faculty of Science [2025/26]

**Scores:** rr 1.00

### q002 — hit — gold [24, 197]

**Q:** What are the prerequisites for CPSC 320?

**Reference:** CPSC 221 (or DSCI 221) plus at least 3 credits of MATH or STAT at the 200 level or above (the 2025/26 edition also accepted COMM 291 or BIOL 300 for the second part).

**Retrieved:** [197] Computer Science, Faculty of Science [2025/26] · [42] Computer Science, Faculty of Science [2026/27] · [214] Computer Science, Faculty of Science [2025/26] · [216] Computer Science, Faculty of Science [2025/26]

**Scores:** rr 1.00

### q003 — hit — gold [20, 193]

**Q:** What are the prerequisites for CPSC 313?

**Reference:** CPSC 213, and either CPSC 221 or DSCI 221.

**Retrieved:** [20] Computer Science, Faculty of Science [2026/27] · [193] Computer Science, Faculty of Science [2025/26] · [213] Computer Science, Faculty of Science [2025/26] · [212] Computer Science, Faculty of Science [2025/26]

**Scores:** rr 1.00

### q004 — hit — gold [580, 2196]

**Q:** Which courses satisfy the prerequisite for MATH 200, Calculus III?

**Reference:** One of MATH 101, MATH 103, MATH 105, MATH 121, SCIE 001, MATH_O 101, or MATH_O 103.

**Retrieved:** [580] Mathematics, Faculty of Science [2026/27] · [2196] Mathematics, Faculty of Science [2025/26] · [2225] Mathematics, Faculty of Science [2025/26] · [609] Mathematics, Faculty of Science [2026/27]

**Scores:** rr 1.00

### q005 — miss — gold [5, 177]

**Q:** How many credits is CPSC 110 worth and what does it cover?

**Reference:** CPSC 110 (Computation, Programs, and Programming) is worth 4 credits and covers fundamental program and computation structures.

**Retrieved:** [327] Bachelor of Science — Computer Science [2025/26] · [149] Bachelor of Science — Computer Science [2026/27] · [146] Bachelor of Science — Computer Science [2026/27] · [318] Bachelor of Science — Computer Science [2025/26]

**Scores:** rr 0.00

### q006 — miss — gold [114, 128]

**Q:** Compare the B.A. degree requirements for students who entered the program in 2023/24 with those who entered in 2024/25 or later.

**Reference:** Students entering 2023/24 or earlier must complete seven requirements: Writing and Research, Language, Science, Literature, Outside, Upper-level, and Arts Credit Minimum. Students entering 2024/25 or later complete five: Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum — the separate Language, Science, and Literature requirements are folded into the Ways of Knowing Breadth requirement.

**Retrieved:** [2916] Bachelor of Arts — Second Degree Studies [2025/26] · [1295] Bachelor of Arts — Second Degree Studies [2026/27] · [2589] Dual Degree Program Option: Bachelor of Arts, UBC and Sciences Po [2025/26] · [963] Dual Degree Program Option: Bachelor of Arts, UBC and Sciences Po [2026/27]

**Scores:** rr 0.00

### q007 — hit — gold [1646, 1668]

**Q:** How does admission to the Bachelor of Computer Science program differ from B.Sc. admission from secondary school?

**Reference:** Bachelor of Computer Science admission is a competitive selection process evaluating applicants on academic and other criteria (not every qualified applicant is admitted); B.Sc. admission from secondary school requires starting first year in September of the Winter session of admission (January starts are not permitted).

**Retrieved:** [1645] Bachelor of Computer Science [2026/27] · [1646] Bachelor of Computer Science [2026/27] · [1654] Bachelor of Computer Science [2026/27] · [1644] Bachelor of Computer Science [2026/27]

**Scores:** rr 0.50

### q008 — hit — gold [20, 10]

**Q:** I have finished CPSC 210. What else do I need to complete before I can take CPSC 313?

**Reference:** CPSC 313 requires CPSC 213 and either CPSC 221 or DSCI 221. CPSC 221 in turn requires (beyond CPSC 210) one of CPSC 121, MATH 220, MATH_O 220, or a 68%+ score in MATH 226. So after CPSC 210 you still need CPSC 213 and CPSC 221 (with its discrete-math prerequisite).

**Retrieved:** [193] Computer Science, Faculty of Science [2025/26] · [20] Computer Science, Faculty of Science [2026/27] · [917] Bachelor of Arts — Computer Science [2026/27] · [2540] Bachelor of Arts — Computer Science [2025/26]

**Scores:** rr 0.50

### q009 — hit — gold [3385]

**Q:** In the 2025/26 calendar, what is the minimum number of credits required for a B.Sc. degree?

**Reference:** A minimum of 120 credits (a major, double major, or General Science option requires at least 120 credits but may require more).

**Retrieved:** [3386] Bachelor of Science — General Degree Requirements [2025/26] · [3385] Bachelor of Science — General Degree Requirements [2025/26] · [3315] Bachelor of Science — Credit at UBC and Elsewhere [2025/26] · [1900] Bachelor of Science — General Degree Requirements [2026/27]

**Scores:** rr 0.50

### q010 — hit — gold [1900]

**Q:** According to the current 2026/27 calendar, what is the minimum number of credits required for a B.Sc. degree?

**Reference:** A minimum of 120 credits (a major, double major, or General Science option requires at least 120 credits but may require more).

**Retrieved:** [1900] Bachelor of Science — General Degree Requirements [2026/27] · [1901] Bachelor of Science — General Degree Requirements [2026/27] · [1831] Bachelor of Science — Credit at UBC and Elsewhere [2026/27] · [2051] Bachelor of Science — Recognition of Academic Achievement [2026/27]

**Scores:** rr 1.00

### q011 — hit — gold [128]

**Q:** Does a B.A. student who entered the program in 2024/25 or later have to complete a language requirement?

**Reference:** No. Their five degree requirements are Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum — there is no separate language requirement (that applies to students who entered in 2023/24 or earlier).

**Retrieved:** [2767] Bachelor of Arts — Linguistics [2025/26] · [128] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27] · [300] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [301] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26]

**Scores:** rr 0.50

### q012 — hit — gold [0]

**Q:** What are the three levels of academic standing at UBC?

**Reference:** In Good Standing; On Academic Probation; and Failed, Required to Withdraw. All students are In Good Standing on initial entry to the University.

**Retrieved:** [0] Academic Standing [2026/27] · [431] Course Standings [2026/27] · [430] Course Standings [2026/27] · [13784] Academic Regulations [2026/27]

**Scores:** rr 1.00

