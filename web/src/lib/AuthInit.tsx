import { useEffect, type ReactNode } from "react";
import { useAuth } from "@clerk/clerk-react";
import { setTokenProvider } from "./api";

/**
 * Bridge component: injects Clerk's getToken into the plain api.ts module.
 * Must be rendered inside <ClerkProvider>.
 */
export default function AuthInit({ children }: { children: ReactNode }) {
  const { getToken } = useAuth();

  useEffect(() => {
    setTokenProvider(() => getToken());
  }, [getToken]);

  return <>{children}</>;
}
