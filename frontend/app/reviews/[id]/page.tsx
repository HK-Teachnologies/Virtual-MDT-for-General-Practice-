'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { API_BASE } from '../../../lib/api';
import { sourceLabel } from '../../../lib/sources';
import { useAuth } from '../../../lib/auth';
import type { ApiReview } from '../../../lib/types';

function AuthedMedia({
  responseId,
  kind,
  token,
}: {
  responseId: string;
  kind: 'image';
  token: string;
}) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    let objectUrl: string | null = null;
    fetch(`${API_BASE}/api/reviews/responses/${responseId}/${kind}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.blob() : null))
      .then((blob) => {
        if (live && blob) {
          objectUrl = URL.createObjectURL(blob);
          setUrl(objectUrl);
        }
      })
      .catch(() => {});
    return () => {
      live = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [responseId, kind, token]);

  if (!url) return null;
  return <img className="response-photo" src={url} alt="Response attachment" />;
}

export default function ReviewDetail() {
  const params = useParams();
  const router = useRouter();
  const { user, token, loading: authLoading } = useAuth();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const [review, setReview] = useState<ApiReview | null>(null);
  const [missing, setMissing] = useState(false);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [photo, setPhoto] = useState<File | null>(null);

  const load = useCallback(async () => {
    if (!id || !token) return;
    const res = await fetch(`${API_BASE}/api/reviews/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 404) {
      setMissing(true);
      return;
    }
    if (res.ok) setReview((await res.json()) as ApiReview);
  }, [id, token]);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [authLoading, user, router]);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  async function postResponse(form: FormData) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/reviews/${id}/responses`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!res.ok) {
        setError(`Could not post the response (${res.status}).`);
      } else {
        setText('');
        setPhoto(null);
        await load();
      }
    } catch {
      setError('Could not reach the server.');
    }
    setBusy(false);
  }

  function submitText(e: FormEvent) {
    e.preventDefault();
    if (!text.trim() && !photo) return;
    const form = new FormData();
    form.append('text', text.trim());
    if (photo) form.append('image', photo, photo.name);
    void postResponse(form);
  }

  async function toggleRecording() {
    if (recording) {
      recorderRef.current?.stop();
      return;
    }
    setError(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError('Microphone unavailable — check browser permission.');
      return;
    }
    const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    chunksRef.current = [];
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      setRecording(false);
      const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' });
      if (blob.size === 0) {
        setError('Nothing was recorded — try again.');
        return;
      }
      const form = new FormData();
      form.append('audio', blob, 'response.webm');
      if (text.trim()) form.append('text', text.trim());
      if (photo) form.append('image', photo, photo.name);
      void postResponse(form);
    };
    recorderRef.current = rec;
    rec.start();
    setRecording(true);
  }

  async function closeReview() {
    setClosing(true);
    try {
      const res = await fetch(`${API_BASE}/api/reviews/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: 'closed' }),
      });
      if (res.ok) setReview((await res.json()) as ApiReview);
    } catch {
      /* keep the review open on failure */
    }
    setClosing(false);
  }

  if (authLoading || !user || !token) return <p>Checking sign-in…</p>;
  if (missing) {
    return (
      <div>
        <p>Review not found.</p>
        <Link className="back-link" href="/reviews">
          ← Back to reviews
        </Link>
      </div>
    );
  }
  if (!review) return <p>Loading review…</p>;

  const canClose =
    review.status !== 'closed' &&
    (user.role === 'admin' || review.requested_by === user.id);
  const snapshotItems = review.brief_snapshot.items ?? [];

  return (
    <div>
      <Link className="back-link" href="/reviews">
        ← Back to reviews
      </Link>
      <div className="row">
        <h1>{review.patient_name}</h1>
        <span className={`badge badge-${review.status}`}>{review.status}</span>
      </div>
      <p className="muted">
        Requested by {review.requester_email} ·{' '}
        <Link href={`/patients/${review.patient_id}`}>Open patient record</Link>
      </p>

      {review.message && (
        <section className="panel">
          <h2>Request</h2>
          <p>{review.message}</p>
        </section>
      )}

      {snapshotItems.length > 0 && (
        <section className="panel">
          <h2>Brief snapshot</h2>
          {snapshotItems.map((item, i) => (
            <div key={i} className="brief-item">
              <div className="brief-item-head">
                <strong>{item.specialty}</strong>
                {sourceLabel(item.source_type ?? '') && (
                  <span className="badge">{sourceLabel(item.source_type ?? '')}</span>
                )}
                {item.urgent && <span className="badge badge-urgent">Urgent</span>}
              </div>
              <p>{item.concern}</p>
              {item.question && (
                <p>
                  <strong>Question: </strong>
                  {item.question}
                </p>
              )}
              <p className="muted">
                {item.citation} · {item.status}
              </p>
            </div>
          ))}
        </section>
      )}

      <section className="panel">
        <h2>Responses ({review.responses.length})</h2>
        {review.responses.length === 0 ? (
          <p className="muted">No responses yet — the request is pending.</p>
        ) : (
          review.responses.map((r) => (
            <article key={r.id} className="response">
              <p>
                <strong>{r.author_name ?? r.author_email}</strong>{' '}
                <span className="muted">{new Date(r.created_at).toLocaleString()}</span>
              </p>
              <p>{r.text}</p>
              {r.has_image && <AuthedMedia responseId={r.id} kind="image" token={token} />}
            </article>
          ))
        )}
      </section>

      {review.status !== 'closed' && (
        <section className="panel">
          <h2>Respond</h2>
          <form onSubmit={submitText}>
            <div className="field">
              <label htmlFor="resptext">Written response</label>
              <textarea
                id="resptext"
                rows={3}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Your clinical opinion…"
              />
            </div>
            <div className="field">
              <label htmlFor="respphoto">Attach a photo (optional)</label>
              <input
                id="respphoto"
                key={review.responses.length}
                type="file"
                accept="image/*"
                onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
              />
              {photo && <p className="muted">Attached: {photo.name}</p>}
            </div>
            {error && <p className="error">{error}</p>}
            <div className="row">
              <button
                className="btn btn-primary"
                type="submit"
                disabled={busy || (!text.trim() && !photo)}
              >
                {busy ? 'Sending…' : 'Send response'}
              </button>
              <button
                className={recording ? 'btn btn-danger' : 'btn'}
                type="button"
                onClick={toggleRecording}
                disabled={busy}
              >
                {recording ? 'Stop & send voice response' : 'Respond by voice'}
              </button>
            </div>
            <p className="muted">
              Voice is transcribed automatically so the requester can read it, and stays listenable
              here.
            </p>
          </form>
        </section>
      )}

      {canClose && (
        <button className="btn" type="button" onClick={closeReview} disabled={closing}>
          {closing ? 'Closing…' : 'Close review'}
        </button>
      )}
    </div>
  );
}
