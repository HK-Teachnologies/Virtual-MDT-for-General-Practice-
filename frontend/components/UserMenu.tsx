'use client';

import { useAuth } from '../lib/auth';

export default function UserMenu() {
  const { user, loading, logout } = useAuth();

  if (loading || !user) return null;

  return (
    <span>
      {user.email} <span className="badge">{user.role}</span>{' '}
      <button className="link-btn" type="button" onClick={logout}>
        Sign out
      </button>
    </span>
  );
}
