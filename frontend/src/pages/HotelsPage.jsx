import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';
import { useAuth } from '../contexts/AuthContext';
import { getHotels, createHotel, getAgents } from '../lib/api';
import { AgentStatusBadge } from '../components/StatusBadge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import {
  Building2, Plus, RefreshCw, MapPin, Settings, Heart, ClipboardCheck
} from 'lucide-react';

const ONBOARDING_STATUS_BADGES = {
  not_started: 'bg-slate-500/15 text-slate-200 border-slate-500/30',
  in_progress: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
  credentials_pending: 'bg-cyan-500/15 text-cyan-200 border-cyan-500/30',
  testing: 'bg-cyan-500/15 text-cyan-200 border-cyan-500/30',
  active: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30',
  blocked: 'bg-rose-500/15 text-rose-200 border-rose-500/30',
};

const ONBOARDING_LABELS = {
  tr: { not_started: 'Baslanmadi', in_progress: 'Devam Ediyor', credentials_pending: 'Bilgi Bekleniyor', testing: 'Test Edilyor', active: 'Aktif', blocked: 'Bloke' },
  en: { not_started: 'Not Started', in_progress: 'In Progress', credentials_pending: 'Credentials Pending', testing: 'Testing', active: 'Active', blocked: 'Blocked' },
};

export default function HotelsPage() {
  const { t, language } = useLanguage();
  const { isAdmin, isManager } = useAuth();
  const navigate = useNavigate();
  const [hotels, setHotels] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: '',
    tax_number: '',
    city: '',
    address: '',
    kbs_institution_code: ''
  });

  const fetchData = useCallback(async () => {
    try {
      const [h, a] = await Promise.all([getHotels(), getAgents()]);
      setHotels(h);
      setAgents(a);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const getAgentStatus = (hotelId) => {
    const agent = agents.find(a => a.hotel_id === hotelId);
    return agent?.status === 'online';
  };

  const handleCreate = async () => {
    if (!form.name || !form.tax_number || !form.city) {
      toast.error(language === 'tr' ? 'Zorunlu alanlar eksik' : 'Required fields missing');
      return;
    }
    setCreating(true);
    try {
      await createHotel(form);
      toast.success(language === 'tr' ? 'Otel eklendi' : 'Hotel added');
      setDialogOpen(false);
      setForm({ name: '', tax_number: '', city: '', address: '', kbs_institution_code: '' });
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="hotels-page">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{t('hotels.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('hotels.subtitle')}</p>
        </div>
        {(isAdmin || isManager) && (
          <Button onClick={() => setDialogOpen(true)} data-testid="hotel-create-button">
            <Plus className="h-4 w-4 mr-2" /> {t('hotels.addHotel')}
          </Button>
        )}
      </div>

      {hotels.length === 0 && !loading ? (
        <Card className="bg-card/60 border-border/50">
          <CardContent className="flex flex-col items-center justify-center py-16 gap-3">
            <Building2 className="h-12 w-12 text-muted-foreground/30" />
            <p className="text-muted-foreground">{t('hotels.noHotels')}</p>
            <Button variant="outline" onClick={() => setDialogOpen(true)}>
              <Plus className="h-4 w-4 mr-2" /> {t('hotels.addHotel')}
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card className="bg-card/40 border-border/50">
          <ScrollArea className="w-full">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent border-border/30">
                  <TableHead>{t('hotels.name')}</TableHead>
                  <TableHead>{t('hotels.city')}</TableHead>
                  <TableHead className="hidden md:table-cell">{t('hotels.taxNumber')}</TableHead>
                  <TableHead>{language === 'tr' ? 'Onboarding' : 'Onboarding'}</TableHead>
                  <TableHead>{t('hotels.agentStatus')}</TableHead>
                  <TableHead className="w-[120px]">{language === 'tr' ? 'Islemler' : 'Actions'}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  Array(3).fill(0).map((_, i) => (
                    <TableRow key={i} className="border-border/20">
                      {Array(6).fill(0).map((_, j) => (
                        <TableCell key={j}>
                          <div className="h-4 bg-muted/30 rounded animate-pulse" />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : (
                  hotels.map((hotel) => {
                    const obStatus = hotel.onboarding_status || 'not_started';
                    return (
                      <TableRow key={hotel.id} className="border-border/20 hover:bg-muted/20" data-testid={`hotel-row-${hotel.id}`}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Building2 className="h-4 w-4 text-primary/60" />
                            <span className="font-medium">{hotel.name}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                            <MapPin className="h-3.5 w-3.5" />
                            {hotel.city}
                          </div>
                        </TableCell>
                        <TableCell className="hidden md:table-cell font-mono text-sm">{hotel.tax_number}</TableCell>
                        <TableCell>
                          <Badge className={`${ONBOARDING_STATUS_BADGES[obStatus] || ONBOARDING_STATUS_BADGES.not_started} border text-xs`}>
                            {ONBOARDING_LABELS[language]?.[obStatus] || obStatus}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <AgentStatusBadge online={getAgentStatus(hotel.id)} />
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={() => navigate(`/hotels/${hotel.id}/onboarding`)}
                              data-testid={`hotel-onboarding-${hotel.id}`}
                              title={language === 'tr' ? 'KBS Kurulum' : 'KBS Setup'}
                            >
                              <Settings className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={() => navigate(`/hotels/${hotel.id}/health`)}
                              data-testid={`hotel-health-${hotel.id}`}
                              title={language === 'tr' ? 'Saglik Paneli' : 'Health Panel'}
                            >
                              <Heart className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={() => navigate(`/hotels/${hotel.id}/go-live`)}
                              data-testid={`hotel-golive-${hotel.id}`}
                              title={language === 'tr' ? 'Go-Live Kontrol' : 'Go-Live Checklist'}
                            >
                              <ClipboardCheck className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </ScrollArea>
        </Card>
      )}

      {/* Create Hotel Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle>{t('hotels.addHotel')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>{t('hotels.name')} *</Label>
              <Input
                value={form.name}
                onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                placeholder="Grand Istanbul Hotel"
                className="mt-1"
                data-testid="hotel-name-input"
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>{t('hotels.taxNumber')} *</Label>
                <Input
                  value={form.tax_number}
                  onChange={e => setForm(p => ({ ...p, tax_number: e.target.value }))}
                  placeholder="1234567890"
                  className="mt-1 font-mono"
                  data-testid="hotel-tax-input"
                />
              </div>
              <div>
                <Label>{t('hotels.city')} *</Label>
                <Input
                  value={form.city}
                  onChange={e => setForm(p => ({ ...p, city: e.target.value }))}
                  placeholder="Istanbul"
                  className="mt-1"
                  data-testid="hotel-city-input"
                />
              </div>
            </div>
            <div>
              <Label>{t('hotels.address')}</Label>
              <Input
                value={form.address}
                onChange={e => setForm(p => ({ ...p, address: e.target.value }))}
                placeholder="Taksim Meydani No:1"
                className="mt-1"
                data-testid="hotel-address-input"
              />
            </div>
            <div>
              <Label>{t('hotels.kbsCode')}</Label>
              <Input
                value={form.kbs_institution_code}
                onChange={e => setForm(p => ({ ...p, kbs_institution_code: e.target.value }))}
                placeholder="IST-2024-0001"
                className="mt-1 font-mono"
                data-testid="hotel-kbs-code-input"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>{t('common.cancel')}</Button>
            <Button onClick={handleCreate} disabled={creating} data-testid="hotel-create-submit-button">
              {creating ? <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
              {t('hotels.addHotel')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
