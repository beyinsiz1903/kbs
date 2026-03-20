import React, { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { useAuth } from '../contexts/AuthContext';
import { getUsers, createUser, getHotels } from '../lib/api';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import { Plus, Users, RefreshCw, Shield, Building2, UserPlus } from 'lucide-react';

const ROLE_BADGES = {
  admin: 'bg-primary/15 text-primary border-primary/30',
  hotel_manager: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
  front_desk: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30',
};

const ROLE_LABELS = {
  tr: { admin: 'Sistem Yoneticisi', hotel_manager: 'Otel Muduru', front_desk: 'Resepsiyon' },
  en: { admin: 'Admin', hotel_manager: 'Hotel Manager', front_desk: 'Front Desk' },
};

export default function UsersPage() {
  const { language } = useLanguage();
  const { isAdmin } = useAuth();
  const t = (tr, en) => language === 'tr' ? tr : en;

  const [users, setUsers] = useState([]);
  const [hotels, setHotels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    email: '', password: '', first_name: '', last_name: '',
    role: 'front_desk', hotel_ids: []
  });

  const fetchData = useCallback(async () => {
    try {
      const [u, h] = await Promise.all([getUsers(), getHotels()]);
      setUsers(u);
      setHotels(h);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleCreate = async () => {
    if (!form.email || !form.password || !form.first_name || !form.last_name) {
      toast.error(t('Zorunlu alanlar eksik', 'Required fields missing'));
      return;
    }
    setCreating(true);
    try {
      await createUser(form);
      toast.success(t('Kullanici olusturuldu', 'User created'));
      setDialogOpen(false);
      setForm({ email: '', password: '', first_name: '', last_name: '', role: 'front_desk', hotel_ids: [] });
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message);
    } finally {
      setCreating(false);
    }
  };

  const getHotelName = (id) => hotels.find(h => h.id === id)?.name || id?.slice(0, 8);

  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <Shield className="h-12 w-12 text-muted-foreground/30" />
        <p className="text-muted-foreground">{t('Bu sayfaya erisim yetkiniz yok', 'You do not have access to this page')}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="users-page">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{t('Kullanici Yonetimi', 'User Management')}</h1>
          <p className="text-muted-foreground mt-1">{t('Sistem kullanicilari ve roller', 'System users and roles')}</p>
        </div>
        <Button onClick={() => setDialogOpen(true)} data-testid="user-create-button">
          <UserPlus className="h-4 w-4 mr-2" /> {t('Kullanici Ekle', 'Add User')}
        </Button>
      </div>

      <Card className="bg-card/40 border-border/50">
        <ScrollArea className="w-full">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent border-border/30">
                <TableHead>{t('Ad Soyad', 'Name')}</TableHead>
                <TableHead>{t('E-posta', 'Email')}</TableHead>
                <TableHead>{t('Rol', 'Role')}</TableHead>
                <TableHead>{t('Oteller', 'Hotels')}</TableHead>
                <TableHead>{t('Durum', 'Status')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                Array(3).fill(0).map((_, i) => (
                  <TableRow key={i} className="border-border/20">
                    {Array(5).fill(0).map((_, j) => (
                      <TableCell key={j}><div className="h-4 bg-muted/30 rounded animate-pulse" /></TableCell>
                    ))}
                  </TableRow>
                ))
              ) : users.map(u => (
                <TableRow key={u.id} className="border-border/20 hover:bg-muted/20" data-testid={`user-row-${u.id}`}>
                  <TableCell className="font-medium">{u.first_name} {u.last_name}</TableCell>
                  <TableCell className="font-mono text-sm">{u.email}</TableCell>
                  <TableCell>
                    <Badge className={`${ROLE_BADGES[u.role] || ''} border text-xs`}>
                      {ROLE_LABELS[language]?.[u.role] || u.role}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {u.role === 'admin' ? (
                      <span className="text-xs text-muted-foreground">{t('Tum Oteller', 'All Hotels')}</span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {(u.hotel_ids || []).map(hid => (
                          <Badge key={hid} variant="outline" className="text-xs">{getHotelName(hid)}</Badge>
                        ))}
                        {(!u.hotel_ids || u.hotel_ids.length === 0) && <span className="text-xs text-muted-foreground">-</span>}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge className={`border text-xs ${u.is_active ? 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30' : 'bg-rose-500/15 text-rose-200 border-rose-500/30'}`}>
                      {u.is_active ? t('Aktif', 'Active') : t('Pasif', 'Inactive')}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </ScrollArea>
      </Card>

      {/* Create User Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle>{t('Kullanici Ekle', 'Add User')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>{t('Ad', 'First Name')} *</Label>
                <Input value={form.first_name} onChange={e => setForm(p => ({...p, first_name: e.target.value}))} className="mt-1" data-testid="user-firstname-input" />
              </div>
              <div>
                <Label>{t('Soyad', 'Last Name')} *</Label>
                <Input value={form.last_name} onChange={e => setForm(p => ({...p, last_name: e.target.value}))} className="mt-1" data-testid="user-lastname-input" />
              </div>
            </div>
            <div>
              <Label>{t('E-posta', 'Email')} *</Label>
              <Input type="email" value={form.email} onChange={e => setForm(p => ({...p, email: e.target.value}))} className="mt-1" data-testid="user-email-input" />
            </div>
            <div>
              <Label>{t('Sifre', 'Password')} *</Label>
              <Input type="password" value={form.password} onChange={e => setForm(p => ({...p, password: e.target.value}))} className="mt-1" data-testid="user-password-input" />
            </div>
            <div>
              <Label>{t('Rol', 'Role')} *</Label>
              <Select value={form.role} onValueChange={v => setForm(p => ({...p, role: v}))}>
                <SelectTrigger className="mt-1" data-testid="user-role-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">{t('Sistem Yoneticisi', 'Admin')}</SelectItem>
                  <SelectItem value="hotel_manager">{t('Otel Muduru', 'Hotel Manager')}</SelectItem>
                  <SelectItem value="front_desk">{t('Resepsiyon', 'Front Desk')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {form.role !== 'admin' && (
              <div>
                <Label>{t('Atanacak Otel', 'Assign Hotel')}</Label>
                <Select value={form.hotel_ids[0] || ''} onValueChange={v => setForm(p => ({...p, hotel_ids: v ? [v] : []}))}>
                  <SelectTrigger className="mt-1" data-testid="user-hotel-select">
                    <SelectValue placeholder={t('Otel secin', 'Select hotel')} />
                  </SelectTrigger>
                  <SelectContent>
                    {hotels.map(h => (
                      <SelectItem key={h.id} value={h.id}>{h.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>{t('Iptal', 'Cancel')}</Button>
            <Button onClick={handleCreate} disabled={creating} data-testid="user-create-submit-button">
              {creating ? <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
              {t('Olustur', 'Create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
