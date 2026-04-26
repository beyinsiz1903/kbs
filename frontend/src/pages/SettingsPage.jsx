import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getSettings, saveSettings, errorMessage } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Save, LogOut, Shield, Database, Bell } from 'lucide-react';
import { Switch } from '../components/ui/switch';
import { getAlertSoundEnabled, setAlertSoundEnabled } from '../lib/operatorPrefs';

export default function SettingsPage() {
  const { logout, refreshKbsStatus } = useAuth();
  const navigate = useNavigate();
  const [pmsUrl, setPmsUrl] = useState('');
  const [tesisKodu, setTesisKodu] = useState('');
  const [kullaniciAdi, setKullaniciAdi] = useState('');
  const [sifre, setSifre] = useState('');
  const [servisUrl, setServisUrl] = useState('');
  const [kbsKurum, setKbsKurum] = useState('');
  const [kbsConfigured, setKbsConfigured] = useState(false);
  const [saving, setSaving] = useState(false);
  // Task #13: operatör tercihleri (frontend-only, localStorage'da kalıcı).
  const [alertSoundEnabled, setAlertSoundEnabledState] = useState(() => getAlertSoundEnabled());

  const handleAlertSoundChange = (value) => {
    setAlertSoundEnabledState(value);
    setAlertSoundEnabled(value);
    toast.success(value ? 'Sesli uyarı açıldı' : 'Sesli uyarı kapatıldı');
  };

  useEffect(() => {
    getSettings()
      .then((s) => {
        setPmsUrl(s.pms_url || '');
        setKbsConfigured(!!s.kbs_configured);
        setKbsKurum(s.kbs_kurum || '');
      })
      .catch((err) => toast.error(errorMessage(err)));
  }, []);

  const handleSave = async () => {
    if (!pmsUrl) {
      toast.error('PMS adresi zorunludur');
      return;
    }
    setSaving(true);
    try {
      await saveSettings({
        pms_url: pmsUrl.trim(),
        kbs_tesis_kodu: tesisKodu.trim(),
        kbs_kullanici_adi: kullaniciAdi.trim(),
        // Bos birakilirsa backend mevcut sifreyi korur (null = preserve)
        kbs_sifre: sifre ? sifre : null,
        kbs_servis_url: servisUrl.trim(),
        kbs_kurum: kbsKurum,
      });
      toast.success('Ayarlar kaydedildi');
      await refreshKbsStatus();
      const s = await getSettings();
      setKbsConfigured(!!s.kbs_configured);
      // Şifre kutusunu temizle - artık session'da
      setSifre('');
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="max-w-3xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Ayarlar</h1>
        <p className="text-xs text-muted-foreground">PMS bağlantısı ve KBS web servisi bilgileri</p>
      </div>

      <Card className="bg-card/40 border-border/50">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-primary" />
            <CardTitle className="text-base">Syroce PMS</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Otelinizin PMS sisteminin adresi. Misafir verileri buradan çekilir.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="pms_url">PMS URL</Label>
            <Input
              id="pms_url"
              type="url"
              placeholder="https://pms.otelinizinadi.com"
              value={pmsUrl}
              onChange={(e) => setPmsUrl(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card/40 border-border/50">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-primary" />
            <CardTitle className="text-base">
              KBS (Emniyet/Jandarma) Web Servisi
              {kbsConfigured && (
                <span className="ml-2 text-xs font-normal text-emerald-400">● yapılandırılmış</span>
              )}
            </CardTitle>
          </div>
          <CardDescription className="text-xs">
            EGM'nin oteliniz için sağladığı KBS bağlantı bilgileri. Şifreli olarak yerel olarak saklanır.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="tesis">Tesis Kodu</Label>
              <Input
                id="tesis"
                placeholder="123456"
                value={tesisKodu}
                onChange={(e) => setTesisKodu(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="kullanici">KBS Kullanıcı Adı</Label>
              <Input
                id="kullanici"
                value={kullaniciAdi}
                onChange={(e) => setKullaniciAdi(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="sifre">KBS Şifresi {kbsConfigured && <span className="text-[10px] text-muted-foreground">(değiştirmek için yeniden girin)</span>}</Label>
            <Input
              id="sifre"
              type="password"
              placeholder={kbsConfigured ? '•••••••• (değiştirmezseniz mevcut şifre korunur)' : ''}
              value={sifre}
              onChange={(e) => setSifre(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="servis">Servis URL</Label>
            <Input
              id="servis"
              type="url"
              placeholder="https://kbs.gov.tr/..."
              value={servisUrl}
              onChange={(e) => setServisUrl(e.target.value)}
            />
            <p className="text-[10px] text-muted-foreground">
              EGM/Jandarma KBS web servisinin SOAP/XML endpoint URL'si.
            </p>
          </div>
          <div className="space-y-2">
            <Label>Kurum</Label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="radio"
                  name="kbs_kurum"
                  value="polis"
                  checked={kbsKurum === 'polis'}
                  onChange={(e) => setKbsKurum(e.target.value)}
                  data-testid="radio-kbs-polis"
                  className="accent-primary"
                />
                Polis (EGM KBS)
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="radio"
                  name="kbs_kurum"
                  value="jandarma"
                  checked={kbsKurum === 'jandarma'}
                  onChange={(e) => setKbsKurum(e.target.value)}
                  data-testid="radio-kbs-jandarma"
                  className="accent-primary"
                />
                Jandarma (JKBS)
              </label>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Otelinizin bağlı olduğu kuruma göre seçin. Yanlış seçim raporun reddedilmesine yol açar.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card/40 border-border/50">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Bell className="h-4 w-4 text-primary" />
            <CardTitle className="text-base">Bildirim Tercihleri</CardTitle>
          </div>
          <CardDescription className="text-xs">
            Bu bilgisayara özel arayüz tercihleri. Hesabınıza değil, bu tarayıcıya kayıtlıdır.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <Label htmlFor="alert-sound" className="text-sm">Sesli uyarı</Label>
              <p className="text-[11px] text-muted-foreground max-w-md">
                PMS push bağlantısı koptuğunda kısa bir bip sesi çalar. Kapatırsanız
                yalnızca ekran uyarısı (toast) ve sekme başlığı değişimi kalır.
              </p>
            </div>
            <Switch
              id="alert-sound"
              checked={alertSoundEnabled}
              onCheckedChange={handleAlertSoundChange}
              data-testid="switch-alert-sound"
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Button variant="outline" onClick={handleLogout} className="gap-2 border-rose-500/40 text-rose-400 hover:bg-rose-500/10">
          <LogOut className="h-4 w-4" />
          Çıkış Yap
        </Button>
        <Button onClick={handleSave} disabled={saving} className="gap-2" data-testid="btn-save-settings">
          <Save className="h-4 w-4" />
          {saving ? 'Kaydediliyor…' : 'Kaydet'}
        </Button>
      </div>
    </div>
  );
}
