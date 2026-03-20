import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';
import { getGoLiveChecklist } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Separator } from '../components/ui/separator';
import {
  ArrowLeft, RefreshCw, CheckCircle2, XCircle, Loader2,
  Settings, Wifi, Key, Activity, FlaskConical, Shield
} from 'lucide-react';

const CATEGORY_ICONS = {
  configuration: Settings,
  network: Wifi,
  credentials: Key,
  agent: Activity,
  testing: FlaskConical,
  compliance: Shield,
};

const CATEGORY_COLORS = {
  configuration: 'text-cyan-400',
  network: 'text-blue-400',
  credentials: 'text-amber-400',
  agent: 'text-emerald-400',
  testing: 'text-purple-400',
  compliance: 'text-teal-400',
};

export default function GoLiveChecklistPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { language } = useLanguage();
  const t = (tr, en) => language === 'tr' ? tr : en;

  const [checklist, setChecklist] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const data = await getGoLiveChecklist(id);
      setChecklist(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!checklist) return null;

  const { items, passed, total, ready, readiness_percentage, hotel_name } = checklist;

  // Group by category
  const grouped = {};
  for (const item of items) {
    const cat = item.category;
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(item);
  }

  return (
    <div className="space-y-6 max-w-4xl" data-testid="go-live-checklist-page">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/hotels')} data-testid="checklist-back-button">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-semibold tracking-tight">{t('Go-Live Kontrol Listesi', 'Go-Live Checklist')}</h1>
          <p className="text-muted-foreground text-sm">{hotel_name}</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => { setLoading(true); fetchData(); }} className="h-8" data-testid="checklist-refresh-button">
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
          {t('Yenile', 'Refresh')}
        </Button>
      </div>

      {/* Readiness Score */}
      <Card className={`border ${ready ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-amber-500/30 bg-amber-500/5'}`}>
        <CardContent className="py-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold">
                {ready
                  ? t('Canli Gecise Hazir', 'Ready for Go-Live')
                  : t('Hazirlik Tamamlanmadi', 'Preparation Incomplete')
                }
              </h2>
              <p className="text-sm text-muted-foreground">
                {passed} / {total} {t('kontrol gecti', 'checks passed')}
              </p>
            </div>
            <Badge className={`text-base px-4 py-1.5 border ${ready ? 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30' : 'bg-amber-500/15 text-amber-200 border-amber-500/30'}`} data-testid="checklist-readiness-badge">
              %{readiness_percentage}
            </Badge>
          </div>
          <Progress value={readiness_percentage} className="h-2" />
        </CardContent>
      </Card>

      {/* Checklist Items by Category */}
      {Object.entries(grouped).map(([category, categoryItems]) => {
        const Icon = CATEGORY_ICONS[category] || Settings;
        const colorClass = CATEGORY_COLORS[category] || 'text-muted-foreground';
        const catLabel = language === 'tr'
          ? { configuration: 'Yapilandirma', network: 'Ag', credentials: 'Kimlik Bilgileri', agent: 'Agent', testing: 'Test', compliance: 'Uyumluluk' }[category]
          : { configuration: 'Configuration', network: 'Network', credentials: 'Credentials', agent: 'Agent', testing: 'Testing', compliance: 'Compliance' }[category];

        return (
          <Card key={category} className="bg-card/60 border-border/50">
            <CardHeader className="pb-3">
              <CardTitle className={`text-sm font-medium flex items-center gap-2 ${colorClass}`}>
                <Icon className="h-4 w-4" /> {catLabel}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              {categoryItems.map((item) => (
                <div key={item.key} className="flex items-center gap-3 py-2.5 px-2 rounded-lg hover:bg-muted/20 transition-colors" data-testid={`checklist-item-${item.key}`}>
                  {item.passed ? (
                    <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
                  ) : (
                    <XCircle className="h-5 w-5 text-rose-400 shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm">{language === 'tr' ? item.label_tr : item.label_en}</p>
                    <p className="text-xs text-muted-foreground truncate">{item.detail}</p>
                  </div>
                  <Badge variant="outline" className={`text-[10px] shrink-0 ${item.passed ? 'border-emerald-500/30 text-emerald-300' : 'border-rose-500/30 text-rose-300'}`}>
                    {item.passed ? t('Gecti', 'Passed') : t('Eksik', 'Missing')}
                  </Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        );
      })}

      {/* Actions */}
      <div className="flex gap-3">
        <Button variant="outline" onClick={() => navigate(`/hotels/${id}/onboarding`)} data-testid="checklist-go-onboarding-button">
          {t('Entegrasyon Ayarlari', 'Integration Settings')}
        </Button>
        <Button variant="outline" onClick={() => navigate(`/hotels/${id}/health`)} data-testid="checklist-go-health-button">
          {t('Saglik Paneli', 'Health Panel')}
        </Button>
      </div>
    </div>
  );
}
