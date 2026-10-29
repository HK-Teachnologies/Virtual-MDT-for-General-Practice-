import type { BriefInteraction, BriefOverdueCheck, CitedLabel, RemovedPoint } from './types';

/** Clinician-facing label for a brief point's evidence source. Empty when unknown. */
export function sourceLabel(sourceType: string | undefined | null): string {
  switch ((sourceType ?? '').trim()) {
    case 'guideline':
      return 'MoH guideline';
    case 'patient_record':
      return 'Patient record';
    case 'clinical_reasoning':
      return 'Clinical reasoning – verify';
    default:
      return '';
  }
}

export function toInteraction(raw: unknown): BriefInteraction {
  if (typeof raw === 'string')
    return { drugs: [], concern: raw, citation: '', source_type: '', cited_labels: [] };
  const p = (raw ?? {}) as Record<string, unknown>;
  return {
    drugs: Array.isArray(p.drugs) ? p.drugs.map(String) : [],
    concern: String(p.concern ?? ''),
    citation: String(p.citation ?? ''),
    source_type: String(p.source_type ?? ''),
    cited_labels: toCitedLabels(p.cited_labels),
  };
}

export function toOverdueCheck(raw: unknown): BriefOverdueCheck {
  if (typeof raw === 'string')
    return { check: raw, last_done: '', citation: '', source_type: '', cited_labels: [] };
  const p = (raw ?? {}) as Record<string, unknown>;
  return {
    check: String(p.check ?? ''),
    last_done: String(p.last_done ?? ''),
    citation: String(p.citation ?? ''),
    source_type: String(p.source_type ?? ''),
    cited_labels: toCitedLabels(p.cited_labels),
  };
}

/** Build the audit-trail entry for one dropped safety-panel point. */
export function toRemovedPanelPoint(
  kind: string,
  raw: unknown,
  reason: string,
): RemovedPoint {
  if (kind === 'interaction') {
    const x = toInteraction(raw);
    return {
      kind,
      text: `${x.drugs.length > 0 ? `${x.drugs.join(' + ')}: ` : ''}${x.concern}`,
      sub: x.citation,
      reason,
    };
  }
  const x = toOverdueCheck(raw);
  return {
    kind: 'overdue_check',
    text: x.check,
    sub: [x.last_done && `last done: ${x.last_done}`, x.citation].filter(Boolean).join(' · '),
    reason,
  };
}

export function toCitedLabels(raw: unknown): CitedLabel[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((c): c is Record<string, unknown> => typeof c === 'object' && c !== null)
    .map((c) => ({
      label: String(c.label ?? ''),
      doc_id: String(c.doc_id ?? ''),
      page: typeof c.page === 'number' ? c.page : null,
    }))
    .filter((c) => c.label !== '');
}

/** Small print under each brief: which model prepared it, and which prompt. */
export function modelLine(model: string, promptVersion: string): string {
  const short = (model || '').split('/').pop() || 'unknown model';
  const pretty = short
    .split(/[-_]/)
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(' ');
  return `Prepared by ${pretty} · prompt ${promptVersion || '?'}`;
}

/** One-line plain-text rendering for copy export and specialist-review snapshots. */
export function interactionLine(x: BriefInteraction): string {
  const drugs = x.drugs.length > 0 ? `${x.drugs.join(' + ')}: ` : '';
  const cite = x.citation ? ` (${x.citation})` : '';
  return `- ${drugs}${x.concern}${cite}`;
}

export function overdueCheckLine(x: BriefOverdueCheck): string {
  const last = x.last_done ? ` — last done: ${x.last_done}` : '';
  const cite = x.citation ? ` (${x.citation})` : '';
  return `- ${x.check}${last}${cite}`;
}
