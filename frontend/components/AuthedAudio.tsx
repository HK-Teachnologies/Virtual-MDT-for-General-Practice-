'use client';

import { useEffect, useState } from 'react';

export default function AuthedAudio({ url, token }: { url: string; token: string }) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    let objectUrl: string | null = null;
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => (res.ok ? res.blob() : null))
      .then((blob) => {
        if (live && blob) {
          objectUrl = URL.createObjectURL(blob);
          setSrc(objectUrl);
        }
      })
      .catch(() => {});
    return () => {
      live = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url, token]);

  if (!src) return <p className="muted">Loading recording…</p>;
  return <audio controls src={src} />;
}
