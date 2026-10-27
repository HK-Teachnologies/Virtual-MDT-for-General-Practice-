import type { Metadata } from 'next';
import type { ReactNode } from 'react';
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
          <header className="site-header">
            <div className="container">
              <span>
                <span className="brand">Virtual MDT</span>
                <span className="muted">for General Practice — demo</span>
              </span>
              <UserMenu />
            </div>
          </header>
          <main className="container">{children}</main>
          <footer className="container footer">
            <p className="muted">
              Clinician-facing decision support. All suggestions need review by a qualified clinician.
              Synthetic data only — no real patient data.
            </p>
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
