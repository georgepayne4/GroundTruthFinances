import { StrictMode, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { ClerkProvider } from '@clerk/clerk-react'
import './index.css'
import App from './App.tsx'

const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;

function AuthWrapper({ children }: { children: ReactNode }) {
  if (!CLERK_KEY) {
    return <>{children}</>;
  }
  return <ClerkProvider publishableKey={CLERK_KEY}>{children}</ClerkProvider>;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthWrapper>
      <App />
    </AuthWrapper>
  </StrictMode>,
)
