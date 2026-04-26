import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { toast } from 'sonner';
import { getWorkerStatus, errorMessage } from '../lib/api';
import { getAlertSoundEnabled } from '../lib/operatorPrefs';

const WorkerStatusContext = createContext(null);

const REFRESH_MS = 5000;

function playAlertBeep() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    if (ctx.state === 'suspended' && typeof ctx.resume === 'function') {
      ctx.resume().catch(() => {});
    }
    const beepAt = (offset, freq) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      const start = ctx.currentTime + offset;
      const dur = 0.18;
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.18, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + dur);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(start);
      osc.stop(start + dur + 0.02);
    };
    beepAt(0, 880);
    beepAt(0.22, 660);
    setTimeout(() => { try { ctx.close(); } catch { /* noop */ } }, 700);
  } catch {
    /* sound is best-effort; UI toast still fires */
  }
}

export function WorkerStatusProvider({ children }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  // Task #10/#12: detect sse_connected transitions across REFRESH_MS polls so
  // the operator gets an active toast/sound + tab-title flag on disconnect,
  // regardless of which page is mounted (Worker Durumu, Ayarlar, ...).
  const prevSseConnectedRef = useRef(null);
  const alertedDisconnectRef = useRef(false);
  const originalTitleRef = useRef(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getWorkerStatus();
      setStatus(res);
      return res;
    } catch (err) {
      toast.error(errorMessage(err));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(t);
  }, [refresh]);

  // SSE connect/disconnect transition alerts. Runs on every status refresh.
  useEffect(() => {
    if (!status) return;
    const mode = status.worker_mode || 'poll';
    const eligible =
      (mode === 'sse' || mode === 'auto') &&
      !!status.running &&
      status.session_status === 'ok';

    // If the worker is no longer in a push-eligible state (mode switched to
    // poll, worker stopped, session dropped) any pending "disconnect" UI
    // becomes stale — supervisor isn't expecting push anymore. Clear the
    // alert latch and restore the tab title so the warning doesn't linger
    // across navigations or mode changes.
    if (!eligible) {
      prevSseConnectedRef.current = null;
      if (alertedDisconnectRef.current) {
        alertedDisconnectRef.current = false;
        if (originalTitleRef.current !== null) {
          document.title = originalTitleRef.current;
          originalTitleRef.current = null;
        }
      }
      return;
    }
    const connected = !!status.sse_connected;
    const prev = prevSseConnectedRef.current;
    prevSseConnectedRef.current = connected;

    // First sample after eligibility: just record, no toast.
    if (prev === null) return;

    if (prev === true && connected === false && !alertedDisconnectRef.current) {
      alertedDisconnectRef.current = true;
      toast.warning('Anlık bildirim kanalı koptu', {
        description: 'PMS push bağlantısı kesildi. Tarama yedeği işleri kaçırmıyor; yeniden bağlanmaya çalışılıyor.',
        duration: 10000,
      });
      // Task #13: operatör Ayarlar'dan sesli uyarıyı kapatabilir; toast +
      // sekme başlığı uyarısı her durumda çalışır, beep tercih kapalıysa çalmaz.
      if (getAlertSoundEnabled()) {
        playAlertBeep();
      }
      if (originalTitleRef.current === null) {
        originalTitleRef.current = document.title;
      }
      document.title = '⚠ Bağlantı koptu — ' + (originalTitleRef.current || 'KBS');
    } else if (connected === true && alertedDisconnectRef.current) {
      alertedDisconnectRef.current = false;
      toast.success('Anlık bildirim tekrar aktif', {
        description: 'PMS push bağlantısı geri kuruldu.',
        duration: 5000,
      });
      if (originalTitleRef.current !== null) {
        document.title = originalTitleRef.current;
        originalTitleRef.current = null;
      }
    }
  }, [status]);

  // Restore the original tab title if the provider unmounts (logout)
  // while a disconnect alert is still outstanding.
  useEffect(() => {
    return () => {
      if (originalTitleRef.current !== null) {
        document.title = originalTitleRef.current;
        originalTitleRef.current = null;
      }
    };
  }, []);

  return (
    <WorkerStatusContext.Provider value={{ status, loading, refresh, refreshIntervalMs: REFRESH_MS }}>
      {children}
    </WorkerStatusContext.Provider>
  );
}

export function useWorkerStatus() {
  const ctx = useContext(WorkerStatusContext);
  if (!ctx) throw new Error('useWorkerStatus must be used within WorkerStatusProvider');
  return ctx;
}
