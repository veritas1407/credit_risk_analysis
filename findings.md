### Finding 1 — Walk-aways exceed lender denials

**Result:** Of 118,431 scoped Maryland applications in 2024, 25.7% were classified as walk-aways, compared with 11.6% denied by the lender. Originations accounted for 62.7%.

**Interpretation:** Applicant exit is a substantial part of the mortgage funnel and deserves investigation alongside lender rejection.

**Limitation:** The walk-away category combines withdrawals, incomplete applications, and customer-declined approvals. Withdrawal timing is unknown, so these outcomes do not all represent confirmed rejection of a mortgage offer.




### Finding 2 — Recorded information varies by outcome

**Result:** Numeric DTI is present for 93.7% of originated applications and 88.4% of lender-denied applications, compared with 0% of withdrawn and incomplete applications. Income remains recorded for 95.0% of withdrawals and 82.6% of incomplete applications.

**Interpretation:** Withdrawn and incomplete applications have substantially less recorded underwriting and pricing information. This supports investigating early-funnel friction.

**Limitation:** Missing DTI is only a proxy for funnel depth, not a directly observed underwriting event. Missing data does not reveal exactly why the application ended.

### Finding 3 — Channel matters more than loan size

**Result:** Direct-channel applications walk away at 27.5% versus 17.1% for indirect (broker) applications. The gap holds inside every loan purpose: for cash-out refinances, 35.0% of direct applications originate versus 55.8% of indirect; for purchases, 72.2% versus 74.4%.

**Interpretation:** Applicants who come through a broker are far less likely to exit, and the effect is largest for refinances. A broker plausibly chases the file to the finish line, which a direct online or branch applicant has to do alone. This points to guided follow-up and status nudges as the product lever, most of all for refinance applicants.

**Limitation:** Channel is not randomly assigned. Brokers may attract more committed, more rate-shopped, or better-qualified borrowers, and HMDA has no credit score to control for that. This is an association, not a measured effect of brokers.


### Finding 4 — Income lowers denials but not walk-aways

**Result:** Across five equal income bands (about 22,000 applications each), the denial rate falls from 20.5% in the lowest band to 6.9% in the highest, while the walk-away rate stays flat at 23.9–25.4%.

**Interpretation:** Higher-income applicants get approved more often but are no more likely to stay. Income does not account for walk-aways. This does not rule out other affordability or credit factors; process and experience are one hypothesis to test.

**Limitation:** 7,196 applications with missing income and 1,234 with zero or negative income are excluded. Income is reported in thousands of dollars and contains extreme values (maximum 400,000 = $400 million), so band edges are driven by the middle of the distribution only.


### Finding 5 — Raw lender walk-away rankings are distorted by loan mix

**Result:** Refinance-heavy lenders look worst on raw walk-away rate: for example one lender at 58.9% walk-away has only 1% purchase loans, 33 percentage points above the state rate. After adjusting for loan purpose × loan type (observed ÷ expected), its O/E falls to 1.42 and a lender at 54.4% raw walk-away with 69% purchase loans moves to O/E 2.26, the second worst of 111. The largest lender (7,533 applications) has a raw walk-away of 12.0% against 28.0% expected for its mix, an O/E of 0.43.

**Interpretation:** Comparing lenders on raw abandonment penalises those that mostly refinance and hides purchase-focused lenders who lose many applicants. Mix-adjusted rankings identify which lenders lose applicants beyond what their book predicts. The highest excess volume sits with two mid-sized lenders, each losing roughly 500–600 more applicants than their mix predicts.

**Limitation:** Only purpose × loan type are adjusted. Income, loan size, county and credit quality are not, and a low denial or walk-away rate on 200–500 applications is noisy. A high O/E is a flag for investigation, not proof of a weaker process.


### Finding 6 — Low walk-aways can come with high denials; the frontier separates the two

**Result:** Using mix-adjusted walk-away and denial O/E, seven of 111 lenders sit on the Pareto frontier (no other lender is at least as good on both and better on one). Only four of these appear on the frontier when raw rates are used instead; Three lenders are on the adjusted frontier only (including Rocket Mortgage, the largest lender) and three on the raw frontier only (including NVR Mortgage Finance). Lenders with the lowest walk-away O/E can have very high denial O/E, for example 0.49 walk-away with 2.92 denial O/E at one lender that denies 69.6% of applications.

**Interpretation:** A lender can look excellent on retention while denying most applicants. Ranking on both measures together, after adjusting for mix, picks out lenders that hold applicants and approve them. Four lenders are better than their mix predicts on both measures and have 455 or more applications each.

**Limitation:** The frontier is sensitive to small samples, especially lenders with only a few dozen denials. Two of the seven frontier lenders have 223–455 applications. Pricing is not analysed because pricing fields exist only for originated loans, which would introduce survivorship bias.


### Finding 7 — The clearest leak is incomplete files in direct-channel refinances

**Result:** 12.2% of direct-channel refinance and cash-out applications (4,221 of 34,527) are closed as incomplete, against 4.0% through brokers and 1.7% for direct purchases. Direct refinances account for 73% of the 5,754 stalled files in the state. Cash-out: 11.9% direct vs 3.7% broker; refinance: 12.6% vs 4.1%.

**Interpretation:** The gap is concentrated in direct refinances. A document collection and follow-up problem is a plausible explanation that a product could address, but HMDA records no reason, so the test has to establish it. Unfinished files are also the smaller part of walk-aways: 4.9 of every 100 applications, against 17.9 withdrawals.

**Limitation:** Brokers pre-screen and coach their borrowers, so not all of the direct-versus-broker gap is recoverable. HMDA does not record why a file was closed incomplete or when.


### Finding 8 — In Maryland, high-retention lenders do not charge more

**Result:** On originated conventional purchase loans (lenders with 100+ such loans), the four lenders on both the mix-adjusted and income-adjusted frontier have a median rate spread of 0.18 and median loan costs of $6,264, against 0.16 and $6,243 for all other lenders (72 lenders). Across 78 lenders, walk-away O/E is uncorrelated with price (Spearman |ρ| ≤ 0.13); denial O/E has a small negative correlation with price (−0.15 to −0.29).

**Interpretation:** In Maryland there is no sign that retention comes with higher prices; this does not hold cleanly in every state. Stricter lenders price slightly lower, consistent with taking safer borrowers.

**Limitation:** Pricing fields exist only for originated loans (survivorship), there is no credit score, and few frontier lenders have enough conventional purchase volume to compare.


### Finding 9 — Denial reasons differ by purpose, and DTI has a cliff at 50%

**Result:** Purchases are denied mainly for debt-to-income (37.2% of purchase denials); cash-out refinances for credit history (27.2%) and DTI (23.4%). "Credit application incomplete" accounts for 21.2% of cash-out and 19.1% of refinance denials but 7.1% of purchase denials. Among originated or denied files with a recorded DTI, the denial rate is 9–10% from 20% to 49% DTI, then 26.6% at 50–60% and 89.5% above 60%.

**Interpretation:** The 50% DTI line behaves like a policy threshold, and applicants approaching it are the natural place for earlier guidance. The incomplete-application denials may reflect the same document problem as the stalled files in Finding 7; the data cannot confirm it.

**Limitation:** Only the first of up to four reported denial reasons is kept. DTI is only recorded for files that reached underwriting, so denial rates by DTI exclude withdrawn files. The 19.3% denial rate below 20% DTI is unexplained.


### Finding 10 — Geography matters little once loan mix is removed

**Result:** Across the 18 jurisdictions with 1,000+ applications, raw walk-away runs from 19.3% to 28.5%, but the mix-adjusted observed ÷ expected ratio runs only from 0.75 to 1.10. Prince George's County and Baltimore City have the highest denial O/E (1.27 and 1.21). The largest lender in most counties has only 6–8% of applications.

**Interpretation:** County adds little to explaining walk-aways. This does not show what the lever is.

**Limitation:** County is the only geography in this data (no tract-level analysis), and 252 applications have no county reported.


### Finding 11 — The frontier holds up partly under stricter checks

**Result:** Of the 7 lenders on the mix-adjusted frontier, 5 stay on it when income band is added to the adjustment and 4 stay when only lenders with 500+ applications are considered. Four lenders appear on both the raw and the adjusted frontier. 36 of 111 lenders have significantly more walk-aways than their mix predicts (z > 1.96) and 44 significantly fewer; the 36 account for about 4,160 excess walk-aways.

**Interpretation:** The headline frontier is a shortlist for investigation, not a final ranking. Lenders on the frontier under every view are the most credible benchmarks.

**Limitation:** With 111 lenders and no multiple-comparison correction, some flags will be false alarms, though the largest z-values are far beyond chance. Income is missing for 7,196 applications.


### Finding 12 — Size of the prize and how to test it

**Result:** Closing 25% of the direct-versus-broker incomplete-file gap in refinances recovers about 718 files, or 606 funded loans (~$196M of volume, ~$2.0M revenue at 100 bps) in Maryland in one year. At the 36 significantly worse lenders, closing 25% of excess walk-aways gives about 877 funded loans (~$329M). A randomised test on incomplete files (12.2% → 9.2%) needs about 1,670 files per arm; powering on the funded rate (40.9% → 43.4%) needs about 6,120 per arm.

**Interpretation:** The opportunity is large enough to justify a controlled test, and the proximal metric (incomplete files) needs a quarter of the sample the funded rate needs.

**Limitation:** The estimates assume recovered files behave like average files that stay to a decision, ignore intervention cost, cover one state and year, and the two scenarios overlap. They are order-of-magnitude figures, adjustable on the Opportunity & test tab.


### Finding 13 — The direct-refinance leak replicates in all six states

**Result:** The same pipeline was run on Maryland, Virginia, Pennsylvania, Delaware, D.C. and West Virginia (553,213 applications). Direct-channel refinances close incomplete at 9.3–12.2% (MD 12.2, DE 11.8, DC 11.8, VA 11.6, PA 9.5, WV 9.3), against 3.3–6.1% for brokered refinances and 1.5–1.8% for direct purchases. Direct refinances are 63–75% of all stalled files in every state. Walk-aways exceed denials everywhere (21–26% vs 10–14%). Income lowers denials (e.g. 20.5% → 6.9% in MD) but moves walk-aways by at most 4 points in any state. The denial rate at 50–60% DTI is 21–39%, against 8–13% at 43–49%.

**Interpretation:** The leak is a pattern, not a Maryland anecdote, which is what justifies a product test. Two checks are weaker: the DTI jump is only 1.99× in West Virginia (below the 2× rule of thumb used on the app's scoreboard), and West Virginia's broker rate rests on 394 applications.

**Limitation:** Neighbouring states share regulators, markets and many lenders, so this is replication, not independence. This finding uses 2024; Finding 18 repeats the core numbers on 2023. Scoreboard thresholds are rules of thumb, not formal tests.


### Finding 14 — Walk-away in general is hard to predict from application data

**Result:** A gradient-boosted model on 13 application-time fields, scored out-of-lender (5-fold cross-validation grouped by lender), reaches AUC 0.55–0.63 for walk-away across states, versus 0.56–0.62 for simply knowing loan purpose and type. Adding the application channel raises it by 0.00–0.02. Denial is far more predictable (AUC 0.72–0.76 vs 0.68–0.70 for the baseline), driven by loan-to-income. Predicted totals are within 1% of observed in the large states.

**Interpretation:** These fields say little about who walks away. That does not show why they leave: credit score, rate shopping, timing and process are all unobserved. This result is about any walk-away. Unfinished files, which the proposed assistant targets, are more predictable (Finding 17).

**Limitation:** HMDA has no credit score, no timestamps and no rate-lock data, which a lender would have. A lender's own data might predict much better, and that is worth testing. Income is also blank more often on incomplete and declined-offer files; in the transfer test, removing the income fields changes walk-away AUC by less than 0.005.


### Finding 15 — Lender gaps are not a loan-mix artefact

**Result:** Replacing the purpose × loan type adjustment with the ML model leaves lender O/E rankings almost unchanged (rank correlation 0.94–0.98) and the true lender-to-lender spread τ at 0.37–0.50 (it was 0.34–0.44). In Maryland, 6 of 7 mix-adjusted frontier lenders stay on the ML frontier; across states the kept share is 4/4, 5/6, 5/5, 2/2 and 6/7 (VA, PA, DE, DC, WV). Counts of significantly worse lenders barely move (MD 36 → 35).

**Interpretation:** A much richer case-mix control does not shrink the gap, so these fields do not explain why lenders differ. The reason could be how they run applications, or something about their customers that HMDA does not record.

**Limitation:** The model uses only 13 lender-independent fields; unobserved borrower quality could still explain some differences. Out-of-lender scoring is harsh in small states, where one large lender can move the totals.


### Finding 16 — How much of the lender spread is real? (funnel plot and shrinkage)

**Result:** After removing sampling noise (DerSimonian–Laird), the true spread of walk-away O/E across lenders is τ ≈ 0.40 in Maryland (0.34–0.44 across states), i.e. roughly ±40% of expected. In Maryland 36 lenders sit above and 43 below the 95% funnel limits, far more than the ~3 expected by chance on each side. Shrunk O/E estimates pull small lenders toward the average in proportion to their noise.

**Interpretation:** Lender differences are large and well beyond chance, although their cause is not identified, so lender-level benchmarking is worthwhile; but individual small-lender rankings should use the shrunk estimate.

**Limitation:** The test assumes independent applications and ignores any clustering inside a lender (e.g. by branch or loan officer).


### Finding 17 — What carries over to states the model has never seen

**Result:** Models trained on Maryland only (no county or income fields) were scored on the other five states. **Closed incomplete:** AUC 0.73–0.78, against 0.71–0.75 for a purpose × channel lookup table. Acting on the 20% highest-scored files reaches 56–58% of incomplete files, against 43–58% for the table; the model does better in four states and worse in D.C. **Any walk-away:** AUC 0.59–0.66 (table 0.55–0.61). **Denial:** AUC 0.71–0.74 (table 0.65–0.69), rising to 0.74–0.77 with income fields. Across the three targets, predicted totals range from 0.87× to 1.26× the observed count. Lenders keep their position across states: for the ten state pairs with 15 or more shared lenders, rank correlation is 0.83–0.92 for walk-away O/E and 0.86–0.95 for denial O/E.

**Interpretation:** Ranking carries over better than exact rates, so any reuse needs recalibration. Unfinished files are moderately predictable, much of it from purpose and channel. This corrects the earlier advice not to score applicants, which rested on the walk-away model rather than the outcome the assistant targets. A score could later prioritise the costly human call, only after a fair-lending review and a test showing that high-risk applicants benefit. The first A/B test should include every eligible applicant. The lender result suggests something company-wide, which could be process or the customers a lender attracts.

**Limitation:** All data is from 2024, and the states are neighbours that share many lenders, so this transfer is probably easier than one to a distant market (Finding 18 tests another year). Only one training state was used. Income is blank for about 20% of incomplete files against 6% of others; keeping or dropping the income fields changes incomplete-file AUC by no more than 0.006.


### Finding 18 — A year apart: what lasted from 2023 to 2024

**Result:** The same cleaning rules and definitions were applied to 2023 (509,440 applications in the six states); the script first reproduces the published 2024 numbers, lender O/E and frontiers. **Headlines in 2023:** walk-aways exceeded denials in all six states (21.7–25.8% vs 10.2–13.3%). Direct refinances closed incomplete at 10.7–14.3%, brokered refinances at 2.1–5.0% and direct purchases at 1.6–2.3%; direct refinances were 62–73% of stalled files. The direct-refinance rate then fell in all six states, by 0.9–2.5 points. **Model (train on a state's 2023, score its 2024; no income or county):** for closed incomplete, AUC 0.71–0.77 against 0.73–0.74 for a purpose × channel table, with the model higher in five states and lower in D.C.; its top 20% reached 49–58% of incomplete files (table 48–58%), more than the table in five states. It over-predicted incomplete files in all six (1.03–1.21×). Any walk-away: AUC 0.58–0.65 (table 0.54–0.61). Denial: 0.70–0.73 (table 0.65–0.68), 0.72–0.77 with income. **Lenders:** walk-away O/E rank correlation between years was 0.72–0.80 in five states (0.43 in D.C., 7 shared lenders); denial 0.88–0.96. Of 128 followable lender-state flags for "significantly more walk-aways" in 2023, 116 (91%) were above expected in 2024 and 103 (80%) were still significant. Another 13 flagged lender-states had under 200 applications in 2024 and could not be followed. **Frontier:** only 14 of 31 places on the 2024 mix-adjusted state frontiers belonged to a lender also on that state's 2023 frontier (Maryland: 3 of 7).

**Interpretation:** The main gaps and most lender flags lasted a year, so they are reasonable places to investigate. Frontier membership did not, so one year is not enough to name best-in-class lenders. This weakens any benchmark based only on the 2024 frontier. Because the incomplete rate moved on its own, an A/B test needs a concurrent control group; a before-and-after comparison could mislead. Rankings can be reused a year later, but predicted counts need recalibration.

**Limitation:** Two adjacent years, the same states and many of the same lenders. It does not test a very different rate environment. A lasting flag may reflect a lender's customers as much as its process. Pricing, DTI, county, income-adjusted and out-of-lender ML results were not re-run on 2023.
