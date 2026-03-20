import React, { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { useAuth } from '../contexts/AuthContext';
import { getComplianceStatus, getHotels, requestDataExport, requestDataDeletion, confirmDataDeletion } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { KpiCard } from '../components/KpiCard';
import { toast } from 'sonner';
import {
  Shield, Database, Eye, Clock, FileDown, Trash2, Lock,
  CheckCircle2, AlertTriangle, Loader2, RefreshCw, Users
} from 'lucide-react';

export default function CompliancePage() {
  const { language } = useLanguage();
  const { user } = useAuth();
  const t = (tr, en) => language === 'tr' ? tr : en;

  const [compliance, setCompliance] = useState(null);
  const [hotels, setHotels] = useState([]);
  const [selectedHotel, setSelectedHotel] = useState('');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [c, h] = await Promise.all([getComplianceStatus(), getHotels()]);
      setCompliance(c);
      setHotels(h);
      if (h.length > 0 && !selectedHotel) setSelectedHotel(h[0].id);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [selectedHotel]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleExport = async () => {
    if (!selectedHotel) return;
    setActionLoading('export');
    try {
      const result = await requestDataExport(selectedHotel);
      toast.success(t('Veri ihrac talebi olusturuldu', 'Data export request created'));
      // Download as JSON
      const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `kvkk_export_${selectedHotel}_${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(t('Ihrac basarisiz', 'Export failed'));
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeletionRequest = async () => {
    if (!selectedHotel) return;
    setActionLoading('delete');
    try {
      const result = await requestDataDeletion(selectedHotel);
      const count = result.data_to_delete;
      const msg = t(
        `Silinecek: ${count.guests} misafir, ${count.submissions} gonderim, ${count.checkins} check-in. Onaylamak icin tekrar tiklayin.`,
        `To delete: ${count.guests} guests, ${count.submissions} submissions, ${count.checkins} check-ins. Click again to confirm.`
      );
      toast.warning(msg, {
        action: {
          label: t('Onayla ve Sil', 'Confirm & Delete'),
          onClick: async () => {
            try {
              await confirmDataDeletion(selectedHotel);
              toast.success(t('Veriler silindi', 'Data deleted'));
              fetchData();
            } catch (e) {
              toast.error(t('Silme basarisiz', 'Deletion failed'));
            }
          }
        },
        duration: 15000,
      });
    } catch (err) {
      toast.error(t('Islem basarisiz', 'Operation failed'));
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!compliance) return null;

  const { data_inventory, access_log_summary, pii_field_inventory, retention_policy, compliance_checklist } = compliance;

  return (
    <div className="space-y-6" data-testid="compliance-page">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{t('KVKK Uyumluluk', 'KVKK Compliance')}</h1>
          <p className="text-muted-foreground mt-1">{t('Kisisel verilerin korunmasi ve veri yonetimi', 'Personal data protection and data governance')}</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => { setLoading(true); fetchData(); }} className="h-8 border-border/50" data-testid="compliance-refresh-button">
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
          {t('Yenile', 'Refresh')}
        </Button>
      </div>

      {/* Data Inventory KPIs */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard title={t('Misafir Kaydi', 'Guest Records')} value={data_inventory.total_guests} icon={Users} />
        <KpiCard title={t('PII Iceren Gonderim', 'Submissions with PII')} value={data_inventory.total_submissions_with_pii} icon={Database} />
        <KpiCard title={t('Denetim Olaylari', 'Audit Events')} value={data_inventory.total_audit_events} icon={Eye} />
        <KpiCard title={t('30 Gun+ Gonderim', '30d+ Submissions')} value={data_inventory.submissions_older_than_30d} icon={Clock} />
      </div>

      {/* Two Column Grid */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Compliance Checklist */}
        <Card className="bg-card/60 border-border/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Shield className="h-4 w-4" /> {t('Uyumluluk Kontrol Listesi', 'Compliance Checklist')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {compliance_checklist.map((item, idx) => (
              <div key={idx} className="flex items-center gap-3 py-2 px-2 rounded-lg hover:bg-muted/20 transition-colors" data-testid={`compliance-item-${idx}`}>
                {item.status === 'active' ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                ) : (
                  <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm">{item.item}</p>
                  <p className="text-[10px] text-muted-foreground truncate">{item.detail}</p>
                </div>
                <Badge variant="outline" className={`text-[10px] ${item.status === 'active' ? 'border-emerald-500/30 text-emerald-300' : 'border-amber-500/30 text-amber-300'}`}>
                  {item.status === 'active' ? t('Aktif', 'Active') : t('Hazir', 'Available')}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* PII Field Inventory */}
        <Card className="bg-card/60 border-border/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Lock className="h-4 w-4" /> {t('Hassas Alan Envanteri', 'Sensitive Field Inventory')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {pii_field_inventory.map((field, idx) => (
                <div key={idx} className="flex items-center gap-3 py-2 px-2 rounded-lg text-sm">
                  <code className="text-xs font-mono bg-muted/30 px-2 py-0.5 rounded">{field.field}</code>
                  <span className="text-xs text-muted-foreground">{field.collection}</span>
                  <span className="flex-1" />
                  <Badge variant="outline" className={`text-[10px] ${
                    field.classification.includes('Kritik') || field.classification.includes('Critical') ? 'border-rose-500/30 text-rose-300' :
                    field.classification.includes('Gizli') || field.classification.includes('Secret') ? 'border-purple-500/30 text-purple-300' :
                    'border-slate-500/30 text-slate-300'
                  }`}>
                    {field.classification}
                  </Badge>
                  {field.masked_in_ui && (
                    <Badge className="bg-emerald-500/15 text-emerald-200 border-emerald-500/30 border text-[10px]">
                      {t('Maskelenmis', 'Masked')}
                    </Badge>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Retention Policy */}
        <Card className="bg-card/60 border-border/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Clock className="h-4 w-4" /> {t('Saklama Politikasi', 'Retention Policy')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">{t('Misafir Verileri', 'Guest Data')}</span>
              <span className="font-mono">{retention_policy.guest_data_retention_days} {t('gun', 'days')}</span>
            </div>
            <Separator className="bg-border/20" />
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">{t('Gonderim Verileri', 'Submission Data')}</span>
              <span className="font-mono">{retention_policy.submission_data_retention_days} {t('gun', 'days')}</span>
            </div>
            <Separator className="bg-border/20" />
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">{t('Denetim Loglari', 'Audit Logs')}</span>
              <span className="font-mono">{retention_policy.audit_log_retention_days} {t('gun', 'days')}</span>
            </div>
            <Separator className="bg-border/20" />
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">{t('Kimlik Bilgileri', 'Credentials')}</span>
              <span className="text-xs">{retention_policy.credential_retention}</span>
            </div>
            <div className="mt-3 p-3 rounded-lg bg-muted/20 border border-border/30">
              <p className="text-xs text-muted-foreground italic">{retention_policy.policy_note}</p>
            </div>
          </CardContent>
        </Card>

        {/* Data Actions */}
        <Card className="bg-card/60 border-border/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Database className="h-4 w-4" /> {t('Veri Islemleri', 'Data Operations')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">{t('Otel Sec', 'Select Hotel')}</label>
              <Select value={selectedHotel} onValueChange={setSelectedHotel}>
                <SelectTrigger className="bg-muted/20" data-testid="compliance-hotel-select">
                  <SelectValue placeholder={t('Otel secin', 'Select hotel')} />
                </SelectTrigger>
                <SelectContent>
                  {hotels.map((h) => (
                    <SelectItem key={h.id} value={h.id}>{h.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Separator className="bg-border/20" />
            <div className="space-y-3">
              <Button
                variant="outline"
                className="w-full justify-start gap-2"
                onClick={handleExport}
                disabled={!selectedHotel || actionLoading === 'export'}
                data-testid="compliance-export-button"
              >
                <FileDown className="h-4 w-4" />
                {actionLoading === 'export' ? t('Ihrac ediliyor...', 'Exporting...') : t('Misafir Verilerini Ihrac Et (JSON)', 'Export Guest Data (JSON)')}
              </Button>
              <p className="text-[10px] text-muted-foreground px-1">
                KVKK Madde 11: {t('Ilgili kisi veri talep hakkina sahiptir', 'Data subject has right to request data')}
              </p>
            </div>
            {user?.role === 'admin' && (
              <>
                <Separator className="bg-border/20" />
                <div className="space-y-3">
                  <Button
                    variant="destructive"
                    className="w-full justify-start gap-2"
                    onClick={handleDeletionRequest}
                    disabled={!selectedHotel || actionLoading === 'delete'}
                    data-testid="compliance-delete-button"
                  >
                    <Trash2 className="h-4 w-4" />
                    {actionLoading === 'delete' ? t('Isleniyor...', 'Processing...') : t('Otel Verilerini Sil', 'Delete Hotel Data')}
                  </Button>
                  <p className="text-[10px] text-rose-400/70 px-1">
                    KVKK Madde 7: {t('Silme islemi geri donusumsuz. Denetim kayitlari korunur.', 'Deletion is irreversible. Audit records preserved.')}
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
