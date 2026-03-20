import React, { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { getObservability } from '../lib/api';
import { KpiCard } from '../components/KpiCard';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import {
  RefreshCw, TrendingUp, AlertTriangle, ShieldAlert, Clock,
  CheckCircle2, XCircle, Activity, Server, Wifi, WifiOff
} from 'lucide-react';

export default function ObservabilityPage() {
  const { t, language } = useLanguage();
  const tr = (trText, enText) => language === 'tr' ? trText : enText;
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const result = await getObservability();
      setData(result);
      setLastUpdate(new Date());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
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
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!data) return null;

  const { summary, agents, tenants } = data;

  return (
    <div className="space-y-6" data-testid="observability-page">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{t('observability.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('observability.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Clock className="h-3.5 w-3.5" />
            {lastUpdate?.toLocaleTimeString() || '-'}
          </div>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing} className="h-8 border-border/50" data-testid="observability-refresh-button">
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} />
            {t('dashboard.refresh')}
          </Button>
        </div>
      </div>

      {/* Global KPIs */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <KpiCard
          title={t('observability.successRate')}
          value={`${summary.success_rate}%`}
          icon={TrendingUp}
          subtitle={`${summary.success_count} / ${summary.total_submissions}`}
        />
        <KpiCard
          title={t('observability.retryCount')}
          value={summary.retry_count}
          icon={RefreshCw}
        />
        <KpiCard
          title={t('observability.quarantineCount')}
          value={summary.quarantine_count}
          icon={ShieldAlert}
        />
        <KpiCard
          title={t('observability.queueDepth')}
          value={summary.queued_count}
          icon={Activity}
        />
        <KpiCard
          title={tr('Toplam Gonderim', 'Total Submissions')}
          value={summary.total_submissions}
          icon={Server}
        />
      </div>

      {/* Agent Health */}
      <Card className="bg-card/60 backdrop-blur border-border/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Activity className="h-4 w-4" /> {t('observability.agentHealth')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {agents.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('agents.noAgents')}</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {agents.map((ag) => {
                const tenant = tenants.find(t => t.hotel_id === ag.hotel_id);
                return (
                  <div key={ag.hotel_id} className="rounded-lg border border-border/40 bg-muted/10 p-4 space-y-2" data-testid={`obs-agent-${ag.hotel_id}`}>
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium truncate">{tenant?.hotel_name || ag.hotel_id}</span>
                      {ag.status === 'online' ? (
                        <Badge className="bg-emerald-500/15 text-emerald-200 border-emerald-500/30 border text-[10px]">
                          <Wifi className="h-3 w-3 mr-1" /> {t('agents.online')}
                        </Badge>
                      ) : (
                        <Badge className="bg-slate-500/15 text-slate-200 border-slate-500/30 border text-[10px]">
                          <WifiOff className="h-3 w-3 mr-1" /> {t('agents.offline')}
                        </Badge>
                      )}
                    </div>
                    <Separator className="bg-border/20" />
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="text-muted-foreground">{t('agents.queueSize')}</div>
                      <div className="text-right font-mono tabular-nums">{ag.queue_size}</div>
                      <div className="text-muted-foreground">{tr('Sinyal Yasi', 'Heartbeat Age')}</div>
                      <div className="text-right">
                        {ag.heartbeat_freshness_seconds != null ? (
                          <span className={ag.heartbeat_stale ? 'text-amber-400' : 'text-emerald-400'}>
                            {ag.heartbeat_freshness_seconds < 60 ? `${Math.round(ag.heartbeat_freshness_seconds)}s` : `${Math.round(ag.heartbeat_freshness_seconds / 60)}m`}
                          </span>
                        ) : '-'}
                      </div>
                      <div className="text-muted-foreground">{t('agents.processedToday')}</div>
                      <div className="text-right font-mono tabular-nums">{ag.processed_today}</div>
                      <div className="text-muted-foreground">{t('agents.failedToday')}</div>
                      <div className="text-right font-mono tabular-nums text-rose-400">{ag.failed_today}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Tenant Readiness */}
      <Card className="bg-card/60 backdrop-blur border-border/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Server className="h-4 w-4" /> {t('observability.tenantReadiness')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="w-full">
            <div className="space-y-3">
              {tenants.map((tenant) => (
                <div key={tenant.hotel_id} className="rounded-lg border border-border/30 bg-muted/5 p-4" data-testid={`obs-tenant-${tenant.hotel_id}`}>
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <span className="text-sm font-medium">{tenant.hotel_name}</span>
                      <span className="text-xs text-muted-foreground ml-2">({tenant.onboarding_status})</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {tenant.agent_online ? (
                        <Badge className="bg-emerald-500/15 text-emerald-200 border-emerald-500/30 border text-[10px]">Agent OK</Badge>
                      ) : (
                        <Badge className="bg-rose-500/15 text-rose-200 border-rose-500/30 border text-[10px]">Agent Offline</Badge>
                      )}
                      {tenant.credential_configured ? (
                        <Badge className="bg-emerald-500/15 text-emerald-200 border-emerald-500/30 border text-[10px]">
                          {t('observability.credentialOk')}
                        </Badge>
                      ) : (
                        <Badge className="bg-amber-500/15 text-amber-200 border-amber-500/30 border text-[10px]">
                          {t('observability.credentialMissing')}
                        </Badge>
                      )}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                    <div>
                      <span className="text-muted-foreground block">{t('observability.successRate')}</span>
                      <div className="flex items-center gap-2 mt-1">
                        <Progress value={tenant.submission_success_rate} className="h-1.5 flex-1" />
                        <span className="font-mono tabular-nums">{tenant.submission_success_rate}%</span>
                      </div>
                    </div>
                    <div>
                      <span className="text-muted-foreground block">{tr('Toplam', 'Total')}</span>
                      <span className="font-mono tabular-nums text-sm">{tenant.submission_total}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block">{t('observability.lastSuccess')}</span>
                      {tenant.last_successful_transmission ? (
                        <span className="text-emerald-400">
                          {new Date(tenant.last_successful_transmission.updated_at).toLocaleString(language === 'tr' ? 'tr-TR' : 'en-US')}
                        </span>
                      ) : <span className="text-muted-foreground">-</span>}
                    </div>
                    <div>
                      <span className="text-muted-foreground block">{t('observability.lastFail')}</span>
                      {tenant.last_failed_transmission ? (
                        <div>
                          <span className="text-rose-400 block">
                            {new Date(tenant.last_failed_transmission.updated_at).toLocaleString(language === 'tr' ? 'tr-TR' : 'en-US')}
                          </span>
                          <span className="text-rose-400/70 text-[10px] truncate block max-w-[200px]">
                            {tenant.last_failed_transmission.last_error}
                          </span>
                        </div>
                      ) : <span className="text-muted-foreground">-</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
