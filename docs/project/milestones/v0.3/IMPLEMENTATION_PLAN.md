# Milestone v0.3 Implementation Plan — Plain-English Questions, Evidence-Backed Answers

**Draft for project-owner review.** Nothing here is approved or scheduled until Milestone v0.2
closes. The [Master Plan](../../MASTER_PLAN.md#milestone-v03-plain-english-questions-evidence-backed-answers)
owns the milestone's place in the roadmap; the
[Discovery Workbook](../../DISCOVERY_WORKBOOK.md#7-ai-philosophy) owns the reasons.

## 1. At a glance

- **What this milestone does:** a person asks a question in ordinary words
  (`ian ask "Is this company's financial position getting weaker?"`) and gets an answer in ordinary
  words. The answer is built only from evidence the engine has stored.
- **What a model is allowed to do:** four narrow jobs. Understand the question. Read a named part
  of a filing and answer a fixed question about it. Write sentences. Check sentences against
  evidence.
- **What a model is never allowed to do:** arithmetic, typing a number into an answer, giving
  advice, or scoring, ranking or predicting anything about an instrument.
- **What it does not add:** a chat window, memory between questions, news or web reading, a cloud
  model, or unattended running. Full list: [Out of scope](#4-out-of-scope).
- **Rules every work package follows:** measure a model-based step against known answers before
  relying on it; prefer a plain rule when it does the job as well; everything runs under Light Mode;
  the managed quality gate after every slice.

## 2. Sequence and status

| Order | Work | Status | Completed |
| :--- | :--- | :--- | :--- |
| 1 | [Feasibility checks (ASK.0)](#ask0--feasibility-checks) | Planned | |
| 2 | [Forecast ledger, recording only (FL.1)](#fl1--forecast-ledger-recording-only) | Planned | |
| 3 | [Filing events, no model (FR.1)](#fr1--filing-events) | Planned | |
| 4 | [Ask: question in, stored answer out (ASK.1)](#ask1--ask) | Planned | |
| 5 | [Answer check (ASK.2)](#ask2--answer-check) | Planned | |
| 6 | [Filing reading, with a model (FR.2)](#fr2--filing-reading) | Planned | |
| Deferred | [Unusual-year flag (candidate)](#candidate-unusual-year-flag) | Deferred | |
| Deferred | [Forecast ledger scoring](#deferred-forecast-ledger-scoring) | Deferred | |
| Deferred | [Reader as a separate package](#deferred-reader-as-a-separate-package) | Deferred | |

**Two outcomes, both a success.** ASK.0 decides which one this milestone delivers. The floor is a
complete product, not a consolation: it needs no model at all.

| | Floor | Full |
| :--- | :--- | :--- |
| **Asking** | A fixed menu of question types; free text is matched to the menu by keywords | Free-text questions |
| **Writing** | Sentences assembled by rule from templates | Sentences written by a model, then checked |
| **Filing evidence** | Filing events, plus keyword rules for prose | The same, plus model filing readings |
| **Relevance** | Topic rule | Topic rule, or a model if it wins |
| **Filters** | Chosen with command options | Stated in words |
| **Needs a model** | No | Yes, within Light Mode |

At both levels the engine places every number, every statement has a source, answers are stored as
Answer Records, and advice is declined. A user with Full Dual-Tier hardware may get more, but Light
Mode always gets at least the floor.

**Work-package codes.** `ASK` covers the path from a question to a stored answer. `FR` ("filing
records") covers new evidence taken from SEC filings. `FL` is the forecast ledger. Letter codes are used because Steps 4–7 are
already taken by later milestones.

**Why this order.** ASK.0 decides whether the model-based parts are worth building at all. FR.1
needs no model, so it delivers new evidence whatever ASK.0 finds. FL.1 is small, depends on
nothing else here, and earns nothing until it starts, so it goes early. ASK.1 and ASK.2 give plain-English
answers over evidence that already exists. FR.2 comes last because it depends most on ASK.0's
results.

## 3. The work packages

### ASK.0 — Feasibility checks

- **Problem:** the milestone rests on three things nobody has measured: that a Light Mode model can
  turn a question into the right research plan, that a local model can read a filing passage
  accurately, and that both fit in Light Mode's memory.
- **Decision:** measure first. No product interface or contract is written until the results are
  in. The one exception is the small reader interface the measuring itself needs.
- **Scope:**
  - *Question understanding.* A fixed set of at least 100 plain-English questions, each with the
    plan it should produce. The set includes questions that must be declined and questions that
    state a preference ("only companies with low debt").
  - *Relevance.* At least 200 question-and-result pairs, each labelled by hand as *bears on the
    question* or *does not*. The baseline is the topic rule: a result is relevant when its strategy
    declares a topic the question asks about.
  - *Filing reading.* For each candidate question, at least 50 passages where the answer is
    *found* and 50 where it is *not found*. The second group includes hard cases, such as
    "prepared on a going-concern basis", where the key words appear without the fact. Labels come
    from SEC records or review by hand, never from a model. Three readers are compared on the same
    passages: a keyword rule, the Light Mode model limited to fixed choices, and a small
    text-comparison model.
  - *Sentence checking.* At least 200 correct sentences and 200 copies with a planted error (a
    reversed direction, a wrong label, a claim with no evidence behind it). A rule generates the
    planted errors from stored runs, so the set costs nothing to enlarge.
  - *Fit.* Peak memory and time per answer on Light Mode hardware, recorded with model names and
    versions. Two things are checked directly: whether the installed Ollama version exposes the
    model's probability for each fixed choice, and whether loading a second model forces the first
    out of memory.
- **One reader, built once:** relevance, filing reading and sentence checking are the same kind
  of job. Each takes some text and one fixed question, and returns one of a few fixed answers, with
  a quoted passage where one applies. ASK.0 defines that one narrow interface and builds the
  measuring harness against it. FR.2 and ASK.2 then reuse both.
- **What happens to the model's own doubt:**
  - If the model exposes a probability for each fixed choice, it is stored with the reading. It is
    never shown to an investor.
  - A cut-off is chosen on the tuning examples: below it, the reading becomes *not determined*.
    The cut-off is then confirmed on the held-out set.
  - Results report two figures together: the share of passages answered, and how often those
    answers were right.
- **Rules for a fair test:**
  - Every set and every bar is fixed before the first measured run.
  - The sets above are held out, and only they count. Prompts are tuned on separate examples,
    which may be fewer.
  - A stated preference from one person is never used as an answer key. It records taste, not
    fact.
- **Stop rules:**
  - Question understanding misses its bar → ASK.1 offers a fixed menu of question types, not free
    text.
  - No reader beats the keyword rule → FR.2 ships keyword rules only, or is deferred.
  - A second model does not fit beside the Light Mode model → one model does every job, or the
    job is dropped.
  - Choice probabilities are not available → the reader relies on its three fixed answers alone,
    with *not determined* as the way to express doubt.
- **Branch:** not opened.
- **Detail:** ⚠ no slice plan yet

### FL.1 — Forecast ledger, recording only

- **Problem:** Step 4.3 will ask for evidence that a method is any good before a composite screen or
  ranking is allowed. That evidence takes a year or more to build up, and nothing builds up until
  recording starts.
- **Decision:** start recording now and score later. Each covered Analysis Run stores a few dated
  questions that later facts will settle.
- **Scope:**
  - A short fixed list of questions, each answerable from facts the engine already fetches. For
    example: "will next fiscal year's diluted EPS be higher than this year's?"
  - Each entry holds the question and its version, the instrument's identity, the run's as-of date,
    the date after which it can be settled, and a prediction from a trivial rule such as "same
    direction as last year".
  - No model is involved, and nothing is scored yet.
  - Entries are measurement records. They are never shown in an answer or any investor view; a
    prediction beside a ticker would break the evidence-not-advice rule.
- **Timing:** begins only after Step 3.5, when stored result shapes have settled. Entries recorded
  against shapes that later change would be thrown away.
- **Branch:** not opened.
- **Detail:** ⚠ no slice plan yet

### FR.1 — Filing events

- **Problem:** several plain warning signs sit in SEC's filing records and never reach an analysis:
  a notice that a report will be late, a change of auditor, a statement that earlier financial
  statements can no longer be relied on, an amended annual report.
- **Decision:** read them from the filing index and cover-page tags. No model is involved. Each
  event carries its form type, filing date and acceptance time, so a request "as of" an earlier date
  never sees a later filing.
- **Scope:**
  - Delivered as an ordinary analysis strategy, so it appears in direct commands, watchlists,
    Analysis Runs and JSON without new plumbing.
  - Each check answers *found*, *not found* or *unavailable* with a reason, like every other result.
  - Candidate checks: late-filing notices; 8-K items reporting an auditor change, non-reliance on
    earlier statements, or an officer's departure; amended annual reports.
  - First slice confirms, against live SEC records, exactly which fields supply each check and from
    what date they are dependable. A check without dependable source fields is dropped.
- **Relation to existing plans:** approves the model-free part of the "Filing red flags" candidate
  in the [Evidence Provider Roadmap](../../EVIDENCE_PROVIDER_ROADMAP.md#new-analysis-strategies).
- **Branch:** not opened.
- **Detail:** ⚠ no slice plan yet

### ASK.1 — Ask

- **Problem:** local-model tool calling exists only inside the evaluation harness. There is no way
  for a person to ask a question.
- **Decision:** one command with five fixed stages: understand, gather, write, check, store. The
  model chooses from menus and writes sentences; the engine does everything else.
- **Scope:**
  - *Understand.* The model produces a typed research plan: which instrument, which topics, which
    date. Topics come from a short fixed list (for example valuation, financial strength, earnings
    quality, price trend, filing events). Each strategy declares the topics it speaks to; rules the
    engine already has decide which strategies apply to the instrument.
  - *Decline.* Requests for advice, predictions, or "which is better" comparisons are declined in
    one or two sentences that say what the engine can show instead.
  - *Gather.* Analyses run through the existing workspace path and are stored as Analysis Runs.
    Every analysis that applies is run; they are cheap, so a vague question costs nothing extra.
  - *Order by relevance.* The topic rule decides which results bear on the question. That decides
    what the written answer leads with and what it leaves to `--details`. A model replaces the rule
    only if it beats it in ASK.0. Either way, relevance never decides which instrument looks better.
  - *Stated-preference filters.* When the investor says what they want ("low debt, and no
    going-concern doubt"), the model turns those words into a typed filter over existing results.
    - The engine shows the filter back in plain words before applying it.
    - The engine applies it by rule. A result that is unavailable stays unavailable; it is never
      counted as a fail.
    - The model adds no condition the investor did not state, and supplies no weights.
    - Conditions are joined by "and" only.
    - The investor may name one measure to sort the passing results by ("highest FCF yield first").
      The engine sorts by rule and lists unavailable values last. With no named measure, results
      stay in watchlist order.
    - The filter belongs to the investor. The engine makes no claim that passing it is good.
    - This is the smallest useful form of the "three-valued composable screens" candidate in the
      [Evidence Provider Roadmap](../../EVIDENCE_PROVIDER_ROADMAP.md#cross-cutting-platform-features).
  - *Write.* The model returns a list of sentences. Each sentence names the evidence it rests on
    and leaves a slot wherever a number belongs. The engine fills the slots from stored values. A
    sentence in which the model typed a digit is rejected.
  - *Say what is missing.* Evidence that could not be obtained is stated, with its reason. It is
    never skipped.
  - *Store.* The question, plan, evidence references, sentences, model name and version, and check
    results are kept as an Answer Record. Showing a stored answer again never calls a model.
  - Every answer ends with the same fixed line saying it is evidence for research, not advice.
- **Branch:** not opened.
- **Detail:** ⚠ no slice plan yet

### ASK.2 — Answer check

- **Problem:** slots stop wrong numbers. They do not stop wrong words: "fell" when the value rose,
  or "safe" when the result says "grey zone".
- **Decision:** check every sentence before it is shown, rules first and a model second.
- **Scope:**
  - *Rules.* Every sentence names at least one piece of evidence. Direction and label words are
    compared with the stored values. Advice wording is refused.
  - *Model.* For what rules cannot settle, one fixed question: does this evidence support this
    sentence — yes, no, or unclear?
  - *Outcome.* A sentence that fails is removed and the answer says so. If too many fail, the answer
    falls back to the ordinary result views, which need no model.
- **Boundary:** this checks the engine's own sentences against its own evidence. It is not the
  general claim-verification engine set aside on 2026-09-23.
- **Branch:** not opened.
- **Detail:** ⚠ no slice plan yet

### FR.2 — Filing reading

- **Problem:** some facts exist only as prose. The clearest case is an auditor's statement of
  substantial doubt that the company can continue as a going concern.
- **Decision:** a short fixed list of questions, each tied to a named part of a named filing type.
  The reader answers *found*, *not found* or *not determined*, and quotes the passage it relied on.
  It never produces a number or a summary.
- **Scope:**
  - Starting candidates, at most three: going-concern doubt in the auditor's report; a reported
    material weakness in internal control; a disagreement reported alongside an auditor change.
    ASK.0's results choose the final list.
  - A question ships only if its reader meets the bars in [Acceptance criteria](#5-acceptance-criteria)
    and beats the keyword rule. Otherwise the keyword rule ships, or the question is left out.
  - Doubt is handled as ASK.0 sets out: a stored probability where the model exposes one, a
    measured cut-off, and *not determined* below it.
  - Filings are fetched through the existing size-limited filing reader.
  - Readings join FR.1's output as further checks, so analyses and answers use them the same way.
- **Branch:** not opened.
- **Detail:** ⚠ no slice plan yet

### Candidate: unusual-year flag

- **Problem:** a multi-year average, such as three-year-average EPS, can hide one year that is far
  from the others. How much to trust the average is then a fair question.
- **Decision proposed:** a rule, not a model. The engine flags the unusual year as a warning beside
  the result. The number itself does not change, and no model decides how much weight a year
  deserves; that would be reweighting a calculation.
- **Scope if approved:** a written definition of "unusual" with its threshold, added through the
  normal method-specification process; the warning in concise and detailed views; fixtures.
- **Link to filing reading:** the reason for an unusual year is often stated in the filing. "Does
  the filing attribute this year's result to a one-time item?" is a candidate FR.2 question.
- **Why not scheduled:** it touches existing strategies' output, so it needs its own approval.

### Deferred: forecast ledger scoring

- **Idea:** once enough entries from FL.1 can be settled, score each predictor against what
  happened and keep the running record.
- **Why it matters:** it is the evidence Step 4.3 requires before any composite screen or ranking,
  and it works with any predictor, including a trivial one.
- **A faster start:** because analyses can run "as of" a past date, a question posed as of 2022 can
  be scored against 2023 facts today. This is sound for rule-based predictors only. A language
  model may already know what happened.
- **Why deferred:** scoring needs settled entries, and recording has only just begun.

### Deferred: reader as a separate package

- **Idea:** the fixed-question reader is not specific to finance and could live in its own package.
- **What is not deferred:** the interface. ASK.0 defines it once, with its measuring harness, so
  FR.2 and ASK.2 do not each grow their own.
- **Why the package is deferred:** one project using it is not evidence that a second one would.

## 4. Out of scope

- Advice to buy, sell or hold, and any score, rank or probability about an instrument's future.
- Model-based ranking or comparison of instruments. Composite screens stay with Step 4.3 and its
  validation requirements. The test: if a model's answer would change which instrument looks
  better, the job does not belong to a model.
- Filters with weights, scores, "or" conditions, sorting by more than one measure, or conditions
  the investor did not state.
- Showing a forecast-ledger entry in any investor view.
- Memory between questions. Each question stands alone.
- Reading news, web pages, earnings-call transcripts or anything other than SEC filings.
- A cloud or hosted model in the core path.
- A chat window, graphical interface or full-screen terminal interface.
- Unattended or scheduled questions.
- An MCP server or HTTP interface. Those stay with the
  [deferred delivery-surfaces record](../v0.2/deferred/DEFERRED_STANDARD_DELIVERY_SURFACES.md), which
  should reuse the Answer Record shape when it is taken up.

## 5. Acceptance criteria

The project owner approved these bars, and the held-out set sizes in ASK.0, on 2026-10-06. They are
fixed before any measured run; changing one afterwards needs a new decision record.

- **Traceable:** every sentence in every answer on the question set names stored evidence. Target:
  all of them.
- **No model-typed numbers:** zero across the question set, enforced by a rule and a test.
- **Question understanding:** the correct plan for at least 90 of 100 held-out questions; every
  advice request declined.
- **Relevance**, on at least 200 held-out pairs: at most 1 in 10 results that bear on the question
  is left out of the answer. A model is used only if it beats the topic rule on the pairs where the
  two disagree, by the same sign test as filing reading. Otherwise the topic rule ships.
- **Forecast ledger:** every Analysis Run of a covered strategy records its questions, and no
  ledger entry appears in any investor view.
- **Stated-preference filters:** the typed filter matches the stated conditions, with nothing added
  and nothing dropped, for at least 90 of 100 held-out requests. Every filter is shown back before
  it is applied.
- **Filing reading**, per question, on 100 held-out passages (50 *found*, 50 *not found*):
  - at most 4 wrong answers. That shows better than 9 in 10 with 95% confidence; 5 wrong does not.
  - wrong *found* and wrong *not found* are reported separately.
  - at most 1 in 5 passages is *not determined*.
  - against the keyword rule, the reader must win the passages where the two disagree by a margin a
    sign test accepts at the 5% level, for example 10 of 12. With fewer than about 10
    disagreements, the keyword rule ships instead.
- **Answer check**, on at least 200 planted errors and 200 correct sentences: catches at least 9 in
  10 planted errors while removing at most 1 in 20 correct sentences.
- **Wording:** a reader that passes is described as "validated at its threshold", never as
  "calibrated". A few hundred cases cannot support the stronger word.
- **Light Mode:** the whole path runs on the supported Light Mode configuration, with model names,
  versions, memory and timings recorded.
- **Replay:** showing a stored answer makes no model call and no network call.
- **Always an answer:** when a model is unavailable or the check fails, the user still gets the
  ordinary result views.
- The managed quality gate passes; deterministic tests make no model or network calls.
- **Level reached:** the milestone exits at the floor or at full. Which one, and the ASK.0 results
  behind it, are recorded in this plan.

## 6. Background

- The project's settled role is a point-in-time evidence provider. This milestone adds a way to ask
  for that evidence, and to have it explained, in ordinary words.
- An earlier proposal placed a model-based "decision layer" after the analyses to select, gate and
  rank results. The workbook records why that was not adopted, which narrow jobs over stored
  results were kept, and what would reopen the question:
  [Why not a decision layer](../../DISCOVERY_WORKBOOK.md#why-not-a-decision-layer).

## Appendix A: Decision records and history

### A.1 Acceptance bars and set sizes approved

On 2026-10-06 the project owner approved the acceptance bars in
[Acceptance criteria](#5-acceptance-criteria) and the held-out set sizes in
[ASK.0](#ask0--feasibility-checks): about 100 questions, 200 relevance pairs, 100 passages per
filing question, and 200 correct plus 200 planted-error sentences. The labelling effort this implies
was accepted. The rest of this plan remains a draft until Milestone v0.2 closes.
