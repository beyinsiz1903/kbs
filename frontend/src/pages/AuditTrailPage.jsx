import React, { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { getAuditEvents, getHotels } from '../lib/api';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { Badge } from '../components/ui/badge';
import {
  Search, RefreshCw, FileText, ChevronLeft, ChevronRight
} from 'lucide-react';

const ACTIONS = [
  'checkin_created', 'submission_created', 'validation_success', 'validation_failed',
  'queued', 'sent_to_kbs', 'kbs_ack', 'kbs_fail', 'retry_scheduled',
  'quarantined', 'manual_correction', 'requeued', 'agent_heartbeat',
  'agent_offline', 'agent_online'
];

const actionColors = {
  checkin_created: 'bg-blue-500/15 text-blue-200 border-blue-500/30',
  submission_created: 'bg-cyan-500/15 text-cyan-200 border-cyan-500/30',
  validation_success: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30',
  validation_failed: 'bg-rose-500/15 text-rose-200 border-rose-500/30',
  queued: 'bg-slate-500/15 text-slate-200 border-slate-500/30',
  sent_to_kbs: 'bg-cyan-500/15 text-cyan-200 border-cyan-500/30',
  kbs_ack: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30',
  kbs_fail: 'bg-rose-500/15 text-rose-200 border-rose-500/30',
  retry_scheduled: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
  quarantined: 'bg-fuchsia-500/10 text-fuchsia-200 border-fuchsia-500/25',
  manual_correction: 'bg-blue-500/15 text-blue-200 border-blue-500/30',
  requeued: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
  agent_heartbeat: 'bg-slate-500/10 text-slate-300 border-slate-500/20',
  agent_offline: 'bg-slate-500/15 text-slate-200 border-slate-500/30',
  agent_online: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30'
};

const PAGE_SIZE = 50;

export default function AuditTrailPage() {
  const { t } = useLanguage();
  const [events, setEvents] = useState([]);
  const [hotels, setHotels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('');
  const [hotelFilter, setHotelFilter] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(0);

  const fetchData = useCallback(async () => {
    try {
      const params = {
        limit: PAGE_SIZE,
        skip: page * PAGE_SIZE
      };
      if (actionFilter) params.action = actionFilter;
      if (hotelFilter) params.hotel_id = hotelFilter;

      const [evts, h] = await Promise.all([
        getAuditEvents(params),
        hotels.length ? Promise.resolve(hotels) : getHotels()
      ]);

      setEvents(evts.items || []);
      if (!hotels.length) setHotels(h);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [actionFilter, hotelFilter, page, hotels.length]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const getHotelName = (hotelId) => {
    return hotels.find(h => h.id === hotelId)?.name || hotelId?.slice(0, 8);
  };

  const filteredEvents = searchTerm
    ? events.filter(e =>
        (e.entity_id || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
        (e.action || '').includes(searchTerm.toLowerCase()) ||
        JSON.stringify(e.details || {}).toLowerCase().includes(searchTerm.toLowerCase())
      )
    : events;

  return (
    <div className="space-y-6" data-testid="audit-page">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">{t('audit.title')}</h1>
        <p className="text-muted-foreground mt-1">{t('audit.subtitle')}</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-[400px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            placeholder="Search events..."
            className="pl-9"
            data-testid="audit-search-input"
          />
        </div>
        <Select value={actionFilter} onValueChange={(v) => { setActionFilter(v === 'all' ? '' : v); setPage(0); }}>
          <SelectTrigger className="w-[200px]" data-testid="audit-action-filter">
            <SelectValue placeholder={t('audit.action')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('submissions.all')}</SelectItem>
            {ACTIONS.map(a => (
              <SelectItem key={a} value={a}>{a.replace(/_/g, ' ')}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {hotels.length > 1 && (
          <Select value={hotelFilter} onValueChange={(v) => { setHotelFilter(v === 'all' ? '' : v); setPage(0); }}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder={t('submissions.hotel')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('submissions.all')}</SelectItem>
              {hotels.map(h => (
                <SelectItem key={h.id} value={h.id}>{h.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={() => { setLoading(true); fetchData(); }}
          className="h-9"
        >
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
          {t('dashboard.refresh')}
        </Button>
      </div>

      {/* Table */}
      <Card className="bg-card/40 border-border/50">
        <ScrollArea className="w-full">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent border-border/30">
                <TableHead className="w-[180px]">{t('audit.action')}</TableHead>
                <TableHead>{t('audit.entity')}</TableHead>
                <TableHead className="hidden md:table-cell">{t('submissions.hotel')}</TableHead>
                <TableHead className="hidden sm:table-cell">{t('audit.actor')}</TableHead>
                <TableHead>{t('audit.timestamp')}</TableHead>
                <TableHead className="hidden lg:table-cell">{t('audit.details')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                Array(8).fill(0).map((_, i) => (
                  <TableRow key={i} className="border-border/20">
                    {Array(6).fill(0).map((_, j) => (
                      <TableCell key={j}>
                        <div className="h-4 bg-muted/30 rounded animate-pulse" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : filteredEvents.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-12 text-muted-foreground">
                    <FileText className="h-8 w-8 mx-auto text-muted-foreground/30 mb-2" />
                    {t('audit.noEvents')}
                  </TableCell>
                </TableRow>
              ) : (
                filteredEvents.map((event) => (
                  <TableRow key={event.id} className="border-border/20 hover:bg-muted/20" data-testid={`audit-log-row-${event.id}`}>
                    <TableCell>
                      <Badge variant="outline" className={`${actionColors[event.action] || ''} border text-[10px] font-mono`}>
                        {event.action?.replace(/_/g, ' ')}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className="text-xs font-mono text-muted-foreground">
                        {event.entity_type}/{event.entity_id?.slice(0, 8)}
                      </span>
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-sm">
                      {getHotelName(event.hotel_id)}
                    </TableCell>
                    <TableCell className="hidden sm:table-cell text-xs text-muted-foreground">
                      {event.actor || 'system'}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {event.created_at ? new Date(event.created_at).toLocaleString() : '-'}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      {event.details && Object.keys(event.details).length > 0 && (
                        <span className="text-[10px] font-mono text-muted-foreground/60 max-w-[200px] block truncate">
                          {JSON.stringify(event.details)}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </ScrollArea>

        {/* Pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border/30">
          <span className="text-xs text-muted-foreground">
            {filteredEvents.length} events
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              className="h-7 w-7"
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            <span className="text-xs text-muted-foreground">{page + 1}</span>
            <Button
              variant="outline"
              size="icon"
              className="h-7 w-7"
              onClick={() => setPage(p => p + 1)}
              disabled={filteredEvents.length < PAGE_SIZE}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
