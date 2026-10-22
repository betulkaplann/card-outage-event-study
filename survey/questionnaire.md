# Merchant survey: card outages and backup payments (draft)

**Purpose:** a master's thesis at Jönköping International Business School on the economics of payment resilience. The answers calibrate the simulation and cost-benefit model in this repository (see `config/assumptions.json`, section `calibration`).

**Respondents:** store managers or owners in retail and hospitality in Sweden and the Nordics.
**Length:** about 8 minutes, 16 questions.
**Planned distribution:** online form; via ID24's contacts and trade associations.

> **Consent and data protection (shown before Q1)**
> Participation is voluntary and anonymous. We do not ask for your name, your company's name or other personal data. You can stop at any time. Answers are stored securely, used only for this thesis, and reported only as totals. Contact: [student e-mail], supervisor: [supervisor].
> ☐ I agree to take part.

---

## A. About the business
**Q1.** Sector: ☐ Grocery ☐ Fashion/apparel ☐ Electronics ☐ Pharmacy ☐ Restaurant/café ☐ Hotel ☐ Other retail ☐ Other: ___
**Q2.** Country of the store(s): ☐ Sweden ☐ Norway ☐ Denmark ☐ Finland ☐ Other
**Q3.** Typical sales per store per day (SEK): ☐ < 10,000 ☐ 10,000–50,000 ☐ 50,000–200,000 ☐ > 200,000
**Q4.** Number of stores: ☐ 1 ☐ 2–10 ☐ 11–50 ☐ > 50
**Q5.** Share of sales paid by: card ___ %, Swish/QR ___ %, cash ___ %, other ___ %

## B. Outages experienced (last 24 months)
**Q6.** How many times could you **not accept card payments** for at least 15 minutes? ☐ 0 ☐ 1 ☐ 2–3 ☐ 4–6 ☐ > 6
**Q7.** How long did the longest one last? ☐ < 30 min ☐ 30 min–1 h ☐ 1–3 h ☐ > 3 h
*(If Q6 = 0, skip to Q12.)*

## C. What happened during the outage
**Q8.** Of the customers who wanted to pay by card, roughly what share **paid another way** (Swish/QR, cash)? ☐ 0–20% ☐ 21–40% ☐ 41–60% ☐ 61–80% ☐ > 80%
**Q9.** Which methods did they use? (tick all) ☐ Swish/QR ☐ Cash ☐ Invoice / pay later ☐ Offline card ☐ Other
**Q10.** Roughly what share **left without buying**? ☐ 0–20% ☐ 21–40% ☐ 41–60% ☐ 61–80% ☐ > 80%
**Q11.** Did some of them **come back later** the same day or the next day? ☐ None ☐ A few ☐ About half ☐ Most

## D. Backup options
**Q12.** Which fallbacks do you have **today**? (tick all) ☐ Cash ☐ Swish/QR at the till ☐ Offline card payments ☐ Second card acquirer / network ☐ Mobile terminal (4G) ☐ None
**Q13.** When were they introduced? ☐ Before 2024 ☐ 2024 ☐ 2025 ☐ 2026 ☐ Don't know
**Q14.** What would you be willing to pay per store per year for a backup that keeps you selling during a card outage (SEK)? ☐ 0 ☐ < 2,000 ☐ 2,000–5,000 ☐ 5,000–10,000 ☐ > 10,000
**Q15.** What stops you from adding a (better) backup? (tick all) ☐ Cost ☐ Outages are too rare ☐ Technical integration ☐ Staff training ☐ Customers would not use it ☐ Not aware of options ☐ Other: ___

## E. Follow-up
**Q16.** Would you be willing to take part in a 30-minute interview? ☐ Yes (we will ask for contact details separately, not linked to these answers) ☐ No

---

### How the answers map to the model

| Model assumption | Question(s) |
|---|---|
| Payment mix | Q5 |
| Outage frequency and duration | Q6, Q7 (plus the public outage catalogue) |
| Switching during an outage, with and without backup | Q8–Q10, split by Q12 |
| Delayed purchases (catch-up) | Q11 |
| Share of stores with a backup, and selection on size | Q12 × Q3/Q4 |
| Willingness to pay vs cost | Q14 |
| Barriers to adoption | Q15 |
