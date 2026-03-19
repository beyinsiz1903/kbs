import React, { useState, useEffect } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { getKBSSimulation, setKBSSimulation, resetKBSSimulation } from '../lib/api';
import { KBSModeBadge } from '../components/StatusBadge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import {
  Radio, RefreshCw, CheckCircle2, XCircle, Clock,
  AlertTriangle, Copy, Zap, RotateCw
} from 'lucide-react';

const KBS_MODES = [
  { value: 'normal', icon: CheckCircle2, color: 'text-emerald-400', desc_tr: 'KBS normal calisir, tum bildirimler basarili', desc_en: 'KBS operates normally, all submissions succeed' },
  { value: 'unavailable', icon: XCircle, color: 'text-rose-400', desc_tr: 'KBS sistemi kullanim disi (503)', desc_en: 'KBS system unavailable (503)' },
  { value: 'timeout', icon: Clock, color: 'text-amber-400', desc_tr: 'KBS baglanti zaman asimi', desc_en: 'KBS connection timeout' },
  { value: 'delayed_ack', icon: Clock, color: 'text-amber-400', desc_tr: 'KBS yanitlari gecikmelidir ama basarili', desc_en: 'KBS responses are delayed but successful' },
  { value: 'duplicate_reject', icon: Copy, color: 'text-fuchsia-400', desc_tr: 'KBS mukerrer bildirimleri reddeder', desc_en: 'KBS rejects duplicate submissions' },
  { value: 'validation_fail', icon: AlertTriangle, color: 'text-rose-400', desc_tr: 'KBS dogrulama hatalari dondurur', desc_en: 'KBS returns validation errors' },
  { value: 'random_errors', icon: Zap, color: 'text-amber-400', desc_tr: 'KBS rastgele hatalar uretir', desc_en: 'KBS produces random errors' },
];

export default function KBSControlPage() {
  const { t, language } = useLanguage();
  const [currentMode, setCurrentMode] = useState('normal');
  const [selectedMode, setSelectedMode] = useState('normal');
  const [errorRate, setErrorRate] = useState(0.3);
  const [delaySeconds, setDelaySeconds] = useState(3);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    getKBSSimulation().then(config => {
      setCurrentMode(config.mode || 'normal');
      setSelectedMode(config.mode || 'normal');
      setErrorRate(config.error_rate || 0.3);
      setDelaySeconds(config.delay_seconds || 3);
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleApply = async () => {
    setApplying(true);
    try {
      await setKBSSimulation({
        mode: selectedMode,
        error_rate: parseFloat(errorRate) || 0,
        delay_seconds: parseFloat(delaySeconds) || 0
      });
      setCurrentMode(selectedMode);
      toast.success(`KBS modu '${selectedMode}' olarak ayarlandi`);
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message);
    } finally {
      setApplying(false);
    }
  };

  const handleReset = async () => {
    try {
      await resetKBSSimulation();
      setCurrentMode('normal');
      setSelectedMode('normal');
      setErrorRate(0.3);
      setDelaySeconds(3);
      toast.success('KBS simulasyon sifirlandi / KBS simulation reset');
    } catch (err) {
      toast.error(err.message);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="kbs-control-page">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{t('kbs.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('kbs.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">{t('kbs.currentMode')}:</span>
          <KBSModeBadge mode={currentMode} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Mode Selection */}
        <div className="lg:col-span-2">
          <Card className="bg-card/60 border-border/50">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Radio className="h-4 w-4 text-primary" />
                KBS Simulasyon Modu
              </CardTitle>
              <CardDescription>Secilen moda gore KBS sistemi davranisini belirleyin</CardDescription>
            </CardHeader>
            <CardContent>
              <RadioGroup value={selectedMode} onValueChange={setSelectedMode} className="space-y-3">
                {KBS_MODES.map((mode) => (
                  <motion.div
                    key={mode.value}
                    whileHover={{ scale: 1.005 }}
                    className={`flex items-start gap-4 rounded-lg border p-4 cursor-pointer transition-all ${
                      selectedMode === mode.value
                        ? 'border-primary/40 bg-primary/5'
                        : 'border-border/30 hover:border-border/60 hover:bg-muted/10'
                    }`}
                    onClick={() => setSelectedMode(mode.value)}
                    data-testid={`kbs-mode-${mode.value}`}
                  >
                    <RadioGroupItem value={mode.value} id={mode.value} />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <mode.icon className={`h-4 w-4 ${mode.color}`} />
                        <label htmlFor={mode.value} className="text-sm font-medium cursor-pointer">
                          {t(`kbs.${mode.value === 'delayed_ack' ? 'delayedAck' : mode.value === 'duplicate_reject' ? 'duplicateReject' : mode.value === 'validation_fail' ? 'validationFail' : mode.value === 'random_errors' ? 'randomErrors' : mode.value}`)}
                        </label>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        {language === 'tr' ? mode.desc_tr : mode.desc_en}
                      </p>
                    </div>
                  </motion.div>
                ))}
              </RadioGroup>
            </CardContent>
          </Card>
        </div>

        {/* Settings & Actions */}
        <div className="space-y-4">
          {/* Extra Settings */}
          <Card className="bg-card/60 border-border/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Parametreler</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {(selectedMode === 'random_errors') && (
                <div>
                  <Label className="text-xs">{t('kbs.errorRate')} ({Math.round(errorRate * 100)}%)</Label>
                  <Input
                    type="range"
                    min="0" max="1" step="0.05"
                    value={errorRate}
                    onChange={e => setErrorRate(parseFloat(e.target.value))}
                    className="mt-1"
                    data-testid="kbs-error-rate-slider"
                  />
                </div>
              )}
              {(selectedMode === 'delayed_ack' || selectedMode === 'timeout') && (
                <div>
                  <Label className="text-xs">{t('kbs.delaySeconds')}</Label>
                  <Input
                    type="number"
                    min="1" max="30"
                    value={delaySeconds}
                    onChange={e => setDelaySeconds(e.target.value)}
                    className="mt-1 font-mono"
                    data-testid="kbs-delay-input"
                  />
                </div>
              )}
            </CardContent>
          </Card>

          {/* Action Buttons */}
          <Card className="bg-card/60 border-border/50">
            <CardContent className="pt-6 space-y-3">
              <Button
                className="w-full"
                onClick={handleApply}
                disabled={applying}
                data-testid="kbs-apply-button"
              >
                {applying ? (
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-4 w-4 mr-2" />
                )}
                {t('kbs.apply')}
              </Button>
              <Button
                variant="outline"
                className="w-full"
                onClick={handleReset}
                data-testid="kbs-reset-button"
              >
                <RotateCw className="h-4 w-4 mr-2" />
                {t('kbs.reset')}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
