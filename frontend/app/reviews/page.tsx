'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { API_BASE } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import type { ApiReview } from '../../lib/types';

function timeAgo(iso: string): string {
  const mins = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

function specialtyNames(r: ApiReview): string {
  const names = r.recipients.map((x) => x.specialty_name).filter(Boolean) as string[];
  return Array.from(new Set(names)).join(', ') || 'Individual request';
}

function ReviewCard({ review, mine }: { review: ApiReview; mine: boolean }) {
  return (
    <Link className="panel review-card" href={`/reviews/${review.id}`}>
      <div className="row review-card-head">
        <strong>{review.patient_name}</strong>
        <span className={`badge badge-${review.status}`}>{review.status}</span>
      </div>
      <p className="muted">
        {specialtyNames(review)} · {review.response_count} response
        {review.response_count === 1 ? '' : 's'} · {mine ? 'requested by you' : `from ${review.requester_email}`} ·{' '}
        {timeAgo(review.created_at)}
      </p>
      {review.message && <p>{review.message}</p>}
    </Link>
  );
}

export default function ReviewsInbox() {
  const router = useRouter();
  const { user, token, loading: authLoading } = useAuth();
  const [tab, setTab] = useState<'inbox' | 'requested'>('inbox');
  const [inbox, setInbox] = useState<ApiReview[] | null>(null);
  const [requested, setRequested] = useState<ApiReview[] | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user || !token) return;
    fetch(`${API_BASE}/api/reviews/inbox`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => (res.ok ? res.json() : null))
      .then((list) => {
        if (list) setInbox(list as ApiReview[]);
      })
      .catch(() => {});
    fetch(`${API_BASE}/api/reviews/requested`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => (res.ok ? res.json() : null))
      .then((list) => {
        if (list) setRequested(list as ApiReview[]);
      })
      .catch(() => {});
  }, [user, token]);

  if (authLoading || !user) return <p>Checking sign-in…</p>;

  const shown = tab === 'inbox' ? inbox : requested;

  return (
    <div>
      <h1>Reviews</h1>
      <div className="row tabs">
        <button
          className={tab === 'inbox' ? 'btn btn-primary' : 'btn'}
          type="button"
          onClick={() => setTab('inbox')}
        >
          Assigned to me{inbox ? ` (${inbox.length})` : ''}
        </button>
        <button
          className={tab === 'requested' ? 'btn btn-primary' : 'btn'}
          type="button"
          onClick={() => setTab('requested')}
        >
          Requested by me{requested ? ` (${requested.length})` : ''}
        </button>
      </div>
      {!shown ? (
        <p>Loading reviews…</p>
      ) : shown.length === 0 ? (
        <p className="muted">
          {tab === 'inbox'
            ? 'No reviews assigned to you yet.'
            : 'You have not requested any reviews yet. Open a patient record to send one.'}
        </p>
      ) : (
        shown.map((r) => <ReviewCard key={r.id} review={r} mine={tab === 'requested'} />)
      )}
    </div>
  );
}
