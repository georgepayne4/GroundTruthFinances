# Legal & Compliance

This page summarises the regulatory position of GroundTruth. The full Terms of Service and Privacy Policy are available in-app at `/terms` and `/privacy`.

## Regulatory classification

GroundTruth is an **information service**, not a regulated financial adviser.

- **Not authorised by the FCA** to provide personal recommendations on retail investment products, mortgages, insurance, or pensions.
- **Outputs are educational.** They surface trade-offs, project scenarios, flag risks. They do not constitute personal financial advice.
- **No fiduciary relationship.** Using GroundTruth does not create an adviser-client relationship.
- **For regulated advice**, consult an FCA-authorised IFA. The FCA register is at https://register.fca.org.uk.

## FCA positioning reference

GroundTruth's approach is informed by FCA Policy Statement PS22/9 (Consumer Duty), which sets standards for consumer communications and outcomes. As an information service, we aim for:

- Fair, clear, not misleading information
- Products and services that meet consumer needs
- Prices and value that are fair
- Communications that support informed decisions

Nothing on this page, in the app, or in any GroundTruth report constitutes advice under Part 4A of the Financial Services and Markets Act 2000 (FSMA).

## Data protection (GDPR / UK GDPR)

GroundTruth is compliant with UK GDPR and the Data Protection Act 2018.

### Your rights

| Right | How to exercise |
|-------|-----------------|
| Access | `GET /api/v1/account/export` — returns full JSON dump of all data held |
| Erasure | `DELETE /api/v1/account` or Profile page "Delete my account" button |
| Portability | The export format is standard JSON — portable to any system |
| Rectification | Edit your profile in Settings and re-analyse |
| Restriction | Contact us to pause processing |
| Object | Stop using the service; processing ceases on account deletion |

Data is held in the EEA/UK on infrastructure provided by sub-processors (see below).

### Sub-processors

| Provider | Purpose | Data accessed |
|----------|---------|---------------|
| Clerk | Authentication | Email, name |
| TrueLayer | Open Banking (optional) | Transaction data, account balances |
| Hosting (v9.8) | Infrastructure | All data at rest (encrypted) |

### Encryption at rest

- Profile YAML content encrypted with Fernet (AES-128-CBC + HMAC-SHA256)
- Bank tokens encrypted with the same mechanism
- Encryption keys held separately from data

### Retention

- **Active accounts:** data held as long as the account exists
- **Deleted accounts:** PII wiped immediately on deletion request; audit logs retained with `user_id` set to NULL (for security/regulatory purposes)
- **Backups:** 30-day rolling backups; deletion propagates to backups within 30 days

## Disclaimer text

### Short form (every page, every export)

> Not financial advice. Educational information only.

### Long form (Terms, Privacy, footer)

> This report is for informational and educational purposes only. GroundTruth is an information service and does not provide regulated financial advice. The outputs are computational analyses of data you have supplied and assumptions we have published. They do not account for your full circumstances, and should not be relied upon as a recommendation. Consult a qualified IFA for regulated advice on retail investment products, mortgages, insurance, or pensions.

## Liability

- No warranty that projections will be accurate.
- No liability for financial decisions made based on outputs.
- Users retain full responsibility for their financial choices.
- The information service model places the interpretive burden on the user.

## Governing law

These Terms are governed by the laws of England and Wales. Disputes are subject to the exclusive jurisdiction of the English courts.

## Changes

Material changes to Terms or Privacy Policy will be notified in-app with at least 14 days' notice. Continued use after the effective date constitutes acceptance.

## Contact

For regulatory questions, data requests, or complaints:

- **Email:** hello@groundtruth.finance
- **Data Protection:** dpo@groundtruth.finance
- **ICO registration** (UK data protection regulator): pending

For complaints about financial advice (not applicable — we don't give advice), the Financial Ombudsman Service is the relevant body. GroundTruth is not a member as we are not an authorised firm.

## White-label & configurability

The disclaimer text, regulatory classification, provider name, and contact email are all configurable via `config/assumptions.yaml` under the `legal:` key. This allows IFAs or partner firms to deploy GroundTruth with their own branding and regulatory positioning (subject to their own FCA authorisation).
