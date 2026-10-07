# UBCHelper agent eval — agent-v1

2026-10-06T22:12:00 · 16 questions (12 specific + 4 general) · k=4 · mode=hybrid_rerank · judge on

Models: chat=`claude-haiku-4-5`, judge=`google/gemma-4-e4b`, embed=`text-embedding-3-small` · corpus=16576 · agent knobs: max_subq=3, subq_top_k=4, synth_context_k=8

## How to read this

- Both arms run the real `pipeline.answer()` with the route forced, not a reimplementation — that bypass is the bug this eval exists to fix.
- **Every comparative metric is at depth k=4 on all arms.** The agent retrieves up to 12 excerpts; scoring it deeper than the simple arm would be a gift, not a comparison.
- `recall@full` and `prompt_recall` are diagnostics, not comparisons. `prompt_recall` counts only the excerpts that actually reached the model (the agent's first 8).
- `simple_matched` is a control: a one-shot retrieve at the agent's own merge depth. It answers "would just retrieving more have worked?" Its generation is not a shipped configuration.
- Groundedness is scored against the **gold** excerpt, so it is arm-invariant. `context_precision`/`context_recall` are depth-sensitive — read them within an arm over time, not across arms.
- n=16, and `decompose` is nondeterministic (no temperature is sent to Anthropic), so a delta smaller than 0.062 is not a result.

## Routing policies

What each routing strategy would have scored, from the arms already run.

| policy | n | % complex | hit@k | recall@k | MRR | grounded | LLM/q | rerank/q | s/q | est $ |
|---|---|---|---|---|---|---|---|---|---|---|
| `always_simple` | 16 | 0% | 0.750 | 0.656 | 0.552 | 0.602 | 1.0 | 1.0 | 3.3 | 0.056 |
| `always_complex` | 16 | 100% | 0.875 | 0.781 | 0.615 | 0.879 | 2.0 | 1.38 | 4.2 | 0.092 |
| `router` | 16 | 38% | 0.750 | 0.656 | 0.573 | 0.743 | 1.38 | 1.38 | 3.9 | 0.077 |
| `oracle` | 16 | 25% | 0.812 | 0.719 | 0.604 | 0.709 | 1.25 | 1.31 | 3.8 | 0.072 |

## Arms by bucket

| bucket | n | arm | depth | hit@k | recall@k | MRR | recall@full | grounded |
|---|---|---|---|---|---|---|---|---|
| overall | 16 | `simple` | 4 | 0.750 | 0.656 | 0.552 | 0.656 | 0.602 |
| overall | 16 | `simple_matched` | 5.19 | 0.750 | 0.656 | 0.552 | 0.656 | 0.717 |
| overall | 16 | `agent` | 5.19 | 0.875 | 0.781 | 0.615 | 0.844 | 0.879 |
| specific | 12 | `simple` | 4 | 0.833 | 0.708 | 0.667 | 0.708 | 0.635 |
| specific | 12 | `simple_matched` | 4.67 | 0.833 | 0.708 | 0.667 | 0.708 | 0.801 |
| specific | 12 | `agent` | 4.67 | 0.917 | 0.792 | 0.667 | 0.792 | 0.872 |
| general | 4 | `simple` | 4 | 0.500 | 0.500 | 0.208 | 0.500 | 0.500 |
| general | 4 | `simple_matched` | 6.75 | 0.500 | 0.500 | 0.208 | 0.500 | 0.464 |
| general | 4 | `agent` | 6.75 | 0.750 | 0.750 | 0.458 | 1.000 | 0.900 |
| code-lookup | 5 | `simple` | 4 | 0.800 | 0.700 | 0.800 | 0.700 | 0.742 |
| code-lookup | 5 | `simple_matched` | 4 | 0.800 | 0.700 | 0.800 | 0.700 | 0.925 |
| code-lookup | 5 | `agent` | 4 | 1.000 | 0.900 | 0.867 | 0.900 | 0.975 |
| multi-hop | 3 | `simple` | 4 | 0.667 | 0.333 | 0.333 | 0.333 | 0.389 |
| multi-hop | 3 | `simple_matched` | 6.67 | 0.667 | 0.333 | 0.333 | 0.333 | 0.694 |
| multi-hop | 3 | `agent` | 6.67 | 1.000 | 0.667 | 0.611 | 0.667 | 0.694 |
| collision | 3 | `simple` | 4 | 1.000 | 1.000 | 0.667 | 1.000 | 0.667 |
| collision | 3 | `simple_matched` | 4 | 1.000 | 1.000 | 0.667 | 1.000 | 0.717 |
| collision | 3 | `agent` | 4 | 0.667 | 0.667 | 0.278 | 0.667 | 0.917 |
| policy | 1 | `simple` | 4 | 1.000 | 1.000 | 1.000 | 1.000 | 0.750 |
| policy | 1 | `simple_matched` | 4 | 1.000 | 1.000 | 1.000 | 1.000 | 0.750 |
| policy | 1 | `agent` | 4 | 1.000 | 1.000 | 1.000 | 1.000 | 0.750 |
| expected=simple | 12 | `simple` | 4 | 0.833 | 0.792 | 0.653 | 0.792 | 0.705 |
| expected=simple | 12 | `simple_matched` | 4.33 | 0.833 | 0.792 | 0.653 | 0.792 | 0.782 |
| expected=simple | 12 | `agent` | 4.33 | 0.917 | 0.875 | 0.667 | 0.875 | 0.931 |
| expected=complex | 4 | `simple` | 4 | 0.500 | 0.250 | 0.250 | 0.250 | 0.292 |
| expected=complex | 4 | `simple_matched` | 7.75 | 0.500 | 0.250 | 0.250 | 0.250 | 0.521 |
| expected=complex | 4 | `agent` | 7.75 | 0.750 | 0.500 | 0.458 | 0.750 | 0.721 |

### agent − simple (depth k, the comparable number)

| bucket | n | Δ hit@k | Δ recall@k | Δ MRR | Δ grounded |
|---|---|---|---|---|---|
| overall | 16 | +0.125 | +0.125 | +0.062 | +0.277 |
| specific | 12 | +0.083 | +0.083 | +0.000 | +0.236 |
| general | 4 | +0.250 | +0.250 | +0.250 | +0.400 |
| code-lookup | 5 | +0.200 | +0.200 | +0.067 | +0.233 |
| multi-hop | 3 | +0.333 | +0.333 | +0.278 | +0.305 |
| collision | 3 | -0.333 | -0.333 | -0.389 | +0.250 |
| policy | 1 | +0.000 | +0.000 | +0.000 | +0.000 |
| expected=simple | 12 | +0.083 | +0.083 | +0.014 | +0.226 |
| expected=complex | 4 | +0.250 | +0.250 | +0.208 | +0.429 |

## Router accuracy

Accuracy **0.875** over 16 questions (3 vote(s) each, stability 0.938). Positive class = `complex`; precision 0.667, recall 1.000.

A bare accuracy figure flatters the router here: only 4 of 16 questions are genuinely complex, so "always simple" would score 0.750. The errors are not symmetric either — a false `complex` wastes two LLM calls and two reranks, a false `simple` silently loses recall.

| | predicted simple | predicted complex |
|---|---|---|
| **actually simple** | 10 | 2 |
| **actually complex** | 0 | 4 |

Disagreements (raw model replies shown, since the parse at `src/router.py:36` is substring containment):

- `q011` expected **simple**, got **complex** — replies: ['simple', 'complex', 'complex']
- `g001` expected **simple**, got **complex** — replies: ['complex', 'complex', 'complex']

## Agent diagnostics

- Sub-questions per item: mean 1.38 (min 1, max 3)
- Merge depth: mean 5.19, mean deduped away 0.31
- Which hop first surfaced each gold: {'hop1': 17, 'hop2': 3, 'hop3': 1, 'none': 4}
- Recall found but ranked below k: 0.0625
- Golds only the agent found: {'q005': [5, 177], 'q006': [114, 128], 'g003': [5]}
- Golds only the simple arm found (merge displaced them): {'q011': [128]}
- **Degenerate** (decompose returned one sub-question, so the agent arm is the simple arm plus wasted calls): ['q001', 'q002', 'q003', 'q004', 'q005', 'q009', 'q010', 'q011', 'q012', 'g002', 'g003']

## Cost

- API calls: {'llm': 112, 'embed': 54, 'rerank': 54} · estimated **$0.276**
- Wall clock: 1076 s
- Judge parse failures by arm: {'agent': 0, 'simple': 0, 'simple_matched': 0}

## Questions

### q001 — code-lookup — gold [10, 182]

**Q:** What are the prerequisites for CPSC 221?

**Reference:** One of CPSC 210 or CPEN 221, and either one of CPSC 121, MATH 220 (or MATH_O 220), or a score of 68% or higher in MATH 226.

**Route:** expected **simple**, router said **simple** (correct)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. What are the prerequisites for CPSC 221?

**Per-hop ids:** [[182, 10, 219, 232]] → merged [182, 10, 219, 232] (deduped away 0)

**`simple`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 0.750 (3/4)

  [182] Computer Science, Faculty of Science [2025/26] · [10] Computer Science, Faculty of Science [2026/27] · [219] Computer Science, Faculty of Science [2025/26] · [232] Computer Science, Faculty of Science [2025/26]

  The prerequisites for CPSC 221 are:

One of CPSC 210 or CPEN 221, **and** either:
- (a) one of CPSC 121, MATH 220, or
- (b) a score of 68% or higher in MATH 226

Note that the course code formatting has been updated in the 2026/27 calendar (now CPSC_V 221, CPEN_V 221, etc.), but the prerequisite requirements remain the same.

For the most current information, see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**`simple_matched`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 1.000 (6/6)

  [182] Computer Science, Faculty of Science [2025/26] · [10] Computer Science, Faculty of Science [2026/27] · [219] Computer Science, Faculty of Science [2025/26] · [232] Computer Science, Faculty of Science [2025/26]

  For the 2026/27 calendar, the prerequisites for CPSC_V 221 are:

One of CPSC_V 210 or CPEN_V 221, **and** either:
- (a) One of CPSC_V 121, MATH_V 220, or MATH_O 220, **or**
- (b) A score of 68% or higher in MATH_V 226

For authoritative and most current wording, see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**`agent`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 1.000 (3/3)

  [182] Computer Science, Faculty of Science [2025/26] · [10] Computer Science, Faculty of Science [2026/27] · [219] Computer Science, Faculty of Science [2025/26] · [232] Computer Science, Faculty of Science [2025/26]

  For the 2026/27 calendar, the prerequisites for CPSC_V 221 are:

One of CPSC_V 210 or CPEN_V 221, **and** either:
- (a) one of CPSC_V 121, MATH_V 220, or MATH_O 220, **or**
- (b) a score of 68% or higher in MATH_V 226

For the most current and authoritative wording, see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**Δ agent−simple:** recall +0.000, gained [], lost [], +1 LLM calls, +2331 ms

### q002 — code-lookup — gold [24, 197]

**Q:** What are the prerequisites for CPSC 320?

**Reference:** CPSC 221 (or DSCI 221) plus at least 3 credits of MATH or STAT at the 200 level or above (the 2025/26 edition also accepted COMM 291 or BIOL 300 for the second part).

**Route:** expected **simple**, router said **simple** (correct)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. What are the prerequisites for CPSC 320?

**Per-hop ids:** [[197, 42, 214, 216]] → merged [197, 42, 214, 216] (deduped away 0)

**`simple`** — depth 4, hit 1, recall@4 0.500, rr 1.000, grounded 0.750 (3/4)

  [197] Computer Science, Faculty of Science [2025/26] · [42] Computer Science, Faculty of Science [2026/27] · [214] Computer Science, Faculty of Science [2025/26] · [216] Computer Science, Faculty of Science [2025/26]

  Based on the 2025/26 calendar, the prerequisites for CPSC 320 (Intermediate Algorithm Design and Analysis) are:

1. **CPSC 221 or DSCI 221**, AND
2. **At least 3 credits from:** COMM 291, BIOL 300, or MATH or STAT at the 200 level or above

For the most current and authoritative wording, please see: https://archive.calendar.ubc.ca/vancouver/2526/course-descriptions/subject/cpscv/index.html

**`simple_matched`** — depth 4, hit 1, recall@4 0.500, rr 1.000, grounded 0.750 (3/4)

  [197] Computer Science, Faculty of Science [2025/26] · [42] Computer Science, Faculty of Science [2026/27] · [214] Computer Science, Faculty of Science [2025/26] · [216] Computer Science, Faculty of Science [2025/26]

  According to the 2025/26 calendar, the prerequisites for CPSC 320 (Intermediate Algorithm Design and Analysis) are:

- **CPSC 221 or DSCI 221**, AND
- **At least 3 credits from:** COMM 291, BIOL 300, or MATH or STAT courses at 200 level or above

For the authoritative and most current wording, see: https://archive.calendar.ubc.ca/vancouver/2526/course-descriptions/subject/cpscv/index.html

**`agent`** — depth 4, hit 1, recall@4 0.500, rr 1.000, grounded 1.000 (3/3)

  [197] Computer Science, Faculty of Science [2025/26] · [42] Computer Science, Faculty of Science [2026/27] · [214] Computer Science, Faculty of Science [2025/26] · [216] Computer Science, Faculty of Science [2025/26]

  The prerequisites for CPSC 320 (Intermediate Algorithm Design and Analysis) are:

1. **CPSC 221 or DSCI 221**, AND
2. **At least 3 credits** from one of: COMM 291, BIOL 300, or MATH or STAT at the 200 level or above

For the authoritative and most current wording, see the Computer Science course descriptions page: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**Δ agent−simple:** recall +0.000, gained [], lost [], +1 LLM calls, +-379 ms

### q003 — code-lookup — gold [20, 193]

**Q:** What are the prerequisites for CPSC 313?

**Reference:** CPSC 213, and either CPSC 221 or DSCI 221.

**Route:** expected **simple**, router said **simple** (correct)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. What are the prerequisites for CPSC 313?

**Per-hop ids:** [[20, 193, 213, 212]] → merged [20, 193, 213, 212] (deduped away 0)

**`simple`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 1.000 (4/4)

  [20] Computer Science, Faculty of Science [2026/27] · [193] Computer Science, Faculty of Science [2025/26] · [213] Computer Science, Faculty of Science [2025/26] · [212] Computer Science, Faculty of Science [2025/26]

  The prerequisites for CPSC 313 (Computer Hardware and Operating Systems) are:

- CPSC 213, **and**
- Either CPSC 221 or DSCI 221

This requirement is consistent across both the 2026/27 and 2025/26 calendars. For the most current and authoritative wording, see https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**`simple_matched`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 1.000 (2/2)

  [20] Computer Science, Faculty of Science [2026/27] · [193] Computer Science, Faculty of Science [2025/26] · [213] Computer Science, Faculty of Science [2025/26] · [212] Computer Science, Faculty of Science [2025/26]

  The prerequisites for CPSC 313 (Computer Hardware and Operating Systems) are:

- CPSC 213, **and**
- either CPSC 221 or DSCI 221

For the most current and authoritative wording, see the course descriptions page: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**`agent`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 1.000 (2/2)

  [20] Computer Science, Faculty of Science [2026/27] · [193] Computer Science, Faculty of Science [2025/26] · [213] Computer Science, Faculty of Science [2025/26] · [212] Computer Science, Faculty of Science [2025/26]

  The prerequisites for CPSC 313 (Computer Hardware and Operating Systems) are:

- CPSC 213, AND
- Either CPSC 221 or DSCI 221

For the most current and authoritative wording, see the UBC Vancouver Academic Calendar at https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**Δ agent−simple:** recall +0.000, gained [], lost [], +1 LLM calls, +630 ms

### q004 — code-lookup — gold [580, 2196]

**Q:** Which courses satisfy the prerequisite for MATH 200, Calculus III?

**Reference:** One of MATH 101, MATH 103, MATH 105, MATH 121, SCIE 001, MATH_O 101, or MATH_O 103.

**Route:** expected **simple**, router said **simple** (correct)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. What are the prerequisite requirements listed for MATH 200, Calculus III?

**Per-hop ids:** [[580, 2196, 2225, 609]] → merged [580, 2196, 2225, 609] (deduped away 0)

**`simple`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 0.875 (7/8)

  [580] Mathematics, Faculty of Science [2026/27] · [2196] Mathematics, Faculty of Science [2025/26] · [2225] Mathematics, Faculty of Science [2025/26] · [609] Mathematics, Faculty of Science [2026/27]

  For the 2026/27 calendar, the courses that satisfy the prerequisite for MATH_V 200 (Calculus III) are:

- MATH_V 101
- MATH_V 103
- MATH_V 105
- MATH_V 121
- SCIE_V 001
- MATH_O 101
- MATH_O 103

You need to complete one of these courses before taking MATH_V 200.

For the most current and authoritative details, see https://vancouver.calendar.ubc.ca/course-descriptions/subject/mathv

**`simple_matched`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 0.875 (7/8)

  [580] Mathematics, Faculty of Science [2026/27] · [2196] Mathematics, Faculty of Science [2025/26] · [2225] Mathematics, Faculty of Science [2025/26] · [609] Mathematics, Faculty of Science [2026/27]

  For the 2026/27 calendar, the courses that satisfy the prerequisite for MATH_V 200 (Calculus III) are:

- MATH_V 101
- MATH_V 103
- MATH_V 105
- MATH_V 121
- SCIE_V 001
- MATH_O 101
- MATH_O 103

You need to complete one of these courses before taking MATH_V 200.

For the authoritative and most current wording, please see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/mathv

**`agent`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 0.875 (7/8)

  [580] Mathematics, Faculty of Science [2026/27] · [2196] Mathematics, Faculty of Science [2025/26] · [2225] Mathematics, Faculty of Science [2025/26] · [609] Mathematics, Faculty of Science [2026/27]

  For MATH_V 200 (Calculus III) in the 2026/27 calendar, the prerequisite is one of the following courses:

- MATH_V 101
- MATH_V 103
- MATH_V 105
- MATH_V 121
- SCIE_V 001
- MATH_O 101
- MATH_O 103

You need to complete just one of these courses to satisfy the prerequisite for MATH_V 200.

For the full and most current details, see the Mathematics course descriptions: https://vancouver.calendar.ubc.ca/course-descriptions/subject/mathv

**Δ agent−simple:** recall +0.000, gained [], lost [], +1 LLM calls, +682 ms

### q005 — code-lookup — gold [5, 177]

**Q:** How many credits is CPSC 110 worth and what does it cover?

**Reference:** CPSC 110 (Computation, Programs, and Programming) is worth 4 credits and covers fundamental program and computation structures.

**Route:** expected **simple**, router said **simple** (correct)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. CPSC 110 credit value and course description/content coverage

**Per-hop ids:** [[155, 327, 5, 177]] → merged [155, 327, 5, 177] (deduped away 0)

**`simple`** — depth 4, hit 0, recall@4 0.000, rr 0.000, grounded 0.333 (1/3)

  [327] Bachelor of Science — Computer Science [2025/26] · [149] Bachelor of Science — Computer Science [2026/27] · [146] Bachelor of Science — Computer Science [2026/27] · [318] Bachelor of Science — Computer Science [2025/26]

  CPSC 110 is worth **4 credits**.

However, the excerpts provided don't contain information about what CPSC 110 covers—they only list it as a required first-year course for Computer Science programs. For details on course content, I'd recommend checking the course description on the UBC Course Calendar or contacting the Department of Computer Science.

For the most current program requirements, see the 2026/27 calendar at https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/computer-science

**`simple_matched`** — depth 4, hit 0, recall@4 0.000, rr 0.000, grounded 1.000 (1/1)

  [327] Bachelor of Science — Computer Science [2025/26] · [149] Bachelor of Science — Computer Science [2026/27] · [146] Bachelor of Science — Computer Science [2026/27] · [318] Bachelor of Science — Computer Science [2025/26]

  CPSC 110 is worth **4 credits**.

However, the excerpts provided don't contain information about what CPSC 110 covers (its course content or topics). They only specify the credit value and note that it can be replaced by CPSC 103 and 107 as an alternative.

For details about course content, I'd recommend checking the course description on the UBC course calendar or contacting the Computer Science department directly.

**`agent`** — depth 4, hit 1, recall@4 1.000, rr 0.333, grounded 1.000 (2/2)

  [155] Bachelor of Science — Computer Science [2026/27] · [327] Bachelor of Science — Computer Science [2025/26] · [5] Computer Science, Faculty of Science [2026/27] · [177] Computer Science, Faculty of Science [2025/26]

  CPSC_V 110 is worth **4 credits**.

It covers fundamental program and computation structures, introductory programming skills, and computation as a tool for information processing, simulation and modelling, and interacting with the world.

For the most current and authoritative details, see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**Δ agent−simple:** recall +1.000, gained [5, 177], lost [], +1 LLM calls, +-121 ms

### q006 — multi-hop — gold [114, 128]

**Q:** Compare the B.A. degree requirements for students who entered the program in 2023/24 with those who entered in 2024/25 or later.

**Reference:** Students entering 2023/24 or earlier must complete seven requirements: Writing and Research, Language, Science, Literature, Outside, Upper-level, and Arts Credit Minimum. Students entering 2024/25 or later complete five: Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum — the separate Language, Science, and Literature requirements are folded into the Ways of Knowing Breadth requirement.

**Route:** expected **complex**, router said **complex** (correct)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. B.A. degree requirements for students who entered in 2023/24
  2. B.A. degree requirements for students who entered in 2024/25 or later

**Per-hop ids:** [[286, 114, 1295, 2916], [300, 128, 302, 130]] → merged [286, 300, 114, 128, 1295, 302, 2916, 130] (deduped away 0)

**`simple`** — depth 4, hit 0, recall@4 0.000, rr 0.000, grounded 0.200 (1/5)

  [2916] Bachelor of Arts — Second Degree Studies [2025/26] · [1295] Bachelor of Arts — Second Degree Studies [2026/27] · [2589] Dual Degree Program Option: Bachelor of Arts, UBC and Sciences Po [2025/26] · [963] Dual Degree Program Option: Bachelor of Arts, UBC and Sciences Po [2026/27]

  I don't have enough information in the provided excerpts to make that comparison. The excerpts reference the different degree requirements for these two cohorts but don't actually include the detailed requirements themselves—they only point to where those requirements can be found in the calendar.

To see the specific differences between B.A. degree requirements for students who entered in 2023/24 versus 2024/25 or later, you would need to consult the full degree requirements pages in the calendar. For the current 2026/27 academic year, you can find this information at:

https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts

I'd recommend checking both the 2023/24 entry cohort requirements and the 2024/25 or later cohort requirements on that page to compare them directly.

**`simple_matched`** — depth 8, hit 0, recall@4 0.000, rr 0.000, grounded 1.000 (9/9)

  [2916] Bachelor of Arts — Second Degree Studies [2025/26] · [1295] Bachelor of Arts — Second Degree Studies [2026/27] · [2589] Dual Degree Program Option: Bachelor of Arts, UBC and Sciences Po [2025/26] · [963] Dual Degree Program Option: Bachelor of Arts, UBC and Sciences Po [2026/27] · [286] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2025/26] · [302] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [300] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [298] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2025/26]

  # B.A. Degree Requirements: 2023/24 vs. 2024/25+ Entry Cohorts

The main difference is in the **breadth requirements**:

**Students who entered in 2023/24 or earlier** must complete **seven requirements**:
1. Writing and Research Requirement
2. Language Requirement
3. Science Requirement
4. Literature Requirement
5. Outside Requirement
6. Upper-level Requirement
7. Arts Credit Minimum Requirement

**Students who entered in 2024/25 or later** must complete **five requirements**:
1. Writing and Research Requirement
2. Ways of Knowing Breadth Requirement
3. Outside Requirement
4. Upper-level Requirement
5. Arts Credit Minimum Requirement

The newer cohort has consolidated the individual breadth requirements (Language, Science, Literature) into a single "Ways of Knowing Breadth Requirement," making the overall structure more streamlined.

Both cohorts retain the Writing and Research Requirement, Outside Requirement, Upper-level Requirement, and Arts Credit Minimum Requirement. Upper-level credit requirements by degree option remain the same.

For the authoritative and most current details, see the 2026/27 calendar pages for [students entering in 2023/24 or earlier](https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202324-or-earlier) and [students entering in 2024/25 or later](https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202425-or-later).

**`agent`** — depth 8, hit 1, recall@4 1.000, rr 0.333, grounded 1.000 (6/6)

  [286] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2025/26] · [300] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [114] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2026/27] · [128] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27] · [1295] Bachelor of Arts — Second Degree Studies [2026/27] · [302] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [2916] Bachelor of Arts — Second Degree Studies [2025/26] · [130] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27]

  # B.A. Degree Requirements: 2023/24 vs. 2024/25+ Entry Cohorts

There are **significant differences** between these two cohorts:

## Students who entered in 2023/24 or earlier (7 requirements):
1. Writing and Research Requirement
2. Language Requirement
3. Science Requirement
4. Literature Requirement
5. Outside Requirement
6. Upper-level Requirement
7. Arts Credit Minimum Requirement

## Students who entered in 2024/25 or later (5 requirements):
1. Writing and Research Requirement
2. Ways of Knowing Breadth Requirement
3. Outside Requirement
4. Upper-level Requirement
5. Arts Credit Minimum Requirement

## Key Changes:
The newer cohort has **eliminated three separate requirements** (Language, Science, and Literature) and replaced them with a single **Ways of Knowing Breadth Requirement**. This represents a streamlined approach to the B.A. degree structure.

For complete details on what each requirement entails, see:
- [2023/24 or earlier cohort](https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202324-or-earlier)
- [2024/25 or later cohort](https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202425-or-later)

**Δ agent−simple:** recall +1.000, gained [114, 128], lost [], +1 LLM calls, +1658 ms

### q007 — multi-hop — gold [1646, 1668]

**Q:** How does admission to the Bachelor of Computer Science program differ from B.Sc. admission from secondary school?

**Reference:** Bachelor of Computer Science admission is a competitive selection process evaluating applicants on academic and other criteria (not every qualified applicant is admitted); B.Sc. admission from secondary school requires starting first year in September of the Winter session of admission (January starts are not permitted).

**Route:** expected **complex**, router said **complex** (correct)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. What are the admission requirements for the Bachelor of Computer Science program from secondary school?
  2. What are the admission requirements for the Bachelor of Computer Science program for applicants who are not coming directly from secondary school (e.g., mature students, transfer students)?

**Per-hop ids:** [[1645, 1646, 1653, 315], [1646, 1645, 1653, 315]] → merged [1645, 1646, 1653, 315] (deduped away 4)

**`simple`** — depth 4, hit 1, recall@4 0.500, rr 0.500, grounded 0.300 (3/10)

  [1645] Bachelor of Computer Science [2026/27] · [1646] Bachelor of Computer Science [2026/27] · [1654] Bachelor of Computer Science [2026/27] · [1644] Bachelor of Computer Science [2026/27]

  The Bachelor of Computer Science (B.C.S.) program is fundamentally different from typical B.Sc. admission because it's specifically designed as a **second bachelor's degree program for students who already hold a recognized bachelor's degree** in a non-computer science field.

Key differences in admission include:

**B.C.S. Admission Requirements:**
- Must have completed a recognized bachelor's degree (not just high school completion)
- Evaluated on academic criteria including overall record and a minimum B- (68%) average on the most recent 30 credits
- Non-academic criteria are assessed through two confidential letters of reference, a self-assessment of work history, and a statement of interest
- The Admission Committee may interview selected applicants

**Prerequisite Requirements (not full subject-based admission):**
- BC Principles of Mathematics 12 or Pre-calculus 12
- Communication requirement (3 credits or English from a university where English is primary)
- Computer literacy course or equivalent

Applicants with strong academic records who don't yet meet all prerequisites are encouraged to apply but must complete missing prerequisites before admission.

The program explicitly states that "dual degree options do not exist" and students cannot pursue another program concurrently with the B.C.S.

For complete and current details, see the official program page: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-computer-science

**`simple_matched`** — depth 4, hit 1, recall@4 0.500, rr 0.500, grounded 0.333 (3/9)

  [1645] Bachelor of Computer Science [2026/27] · [1646] Bachelor of Computer Science [2026/27] · [1654] Bachelor of Computer Science [2026/27] · [1644] Bachelor of Computer Science [2026/27]

  The Bachelor of Computer Science is a second bachelor's degree program specifically designed for students who already hold a recognized bachelor's degree in a field that does not overlap with computer science. This is fundamentally different from typical B.Sc. admission from secondary school.

Key differences include:

**Entry Requirements:**
- B.C.S. applicants must have completed a previous bachelor's degree (not just high school)
- B.C.S. applicants need to demonstrate prerequisites like BC Principles of Mathematics 12 or Pre-calculus 12, a communication requirement, and computer literacy—but applicants with strong records who don't yet meet all requirements may still apply and complete them before admission

**Evaluation Criteria:**
- Academic evaluation includes your overall academic record and most recent 30-credit average (minimum B-/68% required)
- Non-academic evaluation is based on two confidential letters of reference, a self-assessment of work history, and a statement of interest
- The admissions committee may interview selected applicants

**Program Structure:**
- It's a two-year program (rather than the typical four-year B.Sc.)
- Dual degree options do not exist; you cannot pursue another program concurrently with the B.C.S.

For the full and authoritative details on admission requirements and processes, see the program page at https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-computer-science.

**`agent`** — depth 4, hit 1, recall@4 0.500, rr 0.500, grounded 0.333 (2/6)

  [1645] Bachelor of Computer Science [2026/27] · [1646] Bachelor of Computer Science [2026/27] · [1653] Bachelor of Computer Science [2026/27] · [315] Bachelor of Science — Computer Science [2025/26]

  The excerpts provided describe admission to the Bachelor of Computer Science program, which is a **second-degree program** for applicants who have already completed a recognized bachelor's degree. This is fundamentally different from B.Sc. admission from secondary school.

Key differences based on the information available:

**Bachelor of Computer Science (Second Degree):**
- Requires an already-completed bachelor's degree in a non-overlapping field
- Requires specific prerequisites: BC Principles of Mathematics 12 (or equivalent), communication requirement (3 credits), and computer literacy
- Admission is competitive and based on: overall academic record with consideration of grade trends, a minimum B- (68%) average on the most recent 30 credits, two confidential letters of reference, a self-assessment of work history, and a statement of interest
- Students are admitted into third year of the program

**B.Sc. admission from secondary school** is not described in these excerpts, so I cannot provide a detailed comparison of how they differ.

For the most current and complete admission requirements for both pathways, see the official Bachelor of Computer Science program page: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-computer-science

**Δ agent−simple:** recall +0.000, gained [], lost [], +1 LLM calls, +1555 ms

### q008 — multi-hop — gold [20, 10]

**Q:** I have finished CPSC 210. What else do I need to complete before I can take CPSC 313?

**Reference:** CPSC 313 requires CPSC 213 and either CPSC 221 or DSCI 221. CPSC 221 in turn requires (beyond CPSC 210) one of CPSC 121, MATH 220, MATH_O 220, or a 68%+ score in MATH 226. So after CPSC 210 you still need CPSC 213 and CPSC 221 (with its discrete-math prerequisite).

**Route:** expected **complex**, router said **complex** (correct)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. What are the prerequisites for CPSC 313?
  2. What are the prerequisites for CPSC 210, and are there any other courses that must be completed before taking CPSC 313?

**Per-hop ids:** [[20, 193, 213, 212], [1975, 3461, 1959, 1974]] → merged [20, 1975, 193, 3461, 213, 1959, 212, 1974] (deduped away 0)

**`simple`** — depth 4, hit 1, recall@4 0.500, rr 0.500, grounded 0.667 (2/3)

  [193] Computer Science, Faculty of Science [2025/26] · [20] Computer Science, Faculty of Science [2026/27] · [917] Bachelor of Arts — Computer Science [2026/27] · [2540] Bachelor of Arts — Computer Science [2025/26]

  To take CPSC 313, you need to complete:

1. **CPSC 213**
2. **Either CPSC 221 or DSCI 221**

You've already finished CPSC 210, which is good preparation but not a formal prerequisite for CPSC 313.

For the authoritative and most current prerequisite information, see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**`simple_matched`** — depth 8, hit 1, recall@4 0.500, rr 0.500, grounded 0.750 (3/4)

  [193] Computer Science, Faculty of Science [2025/26] · [20] Computer Science, Faculty of Science [2026/27] · [917] Bachelor of Arts — Computer Science [2026/27] · [2540] Bachelor of Arts — Computer Science [2025/26] · [320] Bachelor of Science — Computer Science [2025/26] · [148] Bachelor of Science — Computer Science [2026/27] · [3224] Bachelor of Science — Biology [2025/26] · [158] Bachelor of Science — Computer Science [2026/27]

  To take CPSC 313, you need to complete:

- **CPSC 213**, and
- Either **CPSC 221** or **DSCI 221**

These are the prerequisite requirements for CPSC 313 (Computer Hardware and Operating Systems).

For the authoritative and most current wording, see the Computer Science course descriptions at https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**`agent`** — depth 8, hit 1, recall@4 0.500, rr 1.000, grounded 0.750 (3/4)

  [20] Computer Science, Faculty of Science [2026/27] · [1975] Bachelor of Science — Microbiology and Immunology [2026/27] · [193] Computer Science, Faculty of Science [2025/26] · [3461] Bachelor of Science — Microbiology and Immunology [2025/26] · [213] Computer Science, Faculty of Science [2025/26] · [1959] Bachelor of Science — Mathematics [2026/27] · [212] Computer Science, Faculty of Science [2025/26] · [1974] Bachelor of Science — Microbiology and Immunology [2026/27]

  Based on the course description, to take CPSC 313 (Computer Hardware and Operating Systems), you need:

- CPSC 213
- Either CPSC 221 or DSCI 221

Since you've already completed CPSC 210, you still need to complete CPSC 213 and at least one of CPSC 221 or DSCI 221 before you can enroll in CPSC 313.

For the most current and authoritative information, see: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**Δ agent−simple:** recall +0.000, gained [], lost [], +1 LLM calls, +1622 ms

### q009 — collision — gold [3385]

**Q:** In the 2025/26 calendar, what is the minimum number of credits required for a B.Sc. degree?

**Reference:** A minimum of 120 credits (a major, double major, or General Science option requires at least 120 credits but may require more).

**Route:** expected **simple**, router said **simple** (correct)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. Minimum number of credits required for a B.Sc. degree in the 2025/26 calendar

**Per-hop ids:** [[3386, 3385, 3315, 3319]] → merged [3386, 3385, 3315, 3319] (deduped away 0)

**`simple`** — depth 4, hit 1, recall@4 1.000, rr 0.500, grounded 1.000 (3/3)

  [3386] Bachelor of Science — General Degree Requirements [2025/26] · [3385] Bachelor of Science — General Degree Requirements [2025/26] · [3315] Bachelor of Science — Credit at UBC and Elsewhere [2025/26] · [1900] Bachelor of Science — General Degree Requirements [2026/27]

  In the 2025/26 calendar, the minimum number of credits required for a B.Sc. degree depends on which degree option you pursue:

- **Major, Combined Major, Double Major, or General Science**: 120 credits minimum
- **Honours or Combined Honours**: 132 credits minimum

For more details, see the official calendar page at https://archive.calendar.ubc.ca/vancouver/2526/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements/index.html

**`simple_matched`** — depth 4, hit 1, recall@4 1.000, rr 0.500, grounded 0.750 (3/4)

  [3386] Bachelor of Science — General Degree Requirements [2025/26] · [3385] Bachelor of Science — General Degree Requirements [2025/26] · [3315] Bachelor of Science — Credit at UBC and Elsewhere [2025/26] · [1900] Bachelor of Science — General Degree Requirements [2026/27]

  In the 2025/26 calendar, the minimum number of credits required for a B.Sc. degree depends on which degree option you pursue:

- **Major, Combined Major, Double Major, or General Science**: 120 credits minimum
- **Honours or Combined Honours**: 132 credits minimum

For the most current and authoritative wording, see: https://archive.calendar.ubc.ca/vancouver/2526/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements/index.html

**`agent`** — depth 4, hit 1, recall@4 1.000, rr 0.500, grounded 1.000 (3/3)

  [3386] Bachelor of Science — General Degree Requirements [2025/26] · [3385] Bachelor of Science — General Degree Requirements [2025/26] · [3315] Bachelor of Science — Credit at UBC and Elsewhere [2025/26] · [3319] Bachelor of Science — Credit at UBC and Elsewhere [2025/26]

  According to the 2025/26 calendar, the minimum number of credits required for a Bachelor of Science degree is **120 credits**.

However, this minimum may be higher depending on your specific degree option and specialization. For example, an honours or combined honours option requires a minimum of 132 credits. You should check the requirements for your particular program specialization, as some programs may require more than the baseline 120 credits.

For the most current and detailed information, see: https://archive.calendar.ubc.ca/vancouver/2526/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements/index.html

**Δ agent−simple:** recall +0.000, gained [], lost [], +1 LLM calls, +1991 ms

### q010 — collision — gold [1900]

**Q:** According to the current 2026/27 calendar, what is the minimum number of credits required for a B.Sc. degree?

**Reference:** A minimum of 120 credits (a major, double major, or General Science option requires at least 120 credits but may require more).

**Route:** expected **simple**, router said **simple** (correct)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. minimum number of credits required for a B.Sc. degree at UBC in 2026/27

**Per-hop ids:** [[1831, 1835, 1900, 2048]] → merged [1831, 1835, 1900, 2048] (deduped away 0)

**`simple`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 1.000 (5/5)

  [1900] Bachelor of Science — General Degree Requirements [2026/27] · [1901] Bachelor of Science — General Degree Requirements [2026/27] · [1831] Bachelor of Science — Credit at UBC and Elsewhere [2026/27] · [2051] Bachelor of Science — Recognition of Academic Achievement [2026/27]

  According to the 2026/27 calendar, the minimum number of credits required for a B.Sc. degree is **120 credits**.

This applies to major, combined major, double major, and General Science options. Honours or combined honours options require between 120 to 132 credits, depending on the specific specialization. Additionally, dual degrees require more than 120 credits, though some combinations may be completed in fewer than 180 credits.

For the authoritative and most current wording, see: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements

**`simple_matched`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 1.000 (2/2)

  [1900] Bachelor of Science — General Degree Requirements [2026/27] · [1901] Bachelor of Science — General Degree Requirements [2026/27] · [1831] Bachelor of Science — Credit at UBC and Elsewhere [2026/27] · [2051] Bachelor of Science — Recognition of Academic Achievement [2026/27]

  According to the 2026/27 calendar, the minimum number of credits required for a B.Sc. degree is **120 credits** for a major, combined major, double major, or General Science option. However, an honours or combined honours option requires between 120 to 132 credits as specified by the department's specialization.

For more details, see the official calendar page at https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements

**`agent`** — depth 4, hit 1, recall@4 1.000, rr 0.333, grounded 1.000 (2/2)

  [1831] Bachelor of Science — Credit at UBC and Elsewhere [2026/27] · [1835] Bachelor of Science — Credit at UBC and Elsewhere [2026/27] · [1900] Bachelor of Science — General Degree Requirements [2026/27] · [2048] Bachelor of Science — Recognition of Academic Achievement [2026/27]

  According to the current 2026/27 calendar, the minimum number of credits required for a Bachelor of Science degree is **120 credits**. However, some programs require more than this minimum.

For more details, see: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements

**Δ agent−simple:** recall +0.000, gained [], lost [], +1 LLM calls, +-291 ms

### q011 — collision — gold [128]

**Q:** Does a B.A. student who entered the program in 2024/25 or later have to complete a language requirement?

**Reference:** No. Their five degree requirements are Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum — there is no separate language requirement (that applies to students who entered in 2023/24 or earlier).

**Route:** expected **simple**, router said **complex** (WRONG)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. Does the B.A. program have a language requirement for students entering in 2024/25 or later?

**Per-hop ids:** [[307, 292, 293, 2767]] → merged [307, 292, 293, 2767] (deduped away 0)

**`simple`** — depth 4, hit 1, recall@4 1.000, rr 0.500, grounded 0.000 (0/4)

  [2767] Bachelor of Arts — Linguistics [2025/26] · [128] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27] · [300] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [301] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26]

  Based on the excerpts provided, the language requirement applies specifically to **Linguistics majors**, not to all B.A. students.

If you are pursuing a B.A. in Linguistics, then yes, you must complete 6 credits of coursework in a single language other than English. This requirement cannot be waived based on existing language competency.

If you are a B.A. student in another program, the excerpts do not indicate a general language requirement for all B.A. students entering in 2024/25 or later.

For the most current and complete information, consult the official B.A. Degree Requirements page at: https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202425-or-later

**`simple_matched`** — depth 4, hit 1, recall@4 1.000, rr 0.500, grounded 0.400 (2/5)

  [2767] Bachelor of Arts — Linguistics [2025/26] · [128] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27] · [300] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [301] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26]

  Based on the excerpts provided, I can only speak definitively to the Linguistics major requirement. If you are a Linguistics major, yes, you must complete 6 credits of coursework in a single language other than English. This requirement cannot be waived based on existing language competency, though the courses may simultaneously fulfill your Ways of Knowing Breadth Requirements.

However, the excerpts do not contain information about whether a general B.A. student (not majoring in Linguistics) who entered in 2024/25 or later has a language requirement. The degree requirements listed for students entering 2024/25 or later do not mention a language requirement, but the excerpts provided may not be complete.

For authoritative information on this, I'd recommend consulting the full B.A. degree requirements at:
- https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202425-or-later

or contacting Arts Advising directly.

**`agent`** — depth 4, hit 0, recall@4 0.000, rr 0.000, grounded 0.750 (3/4)

  [307] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [292] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2025/26] · [293] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2025/26] · [2767] Bachelor of Arts — Linguistics [2025/26]

  Based on the excerpts provided, I don't have explicit information about whether BA students who entered in 2024/25 or later have a language requirement. 

The excerpts show that students entering in 2023/24 or earlier do have a Language Requirement, and they detail the "Ways of Knowing Breadth Requirement" which includes a "Language as Meaning" category for students entering in 2024/25 or later. However, the excerpts don't clearly state whether the standalone Language Requirement still exists for the 2024/25+ cohort or if it has been replaced/modified by the new Breadth structure.

For a definitive answer on this, I'd recommend checking the full BA degree requirements page for students entering 2024/25 or later at: https://archive.calendar.ubc.ca/vancouver/2526/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202425-or-later/index.html

You could also contact Arts Academic Advising directly to clarify the requirements for your cohort.

**Δ agent−simple:** recall -1.000, gained [], lost [128], +1 LLM calls, +-406 ms

### q012 — policy — gold [0]

**Q:** What are the three levels of academic standing at UBC?

**Reference:** In Good Standing; On Academic Probation; and Failed, Required to Withdraw. All students are In Good Standing on initial entry to the University.

**Route:** expected **simple**, router said **simple** (correct)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. What are the three levels of academic standing at UBC?

**Per-hop ids:** [[0, 431, 430, 13784]] → merged [0, 431, 430, 13784] (deduped away 0)

**`simple`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 0.750 (3/4)

  [0] Academic Standing [2026/27] · [431] Course Standings [2026/27] · [430] Course Standings [2026/27] · [13784] Academic Regulations [2026/27]

  The three levels of academic standing at UBC are:

1. **In Good Standing**
2. **On Academic Probation**
3. **Failed, Required to Withdraw**

All students enter the University in Good Standing. A student's standing may change to On Academic Probation or Failed, Required to Withdraw based on their academic performance.

For authoritative and current details, see the Academic Standing page in the UBC Vancouver Academic Calendar: https://vancouver.calendar.ubc.ca/campus-wide-policies-and-regulations/academic-standing

**`simple_matched`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 0.750 (3/4)

  [0] Academic Standing [2026/27] · [431] Course Standings [2026/27] · [430] Course Standings [2026/27] · [13784] Academic Regulations [2026/27]

  The three levels of academic standing at UBC are:

1. **In Good Standing**
2. **On Academic Probation**
3. **Failed, Required to Withdraw**

All students start in Good Standing when they initially enter the University. A student's academic standing may change to On Academic Probation or Failed, Required to Withdraw based on their academic performance.

For authoritative details, see: https://vancouver.calendar.ubc.ca/campus-wide-policies-and-regulations/academic-standing

**`agent`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 0.750 (3/4)

  [0] Academic Standing [2026/27] · [431] Course Standings [2026/27] · [430] Course Standings [2026/27] · [13784] Academic Regulations [2026/27]

  The three levels of academic standing at UBC are:

1. **In Good Standing**
2. **On Academic Probation**
3. **Failed, Required to Withdraw**

All students enter the University in Good Standing. A student's academic standing may change to On Academic Probation or Failed, Required to Withdraw based on academic performance evaluations.

For authoritative details, see the Academic Standing policy at https://vancouver.calendar.ubc.ca/campus-wide-policies-and-regulations/academic-standing

**Δ agent−simple:** recall +0.000, gained [], lost [], +1 LLM calls, +409 ms

### g001 — general — gold [0]

**Q:** What happens to a UBC student's academic standing, and what standings exist?

**Reference:** There are three levels of academic standing: In Good Standing, On Academic Probation, and Failed, Required to Withdraw. Students enter the University In Good Standing.

**Route:** expected **simple**, router said **complex** (WRONG)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. What are the different academic standings that can be assigned to UBC students?
  2. What are the consequences or outcomes when a student's academic standing changes or is affected?

**Per-hop ids:** [[431, 430, 13784, 16033], [0, 13647, 16348, 1923]] → merged [431, 0, 430, 13647, 13784, 16348, 16033, 1923] (deduped away 0)

**`simple`** — depth 4, hit 1, recall@4 1.000, rr 0.500, grounded 1.000 (11/11)

  [431] Course Standings [2026/27] · [0] Academic Standing [2026/27] · [430] Course Standings [2026/27] · [13784] Academic Regulations [2026/27]

  # Academic Standing at UBC

There are three levels of academic standing at UBC:

1. **In Good Standing** — All students start here when they enter the University.

2. **On Academic Probation** — A student may be placed on academic probation based on academic performance. Students on probation may have restrictions placed on their registration, which vary by Faculty.

3. **Failed, Required to Withdraw** — Students with this standing are required to withdraw from their studies for 12 months. However, if the determination is made after the last date for withdrawal without a "W" being recorded, students already registered in courses may complete those courses.

A student receiving a "Failed, Required to Withdraw" standing may appeal to continue immediately, but cannot register for or attend courses while awaiting the appeal results (except as noted above).

For more details on how academic standing is determined and what specific performance thresholds apply to your program, see the official policy at https://vancouver.calendar.ubc.ca/campus-wide-policies-and-regulations/academic-standing, as requirements may vary by Faculty.

**`simple_matched`** — depth 8, hit 1, recall@4 1.000, rr 0.500, grounded 0.857 (12/14)

  [431] Course Standings [2026/27] · [0] Academic Standing [2026/27] · [430] Course Standings [2026/27] · [13784] Academic Regulations [2026/27] · [428] Course Standings [2026/27] · [3148] Bachelor of Science — Academic Performance Review and Continuation [2025/26] · [1665] Bachelor of Science — Academic Performance Review and Continuation [2026/27] · [429] Course Standings [2026/27]

  # Academic Standing at UBC

UBC has three levels of academic standing:

1. **In Good Standing** — All students begin at this level upon initial entry to the University.

2. **On Academic Probation** — A student may be placed on academic probation based on academic performance. Students on probation may have restrictions placed on their registration (which vary by faculty). A student who was previously required to withdraw and successfully appealed for readmission may also be placed on Academic Probation.

3. **Failed, Required to Withdraw** — Students assigned this standing are required to withdraw from their studies for 12 months. However, if this standing is determined after the last date for withdrawal without a "W" being recorded, a student already attending courses may complete them. Students can appeal to continue their studies immediately, though they cannot register for or attend courses while awaiting appeal results (except as noted above).

## How Standing Changes

A student's academic standing may change based on academic performance evaluations. The specific criteria for these changes vary by faculty—for example, Science students receive Failed Standing if they fall below a 50% sessional average in any Winter or Summer Session, while Forestry students must pass at least 50% of credits attempted and maintain a 60% or greater sessional average.

For the authoritative and most current details specific to your program, consult the official [Academic Standing](https://vancouver.calendar.ubc.ca/campus-wide-policies-and-regulations/academic-standing) page and your faculty's specific Academic Standing regulations.

**`agent`** — depth 8, hit 1, recall@4 1.000, rr 0.500, grounded 0.800 (8/10)

  [431] Course Standings [2026/27] · [0] Academic Standing [2026/27] · [430] Course Standings [2026/27] · [13647] Bachelor of Education — Academic Policies and Regulations [2026/27] · [13784] Academic Regulations [2026/27] · [16348] Bachelor of Kinesiology — Academic Regulations [2026/27] · [16033] Academic Regulations [2026/27] · [1923] Bachelor of Science — Illness, Academic Concession, and Deferred Standing [2026/27]

  # Academic Standing at UBC

UBC has three levels of academic standing:

1. **In Good Standing** — All students enter the University in this standing initially. This is the normal standing when academic performance is satisfactory.

2. **On Academic Probation** — A student may be placed on academic probation if their academic performance falls below satisfactory levels (specific thresholds vary by faculty). Students on academic probation may have restrictions placed on their registration.

3. **Failed, Required to Withdraw** — A student receives this standing when their academic performance is significantly deficient. Students assigned this standing must withdraw from their studies for a minimum of 12 months. However, if the determination is made after the last date for withdrawal without a "W" being recorded, the student may be permitted to complete courses already in progress. Students can appeal this decision.

**Note:** The specific grade point averages and percentages that trigger movement between these standings vary by faculty (for example, the School of Kinesiology uses a 55% threshold for good standing, while other faculties may use different standards). Additionally, some programs have additional standing categories specific to their requirements.

For the most current and detailed information specific to your program, consult the Academic Standing page at https://vancouver.calendar.ubc.ca/campus-wide-policies-and-regulations/academic-standing or your faculty's specific academic regulations.

**Δ agent−simple:** recall +0.000, gained [], lost [], +1 LLM calls, +2495 ms

### g002 — general — gold [1900]

**Q:** Roughly how many credits does a UBC B.Sc. degree require?

**Reference:** A minimum of 120 credits; some options require more.

**Route:** expected **simple**, router said **simple** (correct)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. Roughly how many credits does a UBC B.Sc. degree require?

**Per-hop ids:** [[1831, 3315, 1900, 3385]] → merged [1831, 3315, 1900, 3385] (deduped away 0)

**`simple`** — depth 4, hit 1, recall@4 1.000, rr 0.333, grounded 1.000 (4/4)

  [1831] Bachelor of Science — Credit at UBC and Elsewhere [2026/27] · [3315] Bachelor of Science — Credit at UBC and Elsewhere [2025/26] · [1900] Bachelor of Science — General Degree Requirements [2026/27] · [3385] Bachelor of Science — General Degree Requirements [2025/26]

  A UBC Bachelor of Science degree requires a minimum of **120 credits** for most options (major, combined major, double major, or General Science). An honours or combined honours option requires between 120 to 132 credits depending on the specific program.

The degree must be completed within a maximum of 180 attempted credits. Additionally, at least 50% of the credits must come from courses taken while registered in the UBC Vancouver B.Sc. program.

For the most current requirements, see the official calendar page on [General Degree Requirements](https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements).

**`simple_matched`** — depth 4, hit 1, recall@4 1.000, rr 0.333, grounded 1.000 (5/5)

  [1831] Bachelor of Science — Credit at UBC and Elsewhere [2026/27] · [3315] Bachelor of Science — Credit at UBC and Elsewhere [2025/26] · [1900] Bachelor of Science — General Degree Requirements [2026/27] · [3385] Bachelor of Science — General Degree Requirements [2025/26]

  A UBC B.Sc. degree requires a minimum of **120 credits** for most options (major, combined major, double major, or General Science).

However, the specific requirement depends on your degree option:
- **Honours or combined honours**: 120 to 132 credits (as specified by your department's specialization)
- **Dual degree**: More than 120 credits, though some combinations may be completed in fewer than 180 credits

You must also complete the degree within a maximum of 180 attempted credits. Additionally, at least 50% of your credits must come from courses taken while registered in the UBC Vancouver B.Sc. program.

For detailed requirements specific to your program, see the [Bachelor of Science General Degree Requirements page](https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements).

**`agent`** — depth 4, hit 1, recall@4 1.000, rr 0.333, grounded 1.000 (3/3)

  [1831] Bachelor of Science — Credit at UBC and Elsewhere [2026/27] · [3315] Bachelor of Science — Credit at UBC and Elsewhere [2025/26] · [1900] Bachelor of Science — General Degree Requirements [2026/27] · [3385] Bachelor of Science — General Degree Requirements [2025/26]

  A UBC B.Sc. degree requires a minimum of **120 credits** for a major, combined major, double major, or General Science option. However, an honours or combined honours option requires between 120 to 132 credits depending on the specific program.

The degree must be completed within a maximum of 180 attempted credits (including transferred credits).

For more details on specific program requirements, consult the [B.Sc. General Degree Requirements page](https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-science/bachelor-science/general-degree-requirements).

**Δ agent−simple:** recall +0.000, gained [], lost [], +1 LLM calls, +-740 ms

### g003 — general — gold [5]

**Q:** What is CPSC 110 at UBC about?

**Reference:** CPSC 110, Computation, Programs, and Programming (4 credits), covers fundamental program and computation structures.

**Route:** expected **simple**, router said **simple** (correct)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. What are the course description, learning outcomes, and main topics covered in CPSC 110?

**Per-hop ids:** [[5, 177, 8, 180]] → merged [5, 177, 8, 180] (deduped away 0)

**`simple`** — depth 4, hit 0, recall@4 0.000, rr 0.000, grounded 0.000 (0/5)

  [1] Computer Science, Faculty of Science [2026/27] · [173] Computer Science, Faculty of Science [2025/26] · [160] Bachelor of Science — Computer Science [2026/27] · [332] Bachelor of Science — Computer Science [2025/26]

  Based on the calendar excerpts, CPSC_V 110 is a first-year Computer Science course designed for students pursuing Computer Science specializations or who plan to take CPSC_V 210. It's the recommended introductory course for students continuing in Computer Science.

The calendar also notes that students with sufficient background in the concepts presented in CPSC_V 110 and an advisor's approval are encouraged to challenge the course for credit by taking an examination.

For more detailed information about course content, I'd recommend consulting the Department of Computer Science's website at http://www.cs.ubc.ca/students/undergrad or checking the full course descriptions on the calendar at https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv.

**`simple_matched`** — depth 4, hit 0, recall@4 0.000, rr 0.000, grounded 0.000 (0/5)

  [1] Computer Science, Faculty of Science [2026/27] · [173] Computer Science, Faculty of Science [2025/26] · [160] Bachelor of Science — Computer Science [2026/27] · [332] Bachelor of Science — Computer Science [2025/26]

  The excerpts provided describe what CPSC_V 110 is designed for rather than its specific course content. According to the calendar, CPSC_V 110 is the first-year Computer Science course intended for students pursuing Computer Science specializations or who plan to take CPSC_V 210. It's the recommended introductory course for students committed to further study in Computer Science.

For detailed information about the actual course content, topics covered, and learning outcomes, you would need to consult the course syllabus or contact the Department of Computer Science directly at http://www.cs.ubc.ca/students/undergrad.

See the full course descriptions at: https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**`agent`** — depth 4, hit 1, recall@4 1.000, rr 1.000, grounded 1.000 (6/6)

  [5] Computer Science, Faculty of Science [2026/27] · [177] Computer Science, Faculty of Science [2025/26] · [8] Computer Science, Faculty of Science [2026/27] · [180] Computer Science, Faculty of Science [2025/26]

  CPSC 110 is titled "Computation, Programs, and Programming" and is a 4-credit course. It covers fundamental program and computation structures, introductory programming skills, and computation as a tool for information processing, simulation and modelling, and interacting with the world. The course format is [3-3-0], indicating 3 hours of lecture, 3 hours of lab/discussion, and 0 hours of other activities per week.

For the most current and authoritative details, you can consult the official course description at https://vancouver.calendar.ubc.ca/course-descriptions/subject/cpscv

**Δ agent−simple:** recall +1.000, gained [5], lost [], +1 LLM calls, +-120 ms

### g004 — general — gold [128, 114]

**Q:** What kinds of requirements does a UBC Bachelor of Arts student have to complete?

**Reference:** B.A. students complete a set of faculty-wide degree requirements — for current entrants (2024/25 or later): Writing and Research, Ways of Knowing Breadth, Outside, Upper-level, and Arts Credit Minimum; earlier cohorts also had separate Language, Science, and Literature requirements.

**Route:** expected **complex**, router said **complex** (correct)

**Sub-questions** (nondeterministic — this is what to diff between runs):

  1. What are the general degree requirements for a UBC Bachelor of Arts program?
  2. What elective and breadth requirements must Bachelor of Arts students fulfill?
  3. What writing, quantitative, and other skill-based requirements apply to Bachelor of Arts students?

**Per-hop ids:** [[120, 292, 305, 831], [305, 300, 133, 128], [301, 129, 114, 286]] → merged [120, 305, 301, 292, 300, 129, 133, 114, 831, 128, 286] (deduped away 1)

**`simple`** — depth 4, hit 0, recall@4 0.000, rr 0.000, grounded 0.000 (0/7)

  [301] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [120] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2026/27] · [292] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2025/26] · [129] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27]

  Based on the calendar excerpts provided, Bachelor of Arts students must complete several key requirements:

1. **Writing and Research Requirement** — This has two components:
   - **Writing Component**: Students must complete 3 credits in a research and writing course (such as Arts One, ENGL 100, or WRDS 150/151, among others). This must be completed before reaching Year 3 standing. Students from secondary school should complete it before reaching 54 credits.
   - **Research Component**: The excerpts reference this but don't provide the full details.

2. **Language Requirement** — Students must demonstrate proficiency in a language other than English through one of three methods:
   - Complete a language course at BC Grade 12 level or equivalent prior to admission
   - Pass a proficiency test
   - Complete language courses at UBC to reach a specified proficiency level

3. **Ways of Knowing Breadth Requirements** — Referenced in the Writing Component section, though the excerpts don't detail these fully.

The excerpts provided don't contain complete information about all degree requirements. For a comprehensive overview of all BA requirements (including total credits needed, major/minor requirements, and other specifics), I'd recommend consulting the full calendar page at https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/ for the most current details.

**`simple_matched`** — depth 11, hit 0, recall@4 0.000, rr 0.000, grounded 0.000 (0/9)

  [301] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [120] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2026/27] · [292] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2025/26] · [129] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27] · [305] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [133] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27] · [116] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2026/27] · [288] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2025/26] · [935] Bachelor of Arts — Degree Program Options [2026/27] · [2561] Bachelor of Arts — Degree Program Options [2025/26] · [311] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26]

  # Bachelor of Arts Requirements

UBC Bachelor of Arts students must complete several key requirements:

1. **Writing and Research Requirement** – Students must complete 3 credits in a designated research and writing course (such as Arts One, ENGL_V 100, WRDS_V 150/151, or similar) before reaching Year 3 standing. This must be attempted early in the degree (within the first 30 credits for direct secondary school entrants, or first Winter Session for transfer students).

2. **Ways of Knowing Breadth Requirement** – Students must complete 18 credits across three of the four breadth areas (Humanities and Creative Arts, Language as Meaning, Natural and Physical Sciences, and Social and Behavioural Systems), distributed as 9 credits, 6 credits, and 3 credits respectively. The fourth area is covered by the student's major.

3. **Place and Power Requirement** – Students must complete 3 credits from an approved course list focused on structures of marginalization and oppression.

4. **Language Requirement** – Students must demonstrate proficiency in a language other than English, either through secondary school coursework, passing a proficiency test, or completing specified language courses at UBC.

5. **Program of Study Requirement** – Students must complete at least one Major or Honours program (single or combined), or an Interdisciplinary Studies program.

6. **Arts Credit Minimum** – A minimum of 72 of the 120 total credits must be Arts credit.

For the most current and detailed information, see the official Bachelor of Arts degree requirements pages on the UBC Calendar.

**`agent`** — depth 11, hit 0, recall@4 0.000, rr 0.000, grounded 0.800 (4/5)

  [120] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2026/27] · [305] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [301] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [292] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2025/26] · [300] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2025/26] · [129] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27] · [133] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27] · [114] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2026/27] · [831] Bachelor of Arts — Admission and Transfer [2026/27] · [128] Bachelor of Arts — Degree Requirements for students who enter the program in 2024/25 or later [2026/27] · [286] Bachelor of Arts — Degree Requirements for students who enter the program in 2023/24 or earlier [2025/26]

  # Bachelor of Arts Requirements

The requirements depend on when you entered the program:

**If you entered in 2023/24 or earlier**, you must complete seven requirements:

1. Writing and Research Requirement
2. Language Requirement
3. Science Requirement
4. Literature Requirement
5. Outside Requirement
6. Upper-level Requirement
7. Arts Credit Minimum Requirement

**If you entered in 2024/25 or later**, you must complete five requirements:

1. Writing and Research Requirement
2. Ways of Knowing Breadth Requirement
3. Outside Requirement
4. Upper-level Requirement
5. Arts Credit Minimum Requirement

The newer requirements (for 2024/25 entry and later) replace the separate Language, Science, and Literature requirements with a more flexible "Ways of Knowing Breadth Requirement" that allows you to choose coursework across multiple disciplinary areas.

For the most current and detailed information about your specific cohort, consult:
- [2026/27 calendar for 2023/24 entry](https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202324-or-earlier)
- [2026/27 calendar for 2024/25 entry](https://vancouver.calendar.ubc.ca/faculties-colleges-and-schools/faculty-arts/bachelor-arts/degree-requirements-students-who-enter-program-202425-or-later)

**Δ agent−simple:** recall +0.000, gained [], lost [], +1 LLM calls, +3272 ms

