'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '../lib/auth';

export default function TopNav() {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();

  const cls = (href: string) => (pathname === href ? 'nav-link active' : 'nav-link');

  return (
    <nav className="topnav">
      <Link className={cls('/about')} href="/about">
        About
      </Link>
      {!loading && !user && (
        <Link className={cls('/patient/login')} href="/patient/login">
          Patient sign in
        </Link>
      )}
      {!loading && user && (
        <span className="user-chip">
          {user.email} <span className="badge">{user.role}</span>{' '}
          <button className="link-btn" type="button" onClick={logout}>
            Sign out
          </button>
        </span>
      )}
    </nav>
  );
}
