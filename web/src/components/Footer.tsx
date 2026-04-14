import { Link } from "react-router-dom";

/**
 * Site-wide footer with legal links and provider classification.
 */
export default function Footer() {
  return (
    <footer
      role="contentinfo"
      className="mt-12 border-t border-gray-200 bg-white py-6 text-xs text-gray-500 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-400"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-medium text-gray-700 dark:text-gray-300">GroundTruth</p>
            <p>
              An information service, not a regulated financial adviser. Not authorised by the FCA
              to give financial advice.
            </p>
          </div>
          <nav aria-label="Legal">
            <ul className="flex flex-wrap gap-4">
              <li>
                <Link
                  to="/terms"
                  className="hover:text-gray-900 hover:underline dark:hover:text-gray-200"
                >
                  Terms
                </Link>
              </li>
              <li>
                <Link
                  to="/privacy"
                  className="hover:text-gray-900 hover:underline dark:hover:text-gray-200"
                >
                  Privacy
                </Link>
              </li>
              <li>
                <a
                  href="mailto:hello@groundtruth.finance"
                  className="hover:text-gray-900 hover:underline dark:hover:text-gray-200"
                >
                  Contact
                </a>
              </li>
            </ul>
          </nav>
        </div>
      </div>
    </footer>
  );
}
