import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { listGuests, submitToKbs, errorMessage } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { Checkbox } from '../components/ui/checkbox';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { RefreshCw, Send, AlertTriangle, CheckCircle2 } from 'lucide-react';

function todayISO() {
  return new Date().toISOString().slice(0, 10);
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

function maskTC(tc) {
  if (!tc) return '—';
  const s = String(tc);
  if (s.length < 4) return s;
  return s.slice(0, 3) + '*****' + s.slice(-3);
}

export default function GuestsPage() {
  const [date, setDate] = useState(todayISO());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [selected, setSelected] = useState(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setSelected(new Set());
    try {
      const res = await listGuests(date);
      setData(res);
    } catch (err) {
      toast.error(errorMessage(err));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => { load(); }, [load]);

  const guests = data?.guests || [];

  const toggleOne = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(guests.map((g) => g.id)));
  const selectReady = () => setSelected(new Set(guests.filter((g) => g.kbs_ready).map((g) => g.id)));
  const clearAll = () => setSelected(new Set());

  const readySelectedCount = useMemo(() =>
    guests.filter((g) => selected.has(g.id) && g.kbs_ready).length, [guests, selected]);

  const handleSubmit = async () => {
    const ids = guests.filter((g) => selected.has(g.id) && g.kbs_ready).map((g) => g.id);
    if (ids.length === 0) {
      toast.error('Gönderilecek hazır misafir seçin');
      return;
    }
    setSubmitting(true);
    try {
      const res = await submitToKbs({ date, booking_ids: ids, notes: '' });
      toast.success(`✅ ${res.guest_count} misafir KBS'ye bildirildi (Ref: ${res.submission_reference})`);
      await load();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">Bugünün Misafirleri</h1>
          <p className="text-xs text-muted-foreground">PMS'ten alınan günlük konaklama listesi</p>
        </div>
        <div className="flex items-end gap-2">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Tarih</label>
            <Input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-44"
              data-testid="input-date"
            />
          </div>
          <Button
            variant="outline"
            onClick={load}
            disabled={loading}
            className="gap-2"
            data-testid="btn-refresh"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Yenile
          </Button>
        </div>
      </div>

      {data && (
        <div className="grid grid-cols-3 gap-3">
          <Card className="p-4 bg-card/40">
            <p className="text-xs text-muted-foreground">Toplam Misafir</p>
            <p className="text-2xl font-semibold">{data.guest_count ?? guests.length}</p>
          </Card>
          <Card className="p-4 bg-card/40">
            <p className="text-xs text-muted-foreground">KBS'ye Hazır</p>
            <p className="text-2xl font-semibold text-emerald-400">{data.ready_count ?? guests.filter(g => g.kbs_ready).length}</p>
          </Card>
          <Card className="p-4 bg-card/40">
            <p className="text-xs text-muted-foreground">Eksik Bilgili</p>
            <p className="text-2xl font-semibold text-rose-400">{data.missing_info_count ?? guests.filter(g => !g.kbs_ready).length}</p>
          </Card>
        </div>
      )}

      <Card className="bg-card/40 border-border/50">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border/30 flex-wrap">
          <Button size="sm" variant="ghost" onClick={selectAll} disabled={!guests.length}>
            Tümünü Seç
          </Button>
          <Button size="sm" variant="ghost" onClick={selectReady} disabled={!guests.length}>
            Sadece Hazırları Seç
          </Button>
          <Button size="sm" variant="ghost" onClick={clearAll} disabled={!selected.size}>
            Temizle
          </Button>
          <span className="text-xs text-muted-foreground ml-2">
            {selected.size} seçili ({readySelectedCount} hazır)
          </span>
          <div className="ml-auto">
            <Button
              onClick={handleSubmit}
              disabled={submitting || readySelectedCount === 0}
              className="gap-2"
              data-testid="btn-send-kbs"
            >
              <Send className={`h-4 w-4 ${submitting ? 'animate-pulse' : ''}`} />
              {submitting ? 'Gönderiliyor…' : `Seçilenleri KBS'ye Gönder (${readySelectedCount})`}
            </Button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/20 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left w-10"></th>
                <th className="px-4 py-3 text-left">Ad Soyad</th>
                <th className="px-4 py-3 text-left">Oda</th>
                <th className="px-4 py-3 text-left">Giriş</th>
                <th className="px-4 py-3 text-left">TC / Pasaport</th>
                <th className="px-4 py-3 text-left">Milliyet</th>
                <th className="px-4 py-3 text-left">Doğum</th>
                <th className="px-4 py-3 text-left">Durum</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">Yükleniyor…</td></tr>
              )}
              {!loading && guests.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">
                  Bu tarihte misafir bulunamadı
                </td></tr>
              )}
              {!loading && guests.map((g) => {
                const isSel = selected.has(g.id);
                return (
                  <tr
                    key={g.id}
                    className={`border-t border-border/20 hover:bg-muted/10 ${
                      !g.kbs_ready ? 'bg-rose-500/5' : ''
                    }`}
                    title={!g.kbs_ready ? 'Eksik bilgi: TC/pasaport, doğum, milliyet vb.' : ''}
                  >
                    <td className="px-4 py-3">
                      <Checkbox checked={isSel} onCheckedChange={() => toggleOne(g.id)} />
                    </td>
                    <td className="px-4 py-3 font-medium">{g.guest_name || '—'}</td>
                    <td className="px-4 py-3">{g.room_number || '—'}</td>
                    <td className="px-4 py-3 text-xs">{fmtDateTime(g.check_in)}</td>
                    <td className="px-4 py-3 font-mono text-xs">
                      {g.id_number ? maskTC(g.id_number) : (g.passport_number || '—')}
                    </td>
                    <td className="px-4 py-3 text-xs">{g.nationality || '—'}</td>
                    <td className="px-4 py-3 text-xs">{g.birth_date || '—'}</td>
                    <td className="px-4 py-3">
                      {g.kbs_ready ? (
                        <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 gap-1">
                          <CheckCircle2 className="h-3 w-3" /> Hazır
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="border-rose-500/40 text-rose-400 gap-1">
                          <AlertTriangle className="h-3 w-3" /> Eksik
                        </Badge>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
