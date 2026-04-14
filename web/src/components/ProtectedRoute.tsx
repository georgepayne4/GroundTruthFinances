import { useAuth } from "@clerk/clerk-react";
import { Navigate, Outlet } from "react-router-dom";

const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

/**
 * Wraps routes that require authentication.
 * When VITE_CLERK_PUBLISHABLE_KEY is unset, allows unauthenticated access (dev mode).
 */
export default function ProtectedRoute() {
  // Dev mode: no Clerk key configured, allow through
  if (!CLERK_KEY) {
    return <Outlet />;
  }

  const { isSignedIn, isLoaded } = useAuth();

  if (!isLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900 dark:border-gray-700 dark:border-t-gray-100" />
      </div>
    );
  }

  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace />;
  }

  return <Outlet />;
}
