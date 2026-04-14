import { UserButton } from "@clerk/clerk-react";

const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

export default function ClerkUserButton() {
  if (!CLERK_KEY) return null;
  return <UserButton afterSignOutUrl="/sign-in" />;
}
