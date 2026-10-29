import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import MenuButton from '../components/MenuButton';
import Sidebar from '../components/Sidebar';
import TopNav from '../components/TopNav';
import { AuthProvider } from '../lib/auth';
import './globals.css';

export const metadata: Metadata = {
  title: 'Virtual MDT for General Practice',
  description:
    'Clinician-facing multidisciplinary review briefs for general practice. Synthetic demo data only.',
  icons: { icon: '/favicon.svg' },
};

// Without this, phones render the ~980px desktop layout scaled down.
export const viewport = {
  width: 'device-width',
  initialScale: 1,
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
                  <MenuButton />
                  <span>
                    <span className="brand">
                      <span className="brand-mark" aria-hidden="true">
                        +
                      </span>
                      Virtual MDT
                    </span>
                    <span className="muted brand-sub">for General Practice — demo</span>
                  </span>
                  <TopNav />
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
