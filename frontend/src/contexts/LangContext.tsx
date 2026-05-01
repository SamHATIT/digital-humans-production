import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

export type Lang = 'en' | 'fr';

interface LangContextValue {
  lang: Lang;
  setLang: (next: Lang) => void;
  toggleLang: () => void;
  /** Choose between an English and French copy. */
  t: <T>(en: T, fr: T) => T;
}

const STORAGE_KEY = 'studio.lang';

const LangContext = createContext<LangContextValue | undefined>(undefined);

function readInitialLang(): Lang {
  if (typeof window === 'undefined') return 'en';
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === 'en' || stored === 'fr') return stored;
  const navLang = window.navigator.language?.toLowerCase() ?? '';
  return navLang.startsWith('fr') ? 'fr' : 'en';
}

interface LangProviderProps {
  children: ReactNode;
}

export function LangProvider({ children }: LangProviderProps) {
  const [lang, setLangState] = useState<Lang>(() => readInitialLang());

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, lang);
      document.documentElement.lang = lang;
    }
  }, [lang]);

  const setLang = useCallback((next: Lang) => setLangState(next), []);
  const toggleLang = useCallback(() => setLangState((prev) => (prev === 'en' ? 'fr' : 'en')), []);

  const value = useMemo<LangContextValue>(
    () => ({
      lang,
      setLang,
      toggleLang,
      t: <T,>(en: T, fr: T) => (lang === 'fr' ? fr : en),
    }),
    [lang, setLang, toggleLang],
  );

  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useLang(): LangContextValue {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error('useLang must be used within a LangProvider');
  return ctx;
}
