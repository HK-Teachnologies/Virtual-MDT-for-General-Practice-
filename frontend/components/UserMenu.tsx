'use client';

import Link from 'next/link';
import { useAuth } from '../lib/auth';

export default function UserMenu() {
  const { user, loading, logout } = useAuth();

  if (loading) return null;
  if (!user) return <Link href="/login">Sign in</Link>;

  return (
    <span>
      {user.email} <span className="badge">{user.role}</span>{' '}
      <button className="link-btn" type="button" onClick={logout}>
        Sign out
      </button>
    </span>
  );
}
