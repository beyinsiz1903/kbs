import React, { useState, useEffect } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { getDeploymentGuide } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { ScrollArea } from '../components/ui/scroll-area';
import {
  Server, Download, Wifi, Lock, Layers, Settings,
  Loader2, Cloud, Monitor, Building2, ChevronRight,
  Copy, CheckCircle2
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';

const SECTION_ICONS = {
  architecture: Cloud,
  agent_installation: Download,
  network_requirements: Wifi,
  credential_vault: Lock,
  environment_separation: Layers,
  per_hotel_config: Settings,
};

export default function DeploymentGuidePage() {
  const { language } = useLanguage();
  const t = (tr, en) => language === 'tr' ? tr : en;
  const [guide, setGuide] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const data = await getDeploymentGuide();
        setGuide(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success(t('Kopyalandi!', 'Copied!'));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!guide) return null;

  return (
    <div className="space-y-6 max-w-5xl" data-testid="deployment-guide-page">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">{t('Dagitim Rehberi', 'Deployment Guide')}</h1>
        <p className="text-muted-foreground mt-1">{t('Sistem mimarisi ve kurulum dokumantasyonu', 'System architecture and installation documentation')}</p>
      </div>

      {/* Architecture */}
      <Card className="bg-card/60 border-border/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Cloud className="h-4 w-4" />
            {language === 'tr' ? guide.architecture.title_tr : guide.architecture.title_en}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            {guide.architecture.components.map((comp, idx) => {
              const icons = [Cloud, Monitor, Building2];
              const Icon = icons[idx] || Server;
              return (
                <div key={idx} className="rounded-lg border border-border/30 bg-muted/10 p-4 space-y-3" data-testid={`arch-component-${idx}`}>
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 border border-primary/20">
                      <Icon className="h-4 w-4 text-primary" />
                    </div>
                    <span className="text-sm font-semibold">{comp.name}</span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {language === 'tr' ? comp.description_tr : comp.description_en}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="outline" className="text-[10px]">{comp.deployment}</Badge>
                    <Badge variant="outline" className="text-[10px] border-primary/30 text-primary">{comp.tech}</Badge>
                  </div>
                </div>
              );
            })}
          </div>
          {/* Architecture Flow */}
          <div className="mt-4 flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <Badge className="bg-primary/10 text-primary border-primary/20 border">Cloud Panel</Badge>
            <ChevronRight className="h-3 w-3" />
            <Badge className="bg-cyan-500/10 text-cyan-300 border-cyan-500/20 border">Bridge Agent</Badge>
            <ChevronRight className="h-3 w-3" />
            <Badge className="bg-amber-500/10 text-amber-300 border-amber-500/20 border">KBS SOAP</Badge>
          </div>
        </CardContent>
      </Card>

      {/* Agent Installation */}
      <Card className="bg-card/60 border-border/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Download className="h-4 w-4" />
            {language === 'tr' ? guide.agent_installation.title_tr : guide.agent_installation.title_en}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            {guide.agent_installation.steps.map((step) => (
              <div key={step.step} className="flex items-start gap-3 py-2">
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 border border-primary/20 text-xs font-semibold text-primary shrink-0 mt-0.5">
                  {step.step}
                </div>
                <p className="text-sm">{language === 'tr' ? step.tr : step.en}</p>
              </div>
            ))}
          </div>
          <Separator className="bg-border/20" />
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground font-medium">{t('Ornek Yapilandirma Dosyasi', 'Example Configuration File')}</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={() => copyToClipboard(JSON.stringify(guide.agent_installation.config_template, null, 2))}
                data-testid="copy-config-button"
              >
                <Copy className="h-3 w-3 mr-1" /> {t('Kopyala', 'Copy')}
              </Button>
            </div>
            <pre className="rounded-lg bg-muted/30 border border-border/30 p-4 text-xs font-mono overflow-x-auto">
              {JSON.stringify(guide.agent_installation.config_template, null, 2)}
            </pre>
          </div>
        </CardContent>
      </Card>

      {/* Network Requirements */}
      <Card className="bg-card/60 border-border/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Wifi className="h-4 w-4" />
            {language === 'tr' ? guide.network_requirements.title_tr : guide.network_requirements.title_en}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {guide.network_requirements.items.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm">
                <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                {language === 'tr' ? item.tr : item.en}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {/* Credential Vault + Env Separation side by side */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Credential Vault */}
        <Card className="bg-card/60 border-border/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Lock className="h-4 w-4" />
              {language === 'tr' ? guide.credential_vault.title_tr : guide.credential_vault.title_en}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {guide.credential_vault.items.map((item, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm">
                  <Lock className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
                  {language === 'tr' ? item.tr : item.en}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {/* Environment Separation */}
        <Card className="bg-card/60 border-border/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Layers className="h-4 w-4" />
              {language === 'tr' ? guide.environment_separation.title_tr : guide.environment_separation.title_en}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {guide.environment_separation.environments.map((env, idx) => (
              <div key={idx} className="rounded-lg border border-border/30 bg-muted/10 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="outline" className={`text-[10px] ${
                    env.name === 'Production' ? 'border-rose-500/30 text-rose-300' :
                    env.name === 'Staging' ? 'border-amber-500/30 text-amber-300' :
                    'border-emerald-500/30 text-emerald-300'
                  }`}>{env.name}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">{language === 'tr' ? env.tr : env.en}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Per-Hotel Config */}
      <Card className="bg-card/60 border-border/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Settings className="h-4 w-4" />
            {language === 'tr' ? guide.per_hotel_config.title_tr : guide.per_hotel_config.title_en}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {guide.per_hotel_config.items.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm">
                <Settings className="h-3.5 w-3.5 text-cyan-400 shrink-0 mt-0.5" />
                {language === 'tr' ? item.tr : item.en}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {/* Simulation Notice */}
      <Card className="border-amber-500/20 bg-amber-500/5">
        <CardContent className="py-4">
          <div className="flex items-start gap-3">
            <Badge className="bg-amber-500/15 text-amber-200 border-amber-500/30 border shrink-0">SIMÜLASYON</Badge>
            <p className="text-sm text-muted-foreground">
              {t(
                'Bu sistem su an simulasyon modundadir. KBS SOAP endpoint\'i ve Bridge Agent, gercek entegrasyonu taklit eden dahili simulatorler tarafindan saglanmaktadir. Canli gecis icin gercek EGM/Jandarma KBS endpointlerine baglanilmasi gerekecektir.',
                'This system is currently in simulation mode. The KBS SOAP endpoint and Bridge Agent are provided by internal simulators mimicking real integration. For go-live, connection to actual EGM/Jandarma KBS endpoints will be required.'
              )}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
