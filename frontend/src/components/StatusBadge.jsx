import React from 'react';
import { Badge } from './ui/badge';
import { useLanguage } from '../contexts/LanguageContext';

const statusStyles = {
  pending: 'bg-slate-500/15 text-slate-200 border-slate-500/30',
  validating: 'bg-blue-500/15 text-blue-200 border-blue-500/30',
  queued: 'bg-slate-500/15 text-slate-200 border-slate-500/30',
  sending: 'bg-cyan-500/15 text-cyan-200 border-cyan-500/30',
  acked: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30',
  failed: 'bg-rose-500/15 text-rose-200 border-rose-500/30',
  retrying: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
  quarantined: 'bg-fuchsia-500/10 text-fuchsia-200 border-fuchsia-500/25'
};

export function StatusBadge({ status, className = '' }) {
  const { t } = useLanguage();
  const style = statusStyles[status] || statusStyles.pending;
  const label = t(`status.${status}`) || status;

  return (
    <Badge
      variant="outline"
      className={`${style} border font-medium text-xs px-2.5 py-0.5 ${className}`}
      data-testid={`status-badge-${status}`}
    >
      {label}
    </Badge>
  );
}

export function AgentStatusBadge({ online }) {
  const { t } = useLanguage();

  if (online) {
    return (
      <Badge variant="outline" className="bg-emerald-500/15 text-emerald-200 border-emerald-500/30 gap-1.5">
        <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse-dot" />
        {t('agents.online')}
      </Badge>
    );
  }

  return (
    <Badge variant="outline" className="bg-slate-500/15 text-slate-300 border-slate-500/30 gap-1.5">
      <span className="h-2 w-2 rounded-full border border-slate-400" />
      {t('agents.offline')}
    </Badge>
  );
}

export function KBSModeBadge({ mode }) {
  const modeStyles = {
    normal: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30',
    unavailable: 'bg-rose-500/15 text-rose-200 border-rose-500/30',
    timeout: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
    delayed_ack: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
    duplicate_reject: 'bg-fuchsia-500/10 text-fuchsia-200 border-fuchsia-500/25',
    validation_fail: 'bg-rose-500/15 text-rose-200 border-rose-500/30',
    random_errors: 'bg-amber-500/15 text-amber-200 border-amber-500/30'
  };

  return (
    <Badge variant="outline" className={`${modeStyles[mode] || modeStyles.normal} border font-medium`}>
      {mode?.replace(/_/g, ' ').toUpperCase() || 'NORMAL'}
    </Badge>
  );
}
