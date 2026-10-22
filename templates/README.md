# Outage catalogue (work package 1)

`outage_catalogue_template.csv` is the empty template for the public outage catalogue. **It is empty on purpose:** every row must come from a public source that is cited in `source_url`. Nothing is filled in from memory or estimates.

| Column | Meaning |
|---|---|
| `event_id` | running number |
| `date`, `start_time_local`, `end_time_local` | when payments failed (local time); leave a time empty if unknown |
| `duration_hours` | end − start, in hours |
| `country` | SE, NO, DK, FI, … |
| `scope` | `National`, `Regional` (name the region in `notes`), or `Merchant` (one chain or acquirer) |
| `affected_service` | e.g. a card network, an acquirer, a bank, a payment terminal provider, Swish |
| `affected_party_type` | `network`, `acquirer`, `issuer/bank`, `terminal/POS`, `A2A`, `other` |
| `cause_reported` | as stated in the source (e.g. technical fault, cyberattack, power outage) |
| `card_payments_affected`, `swish_affected` | `yes` / `no` / `unknown` |
| `source_title`, `source_url`, `source_published` | the public source: an operator status page, a press release, a news article or an authority report |
| `notes` | anything else, e.g. number of merchants affected, if reported |

Once filled, the catalogue gives the outage frequency and duration used in `config/assumptions.json` (`outages`), and a list of events to study if a retailer later shares aggregated data.
