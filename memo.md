# Product memo: stop losing refinance applicants to unfinished files

**To:** Head of Product, digital mortgage lender  **From:** Product analytics  **Data:** HMDA 2024, Maryland (118,431 applications) and five neighbouring states (553,213 in total)
**Decision requested:** approve a controlled test of a *file-completion assistant* for direct-channel refinance applications.

## 1. The problem

25.7% of applications end because the applicant leaves (withdraws, never finishes, or declines the offer). Only 11.6% are denied.
Funded loans are 62.7%. The larger loss is the one fewer teams measure.

## 2. Where the loss is

| Segment | Applications | Closed as incomplete |
|---|---|---|
| Direct refinance + cash-out | 34,527 | **12.2%** (4,221 files) |
| Broker (indirect) refinance + cash-out | 5,893 | 4.0% |
| Direct purchase | 63,341 | 1.7% |

- Direct refinances are **73% of all stalled files** in the state (4,221 of 5,754).
- Income does not explain it: denials fall from 20.5% to 6.9% as income rises, walk-aways stay at 24–25% in every band.
- Geography does not explain it: after adjusting for loan mix, county ratios run 0.75–1.10.
- Price does not explain it: across 78 lenders, walk-away rate (adjusted for loan mix) is uncorrelated with price (|ρ| ≤ 0.13).

## 3. How lenders compare (once loan mix is removed)

Raw walk-away rankings mislead, because refinance-heavy lenders lose more applicants everywhere. I compared each lender with what
its own loan mix predicts (observed ÷ expected). 36 of 111 lenders lose significantly more applicants than their mix predicts; 44
significantly fewer. On the walk-away-versus-denial frontier, only 4 of 7 lenders are on both the raw and the mix-adjusted frontier,
and 5 of 7 survive adding income to the adjustment. The best lenders do not charge more (median rate spread 0.18 vs 0.16 points).

**Does it generalise, and can a model explain it?** The direct-refinance leak replicates in Virginia, Pennsylvania, Delaware, D.C. and West
Virginia (direct refinances close incomplete at 9.3–12.2%, brokered 3.3–6.1%, direct purchases 1.5–1.8%; 63–75% of all stalled files). A gradient-boosted
model on 13 application-time fields predicts walk-away barely better than loan purpose and type alone (AUC about 0.6), and does not shrink the real
spread between lenders (τ about 0.4). So walk-away is driven by what happens *after* applying, not by who applies: offer the fix to everyone, do not score.

## 4. Why this intervention (and not the alternatives)

| Option | Verdict |
|---|---|
| **File-completion assistant** (live document checklist, nudges, human call at 48 hours) | Targets the single largest identifiable leak; does not touch credit decisions |
| Push more volume to brokers | Gap is partly self-selection; reduces our control of the experience |
| Cut prices | Walk-away is uncorrelated with price across lenders |
| Loosen credit | Not an applicant-experience lever; adds risk |

## 5. Size of the prize (Maryland, one year, assumptions adjustable in the app)

- Closing **25%** of the direct-versus-broker incomplete-file gap recovers about 718 files = **606 funded loans**, ~$196M origination volume,
  ~$2.0M revenue at 100 bps.
- Across the 36 significantly worse lenders, closing 25% of excess walk-aways ≈ 877 loans (~$329M). The two scenarios overlap.
- These are order-of-magnitude figures: they assume recovered files behave like average files that stay to a decision (84.4% fund), and ignore intervention cost.

## 6. How we would test it

- **Population:** new direct refinance and cash-out applications; randomise 50/50 at application level, stratified by purpose and loan type.
- **Primary metric:** share of files closed incomplete (baseline 12.2%, target 9.2%): about **1,670 files per arm** (80% power, α = 5%).
  Funded rate (40.9% → 43.4%) is a pre-registered secondary readout and would need about 6,120 per arm.
- **Guardrails:** denial-rate *mix* (denials may rise mechanically as more files reach underwriting), cost per file, complaints, time to decision, treatment parity.
- **Ship if:** incomplete rate falls ≥ 2 points, funded rate does not fall, and guardrails hold. **Stop if** cost per recovered loan exceeds contribution per loan.

## 7. Risks and what I don't know

- Brokers pre-screen applicants, so the direct-versus-broker gap overstates what a product can recover.
- HMDA has no credit score, no timestamps and no reason for withdrawal; the test should capture *why* files stall.
- Six neighbouring states and one year. The leak replicates, but the states share regulators and lenders; confirm on a distant region before sizing nationally.
- Fair lending: the intervention must be offered identically to all applicants and must not alter underwriting; monitor outcomes by protected class under the lender's compliance process (not analysed here).

## 8. Next steps

1. Instrument the stall: log which document and which step each stalled file waits on (2 weeks).
2. Run the test described above (about 8 weeks at 400 eligible applications a week).
3. Re-run the lender comparison on 2023 and 2025 HMDA to see whether the frontier is stable, and rebuild the walk-away model on the lender's own data (credit score, timestamps) to see how much more predictable it is.

*Descriptive analysis of public HMDA data; makes no claim about any lender's practices. Interactive version: `streamlit run app.py`.*
