import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';
import { getHotel, updateHotelOnboarding, updateKbsConfig, testHotelIntegration } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';
import {
  Building2, MapPin, Shield, Radio, Server, Key,
  CheckCircle2, XCircle, ArrowLeft, ArrowRight, Loader2,
  Globe, ExternalLink, RefreshCw, Lock, Network
} from 'lucide-react';

const STEPS = [
  { key: 'profile', icon: Building2 },
  { key: 'region', icon: Shield },
  { key: 'integration', icon: Radio },
  { key: 'network', icon: Network },
  { key: 'credentials', icon: Key },
  { key: 'test', icon: Server },
];

export default function HotelOnboardingPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { language } = useLanguage();
  const t = (tr, en) => language === 'tr' ? tr : en;

  const [hotel, setHotel] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [currentStep, setCurrentStep] = useState(0);

  const [form, setForm] = useState({
    authority_region: '',
    integration_type: '',
    district: '',
    authorized_contact_name: '',
    authorized_contact_phone: '',
    authorized_contact_email: '',
    static_ip: '',
    kbs_institution_code: '',
    // Credential vault fields
    kbs_username: '',
    facility_code: '',
    service_username: '',
    secret: '',
    endpoint_url: '',
    environment: 'test',
    auth_method: 'username_password',
  });

  useEffect(() => {
    if (id) {
      getHotel(id).then(h => {
        setHotel(h);
        setForm(prev => ({
          ...prev,
          authority_region: h.authority_region || '',
          integration_type: h.integration_type || '',
          district: h.district || '',
          authorized_contact_name: h.authorized_contact_name || '',
          authorized_contact_phone: h.authorized_contact_phone || '',
          authorized_contact_email: h.authorized_contact_email || '',
          static_ip: h.static_ip || '',
          kbs_institution_code: h.kbs_institution_code || '',
        }));
        setCurrentStep(h.onboarding_step || 0);
        setLoading(false);
      }).catch(() => {
        toast.error('Hotel not found');
        navigate('/hotels');
      });
    }
  }, [id, navigate]);

  const handleChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  const handleSaveStep = async () => {
    setSaving(true);
    try {
      // Save hotel onboarding data
      await updateHotelOnboarding(id, {
        authority_region: form.authority_region || undefined,
        integration_type: form.integration_type || undefined,
        district: form.district || undefined,
        authorized_contact_name: form.authorized_contact_name || undefined,
        authorized_contact_phone: form.authorized_contact_phone || undefined,
        authorized_contact_email: form.authorized_contact_email || undefined,
        static_ip: form.static_ip || undefined,
        kbs_institution_code: form.kbs_institution_code || undefined,
        onboarding_step: currentStep,
        onboarding_status: currentStep >= 4 ? 'credentials_pending' : 'in_progress',
      });

      // If on credentials step, also save KBS config
      if (currentStep === 4 && (form.kbs_username || form.facility_code || form.endpoint_url)) {
        await updateKbsConfig(id, {
          kbs_username: form.kbs_username || undefined,
          facility_code: form.facility_code || undefined,
          service_username: form.service_username || undefined,
          secret: form.secret || undefined,
          endpoint_url: form.endpoint_url || undefined,
          environment: form.environment,
          auth_method: form.auth_method,
        });
      }

      toast.success(t('Adim kaydedildi', 'Step saved'));
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleNext = async () => {
    await handleSaveStep();
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(prev => prev + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) setCurrentStep(prev => prev - 1);
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testHotelIntegration(id);
      setTestResult(result);
      if (result.success) {
        toast.success(t('Baglanti basarili!', 'Connection successful!'));
      } else {
        toast.error(t('Baglanti basarisiz', 'Connection failed'));
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message);
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl" data-testid="hotel-onboarding-page">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/hotels')} data-testid="onboarding-back-button">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {t('KBS Entegrasyon Kurulumu', 'KBS Integration Setup')}
          </h1>
          <p className="text-muted-foreground text-sm">{hotel?.name} - {hotel?.city}</p>
        </div>
      </div>

      {/* Steps Indicator */}
      <div className="flex items-center gap-2">
        {STEPS.map((step, i) => {
          const StepIcon = step.icon;
          const isActive = i === currentStep;
          const isComplete = i < currentStep;
          return (
            <React.Fragment key={step.key}>
              <button
                onClick={() => setCurrentStep(i)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-primary/10 text-primary border border-primary/20'
                    : isComplete
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
                }`}
                data-testid={`onboarding-step-${step.key}`}
              >
                <StepIcon className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{i + 1}</span>
              </button>
              {i < STEPS.length - 1 && (
                <div className={`h-px flex-1 ${isComplete ? 'bg-emerald-500/40' : 'bg-border/40'}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Step Content */}
      <Card className="bg-card/60 border-border/50">
        <CardContent className="pt-6">
          {/* Step 0: Profile */}
          {currentStep === 0 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-medium mb-1">{t('Otel Profili', 'Hotel Profile')}</h3>
                <p className="text-sm text-muted-foreground">{t('Otel ve yetkili kisi bilgileri', 'Hotel and authorized contact info')}</p>
              </div>
              <Separator />
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label>{t('Otel Adi', 'Hotel Name')}</Label>
                  <Input value={hotel?.name || ''} disabled className="mt-1 bg-muted/20" />
                </div>
                <div>
                  <Label>{t('Vergi No', 'Tax Number')}</Label>
                  <Input value={hotel?.tax_number || ''} disabled className="mt-1 bg-muted/20 font-mono" />
                </div>
                <div>
                  <Label>{t('Sehir', 'City')}</Label>
                  <Input value={hotel?.city || ''} disabled className="mt-1 bg-muted/20" />
                </div>
                <div>
                  <Label>{t('Ilce', 'District')}</Label>
                  <Input value={form.district} onChange={e => handleChange('district', e.target.value)} className="mt-1" placeholder={t('Beyoglu', 'Beyoglu')} data-testid="onboarding-district-input" />
                </div>
              </div>
              <Separator />
              <h4 className="text-sm font-medium">{t('Yetkili Kisi', 'Authorized Contact')}</h4>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label>{t('Ad Soyad', 'Full Name')}</Label>
                  <Input value={form.authorized_contact_name} onChange={e => handleChange('authorized_contact_name', e.target.value)} className="mt-1" data-testid="onboarding-contact-name-input" />
                </div>
                <div>
                  <Label>{t('Telefon', 'Phone')}</Label>
                  <Input value={form.authorized_contact_phone} onChange={e => handleChange('authorized_contact_phone', e.target.value)} className="mt-1" placeholder="+905551234567" data-testid="onboarding-contact-phone-input" />
                </div>
                <div className="md:col-span-2">
                  <Label>{t('E-posta', 'Email')}</Label>
                  <Input value={form.authorized_contact_email} onChange={e => handleChange('authorized_contact_email', e.target.value)} className="mt-1" type="email" data-testid="onboarding-contact-email-input" />
                </div>
              </div>
            </div>
          )}

          {/* Step 1: Authority Region */}
          {currentStep === 1 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-medium mb-1">{t('Yetki Bolgesi', 'Authority Region')}</h3>
                <p className="text-sm text-muted-foreground">{t('Otelinizin bagli oldugu guvenlik bolgesi', 'Security authority region for your hotel')}</p>
              </div>
              <Separator />
              <div className="grid gap-4 md:grid-cols-2">
                {[
                  { value: 'egm', title: t('Emniyet Genel Mudurlugu', 'General Directorate of Security'), desc: t('Sehir icindeki oteller - EGM KBS', 'City hotels - Police KBS') },
                  { value: 'jandarma', title: t('Jandarma Genel Komutanligi', 'Gendarmerie General Command'), desc: t('Kirsal/ilce oteller - Jandarma KBS', 'Rural/district hotels - Gendarmerie KBS') },
                ].map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => handleChange('authority_region', opt.value)}
                    className={`text-left rounded-xl border p-5 transition-all ${
                      form.authority_region === opt.value
                        ? 'border-primary/50 bg-primary/5'
                        : 'border-border/40 bg-muted/10 hover:border-border hover:bg-muted/20'
                    }`}
                    data-testid={`onboarding-region-${opt.value}`}
                  >
                    <Shield className={`h-6 w-6 mb-3 ${form.authority_region === opt.value ? 'text-primary' : 'text-muted-foreground'}`} />
                    <h4 className="font-medium mb-1">{opt.title}</h4>
                    <p className="text-xs text-muted-foreground">{opt.desc}</p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 2: Integration Type */}
          {currentStep === 2 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-medium mb-1">{t('Entegrasyon Tipi', 'Integration Type')}</h3>
                <p className="text-sm text-muted-foreground">{t('KBS entegrasyon yontemi', 'KBS integration method')}</p>
              </div>
              <Separator />
              <div className="grid gap-4 md:grid-cols-2">
                {[
                  { value: 'egm_kbs', title: 'EGM KBS', desc: t('Emniyet KBS web servisi entegrasyonu', 'Police KBS web service integration'), disabled: form.authority_region === 'jandarma' },
                  { value: 'jandarma_kbs', title: t('Jandarma KBS', 'Gendarmerie KBS'), desc: t('Jandarma KBS / e-Devlet entegrasyonu', 'Gendarmerie KBS / e-Government integration'), disabled: form.authority_region === 'egm' },
                ].map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => !opt.disabled && handleChange('integration_type', opt.value)}
                    className={`text-left rounded-xl border p-5 transition-all ${
                      opt.disabled ? 'opacity-40 cursor-not-allowed border-border/20' :
                      form.integration_type === opt.value
                        ? 'border-primary/50 bg-primary/5'
                        : 'border-border/40 bg-muted/10 hover:border-border hover:bg-muted/20'
                    }`}
                    disabled={opt.disabled}
                    data-testid={`onboarding-type-${opt.value}`}
                  >
                    <Radio className={`h-6 w-6 mb-3 ${form.integration_type === opt.value ? 'text-primary' : 'text-muted-foreground'}`} />
                    <h4 className="font-medium mb-1">{opt.title}</h4>
                    <p className="text-xs text-muted-foreground">{opt.desc}</p>
                  </button>
                ))}
              </div>
              <div>
                <Label>{t('KBS Kurum Kodu', 'KBS Institution Code')}</Label>
                <Input value={form.kbs_institution_code} onChange={e => handleChange('kbs_institution_code', e.target.value)} className="mt-1 font-mono" placeholder="IST-2024-0001" data-testid="onboarding-kbs-code-input" />
              </div>
            </div>
          )}

          {/* Step 3: Network */}
          {currentStep === 3 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-medium mb-1">{t('Ag Gereksinimleri', 'Network Requirements')}</h3>
                <p className="text-sm text-muted-foreground">{t('Sabit IP ve ag yapilandirmasi', 'Static IP and network configuration')}</p>
              </div>
              <Separator />
              <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4">
                <p className="text-sm text-amber-200">
                  {t(
                    'KBS erisimi icin sabit IP adresi gereklidir. IP adresinizi resmi basvuru sirasinda bildirmeniz gerekmektedir.',
                    'A static IP address is required for KBS access. You must declare your IP during the official application process.'
                  )}
                </p>
              </div>
              <div>
                <Label>{t('Sabit IP Adresi', 'Static IP Address')}</Label>
                <Input value={form.static_ip} onChange={e => handleChange('static_ip', e.target.value)} className="mt-1 font-mono" placeholder="203.0.113.10" data-testid="onboarding-ip-input" />
              </div>
            </div>
          )}

          {/* Step 4: Credentials */}
          {currentStep === 4 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-medium mb-1">{t('Erisim Bilgileri', 'Access Credentials')}</h3>
                <p className="text-sm text-muted-foreground">{t('Resmi makamlardan alinan servis erisim bilgileri', 'Service access credentials obtained from official authorities')}</p>
              </div>
              <Separator />
              <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 flex items-start gap-3">
                <Lock className="h-5 w-5 text-primary mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium">{t('Guvenlik Notu', 'Security Note')}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {t(
                      'Burada saklanan bilgiler sifrelenerek korunur. e-Devlet sifrenizi buraya GİRMEYİN. Sadece resmi makamlardan size verilen servis erisim bilgilerini girin.',
                      'Credentials stored here are encrypted. Do NOT enter your e-Government password. Only enter service credentials issued by official authorities.'
                    )}
                  </p>
                </div>
              </div>
              <div>
                <Label>{t('Kimlik Dogrulama Yontemi', 'Authentication Method')}</Label>
                <Select value={form.auth_method} onValueChange={v => handleChange('auth_method', v)}>
                  <SelectTrigger className="mt-1" data-testid="onboarding-auth-method-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="username_password">{t('Kullanici Adi / Parola', 'Username / Password')}</SelectItem>
                    <SelectItem value="certificate">{t('Sertifika', 'Certificate')}</SelectItem>
                    <SelectItem value="api_token">{t('API Token', 'API Token')}</SelectItem>
                    <SelectItem value="web_service">{t('Web Servis', 'Web Service')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label>{t('KBS Kullanici Adi', 'KBS Username')}</Label>
                  <Input value={form.kbs_username} onChange={e => handleChange('kbs_username', e.target.value)} className="mt-1 font-mono" data-testid="onboarding-kbs-username-input" />
                </div>
                <div>
                  <Label>{t('Tesis Kodu', 'Facility Code')}</Label>
                  <Input value={form.facility_code} onChange={e => handleChange('facility_code', e.target.value)} className="mt-1 font-mono" data-testid="onboarding-facility-code-input" />
                </div>
                <div>
                  <Label>{t('Servis Kullanici Adi', 'Service Username')}</Label>
                  <Input value={form.service_username} onChange={e => handleChange('service_username', e.target.value)} className="mt-1 font-mono" data-testid="onboarding-service-username-input" />
                </div>
                <div>
                  <Label>{t('Parola / Token', 'Password / Token')}</Label>
                  <Input type="password" value={form.secret} onChange={e => handleChange('secret', e.target.value)} className="mt-1 font-mono" placeholder="********" data-testid="onboarding-secret-input" />
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label>{t('Endpoint URL', 'Endpoint URL')}</Label>
                  <Input value={form.endpoint_url} onChange={e => handleChange('endpoint_url', e.target.value)} className="mt-1 font-mono text-xs" placeholder="https://kbs.egm.gov.tr/ws/submit.asmx" data-testid="onboarding-endpoint-input" />
                </div>
                <div>
                  <Label>{t('Ortam', 'Environment')}</Label>
                  <Select value={form.environment} onValueChange={v => handleChange('environment', v)}>
                    <SelectTrigger className="mt-1" data-testid="onboarding-environment-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="test">{t('Test Ortami', 'Test Environment')}</SelectItem>
                      <SelectItem value="production">{t('Canli Ortam', 'Production')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          )}

          {/* Step 5: Test & Official Redirects */}
          {currentStep === 5 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-medium mb-1">{t('Baglanti Testi & Resmi Erisim', 'Connection Test & Official Access')}</h3>
                <p className="text-sm text-muted-foreground">{t('Entegrasyonu test edin ve resmi portallara erisin', 'Test integration and access official portals')}</p>
              </div>
              <Separator />

              {/* Connection Test */}
              <Card className="bg-muted/20 border-border/40">
                <CardContent className="pt-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium">{t('Baglanti Testi', 'Connection Test')}</h4>
                      <p className="text-xs text-muted-foreground">{t('KBS servisine baglanti kontrolu', 'Check connectivity to KBS service')}</p>
                    </div>
                    <Button onClick={handleTestConnection} disabled={testing} data-testid="onboarding-test-connection-button">
                      {testing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Server className="h-4 w-4 mr-2" />}
                      {t('Testi Calistir', 'Run Test')}
                    </Button>
                  </div>
                  {testResult && (
                    <div className={`rounded-lg p-4 border ${
                      testResult.success
                        ? 'bg-emerald-500/10 border-emerald-500/20'
                        : 'bg-rose-500/10 border-rose-500/20'
                    }`}>
                      <div className="flex items-center gap-2 mb-2">
                        {testResult.success ? <CheckCircle2 className="h-5 w-5 text-emerald-400" /> : <XCircle className="h-5 w-5 text-rose-400" />}
                        <span className="font-medium text-sm">{testResult.message}</span>
                      </div>
                      {testResult.details && (
                        <div className="grid gap-1 text-xs mt-2">
                          {Object.entries(testResult.details).map(([k, v]) => v !== null && (
                            <div key={k} className="flex justify-between">
                              <span className="text-muted-foreground">{k}</span>
                              <span className="font-mono">{String(v)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Official Redirects */}
              <Card className="bg-muted/20 border-border/40">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">{t('Resmi Portal Erisimleri', 'Official Portal Access')}</CardTitle>
                  <CardDescription>{t('Yetki almak veya bilgi girisi icin resmi portallara yonlendirme', 'Redirect to official portals for authorization or info entry')}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <a
                    href="https://kbs.egm.gov.tr"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between rounded-lg border border-border/40 bg-background/50 p-4 hover:bg-muted/20 transition-colors"
                    data-testid="onboarding-redirect-egm"
                  >
                    <div className="flex items-center gap-3">
                      <Shield className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium text-sm">{t('EGM KBS Giris Sayfasi', 'EGM KBS Login Page')}</p>
                        <p className="text-xs text-muted-foreground">kbs.egm.gov.tr</p>
                      </div>
                    </div>
                    <ExternalLink className="h-4 w-4 text-muted-foreground" />
                  </a>
                  <a
                    href="https://www.turkiye.gov.tr/jandarma-kimlik-bildirim-sistemi"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between rounded-lg border border-border/40 bg-background/50 p-4 hover:bg-muted/20 transition-colors"
                    data-testid="onboarding-redirect-jandarma"
                  >
                    <div className="flex items-center gap-3">
                      <Globe className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium text-sm">{t('Jandarma KBS / e-Devlet', 'Gendarmerie KBS / e-Government')}</p>
                        <p className="text-xs text-muted-foreground">turkiye.gov.tr</p>
                      </div>
                    </div>
                    <ExternalLink className="h-4 w-4 text-muted-foreground" />
                  </a>
                  <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
                    <p className="text-xs text-amber-200">
                      {t(
                        'Resmi portalda yetki islemlerinizi tamamladiktan sonra size verilen servis erisim bilgilerini bir onceki adimda (Erisim Bilgileri) girin.',
                        'After completing authorization on the official portal, enter the service credentials provided to you in the previous step (Access Credentials).'
                      )}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <Button variant="outline" onClick={handleBack} disabled={currentStep === 0} data-testid="onboarding-back-step-button">
          <ArrowLeft className="h-4 w-4 mr-2" /> {t('Geri', 'Back')}
        </Button>
        <div className="flex gap-2">
          {currentStep < STEPS.length - 1 ? (
            <Button onClick={handleNext} disabled={saving} data-testid="onboarding-next-step-button">
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              {t('Kaydet ve Devam Et', 'Save & Continue')} <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          ) : (
            <Button onClick={handleSaveStep} disabled={saving} data-testid="onboarding-finish-button">
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CheckCircle2 className="h-4 w-4 mr-2" />}
              {t('Kurulumu Tamamla', 'Complete Setup')}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
