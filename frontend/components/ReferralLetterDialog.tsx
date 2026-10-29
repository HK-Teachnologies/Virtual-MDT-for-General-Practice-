'use client';

import { useState } from 'react';

/** Creation form for a referral letter: destination, reason, note. */
export default function ReferralLetterForm({
  busy,
  onDraft,
}: {
  busy: boolean;
  onDraft: (data: {
    destination_facility: string;
    reason: string;
    additional_note: string;
  }) => void;
}) {
  const [destination, setDestination] = useState('');
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');

  return (
    <div>
      <div className="field">
        <label htmlFor="ref-dest">Destination facility</label>
        <input
          id="ref-dest"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          placeholder="e.g. Mbarara Regional Referral Hospital"
        />
      </div>
      <div className="field">
        <label htmlFor="ref-reason">Reason for referral</label>
        <textarea
          id="ref-reason"
          rows={2}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. Blood pressure uncontrolled on current treatment"
        />
      </div>
      <div className="field">
        <label htmlFor="ref-note">Additional note (optional)</label>
        <textarea
          id="ref-note"
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      <button
        className="btn btn-primary"
        type="button"
        onClick={() =>
          onDraft({
            destination_facility: destination.trim(),
            reason: reason.trim(),
            additional_note: note.trim(),
          })
        }
        disabled={busy || !destination.trim() || !reason.trim()}
      >
        {busy ? 'Drafting…' : 'Draft letter'}
      </button>
    </div>
  );
}
