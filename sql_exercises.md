# SQL practice on the HMDA Maryland project

Write each query yourself in `diagnostics.py` (views `lar`, `lender_scorecard`, `lender_oe` already exist there).
Open hints one level at a time. Check your numbers against the sanity checks.
Reference for the DataLemur CTE / subquery tutorial: https://datalemur.com/sql-tutorial/sql-cte-subquery

## Done

| # | Skill | What it built |
|---|---|---|
| Q1 | CTE, `NTILE`, `FILTER` (diagnostics.py) | Outcome split, field availability by outcome, loan-size quartile × channel |
| Q2 | Two CTEs + `CROSS JOIN` | `lender_scorecard`: rates and gaps vs Maryland per lender |
| Q3 | Join a summary CTE back onto detail rows | Mix-adjusted walk-away (observed ÷ expected) |
| Q4 | Same pattern + `CASE`, saved as `CREATE VIEW` | `lender_oe`: walk-away and denial O/E |
| Q5 | `NOT EXISTS` correlated subquery | Pareto frontier on mix-adjusted O/E (7 lenders) |

---

## To do (in this order)

### Q5b. Raw vs adjusted frontier
Run the Q5 query on `lender_scorecard` (`walkaway_pct`, `denial_pct`), then build one table showing each lender
that is on **either** frontier and which one(s).

**Hint 1:** Step 1 is only a rename: same query, new view, new column names.
**Hint 2:** Turn each frontier into a CTE returning `lei`. Start from `lender_scorecard`, join `lender_oe` on `lei`,
`LEFT JOIN` both CTEs, and flag with `CASE WHEN f.lei IS NOT NULL THEN 1 ELSE 0 END`.
**Check:** 7 lenders on each frontier, 4 on both, 10 in the final table.
**Think:** what do the lenders on the raw frontier but not the adjusted one have in common (`purchase_share`)?

### Q6. Does the frontier cost the borrower?
For **originated conventional purchase loans** (`loan_type = '1'`, `purpose_label = 'purchase'`), find each lender's
median `rate_spread` and median `total_loan_costs` (lenders with ≥ 100 such loans). Compare frontier lenders with the rest.

**Concept:** `MEDIAN()` aggregate, `IN (subquery)` or a `LEFT JOIN` flag.
**Hint 1:** filter first (`WHERE`), group by `lei`, then attach the frontier flag from Q5b.
**Hint 2:** compare group medians with an outer `GROUP BY is_frontier`. Do not average the lender medians blindly; ask whether to weight by loans.
**Check:** 37,036 originated loans overall; overall median `rate_spread` ≈ 0.17, median `total_loan_costs` ≈ $6,245; 79 lenders with ≥ 100 loans.
**Watch out:** pricing only exists for originated loans (survivorship), which is why the segment is held fixed.

### Q7. Why are applicants denied?
`denial_reason` codes: 1 DTI, 2 employment history, 3 credit history, 4 collateral, 5 insufficient cash,
6 unverifiable information, 7 credit application incomplete, 8 mortgage insurance denied, 9 other.
For each loan purpose, show each reason's share of that purpose's denials, ranked.

**Concept:** window `SUM(COUNT(*)) OVER (PARTITION BY purpose_label)` and `RANK()` or `ROW_NUMBER()`.
**Hint 1:** `WHERE outcome = 'lender_denied'`, group by purpose and reason, then divide by the purpose total with a window function.
**Check:** purchase: DTI (code 1) is the top reason, 2,045 denials; cash-out refi: credit history (code 3), 1,573.
**Think:** code 7 ("application incomplete") is a process failure, not a credit decision. How big is it for refinances?

### Q8. Geography
For counties with ≥ 1,000 applications: walk-away % and denial %, and which lender has the most applications in each
county.

**Concept:** `HAVING`; correlated subquery `WHERE apps = (SELECT MAX(apps) ... WHERE county_code = outer.county_code)`.
Then redo the "top lender" with `ROW_NUMBER() OVER (PARTITION BY county_code ORDER BY apps DESC)`. Know both.
**Check:** 18 counties; highest walk-away is county 24033 (28.5%), lowest 24001 (19.3%).

### Q9. Does the frontier survive a stricter adjustment?
Rebuild `lender_oe` with **income quintile** as a third adjustment column (segment = purpose × loan type × income band).
How many of the 7 adjusted-frontier lenders remain?

**Concept:** extend the CTE chain (`NTILE` in `seg_rate`'s source, join on three columns). Exclude income ≤ 0 or NULL.
**Check:** O/E averaged over all applications should still be ≈ 1.0. Report overlap as "k of 7".
This is the robustness check for Finding 6.

---

After each: add a `### Finding N` to `findings.md` (Result / Interpretation / Limitation), then
`python build_data.py` if the change feeds the app.
