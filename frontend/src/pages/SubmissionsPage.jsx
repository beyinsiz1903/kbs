import React, { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { getSubmissions, getHotels, requeueSubmission } from '../lib/api';
import { StatusBadge } from '../components/StatusBadge';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import {
  Search, RefreshCw, RotateCw, Eye, ChevronLeft, ChevronRight
} from 'lucide-react';

const STATUSES = ['', 'pending', 'queued', 'sending', 'acked', 'failed', 'retrying', 'quarantined'];
const PAGE_SIZE = 25;

export default function SubmissionsPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [submissions, setSubmissions] = useState([]);
  const [total, setTotal] = useState(0);
  const [hotels, setHotels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [hotelFilter, setHotelFilter] = useState('');
  const [page, setPage] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const params = { limit: PAGE_SIZE, skip: page * PAGE_SIZE };
      if (statusFilter) params.status = statusFilter;
      if (hotelFilter) params.hotel_id = hotelFilter;

      const [subs, h] = await Promise.all([
        getSubmissions(params),
        hotels.length ? Promise.resolve(hotels) : getHotels()
      ]);

      setSubmissions(subs.items || []);
      setTotal(subs.total || 0);
      if (!hotels.length) setHotels(h);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, hotelFilter, page, hotels.length]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  const handleRequeue = async (id) => {
    try {
      await requeueSubmission(id);
      toast.success('Yeniden kuyruga eklendi / Requeued');
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message);
    }
  };

  const getHotelName = (hotelId) => {
    const hotel = hotels.find(h => h.id === hotelId);
    return hotel?.name || hotelId?.slice(0, 8);
  };

  const filteredSubs = search
    ? submissions.filter(s => {
        const gd = s.guest_data || {};
        const searchLower = search.toLowerCase();
        return (
          (gd.first_name || '').toLowerCase().includes(searchLower) ||
          (gd.last_name || '').toLowerCase().includes(searchLower) ||
          (gd.tc_kimlik_no || '').includes(search) ||
          (gd.passport_no || '').toLowerCase().includes(searchLower) ||
          (s.id || '').toLowerCase().includes(searchLower)
        );
      })
    : submissions;

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-6" data-testid="submissions-page">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{t('submissions.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('submissions.subtitle')}</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={refreshing}
          className="h-8 border-border/50"
          data-testid="submissions-refresh-button"
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} />
          {t('dashboard.refresh')}
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-[400px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder={t('submissions.search')}
            className="pl-9"
            data-testid="submissions-search-input"
          />
        </div>
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v === 'all' ? '' : v); setPage(0); }}>
          <SelectTrigger className="w-[180px]" data-testid="submissions-status-filter-select">
            <SelectValue placeholder={t('submissions.filterStatus')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('submissions.all')}</SelectItem>
            {STATUSES.filter(Boolean).map(s => (
              <SelectItem key={s} value={s}>{t(`status.${s}`)}</SelectItem>
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
      </div>

      {/* Table */}
      <Card className="bg-card/40 border-border/50">
        <ScrollArea className="w-full">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent border-border/30">
                <TableHead className="w-[120px]">{t('submissions.status')}</TableHead>
                <TableHead>{t('submissions.guest')}</TableHead>
                <TableHead>{t('submissions.document')}</TableHead>
                <TableHead className="hidden md:table-cell">{t('submissions.hotel')}</TableHead>
                <TableHead className="text-center">{t('submissions.attempts')}</TableHead>
                <TableHead className="hidden sm:table-cell">{t('submissions.created')}</TableHead>
                <TableHead className="w-[120px]">{t('submissions.actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                Array(5).fill(0).map((_, i) => (
                  <TableRow key={i} className="border-border/20">
                    {Array(7).fill(0).map((_, j) => (
                      <TableCell key={j}>
                        <div className="h-4 bg-muted/30 rounded animate-pulse" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : filteredSubs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">
                    {t('submissions.noSubmissions')}
                  </TableCell>
                </TableRow>
              ) : (
                filteredSubs.map((sub) => {
                  const gd = sub.guest_data || {};
                  return (
                    <TableRow
                      key={sub.id}
                      className="border-border/20 hover:bg-muted/20 cursor-pointer transition-colors"
                      onClick={() => navigate(`/submissions/${sub.id}`)}
                      data-testid={`submission-row-${sub.id}`}
                    >
                      <TableCell>
                        <StatusBadge status={sub.status} />
                      </TableCell>
                      <TableCell>
                        <div className="font-medium text-sm">{gd.first_name} {gd.last_name}</div>
                        <div className="text-xs text-muted-foreground">{sub.guest_type === 'tc_citizen' ? 'TC' : 'Passport'}</div>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-xs">
                          {gd.tc_kimlik_no || gd.passport_no || '-'}
                        </span>
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-sm">
                        {getHotelName(sub.hotel_id)}
                      </TableCell>
                      <TableCell className="text-center">
                        <span className="font-mono text-sm">{sub.attempt_count || 0}</span>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell text-xs text-muted-foreground">
                        {sub.created_at ? new Date(sub.created_at).toLocaleString() : '-'}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => navigate(`/submissions/${sub.id}`)}
                            data-testid={`submission-view-${sub.id}`}
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </Button>
                          {(sub.status === 'quarantined' || sub.status === 'failed') && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-amber-400 hover:text-amber-300"
                              onClick={() => handleRequeue(sub.id)}
                              data-testid={`submission-requeue-${sub.id}`}
                            >
                              <RotateCw className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </ScrollArea>

        {/* Pagination */}
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border/30">
            <span className="text-xs text-muted-foreground">
              {t('submissions.total')}: {total}
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
              <span className="text-xs text-muted-foreground">
                {page + 1} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="icon"
                className="h-7 w-7"
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
