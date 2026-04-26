import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { login as apiLogin, logout as apiLogout, me as apiMe, setUnauthorizedHandler } from '../lib/api';

const AuthContext = createContext(null);
const INACTIVITY_MS = 30 * 60 * 1000;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [pmsUrl, setPmsUrl] = useState('');
  const [hotelId, setHotelId] = useState('');
  const [kbsConfigured, setKbsConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const inactivityTimer = useRef(null);

  const doLogout = useCallback(async () => {
    try { await apiLogout(); } catch {}
    setUser(null);
    setPmsUrl('');
    setHotelId('');
    setKbsConfigured(false);
  }, []);

  const resetInactivity = useCallback(() => {
    if (inactivityTimer.current) clearTimeout(inactivityTimer.current);
    if (user) {
      inactivityTimer.current = setTimeout(() => {
        doLogout();
      }, INACTIVITY_MS);
    }
  }, [user, doLogout]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setPmsUrl('');
      setHotelId('');
    });
    apiMe()
      .then((d) => {
        setUser(d.user);
        setPmsUrl(d.pms_url || '');
        setHotelId(d.hotel_id || '');
        setKbsConfigured(!!d.kbs_configured);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!user) return;
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];
    events.forEach((e) => window.addEventListener(e, resetInactivity));
    resetInactivity();
    return () => {
      events.forEach((e) => window.removeEventListener(e, resetInactivity));
      if (inactivityTimer.current) clearTimeout(inactivityTimer.current);
    };
  }, [user, resetInactivity]);

  const login = async ({ email, password, pms_url, hotel_id, remember_me }) => {
    const res = await apiLogin({ email, password, pms_url, hotel_id, remember_me });
    setUser(res.user);
    setPmsUrl(pms_url);
    setHotelId(hotel_id);
    try {
      const m = await apiMe();
      setKbsConfigured(!!m.kbs_configured);
    } catch {}
    return res.user;
  };

  return (
    <AuthContext.Provider
      value={{
        user, pmsUrl, hotelId, kbsConfigured, loading,
        isAuthenticated: !!user,
        login, logout: doLogout,
        refreshKbsStatus: async () => {
          try {
            const m = await apiMe();
            setKbsConfigured(!!m.kbs_configured);
          } catch {}
        },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
