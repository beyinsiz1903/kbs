import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { getSettings, errorMessage } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
import { Radio, LogIn, Eye, EyeOff } from 'lucide-react';

export default function LoginPage() {
  const { login } = useAuth();
  const [pmsUrl, setPmsUrl] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getSettings()
      .then((s) => {
        if (s.pms_url) setPmsUrl(s.pms_url);
      })
      .catch(() => {});
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!pmsUrl || !email || !password) {
      toast.error('PMS adresi, e-posta ve şifre zorunludur');
      return;
    }
    setLoading(true);
    try {
      await login({
        pms_url: pmsUrl.trim(),
        email: email.trim(),
        password,
        remember_me: rememberMe,
      });
      toast.success('Giriş başarılı');
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4" data-testid="login-page">
      <Card className="w-full max-w-md border-border/50 bg-card/40 backdrop-blur-xl">
        <CardHeader className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 border border-primary/20">
              <Radio className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">KBS Bridge</CardTitle>
              <CardDescription className="text-xs">Konaklama Bildirim Sistemi</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="pms_url">Syroce PMS Adresi</Label>
              <Input
                id="pms_url"
                type="url"
                placeholder="https://pms.otelinizinadi.com"
                value={pmsUrl}
                onChange={(e) => setPmsUrl(e.target.value)}
                data-testid="input-pms-url"
              />
              <p className="text-[10px] text-muted-foreground">
                Otel yönetiminizin PMS adresi. Bir kere girince hatırlanır.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">PMS Kullanıcı E-postası</Label>
              <Input
                id="email"
                type="email"
                placeholder="resepsiyon@oteliniz.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                data-testid="input-email"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Şifre</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  data-testid="input-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="remember"
                checked={rememberMe}
                onCheckedChange={(v) => setRememberMe(!!v)}
              />
              <Label htmlFor="remember" className="text-xs cursor-pointer text-muted-foreground">
                Beni hatırla
              </Label>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full gap-2"
              data-testid="btn-login"
            >
              <LogIn className="h-4 w-4" />
              {loading ? 'Giriş yapılıyor…' : 'Giriş Yap'}
            </Button>

            <p className="text-[10px] text-center text-muted-foreground pt-2">
              Şifreniz Syroce PMS'e gönderilir, burada saklanmaz.
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
