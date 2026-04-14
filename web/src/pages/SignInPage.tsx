import { SignIn } from "@clerk/clerk-react";

export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-950">
      <SignIn
        routing="path"
        path="/sign-in"
        signUpUrl="/sign-up"
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
