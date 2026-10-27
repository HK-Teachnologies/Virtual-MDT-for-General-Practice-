'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '../lib/auth';

export default function Sidebar() {
  const { user } = useAuth();
  const pathname = usePathname();

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
    <aside className="sidebar">
      <p className="side-label">Workspace</p>
      {link('/', 'Patients')}
      {link('/profile', 'My profile')}
      {user.role === 'admin' && (
        <>
          <p className="side-label">Admin</p>
          {link('/admin/users', 'Users')}
          {link('/admin/clinics', 'Clinics')}
        </>
      )}
    </aside>
  );
}
