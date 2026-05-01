import type { ReactNode } from 'react';
import { LangProvider } from '../../contexts/LangContext';
import StudioHeader from './StudioHeader';
import StudioHeaderPublic from './StudioHeaderPublic';
import StudioFooter from './StudioFooter';

type AppShellVariant = 'app' | 'public';

interface AppShellProps {
  children: ReactNode;
  /**
   * `app` (default) : header complet avec CreditCounter + nav user.
   * `public`        : header sans appels API protégés (pour /pricing public).
   */
  variant?: AppShellVariant;
}

/**
 * Layout commun aux pages Studio.
 * Header sticky + main + footer, fond ink, typo Inter par défaut.
 */
export default function AppShell({ children, variant = 'app' }: AppShellProps) {
  return (
    <LangProvider>
      <div className="min-h-screen flex flex-col bg-ink text-bone">
        {variant === 'public' ? <StudioHeaderPublic /> : <StudioHeader />}
        <main className="flex-1">{children}</main>
        <StudioFooter />
      </div>
    </LangProvider>
  );
}
