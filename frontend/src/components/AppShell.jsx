import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Users, FileText, Settings, LogOut, Radio, AlertTriangle } from 'lucide-react';

export function AppShell({ children }) {
  const { user, logout, kbsConfigured, pmsUrl } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const fullName = user?.full_name || user?.email || '';
  const tenantId = user?.tenant_id || '';

  const navItems = [
    { path: '/', icon: Users, label: 'Bugünün Misafirleri' },
    { path: '/raporlar', icon: FileText, label: 'Rapor Geçmişi' },
    { path: '/ayarlar', icon: Settings, label: 'Ayarlar' },
  ];

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed top-0 left-0 z-30 h-svh w-64 border-r border-border/50 bg-card/30 backdrop-blur-xl">
        <div className="flex h-full flex-col">
          <div className="flex items-center gap-3 px-5 py-5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 border border-primary/20">
              <Radio className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-sm font-semibold tracking-tight">KBS Bridge</h1>
              <p className="text-[10px] text-muted-foreground">Konaklama Bildirim Sistemi</p>
            </div>
          </div>

          <nav className="flex-1 px-3 py-4 space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all ${
                    isActive
                      ? 'bg-primary/10 text-primary border border-primary/20'
                      : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground'
                  }`
                }
              >
                <item.icon className="h-4 w-4" />
                <span className="font-medium">{item.label}</span>
                {item.path === '/ayarlar' && !kbsConfigured && (
                  <AlertTriangle className="ml-auto h-3.5 w-3.5 text-amber-400" />
                )}
              </NavLink>
            ))}
          </nav>

          <div className="px-4 py-3 border-t border-border/30 space-y-2">
            <div className="px-2 py-1.5">
              <p className="text-xs font-medium truncate">{fullName}</p>
              {tenantId && (
                <p className="text-[10px] text-muted-foreground truncate">Otel: {tenantId}</p>
              )}
              {pmsUrl && (
                <p className="text-[10px] text-muted-foreground truncate" title={pmsUrl}>
                  {pmsUrl.replace(/^https?:\/\//, '')}
                </p>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="w-full justify-start gap-2 text-muted-foreground hover:text-rose-400"
              data-testid="logout-button"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span className="text-xs">Çıkış</span>
            </Button>
          </div>
        </div>
      </aside>

      <div className="ml-64">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-4 border-b border-border/50 bg-background/80 backdrop-blur-xl px-6">
          <div className="flex-1">
            <p className="text-sm">
              Hoş geldin <span className="font-medium">{fullName}</span>
              {tenantId && <span className="text-muted-foreground"> — Otel: {tenantId}</span>}
            </p>
          </div>
          {!kbsConfigured && (
            <Badge variant="outline" className="border-amber-500/40 text-amber-400 gap-1.5">
              <AlertTriangle className="h-3 w-3" />
              KBS ayarları eksik
            </Badge>
          )}
        </header>
        <main className="p-6">{children}</main>
      </div>
    </div>
  );
}
