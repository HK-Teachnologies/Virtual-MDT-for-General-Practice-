import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import Link from 'next/link';
import Sidebar from '../components/Sidebar';
import UserMenu from '../components/UserMenu';
import { AuthProvider } from '../lib/auth';
import './globals.css';

export const metadata: Metadata = {
  title: 'Virtual MDT for General Practice',
  description:
    'Clinician-facing multidisciplinary review briefs for general practice. Synthetic demo data only.',
  icons: { icon: '/favicon.svg' },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <div className="shell">
            <Sidebar />
            <div className="shell-main">
              <header className="site-header">
                <div className="container">
                  <span>
                    <span className="brand">Virtual MDT</span>
                    <span className="muted">for General Practice — demo</span>
                  </span>
                  <span>
                    <Link href="/about">About</Link> <UserMenu />
                  </span>
                </div>
              </header>
              <main className="container">{children}</main>
              <footer className="container footer">
                <p className="muted">
                  Clinician-facing decision support. All suggestions need review by a qualified clinician.
                  Synthetic data only — no real patient data.
                </p>
              </footer>
            </div>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
