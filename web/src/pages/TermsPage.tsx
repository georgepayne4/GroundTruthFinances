/**
 * Terms of Service — draft for review by qualified legal counsel before
 * public launch. Current positioning: GroundTruth is an information service,
 * not a regulated financial adviser.
 */
export default function TermsPage() {
  return (
    <article className="prose prose-gray dark:prose-invert mx-auto max-w-3xl px-4 py-8">
      <h1>Terms of Service</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Last updated: April 2026 · This is a draft pending professional legal review.
      </p>

      <h2>1. What GroundTruth Is</h2>
      <p>
        GroundTruth is an information service that analyses financial data you provide and produces
        educational reports, projections, and suggestions. We help you understand your own
        financial position.
      </p>

      <h2>2. What GroundTruth Is Not</h2>
      <p>
        GroundTruth <strong>is not</strong> a regulated financial adviser and{" "}
        <strong>does not provide financial, investment, tax, or legal advice</strong>. We are not
        authorised by the Financial Conduct Authority (FCA) to give regulated advice. Our output is
        for educational and informational purposes only.
      </p>
      <p>
        For regulated financial advice tailored to your circumstances, consult a qualified adviser
        authorised by the FCA. You can find one via the{" "}
        <a href="https://www.fca.org.uk/firms" target="_blank" rel="noreferrer noopener">
          FCA Register
        </a>
        .
      </p>

      <h2>3. Accuracy of Output</h2>
      <p>
        All analysis is based on the information you provide and the assumptions documented in our
        assumptions file. Projections are estimates, not guarantees. Past performance is not
        indicative of future results. Tax rates, thresholds, and rules change — we update our
        assumptions regularly but cannot guarantee they are current at every moment.
      </p>

      <h2>4. Your Responsibilities</h2>
      <ul>
        <li>Provide accurate information. Garbage in, garbage out.</li>
        <li>
          Do not rely solely on GroundTruth output for significant financial decisions. Seek
          professional advice.
        </li>
        <li>Keep your account credentials secure.</li>
        <li>Use the service only for your own personal financial planning.</li>
      </ul>

      <h2>5. Account Termination</h2>
      <p>
        You may delete your account at any time from your Profile page. Deletion is immediate and
        irreversible — all associated data is wiped in line with our Privacy Policy.
      </p>

      <h2>6. Limitation of Liability</h2>
      <p>
        To the maximum extent permitted by law, GroundTruth is not liable for any loss, damage, or
        cost arising from decisions made on the basis of information provided by the service. The
        service is provided "as is" without warranty.
      </p>

      <h2>7. Changes to These Terms</h2>
      <p>
        We may update these terms. Material changes will be communicated by email or in-app notice
        at least 14 days before taking effect.
      </p>

      <h2>8. Contact</h2>
      <p>
        Questions about these terms:{" "}
        <a href="mailto:hello@groundtruth.finance">hello@groundtruth.finance</a>.
      </p>
    </article>
  );
}
