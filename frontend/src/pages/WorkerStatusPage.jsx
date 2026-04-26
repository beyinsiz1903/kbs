import React, { useCallback, useEffect, useState } from 'react';
import { getWorkerStatus, triggerWorkerPoll, errorMessage } from '../lib/api';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import {
  RefreshCw, PlayCircle, CheckCircle2, AlertTriangle, XCircle,
  Activity, Wifi, WifiOff, Clock, Users, Radio, Satellite, ZapOff, Loader2,
} from 'lucide-react';

const REFRESH_MS = 5000;

function fmtTime(s) {
  if (!s) return '—';
  try {
    return new Date(s).toLocaleString('tr-TR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch { return s; }
}

function relTime(s) {
  if (!s) return '—';
  try {
    const sec = Math.max(0, Math.floor((Date.now() - new Date(s).getTime()) / 1000));
    if (sec < 60) return `${sec} sn önce`;
    if (sec < 3600) return `${Math.floor(sec / 60)} dk önce`;
    return `${Math.floor(sec / 3600)} sa önce`;
  } catch { return s; }
}

function StatBox({ label, value, accent }) {
  const color = accent === 'green' ? 'text-emerald-400'
    : accent === 'red' ? 'text-rose-400'
    : accent === 'amber' ? 'text-amber-400'
    : accent === 'blue' ? 'text-sky-400'
    : 'text-foreground';
  return (
    <Card className="p-4 bg-card/40">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-2xl font-semibold ${color}`}>{value ?? 0}</p>
    </Card>
  );
}

function OutcomeBadge({ outcome }) {
  if (outcome === 'ok') {
    return <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 gap-1"><CheckCircle2 className="h-3 w-3" />ok</Badge>;
  }
  if (outcome === 'retry' || outcome === 'rate_limit') {
    return <Badge variant="outline" className="border-amber-500/40 text-amber-400 gap-1"><RefreshCw className="h-3 w-3" />{outcome}</Badge>;
  }
  if (outcome === 'dead' || outcome === 'error' || outcome === 'pms-error') {
    return <Badge variant="outline" className="border-rose-500/40 text-rose-400 gap-1"><XCircle className="h-3 w-3" />{outcome}</Badge>;
  }
  if (outcome?.startsWith('skip')) {
    return <Badge variant="outline" className="border-muted-foreground/40 text-muted-foreground gap-1">{outcome}</Badge>;
  }
  return <Badge variant="outline">{outcome}</Badge>;
}

export default function WorkerStatusPage() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getWorkerStatus();
      setStatus(res);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, REFRESH_MS);
    return () => clearInterval(t);
  }, [load]);

  const handlePollNow = async () => {
    setPolling(true);
    try {
      const res = await triggerWorkerPoll();
      if (res.triggered) toast.success('Worker tetiklendi');
      else toast.error('Worker calismiyor');
      setTimeout(load, 800);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setPolling(false);
    }
  };

  const stats = status?.queue_stats || {};
  const counters = status?.counters || {};
  const sessionStatus = status?.session_status || 'no_session';
  const running = !!status?.running;
  const workerMode = status?.worker_mode || 'poll';
  const sseConnected = !!status?.sse_connected;
  const sseLastEventAt = status?.sse_last_event_at || null;
  const sseReconnectCount = status?.sse_reconnect_count || 0;
  const sseConsecutiveFailures = status?.sse?.consecutive_failures || 0;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">Worker Durumu</h1>
          <p className="text-xs text-muted-foreground">
            Otomatik KBS bildirim ajaninin canli durumu (her {REFRESH_MS / 1000} sn yenilenir)
          </p>
        </div>
        <div className="flex items-end gap-2">
          <Button
            variant="outline"
            onClick={load}
            disabled={loading}
            className="gap-2"
            data-testid="btn-refresh-status"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Yenile
          </Button>
          <Button
            onClick={handlePollNow}
            disabled={polling || !running}
            className="gap-2"
            data-testid="btn-poll-now"
          >
            <PlayCircle className={`h-4 w-4 ${polling ? 'animate-pulse' : ''}`} />
            Şimdi Tara
          </Button>
        </div>
      </div>

      {/* Worker meta */}
      <Card className="bg-card/40 border-border/50 p-4 space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-3">
            <Activity className={`h-5 w-5 ${running ? 'text-emerald-400 animate-pulse' : 'text-muted-foreground'}`} />
            <div>
              <p className="text-xs text-muted-foreground">Worker ID</p>
              <p className="text-sm font-mono">{status?.worker_id || '—'}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {running ? (
              <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 gap-1.5">
                <Activity className="h-3 w-3" /> Çalışıyor
              </Badge>
            ) : (
              <Badge variant="outline" className="border-rose-500/40 text-rose-400 gap-1.5">
                <XCircle className="h-3 w-3" /> Durdu
              </Badge>
            )}
            {sessionStatus === 'ok' && (
              <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 gap-1.5">
                <Wifi className="h-3 w-3" /> PMS oturumu açık
              </Badge>
            )}
            {sessionStatus === 'no_session' && (
              <Badge variant="outline" className="border-muted-foreground/40 text-muted-foreground gap-1.5">
                <WifiOff className="h-3 w-3" /> Oturum yok
              </Badge>
            )}
            {sessionStatus === 'invalid' && (
              <Badge variant="outline" className="border-amber-500/40 text-amber-400 gap-1.5">
                <AlertTriangle className="h-3 w-3" /> Oturum geçersiz
              </Badge>
            )}
            {/* Phase D follow-up: live push channel indicator. Tells the
                operator at a glance whether jobs arrive instantly (SSE) or
                with up to POLL_INTERVAL delay (poll). */}
            {workerMode === 'poll' && running && (
              <Badge
                variant="outline"
                className="border-sky-500/40 text-sky-400 gap-1.5"
                data-testid="badge-channel-poll"
                title="Worker düzenli aralıklarla PMS'i tarıyor (push kanalı yok)"
              >
                <Satellite className="h-3 w-3" /> Tarama modu
              </Badge>
            )}
            {(workerMode === 'sse' || workerMode === 'auto') && running && sseConnected && (
              <Badge
                variant="outline"
                className="border-emerald-500/40 text-emerald-400 gap-1.5"
                data-testid="badge-channel-live"
                title={`PMS'e canlı push bağlantısı açık. Son olay: ${relTime(sseLastEventAt)}`}
              >
                <Radio className="h-3 w-3 animate-pulse" /> Canlı bağlantı
              </Badge>
            )}
            {/* Initial connect window: SSE/auto açıldı ama henüz ne event geldi
                ne de hata oldu. Operatör bu kısa pencerede de kanal durumunu
                görsün (yoksa "rozet yok" gibi sessiz görünür). Session yoksa
                supervisor zaten bekliyor — "Bağlanıyor" yanıltıcı olur, gizle. */}
            {(workerMode === 'sse' || workerMode === 'auto') && running && sessionStatus === 'ok' && !sseConnected && sseConsecutiveFailures === 0 && sseReconnectCount === 0 && (
              <Badge
                variant="outline"
                className="border-sky-500/40 text-sky-400 gap-1.5"
                data-testid="badge-channel-connecting"
                title="Push kanalı açılıyor; ilk bağlantı kuruluyor."
              >
                <Loader2 className="h-3 w-3 animate-spin" /> Bağlanıyor
              </Badge>
            )}
            {(workerMode === 'sse' || workerMode === 'auto') && running && !sseConnected && sseConsecutiveFailures > 0 && (
              <Badge
                variant="outline"
                className="border-amber-500/40 text-amber-400 gap-1.5"
                data-testid="badge-channel-reconnecting"
                title={`Push bağlantısı koptu, ${sseConsecutiveFailures}. kez yeniden deneniyor. Tarama yedeği işleri kaçırmıyor.`}
              >
                <RefreshCw className="h-3 w-3 animate-spin" /> Yeniden bağlanıyor
              </Badge>
            )}
            {workerMode === 'auto' && running && !sseConnected && sseConsecutiveFailures === 0 && sseReconnectCount > 0 && (
              <Badge
                variant="outline"
                className="border-muted-foreground/40 text-muted-foreground gap-1.5"
                data-testid="badge-channel-fallback"
                title="Push kapalı; tarama yedeği aktif. Bağlantı geri geldiğinde otomatik geçilir."
              >
                <ZapOff className="h-3 w-3" /> Tarama yedeğine düştü
              </Badge>
            )}
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2 border-t border-border/30">
          <div>
            <p className="text-[10px] uppercase text-muted-foreground">Tarama aralığı</p>
            <p className="text-sm">{status?.poll_interval ?? '—'} sn</p>
          </div>
          <div>
            <p className="text-[10px] uppercase text-muted-foreground">Başladı</p>
            <p className="text-sm">{relTime(status?.started_at)}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase text-muted-foreground">Son tarama</p>
            <p className="text-sm flex items-center gap-1">
              <Clock className="h-3 w-3 text-muted-foreground" />
              {relTime(status?.last_poll_at)}
            </p>
          </div>
          <div>
            <p className="text-[10px] uppercase text-muted-foreground">Son tarama sonucu</p>
            <p className="text-sm">
              {status?.last_poll_ok === true && <span className="text-emerald-400">başarılı</span>}
              {status?.last_poll_ok === false && <span className="text-rose-400">başarısız</span>}
              {status?.last_poll_ok == null && '—'}
            </p>
          </div>
        </div>
        {/* SSE channel detail row — visible only when SSE/auto mode is in use.
            Adds last-event freshness + reconnect count without crowding the
            top badge area. Operator-grade detail; pure poll users don't see it. */}
        {(workerMode === 'sse' || workerMode === 'auto') && (
          <div
            className="grid grid-cols-2 md:grid-cols-3 gap-3 pt-2 border-t border-border/30"
            data-testid="row-sse-detail"
          >
            <div>
              <p className="text-[10px] uppercase text-muted-foreground">Kanal modu</p>
              <p className="text-sm">
                {workerMode === 'sse' && 'SSE (yalnız push)'}
                {workerMode === 'auto' && 'Otomatik (push + tarama yedeği)'}
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase text-muted-foreground">Son canlı olay</p>
              <p className="text-sm flex items-center gap-1" data-testid="text-sse-last-event">
                <Clock className="h-3 w-3 text-muted-foreground" />
                {sseLastEventAt ? relTime(sseLastEventAt) : 'Henüz olay yok'}
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase text-muted-foreground">Yeniden bağlanma</p>
              <p className="text-sm" data-testid="text-sse-reconnect-count">
                {sseReconnectCount === 0 ? (
                  <span className="text-muted-foreground">Hiç olmadı</span>
                ) : (
                  <span className={sseReconnectCount > 3 ? 'text-amber-400' : 'text-foreground'}>
                    {sseReconnectCount} kez
                    {sseConsecutiveFailures > 0 && (
                      <span className="text-amber-400"> ({sseConsecutiveFailures} ardışık)</span>
                    )}
                  </span>
                )}
              </p>
            </div>
          </div>
        )}
        {status?.last_error && (
          <div className="text-xs bg-rose-500/10 border border-rose-500/30 rounded px-3 py-2 text-rose-300 font-mono break-all">
            {status.last_error}
          </div>
        )}
      </Card>

      {/* Queue stats */}
      <div>
        <h2 className="text-sm font-semibold mb-2 text-muted-foreground uppercase tracking-wide">PMS Kuyruğu</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <StatBox label="Bekleyen" value={stats.pending} accent="amber" />
          <StatBox label="İşleniyor" value={stats.in_progress} accent="blue" />
          <StatBox label="Tamamlandı" value={stats.done} accent="green" />
          <StatBox label="Başarısız" value={stats.failed} accent="amber" />
          <StatBox label="Ölü" value={stats.dead} accent="red" />
        </div>
      </div>

      {/* Counters */}
      <div>
        <h2 className="text-sm font-semibold mb-2 text-muted-foreground uppercase tracking-wide">Bu Oturumdaki Sayaçlar</h2>
        <div className="grid grid-cols-3 gap-3">
          <StatBox label="Claim" value={counters.claim} accent="blue" />
          <StatBox label="Complete" value={counters.complete} accent="green" />
          <StatBox label="Fail" value={counters.fail} accent="red" />
        </div>
      </div>

      {/* Other agents (Phase D — multi-agent visibility) */}
      <Card className="bg-card/40 border-border/50" data-testid="card-other-workers">
        <div className="px-4 py-3 border-b border-border/30 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4 text-sky-400" />
            <p className="text-sm font-semibold">Diğer Aktif Ajanlar</p>
          </div>
          <Badge variant="outline" className="text-xs">
            {(status?.other_workers || []).length} ajan
          </Badge>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/20 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">Worker ID</th>
                <th className="px-4 py-3 text-left">İşlenen iş</th>
                <th className="px-4 py-3 text-left">Lease bitişi</th>
              </tr>
            </thead>
            <tbody>
              {(status?.other_workers || []).length === 0 && (
                <tr>
                  <td colSpan={3} className="px-4 py-6 text-center text-xs text-muted-foreground">
                    Şu anda bu otelde başka aktif ajan yok. (PMS yalnızca senin ajanını görüyor.)
                  </td>
                </tr>
              )}
              {(status?.other_workers || []).map((w) => (
                <tr key={w.worker_id} className="border-t border-border/20 hover:bg-muted/10" data-testid={`row-other-worker-${w.worker_id}`}>
                  <td className="px-4 py-2 font-mono text-xs">{w.worker_id}</td>
                  <td className="px-4 py-2 text-xs">{w.job_count}</td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">{fmtTime(w.lease_expires_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Recent jobs */}
      <Card className="bg-card/40 border-border/50">
        <div className="px-4 py-3 border-b border-border/30">
          <p className="text-sm font-semibold">Son İşlenen İşler</p>
          <p className="text-[10px] text-muted-foreground">En son 20 işlem (en yeni önce)</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/20 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">Zaman</th>
                <th className="px-4 py-3 text-left">Job ID</th>
                <th className="px-4 py-3 text-left">İşlem</th>
                <th className="px-4 py-3 text-left">Sonuç</th>
                <th className="px-4 py-3 text-left">Detay</th>
              </tr>
            </thead>
            <tbody>
              {(status?.recent_jobs || []).length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                    Henüz işlenmiş job yok. İlk tarama tamamlandığında burada listelenir.
                  </td>
                </tr>
              )}
              {(status?.recent_jobs || []).map((j, i) => (
                <tr key={i} className="border-t border-border/20 hover:bg-muted/10">
                  <td className="px-4 py-2 text-xs text-muted-foreground">{fmtTime(j.ts)}</td>
                  <td className="px-4 py-2 font-mono text-xs">{j.job_id}</td>
                  <td className="px-4 py-2 text-xs">{j.action}</td>
                  <td className="px-4 py-2"><OutcomeBadge outcome={j.outcome} /></td>
                  <td className="px-4 py-2 text-xs text-muted-foreground font-mono break-all max-w-md">
                    {j.detail || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
