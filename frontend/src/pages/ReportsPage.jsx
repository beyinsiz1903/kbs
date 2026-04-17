import React, { useCallback, useEffect, useState } from 'react';
import { listReports, errorMessage } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { toast } from 'sonner';
import { RefreshCw } from 'lucide-react';

function todayISO() { return new Date().toISOString().slice(0, 10); }
function daysAgo(n) {
  const d = new Date(); d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

function fmtDateTime(s) {
  if (!s) return '—';
  try {
    return new Date(s).toLocaleString('tr-TR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return s; }
}

export default function ReportsPage() {
  const [from, setFrom] = useState(daysAgo(7));
  const [to, setTo] = useState(todayISO());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listReports(from, to);
      setData(res);
    } catch (err) {
      toast.error(errorMessage(err));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [from, to]);

  useEffect(() => { load(); }, [load]);

  const reports = data?.reports || (Array.isArray(data) ? data : []);

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">Rapor Geçmişi</h1>
          <p className="text-xs text-muted-foreground">PMS'e işlenmiş KBS bildirimleri</p>
        </div>
        <div className="flex items-end gap-2">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Başlangıç</label>
            <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="w-44" />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Bitiş</label>
            <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="w-44" />
          </div>
          <Button variant="outline" onClick={load} disabled={loading} className="gap-2">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Yenile
          </Button>
        </div>
      </div>

      <Card className="bg-card/40 border-border/50 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/20 text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-3 text-left">Tarih</th>
              <th className="px-4 py-3 text-left">Misafir Sayısı</th>
              <th className="px-4 py-3 text-left">Gönderen</th>
              <th className="px-4 py-3 text-left">KBS Referansı</th>
              <th className="px-4 py-3 text-left">Oluşturma</th>
              <th className="px-4 py-3 text-left">Notlar</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={6} className="px-4 py-12 text-center text-muted-foreground">Yükleniyor…</td></tr>
            )}
            {!loading && reports.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-12 text-center text-muted-foreground">
                Bu aralıkta gönderilmiş rapor yok
              </td></tr>
            )}
            {!loading && reports.map((r) => (
              <tr key={r.id || r.submission_reference} className="border-t border-border/20 hover:bg-muted/10">
                <td className="px-4 py-3">{r.date || '—'}</td>
                <td className="px-4 py-3">{r.guest_count ?? r.booking_ids?.length ?? '—'}</td>
                <td className="px-4 py-3 text-xs">{r.created_by || r.submitted_by || '—'}</td>
                <td className="px-4 py-3 font-mono text-xs">{r.submission_reference || '—'}</td>
                <td className="px-4 py-3 text-xs">{fmtDateTime(r.created_at || r.submitted_at)}</td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{r.notes || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
