import React, { useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import { Separator } from './ui/separator';
import { Badge } from './ui/badge';
import {
  LayoutDashboard, UserPlus, Send, Activity, Radio, FileText,
  Building2, Globe, Menu, X, ChevronRight, LogOut, Users, Settings,
  Heart, BarChart3, Shield, BookOpen
} from 'lucide-react';

const ROLE_LABELS = {
  tr: { admin: 'Yonetici', hotel_manager: 'Otel Muduru', front_desk: 'Resepsiyon' },
  en: { admin: 'Admin', hotel_manager: 'Manager', front_desk: 'Front Desk' },
};

const navGroups = (t, role) => {
  const groups = [
    {
      label: t('nav.overview'),
      items: [
        { path: '/', icon: LayoutDashboard, label: t('nav.dashboard') },
        { path: '/observability', icon: BarChart3, label: t('observability.title') || 'Observability' },
      ]
    },
    {
      label: t('nav.operations'),
      items: [
        { path: '/checkin', icon: UserPlus, label: t('nav.checkin') },
        { path: '/submissions', icon: Send, label: t('nav.submissions') },
      ]
    },
    {
      label: t('nav.monitoring'),
      items: [
        { path: '/agents', icon: Activity, label: t('nav.agents') },
        { path: '/kbs-control', icon: Radio, label: t('nav.kbsControl') },
      ]
    },
    {
      label: t('nav.compliance'),
      items: [
        { path: '/audit', icon: FileText, label: t('nav.audit') },
        { path: '/compliance', icon: Shield, label: t('kvkk.title') || 'KVKK' },
      ]
    },
    {
      label: t('nav.admin'),
      items: [
        { path: '/hotels', icon: Building2, label: t('nav.hotels') },
        { path: '/deployment', icon: BookOpen, label: t('deployment.title') || 'Deployment' },
      ]
    }
  ];

  // Add user management for admin only
  if (role === 'admin') {
    groups[groups.length - 1].items.push(
      { path: '/users', icon: Users, label: t('nav.users') || 'Kullanicilar' }
    );
  }

  // For front_desk, remove monitoring, compliance and admin sections
  if (role === 'front_desk') {
    return groups.filter(g =>
      g.label !== t('nav.monitoring') &&
      g.label !== t('nav.admin') &&
      g.label !== t('nav.compliance')
    ).map(g => ({
      ...g,
      items: g.items.filter(i => i.path !== '/observability')
    }));
  }

  return groups;
};

export function DashboardShell({ children }) {
  const { t, language, toggleLanguage } = useLanguage();
  const { user, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const groups = navGroups(t, user?.role);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-background" data-testid="dashboard-shell">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed top-0 left-0 z-50 h-svh w-[280px] border-r border-border/50 bg-card/30 backdrop-blur-xl transition-transform duration-300 lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-full flex-col">
          {/* Logo */}
          <div className="flex items-center gap-3 px-6 py-5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 border border-primary/20">
              <Radio className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-sm font-semibold tracking-tight">KBS Bridge</h1>
              <p className="text-[10px] text-muted-foreground">Management System</p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="ml-auto lg:hidden h-8 w-8"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          <Separator className="bg-border/30" />

          {/* Navigation */}
          <ScrollArea className="flex-1 px-3 py-4">
            <nav className="space-y-6">
              {groups.map((group) => (
                <div key={group.label}>
                  <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                    {group.label}
                  </p>
                  <div className="space-y-1">
                    {group.items.map((item) => {
                      const isActive = location.pathname === item.path ||
                        (item.path !== '/' && location.pathname.startsWith(item.path));
                      return (
                        <NavLink
                          key={item.path}
                          to={item.path}
                          data-testid={`nav-${item.path.replace(/\//g, '').replace(/-/g, '') || 'dashboard'}`}
                          data-nav-path={item.path}
                          onClick={() => setSidebarOpen(false)}
                          className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all duration-200 ${
                            isActive
                              ? 'bg-primary/10 text-primary border border-primary/20'
                              : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground'
                          }`}
                        >
                          <item.icon className={`h-4 w-4 ${isActive ? 'text-primary' : ''}`} />
                          <span className="font-medium">{item.label}</span>
                          {isActive && <ChevronRight className="ml-auto h-3 w-3 text-primary/60" />}
                        </NavLink>
                      );
                    })}
                  </div>
                </div>
              ))}
            </nav>
          </ScrollArea>

          {/* User Info + Footer */}
          <Separator className="bg-border/30" />
          <div className="px-4 py-3 space-y-2">
            {/* User info */}
            {user && (
              <div className="flex items-center gap-3 px-2 py-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 border border-primary/20 text-xs font-semibold text-primary">
                  {user.first_name?.[0]}{user.last_name?.[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium truncate">{user.first_name} {user.last_name}</p>
                  <p className="text-[10px] text-muted-foreground truncate">{ROLE_LABELS[language]?.[user.role] || user.role}</p>
                </div>
              </div>
            )}

            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleLanguage}
                className="flex-1 justify-start gap-2 text-muted-foreground hover:text-foreground h-8"
                data-testid="language-toggle"
              >
                <Globe className="h-3.5 w-3.5" />
                <span className="text-xs">{language === 'tr' ? 'TR' : 'EN'}</span>
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleLogout}
                className="h-8 w-8 text-muted-foreground hover:text-rose-400"
                data-testid="logout-button"
              >
                <LogOut className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="lg:ml-[280px]">
        {/* Topbar */}
        <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b border-border/50 bg-background/80 backdrop-blur-xl px-4 sm:px-6 lg:px-8">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden h-8 w-8"
            onClick={() => setSidebarOpen(true)}
            data-testid="mobile-menu-button"
          >
            <Menu className="h-5 w-5" />
          </Button>

          {/* Breadcrumb area */}
          <div className="flex-1" />

          {/* User role badge */}
          {user && (
            <Badge variant="outline" className="text-[10px] border-border/50 bg-card/40" data-testid="user-role-badge">
              {ROLE_LABELS[language]?.[user.role] || user.role}
            </Badge>
          )}

          {/* Language toggle (desktop) */}
          <Button
            variant="outline"
            size="sm"
            onClick={toggleLanguage}
            className="hidden sm:flex gap-2 h-8 border-border/50 bg-card/40"
            data-testid="language-toggle-desktop"
          >
            <Globe className="h-3.5 w-3.5" />
            <span className="text-xs">{language === 'tr' ? 'TR' : 'EN'}</span>
          </Button>
        </header>

        {/* Page Content */}
        <main className="px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </main>
      </div>
    </div>
  );
}
