import { SignUp } from "@clerk/clerk-react";

export default function SignUpPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-950">
      <SignUp
        routing="path"
        path="/sign-up"
        signInUrl="/sign-in"
        appearance={{
          elements: {
            rootBox: "mx-auto",
            card: "rounded-lg shadow-lg",
          },
        }}
      />
    </div>
  );
}
