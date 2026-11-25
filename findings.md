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

**Interpretation:** Higher-income applicants get approved more often but are no more likely to stay. Abandonment is therefore not an affordability problem that income would explain, which supports looking at process and experience instead.

**Limitation:** 7,196 applications with missing income and 1,234 with zero or negative income are excluded. Income is reported in thousands of dollars and contains extreme values (maximum 400,000 = $400 million), so band edges are driven by the middle of the distribution only.


### Finding 5 — Lender walk-away rates are largely driven by loan mix

**Result:** Refinance-heavy lenders look worst on raw walk-away rate: for example one lender at 58.9% walk-away has only 1% purchase loans, 33 percentage points above the state rate. After adjusting for loan purpose × loan type (observed ÷ expected), its O/E falls to 1.42 and a lender at 54.4% raw walk-away with 69% purchase loans moves to O/E 2.26, the second worst of 111. The largest lender (7,533 applications) has a raw walk-away of 12.0% against 28.0% expected for its mix, an O/E of 0.43.

**Interpretation:** Comparing lenders on raw abandonment penalises those that mostly refinance and hides purchase-focused lenders who lose many applicants. Mix-adjusted rankings identify which lenders lose applicants beyond what their book predicts. The highest excess volume sits with two mid-sized lenders, each losing roughly 500–600 more applicants than their mix predicts.

**Limitation:** Only purpose × loan type are adjusted. Income, loan size, county and credit quality are not, and a low denial or walk-away rate on 200–500 applications is noisy. A high O/E is a flag for investigation, not proof of a weaker process.


### Finding 6 — Low walk-aways can be bought with high denials; the frontier separates the two

**Result:** Using mix-adjusted walk-away and denial O/E, seven of 111 lenders sit on the Pareto frontier (no other lender is at least as good on both and better on one). Only four of these appear on the frontier when raw rates are used instead; Three lenders are on the adjusted frontier only (including Rocket Mortgage, the largest lender) and three on the raw frontier only (including NVR Mortgage Finance). Lenders with the lowest walk-away O/E can have very high denial O/E, for example 0.49 walk-away with 2.92 denial O/E at one lender that denies 69.6% of applications.

**Interpretation:** A lender can look excellent on retention by turning most applicants away before they can leave. Ranking on both measures together, after adjusting for mix, picks out lenders that hold applicants and approve them. Four lenders are better than their mix predicts on both measures and have 455 or more applications each.

**Limitation:** The frontier is sensitive to small samples, especially lenders with only a few dozen denials. Two of the seven frontier lenders have 223–455 applications. Pricing is not analysed because pricing fields exist only for originated loans, which would introduce survivorship bias.


### Finding 7 — The clearest leak is incomplete files in direct-channel refinances

**Result:** 12.2% of direct-channel refinance and cash-out applications (4,221 of 34,527) are closed as incomplete, against 4.0% through brokers and 1.7% for direct purchases. Direct refinances account for 73% of the 5,754 stalled files in the state. Cash-out: 11.9% direct vs 3.7% broker; refinance: 12.6% vs 4.1%.

**Interpretation:** The leak is specific to refinances that applicants must paper on their own, which makes it a process problem (document collection and follow-up) that a product can address, rather than a credit or affordability problem.

**Limitation:** Brokers pre-screen and coach their borrowers, so not all of the direct-versus-broker gap is recoverable. HMDA does not record why a file was closed incomplete or when.


### Finding 8 — High-retention lenders do not charge more

**Result:** On originated conventional purchase loans (lenders with 100+ such loans), the four lenders on both the mix-adjusted and income-adjusted frontier have a median rate spread of 0.18 and median loan costs of $6,264, against 0.16 and $6,243 for all other lenders (72 lenders). Across 78 lenders, walk-away O/E is uncorrelated with price (Spearman |ρ| ≤ 0.13); denial O/E has a small negative correlation with price (−0.15 to −0.29).

**Interpretation:** Retaining applicants is not being bought with higher prices. Stricter lenders price slightly lower, consistent with taking safer borrowers.

**Limitation:** Pricing fields exist only for originated loans (survivorship), there is no credit score, and few frontier lenders have enough conventional purchase volume to compare.


### Finding 9 — Denial reasons differ by purpose, and DTI has a cliff at 50%

**Result:** Purchases are denied mainly for debt-to-income (37.2% of purchase denials); cash-out refinances for credit history (27.2%) and DTI (23.4%). "Credit application incomplete" accounts for 21.2% of cash-out and 19.1% of refinance denials but 7.1% of purchase denials. Among originated or denied files with a recorded DTI, the denial rate is 9–10% from 20% to 49% DTI, then 26.6% at 50–60% and 89.5% above 60%.

**Interpretation:** The 50% DTI line behaves like a policy threshold, and applicants approaching it are the natural place for earlier guidance. The incomplete-application denials mirror the stalled files in Finding 7.

**Limitation:** Only the first of up to four reported denial reasons is kept. DTI is only recorded for files that reached underwriting, so denial rates by DTI exclude withdrawn files. The 19.3% denial rate below 20% DTI is unexplained.


### Finding 10 — Geography matters little once loan mix is removed

**Result:** Across the 18 jurisdictions with 1,000+ applications, raw walk-away runs from 19.3% to 28.5%, but the mix-adjusted observed ÷ expected ratio runs only from 0.75 to 1.10. Prince George's County and Baltimore City have the highest denial O/E (1.27 and 1.21). The largest lender in most counties has only 6–8% of applications.

**Interpretation:** Where an applicant lives is not the lever; loan type, channel and process are.

**Limitation:** County is the only geography in this data (no tract-level analysis), and 252 applications have no county reported.


### Finding 11 — The frontier holds up partly under stricter checks

**Result:** Of the 7 lenders on the mix-adjusted frontier, 5 stay on it when income band is added to the adjustment and 4 stay when only lenders with 500+ applications are considered. Four lenders appear on both the raw and the adjusted frontier. 36 of 111 lenders have significantly more walk-aways than their mix predicts (z > 1.96) and 44 significantly fewer; the 36 account for about 4,160 excess walk-aways.

**Interpretation:** The headline frontier is a shortlist for investigation, not a final ranking. Lenders on the frontier under every view are the most credible benchmarks.

**Limitation:** With 111 lenders and no multiple-comparison correction, some flags will be false alarms, though the largest z-values are far beyond chance. Income is missing for 7,196 applications.


### Finding 12 — Size of the prize and how to test it

**Result:** Closing 25% of the direct-versus-broker incomplete-file gap in refinances recovers about 718 files, or 606 funded loans (~$196M of volume, ~$2.0M revenue at 100 bps) in Maryland in one year. At the 36 significantly worse lenders, closing 25% of excess walk-aways gives about 877 funded loans (~$329M). A randomised test on incomplete files (12.2% → 9.2%) needs about 1,670 files per arm; powering on the funded rate (40.9% → 43.4%) needs about 6,120 per arm.

**Interpretation:** The opportunity is large enough to justify a controlled test, and the proximal metric (incomplete files) needs a quarter of the sample the funded rate needs.

**Limitation:** The estimates assume recovered files behave like average files that stay to a decision, ignore intervention cost, cover one state and year, and the two scenarios overlap. They are order-of-magnitude figures, adjustable on the Opportunity & test tab.
