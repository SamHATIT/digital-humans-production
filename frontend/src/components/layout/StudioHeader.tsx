import { useEffect, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { LogOut, User as UserIcon } from 'lucide-react';
import { auth } from '../../services/api';
import { useLang } from '../../contexts/LangContext';
import CreditCounter from './CreditCounter';
import LangToggle from './LangToggle';

interface CurrentUser {
  email?: string;
  name?: string;
}

const NAV = (t: <T>(en: T, fr: T) => T) => [
  { to: '/', label: t('Dashboard', 'Tableau de bord'), end: true },
  { to: '/projects', label: t('Projects', 'Projets'), end: false },
  { to: '/wizard', label: t('New project', 'Nouveau projet'), end: false },
];

export default function StudioHeader() {
  const navigate = useNavigate();
  const { t } = useLang();
  const [user, setUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    let cancelled = false;
    auth
      .getCurrentUser()
      .then((data) => {
        if (!cancelled) setUser({ email: data?.email, name: data?.name });
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleLogout = () => {
    auth.logout();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-40 bg-ink-2/95 backdrop-blur-md border-b border-brass/20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-6">
          {/* Logo */}
          <Link to="/" className="flex flex-col leading-tight group">
            <span className="font-serif italic text-xl text-bone group-hover:text-brass transition-colors">
              Digital · Humans
            </span>
            <span className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
              Autonomous Studio · Est MMXXV
            </span>
          </Link>

          {/* Nav */}
          <nav className="hidden md:flex items-center gap-1">
            {NAV(t).map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `px-4 py-2 font-mono text-[11px] tracking-eyebrow uppercase transition-colors ${
                    isActive
                      ? 'text-brass border-b border-brass'
                      : 'text-bone-3 hover:text-bone'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          {/* Right side */}
          <div className="flex items-center gap-4">
            <CreditCounter />
            <LangToggle />
            <div className="flex items-center gap-2 pl-3 border-l border-bone/10">
              <div className="w-7 h-7 rounded-full bg-ink-3 border border-brass/30 flex items-center justify-center">
                <UserIcon className="w-3.5 h-3.5 text-brass" />
              </div>
              <span className="hidden lg:inline font-mono text-[11px] text-bone-3 truncate max-w-[160px]">
                {user?.email ?? '—'}
              </span>
              <button
                type="button"
                onClick={handleLogout}
                aria-label={t('Sign out', 'Déconnexion')}
                className="ml-1 p-1.5 text-bone-4 hover:text-error transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
