import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';
import { getHotelHealth } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { KpiCard } from '../components/KpiCard';
import { AgentStatusBadge } from '../components/StatusBadge';
import {
  ArrowLeft, RefreshCw, Activity, Server, Send, ShieldAlert,
  CheckCircle2, XCircle, Clock, Loader2
} from 'lucide-react';

export default function HotelHealthPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { language } = useLanguage();
  const t = (tr, en) => language === 'tr' ? tr : en;

  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const data = await getHotelHealth(id);
      setHealth(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!health) return null;

  const { hotel, agent, integration, submissions, onboarding_status } = health;
  const statusColors = {
    not_started: 'bg-slate-500/15 text-slate-200 border-slate-500/30',
    in_progress: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
    credentials_pending: 'bg-cyan-500/15 text-cyan-200 border-cyan-500/30',
    testing: 'bg-cyan-500/15 text-cyan-200 border-cyan-500/30',
    active: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30',
    blocked: 'bg-rose-500/15 text-rose-200 border-rose-500/30',
  };

  return (
    <div className="space-y-6 max-w-5xl" data-testid="hotel-health-page">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/hotels')} data-testid="health-back-button">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{hotel?.name}</h1>
            <Badge className={`${statusColors[onboarding_status] || statusColors.not_started} border text-xs`}>
              {onboarding_status}
            </Badge>
          </div>
          <p className="text-muted-foreground text-sm">{hotel?.city} - {t('Saglik Paneli', 'Health Panel')}</p>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing} className="h-8" data-testid="health-refresh-button">
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} />
          {t('Yenile', 'Refresh')}
        </Button>
      </div>

      {/* KPIs */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard title={t('Agent Durumu', 'Agent Status')} value={agent.status === 'online' ? t('Cevrimici', 'Online') : t('Cevrimdisi', 'Offline')} icon={Activity} />
        <KpiCard title={t('Kuyruk', 'Queue')} value={agent.queue_size} icon={Send} subtitle={`${agent.processed_today} ${t('bugun islendi', 'processed today')}`} />
        <KpiCard title={t('Toplam Gonderim', 'Total Submissions')} value={submissions.total} icon={Server} />
        <KpiCard title={t('Karantina', 'Quarantined')} value={submissions.quarantined} icon={ShieldAlert} />
      </div>

      {/* Details Grid */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Agent */}
        <Card className="bg-card/60 border-border/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Activity className="h-4 w-4" /> {t('Agent Detaylari', 'Agent Details')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{t('Durum', 'Status')}</span>
              <AgentStatusBadge online={agent.status === 'online'} />
            </div>
            <Separator className="bg-border/20" />
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{t('Son Sinyal', 'Last Heartbeat')}</span>
              <span className="text-sm font-mono">{agent.last_heartbeat ? new Date(agent.last_heartbeat).toLocaleTimeString() : '-'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{t('Bugun Islenen', 'Processed Today')}</span>
              <span className="text-sm font-mono tabular-nums">{agent.processed_today}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{t('Bugun Basarisiz', 'Failed Today')}</span>
              <span className="text-sm font-mono tabular-nums text-rose-400">{agent.failed_today}</span>
            </div>
          </CardContent>
        </Card>

        {/* Integration */}
        <Card className="bg-card/60 border-border/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Server className="h-4 w-4" /> {t('Entegrasyon Durumu', 'Integration Status')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{t('Yapilandirildi', 'Configured')}</span>
              {integration.configured ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : <XCircle className="h-4 w-4 text-rose-400" />}
            </div>
            <Separator className="bg-border/20" />
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{t('Ortam', 'Environment')}</span>
              <Badge variant="outline" className="text-xs">{integration.environment || '-'}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{t('Son Baglanti Testi', 'Last Connection Test')}</span>
              <span className="text-sm font-mono">{integration.last_connection_test ? new Date(integration.last_connection_test).toLocaleString() : '-'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{t('Sonuc', 'Result')}</span>
              {integration.last_connection_success === true ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : integration.last_connection_success === false ? <XCircle className="h-4 w-4 text-rose-400" /> : <span className="text-xs text-muted-foreground">-</span>}
            </div>
          </CardContent>
        </Card>

        {/* Submissions Breakdown */}
        <Card className="bg-card/60 border-border/50 lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Send className="h-4 w-4" /> {t('Gonderim Dagilimi', 'Submission Distribution')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {Object.entries(submissions.by_status || {}).map(([status, count]) => (
                <div key={status} className="rounded-lg border border-border/30 bg-muted/10 p-3 text-center">
                  <p className="text-2xl font-semibold tabular-nums">{count}</p>
                  <p className="text-xs text-muted-foreground capitalize mt-1">{status}</p>
                </div>
              ))}
            </div>
            {submissions.last_successful && (
              <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                {t('Son basarili gonderim', 'Last successful submission')}: {submissions.last_successful.updated_at ? new Date(submissions.last_successful.updated_at).toLocaleString() : '-'}
              </div>
            )}
            {submissions.last_error && (
              <div className="mt-2 flex items-center gap-2 text-xs text-rose-400">
                <XCircle className="h-3.5 w-3.5" />
                {t('Son hata', 'Last error')}: {submissions.last_error.last_error || 'unknown'}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <Button variant="outline" onClick={() => navigate(`/hotels/${id}/onboarding`)} data-testid="health-go-onboarding-button">
          {t('Entegrasyon Ayarlari', 'Integration Settings')}
        </Button>
        <Button variant="outline" onClick={() => navigate('/submissions')} data-testid="health-go-submissions-button">
          {t('Gonderimlere Git', 'Go to Submissions')}
        </Button>
      </div>
    </div>
  );
}
