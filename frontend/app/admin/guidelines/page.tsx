'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';
import { API_BASE } from '../../../lib/api';
import { useAuth } from '../../../lib/auth';
import type { ApiGuideline } from '../../../lib/types';

export default function AdminGuidelines() {
  const { user, token, loading: authLoading } = useAuth();
  const router = useRouter();
  const [docs, setDocs] = useState<ApiGuideline[] | null>(null);
  const [title, setTitle] = useState('');
  const [version, setVersion] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user || user.role !== 'admin' || !token) return;
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, token]);

  function refresh() {
    if (!token) return;
    fetch(`${API_BASE}/api/mdt/guidelines`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((list) => {
        if (list) setDocs(list as ApiGuideline[]);
      })
      .catch(() => {});
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!token || !title.trim() || !file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('title', title.trim());
      form.append('version', version.trim());
      form.append('file', file);
      const res = await fetch(`${API_BASE}/api/mdt/guidelines`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
        setError(
          body && typeof body.detail === 'string'
            ? body.detail
            : `Could not upload the guideline (${res.status}).`,
        );
      } else {
        const created = (await res.json()) as ApiGuideline;
        setDocs((prev) => (prev ? [created, ...prev] : [created]));
        setTitle('');
        setVersion('');
        setFile(null);
      }
    } catch {
      setError('Could not reach the server.');
    }
    setBusy(false);
  }

  async function toggleActive(doc: ApiGuideline) {
    if (!token) return;
    const res = await fetch(`${API_BASE}/api/mdt/guidelines/${doc.id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ active: !doc.active }),
    });
    if (!res.ok) return;
    const updated = (await res.json()) as ApiGuideline;
    setDocs((prev) => (prev ? prev.map((d) => (d.id === updated.id ? updated : d)) : prev));
  }

  async function retryIndex(doc: ApiGuideline) {
    if (!token) return;
    setError(null);
    const res = await fetch(`${API_BASE}/api/mdt/guidelines/${doc.id}/reindex`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      setError(`Could not restart indexing (${res.status}).`);
      return;
    }
    const updated = (await res.json()) as ApiGuideline;
    setDocs((prev) => (prev ? prev.map((d) => (d.id === updated.id ? updated : d)) : prev));
  }

  if (authLoading || !user) return <p>Checking sign-in…</p>;

  if (user.role !== 'admin') {
    return (
      <div>
        <h1>Guidelines</h1>
        <p>Admin access required.</p>
        <Link className="back-link" href="/">
          ← Back to patients
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1>Guidelines</h1>
      <p className="muted">
        Clinical protocols the MDT agent cites (Uganda Clinical Guidelines, WHO
        protocols, …). Upload the PDF or text — it is indexed for retrieval.
        Deactivate a superseded edition to retire it without deleting history.
      </p>

      <section className="panel">
        <h2>Upload guideline</h2>
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="gtitle">Title</label>
            <input
              id="gtitle"
              type="text"
              required
              placeholder="e.g. Uganda Clinical Guidelines"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="gversion">Version / year</label>
            <input
              id="gversion"
              type="text"
              placeholder="e.g. 2023"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="gfile">Document (.pdf, .txt, .md)</label>
            <input
              id="gfile"
              type="file"
              required
              accept=".pdf,.txt,.md"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <p className="muted">
            Text-based PDFs are indexed page by page. Scanned (image-only)
            PDFs are rejected — photograph key pages via Capture instead.
          </p>
          {error && <p className="error">{error}</p>}
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? 'Uploading & indexing…' : 'Upload guideline'}
          </button>
        </form>
      </section>

      {!docs ? (
        <p>Loading guidelines…</p>
      ) : docs.length === 0 ? (
        <p className="muted">No guidelines uploaded yet.</p>
      ) : (
        <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Version</th>
              <th>Chunks</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id}>
                <td>{d.title}</td>
                <td>{d.version || '—'}</td>
                <td>
                  {['queued', 'indexing'].includes(d.index_status)
                    ? `${d.chunks} (${d.index_status === 'queued' ? 'queued' : 'indexing'}…)`
                    : d.chunks}
                </td>
                <td>
                  {d.index_status === 'queued'
                    ? 'Queued'
                    : d.index_status === 'indexing'
                      ? 'Indexing…'
                      : d.index_status === 'failed'
                        ? 'Indexing failed'
                        : d.active
                          ? 'Active'
                          : 'Retired'}
                  {d.index_status === 'failed' && d.index_error && (
                    <p className="error">{d.index_error}</p>
                  )}
                </td>
                <td>
                  {d.index_status === 'failed' && (
                    <button className="link-btn" type="button" onClick={() => retryIndex(d)}>
                      Retry indexing
                    </button>
                  )}{' '}
                  <button className="link-btn" type="button" onClick={() => toggleActive(d)}>
                    {d.active ? 'Retire' : 'Reactivate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}
    </div>
  );
}
