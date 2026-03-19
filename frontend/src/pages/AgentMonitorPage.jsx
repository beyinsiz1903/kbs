import React, { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { getAgents, getHotels, toggleAgent } from '../lib/api';
import { AgentStatusBadge } from '../components/StatusBadge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import {
  Activity, RefreshCw, Power, PowerOff, Clock,
  CheckCircle2, XCircle, Layers
} from 'lucide-react';

export default function AgentMonitorPage() {
  const { t } = useLanguage();
  const [agents, setAgents] = useState([]);
  const [hotels, setHotels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [a, h] = await Promise.all([getAgents(), getHotels()]);
      setAgents(a);
      setHotels(h);
      setLastUpdate(new Date());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleToggle = async (hotelId, currentOnline) => {
    try {
      await toggleAgent(hotelId, !currentOnline);
      toast.success(`Agent ${!currentOnline ? 'cevrimici / online' : 'cevrimdisi / offline'}`);
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message);
    }
  };

  const getHotelName = (hotelId) => {
    return hotels.find(h => h.id === hotelId)?.name || hotelId;
  };

  const getTimeSince = (timestamp) => {
    if (!timestamp) return '-';
    const diff = (Date.now() - new Date(timestamp).getTime()) / 1000;
    if (diff < 60) return `${Math.round(diff)}s`;
    if (diff < 3600) return `${Math.round(diff / 60)}m`;
    return `${Math.round(diff / 3600)}h`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="agents-page">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{t('agents.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('agents.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Clock className="h-3.5 w-3.5" />
          {t('dashboard.lastUpdated')}: {lastUpdate?.toLocaleTimeString() || '-'}
        </div>
      </div>

      {agents.length === 0 ? (
        <Card className="bg-card/60 border-border/50">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Activity className="h-12 w-12 text-muted-foreground/30 mb-3" />
            <p className="text-muted-foreground">{t('agents.noAgents')}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {agents.map((agent, i) => {
            const isOnline = agent.status === 'online';
            return (
              <motion.div
                key={agent.hotel_id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
              >
                <Card className={`bg-card/60 border-border/50 transition-all ${
                  isOnline ? 'border-l-2 border-l-emerald-500/60' : 'border-l-2 border-l-slate-500/40'
                }`} data-testid={`agent-card-${agent.hotel_id}`}>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="text-base">{getHotelName(agent.hotel_id)}</CardTitle>
                        <p className="text-xs text-muted-foreground font-mono mt-0.5">
                          v{agent.version || '1.0.0'}
                        </p>
                      </div>
                      <AgentStatusBadge online={isOnline} />
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Stats */}
                    <div className="grid grid-cols-3 gap-3">
                      <div className="text-center rounded-lg bg-muted/20 py-2">
                        <Layers className="h-4 w-4 mx-auto text-primary/70 mb-1" />
                        <p className="text-lg font-semibold tabular-nums">{agent.queue_size || 0}</p>
                        <p className="text-[10px] text-muted-foreground">{t('agents.queueSize')}</p>
                      </div>
                      <div className="text-center rounded-lg bg-muted/20 py-2">
                        <CheckCircle2 className="h-4 w-4 mx-auto text-emerald-400/70 mb-1" />
                        <p className="text-lg font-semibold tabular-nums">{agent.processed_today || 0}</p>
                        <p className="text-[10px] text-muted-foreground">{t('agents.processedToday')}</p>
                      </div>
                      <div className="text-center rounded-lg bg-muted/20 py-2">
                        <XCircle className="h-4 w-4 mx-auto text-rose-400/70 mb-1" />
                        <p className="text-lg font-semibold tabular-nums">{agent.failed_today || 0}</p>
                        <p className="text-[10px] text-muted-foreground">{t('agents.failedToday')}</p>
                      </div>
                    </div>

                    {/* Heartbeat */}
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t('agents.lastHeartbeat')}</span>
                      <span className="font-mono text-xs">
                        {agent.last_heartbeat ? getTimeSince(agent.last_heartbeat) + ' ago' : '-'}
                      </span>
                    </div>

                    {/* Toggle Button */}
                    <Button
                      variant={isOnline ? 'outline' : 'default'}
                      size="sm"
                      className="w-full"
                      onClick={() => handleToggle(agent.hotel_id, isOnline)}
                      data-testid={`agent-toggle-${agent.hotel_id}`}
                    >
                      {isOnline ? (
                        <><PowerOff className="h-3.5 w-3.5 mr-1.5" /> {t('agents.toggleOffline')}</>
                      ) : (
                        <><Power className="h-3.5 w-3.5 mr-1.5" /> {t('agents.toggleOnline')}</>
                      )}
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
