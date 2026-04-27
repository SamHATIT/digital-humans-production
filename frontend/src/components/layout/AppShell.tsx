import type { ReactNode } from 'react';
import { LangProvider } from '../../contexts/LangContext';
import StudioHeader from './StudioHeader';
import StudioFooter from './StudioFooter';

interface AppShellProps {
  children: ReactNode;
}

/**
 * Layout commun aux pages protégées Studio.
 * Header sticky + main + footer, fond ink, typo Inter par défaut.
 */
export default function AppShell({ children }: AppShellProps) {
  return (
    <LangProvider>
      <div className="min-h-screen flex flex-col bg-ink text-bone">
        <StudioHeader />
        <main className="flex-1">{children}</main>
        <StudioFooter />
      </div>
    </LangProvider>
  );
}
