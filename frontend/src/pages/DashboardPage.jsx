import React, { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { getMetrics, getHotels } from '../lib/api';
import { KpiCard } from '../components/KpiCard';
import { AgentStatusBadge, KBSModeBadge } from '../components/StatusBadge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { useNavigate } from 'react-router-dom';
import {
  RefreshCw, Send, CheckCircle2, XCircle, ShieldAlert,
  Activity, Clock, Building2, Plus
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';

const CHART_COLORS = {
  acked: 'hsl(142, 70%, 45%)',
  failed: 'hsl(0, 72%, 52%)',
  retrying: 'hsl(38, 92%, 50%)',
  queued: 'hsl(188, 86%, 45%)',
  quarantined: 'hsl(292, 60%, 55%)'
};

export default function DashboardPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState(null);
  const [hotels, setHotels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [m, h] = await Promise.all([getMetrics(), getHotels()]);
      setMetrics(m);
      setHotels(h);
      setLastUpdate(new Date());
    } catch (err) {
      console.error('Failed to fetch metrics:', err);
    } finally {
      setLoading(false);
    }
  }, []);

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
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const subs = metrics?.submissions || {};
  const agents = metrics?.agents || [];
  const kbsMode = metrics?.kbs_simulation?.mode || 'normal';
  const onlineAgents = agents.filter(a => a.status === 'online').length;

  const pieData = Object.entries(subs.by_status || {}).map(([key, val]) => ({
    name: key, value: val
  })).filter(d => d.value > 0);

  const barData = [
    { name: t('status.acked'), value: subs.success_count || 0, fill: CHART_COLORS.acked },
    { name: t('status.failed'), value: subs.failed_count || 0, fill: CHART_COLORS.failed },
    { name: t('status.retrying'), value: subs.by_status?.retrying || 0, fill: CHART_COLORS.retrying },
    { name: t('status.queued'), value: subs.by_status?.queued || 0, fill: CHART_COLORS.queued },
  ];

  if (hotels.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{t('dashboard.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('dashboard.subtitle')}</p>
        </div>
        <Card className="bg-card/60 border-border/50">
          <CardContent className="flex flex-col items-center justify-center py-16 gap-4">
            <Building2 className="h-12 w-12 text-muted-foreground/30" />
            <p className="text-lg text-muted-foreground">{t('dashboard.noHotels')}</p>
            <Button onClick={() => navigate('/hotels')} data-testid="dashboard-add-hotel-button">
              <Plus className="h-4 w-4 mr-2" />
              {t('dashboard.addHotelFirst')}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{t('dashboard.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('dashboard.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Clock className="h-3.5 w-3.5" />
            {t('dashboard.lastUpdated')}: {lastUpdate?.toLocaleTimeString() || '-'}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
            className="h-8 border-border/50"
            data-testid="dashboard-refresh-button"
          >
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} />
            {t('dashboard.refresh')}
          </Button>
          <KBSModeBadge mode={kbsMode} />
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title={t('dashboard.totalQueued')}
          value={subs.pending_count || 0}
          icon={Send}
          subtitle={`${subs.total || 0} ${t('submissions.total').toLowerCase()}`}
        />
        <KpiCard
          title={t('dashboard.totalAcked')}
          value={subs.success_count || 0}
          icon={CheckCircle2}
          subtitle={`${subs.success_rate || 0}% ${t('dashboard.successRate').toLowerCase()}`}
        />
        <KpiCard
          title={t('dashboard.totalFailed')}
          value={subs.failed_count || 0}
          icon={XCircle}
        />
        <KpiCard
          title={t('dashboard.agentsOnline')}
          value={`${onlineAgents}/${agents.length}`}
          icon={Activity}
          subtitle={`${agents.length} ${t('nav.agents').toLowerCase()}`}
        />
      </div>

      {/* Charts Row */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Bar Chart */}
        <Card className="bg-card/60 backdrop-blur border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {t('submissions.title')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(220, 14%, 18%)" />
                  <XAxis dataKey="name" tick={{ fill: 'hsl(215, 18%, 70%)', fontSize: 11 }} />
                  <YAxis tick={{ fill: 'hsl(215, 18%, 70%)', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(220, 18%, 12%)',
                      border: '1px solid hsl(220, 14%, 22%)',
                      borderRadius: '8px',
                      color: 'hsl(210, 40%, 98%)',
                      fontSize: '12px'
                    }}
                  />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                    {barData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Pie Chart */}
        <Card className="bg-card/60 backdrop-blur border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {t('dashboard.successRate')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[220px] flex items-center justify-center">
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%" cy="50%"
                      innerRadius={50} outerRadius={80}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={CHART_COLORS[entry.name] || '#8884d8'} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(220, 18%, 12%)',
                        border: '1px solid hsl(220, 14%, 22%)',
                        borderRadius: '8px',
                        color: 'hsl(210, 40%, 98%)',
                        fontSize: '12px'
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-muted-foreground text-sm">{t('submissions.noSubmissions')}</p>
              )}
            </div>
            {/* Legend */}
            <div className="flex flex-wrap gap-3 mt-2 justify-center">
              {pieData.map(d => (
                <div key={d.name} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="h-2.5 w-2.5 rounded-sm" style={{ background: CHART_COLORS[d.name] || '#8884d8' }} />
                  {d.name}: {d.value}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Agent Strip */}
      {agents.length > 0 && (
        <Card className="bg-card/60 backdrop-blur border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {t('nav.agents')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {agents.map((agent) => {
                const hotel = hotels.find(h => h.id === agent.hotel_id);
                return (
                  <div
                    key={agent.hotel_id}
                    className="flex items-center gap-3 rounded-lg border border-border/40 bg-muted/20 px-4 py-3 cursor-pointer hover:bg-muted/40 transition-colors"
                    onClick={() => navigate('/agents')}
                    data-testid={`agent-card-${agent.hotel_id}`}
                  >
                    <AgentStatusBadge online={agent.status === 'online'} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{hotel?.name || agent.hotel_id}</p>
                      <p className="text-xs text-muted-foreground">
                        {t('agents.queueSize')}: {agent.queue_size || 0}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
