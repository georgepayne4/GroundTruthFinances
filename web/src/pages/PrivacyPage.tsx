/**
 * Privacy Policy — GDPR-compliant draft. Covers what we collect, why, how
 * long we keep it, your rights, and how to exercise them.
 */
export default function PrivacyPage() {
  return (
    <article className="prose prose-gray dark:prose-invert mx-auto max-w-3xl px-4 py-8">
      <h1>Privacy Policy</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Last updated: April 2026 · This is a draft pending professional legal review.
      </p>

      <h2>1. Who We Are</h2>
      <p>
        GroundTruth is the data controller for personal data collected through this service.
        Contact: <a href="mailto:hello@groundtruth.finance">hello@groundtruth.finance</a>.
      </p>

      <h2>2. What We Collect</h2>
      <ul>
        <li>
          <strong>Account data</strong> — your email, name, and authentication details (managed by
          our auth provider, Clerk).
        </li>
        <li>
          <strong>Profile data</strong> — the financial information you enter: income, expenses,
          debts, goals, investments, mortgage details, life events. Stored encrypted at rest.
        </li>
        <li>
          <strong>Open Banking data</strong> (optional) — if you choose to connect a bank via
          TrueLayer, we receive account balances and transactions. Access tokens are encrypted at
          rest and revocable at any time.
        </li>
        <li>
          <strong>Analysis output</strong> — reports generated from your profile data. Stored for
          your own historical reference.
        </li>
        <li>
          <strong>Audit log</strong> — which API endpoints you called and when, for security and
          compliance. Retained for 12 months.
        </li>
      </ul>

      <h2>3. Why We Collect It</h2>
      <p>
        We process your data only to provide the financial analysis service you have asked for.
        Lawful basis: <strong>performance of a contract</strong> (our Terms of Service).
      </p>
      <p>
        We do <strong>not</strong> sell, rent, or share your data with third parties for marketing.
        We do not use your financial data to train machine learning models.
      </p>

      <h2>4. How Long We Keep It</h2>
      <ul>
        <li>Account + profile data: until you delete your account.</li>
        <li>Audit log entries: 12 months, then automatically purged.</li>
        <li>
          Backups: rolling 30-day backups; deleted data is purged from backups within 30 days.
        </li>
      </ul>

      <h2>5. Your Rights Under UK GDPR</h2>
      <ul>
        <li>
          <strong>Right of access</strong> — download all data we hold about you from your Profile
          page.
        </li>
        <li>
          <strong>Right to erasure</strong> — delete your account from your Profile page; all
          personal data is immediately wiped.
        </li>
        <li>
          <strong>Right to rectification</strong> — update any field directly in the app at any
          time.
        </li>
        <li>
          <strong>Right to portability</strong> — exported data is provided in machine-readable
          JSON.
        </li>
        <li>
          <strong>Right to withdraw consent</strong> for optional integrations (Open Banking) at
          any time, from Settings.
        </li>
        <li>
          <strong>Right to complain</strong> to the{" "}
          <a href="https://ico.org.uk/" target="_blank" rel="noreferrer noopener">
            Information Commissioner's Office (ICO)
          </a>
          .
        </li>
      </ul>

      <h2>6. Security</h2>
      <p>
        Sensitive fields (profile YAML, Open Banking tokens) are encrypted at rest. Communication
        is encrypted in transit with TLS. Access to production systems is limited and logged.
      </p>

      <h2>7. Sub-processors</h2>
      <ul>
        <li>
          <strong>Clerk</strong> — authentication and user identity management.
        </li>
        <li>
          <strong>TrueLayer</strong> — Open Banking connectivity (only if you choose to connect).
        </li>
        <li>
          <strong>Hosting provider</strong> — infrastructure for running the service.
        </li>
      </ul>

      <h2>8. Cookies</h2>
      <p>
        We use only essential cookies required for authentication (set by Clerk). We do not use
        advertising or tracking cookies.
      </p>

      <h2>9. FCA Regulatory Positioning</h2>
      <p>
        GroundTruth is an <strong>information service</strong>, not a regulated financial adviser.
        We operate with reference to FCA Policy Statement{" "}
        <a
          href="https://www.fca.org.uk/publications/policy-statements/ps22-9-new-consumer-duty"
          target="_blank"
          rel="noreferrer noopener"
        >
          PS22/9 (Consumer Duty)
        </a>
        : we act in good faith, avoid foreseeable harm, and support informed financial decisions.
      </p>

      <h2>10. Changes to This Policy</h2>
      <p>
        We will notify you of material changes by email at least 14 days before they take effect.
        Previous versions are archived on request.
      </p>
    </article>
  );
}
