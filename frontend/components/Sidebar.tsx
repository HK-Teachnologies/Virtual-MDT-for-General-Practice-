'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { API_BASE } from '../lib/api';
import { useAuth } from '../lib/auth';
import type { ApiSpecialty } from '../lib/types';

export default function Sidebar() {
  const { user, token } = useAuth();
  const pathname = usePathname();
  const [specialties, setSpecialties] = useState<string[] | null>(null);

  useEffect(() => {
    if (!user || !token) return;
    fetch(`${API_BASE}/api/specialties/mine`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((list) => {
        if (list) setSpecialties((list as ApiSpecialty[]).map((s) => s.name));
      })
      .catch(() => {});
  }, [user, token]);

  function close() {
    document.body.classList.remove('nav-open');
  }

  // The drawer closes itself after navigating (mobile) or on Escape.
  useEffect(() => {
    close();
  }, [pathname]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') close();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // No sidebar for signed-out visitors: the login page needs no navigation.
  if (!user) return null;

  const link = (href: string, label: string) => (
    <Link
      key={href}
      href={href}
      className={pathname === href ? 'side-link active' : 'side-link'}
    >
      {label}
    </Link>
  );

  return (
    <>
      <div className="nav-backdrop" onClick={close} aria-hidden="true" />
      <aside className="sidebar">
      <p className="side-label">Workspace</p>
      {link('/', 'Patients')}
      {link('/reviews', 'Reviews')}
      {link('/guide', 'Guide')}
      {link('/profile', 'My profile')}
      {specialties !== null && (
        <p className="muted side-note">
          {specialties.length === 0
            ? 'No specialty assigned'
            : `Specialties: ${specialties.join(', ')}`}
        </p>
      )}
      {user.role === 'admin' && (
        <>
          <p className="side-label">Admin</p>
          {link('/admin/users', 'Users')}
          {link('/admin/clinics', 'Clinics')}
          {link('/admin/guidelines', 'Guidelines')}
          {link('/admin/specialties', 'Specialties')}
        </>
      )}
      </aside>
    </>
  );
}
