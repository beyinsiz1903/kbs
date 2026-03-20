import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useLanguage } from '../contexts/LanguageContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Radio, Globe, LogIn, Eye, EyeOff } from 'lucide-react';

export default function LoginPage() {
  const { login } = useAuth();
  const { t, language, toggleLanguage } = useLanguage();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error(language === 'tr' ? 'E-posta ve sifre zorunludur' : 'Email and password required');
      return;
    }
    setLoading(true);
    try {
      await login(email, password);
      toast.success(language === 'tr' ? 'Giris basarili' : 'Login successful');
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" data-testid="login-page">
      {/* Left Panel - Brand */}
      <div className="hidden lg:flex lg:w-1/2 relative bg-card/30 items-center justify-center overflow-hidden">
        <div className="absolute inset-0" style={{
          background: 'radial-gradient(1200px circle at 30% 40%, rgba(20,184,166,0.12), transparent 55%), radial-gradient(900px circle at 70% 20%, rgba(56,189,248,0.08), transparent 55%)'
        }} />
        <div className="relative z-10 px-12 max-w-lg">
          <div className="flex items-center gap-3 mb-8">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 border border-primary/20">
              <Radio className="h-7 w-7 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">KBS Bridge</h1>
              <p className="text-sm text-muted-foreground">Management System</p>
            </div>
          </div>
          <h2 className="text-3xl font-semibold tracking-tight mb-4">
            {language === 'tr' ? 'Kimlik Bildirim Sistemi' : 'Identity Reporting System'}
          </h2>
          <p className="text-muted-foreground leading-relaxed">
            {language === 'tr'
              ? 'Otel bazli kimlik bildirimi yonetimi, KBS entegrasyonu ve uyumluluk takibi icin merkezi kontrol paneli.'
              : 'Centralized management panel for hotel-based identity reporting, KBS integration, and compliance tracking.'}
          </p>
          <div className="mt-8 grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-border/40 bg-muted/20 p-4">
              <p className="text-2xl font-semibold tabular-nums text-primary">EGM</p>
              <p className="text-xs text-muted-foreground mt-1">{language === 'tr' ? 'Emniyet KBS' : 'Police KBS'}</p>
            </div>
            <div className="rounded-lg border border-border/40 bg-muted/20 p-4">
              <p className="text-2xl font-semibold tabular-nums text-primary">JGK</p>
              <p className="text-xs text-muted-foreground mt-1">{language === 'tr' ? 'Jandarma KBS' : 'Gendarmerie KBS'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center p-6 bg-background">
        <div className="w-full max-w-[400px]">
          {/* Mobile logo */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 border border-primary/20">
              <Radio className="h-5 w-5 text-primary" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight">KBS Bridge</h1>
          </div>

          <Card className="bg-card/60 border-border/50 backdrop-blur">
            <CardHeader className="space-y-1">
              <CardTitle className="text-2xl">
                {language === 'tr' ? 'Giris Yap' : 'Sign In'}
              </CardTitle>
              <CardDescription>
                {language === 'tr' ? 'KBS Bridge paneline erisim icin giris yapin' : 'Sign in to access the KBS Bridge panel'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">{language === 'tr' ? 'E-posta' : 'Email'}</Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="admin@kbsbridge.com"
                    className="h-10"
                    data-testid="login-email-input"
                    autoComplete="email"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">{language === 'tr' ? 'Sifre' : 'Password'}</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      placeholder="********"
                      className="h-10 pr-10"
                      data-testid="login-password-input"
                      autoComplete="current-password"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="absolute right-0 top-0 h-10 w-10 text-muted-foreground hover:text-foreground"
                      onClick={() => setShowPassword(!showPassword)}
                      data-testid="login-toggle-password"
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
                <Button
                  type="submit"
                  className="w-full h-10"
                  disabled={loading}
                  data-testid="login-submit-button"
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <span className="h-4 w-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                      {language === 'tr' ? 'Giris yapiliyor...' : 'Signing in...'}
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <LogIn className="h-4 w-4" />
                      {language === 'tr' ? 'Giris Yap' : 'Sign In'}
                    </span>
                  )}
                </Button>
              </form>

              {/* Demo credentials */}
              <div className="mt-6 rounded-lg bg-muted/30 border border-border/30 p-3">
                <p className="text-xs font-medium text-muted-foreground mb-2">
                  {language === 'tr' ? 'Demo Hesaplari' : 'Demo Accounts'}
                </p>
                <div className="space-y-1.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Admin:</span>
                    <span className="font-mono">admin@kbsbridge.com / admin123</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Manager:</span>
                    <span className="font-mono">manager@grandistanbul.com / manager123</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Front Desk:</span>
                    <span className="font-mono">resepsiyon@grandistanbul.com / front123</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Language toggle */}
          <div className="flex justify-center mt-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleLanguage}
              className="text-muted-foreground hover:text-foreground gap-2"
              data-testid="login-language-toggle"
            >
              <Globe className="h-4 w-4" />
              {language === 'tr' ? 'English' : 'Turkce'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
