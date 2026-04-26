// Operator-local UI preferences persisted in localStorage. These are pure
// frontend tercihler (per browser / per PC); not synced with backend. Keep
// keys + defaults centralized so all callers agree on shape.

const ALERT_SOUND_KEY = 'kbs.operator.alertSoundEnabled';
const ALERT_SOUND_EVENT = 'kbs:operator-alert-sound-changed';

export function getAlertSoundEnabled() {
  try {
    const raw = localStorage.getItem(ALERT_SOUND_KEY);
    if (raw === null) return true;
    return raw === 'true';
  } catch {
    return true;
  }
}

export function setAlertSoundEnabled(value) {
  const v = !!value;
  try {
    localStorage.setItem(ALERT_SOUND_KEY, v ? 'true' : 'false');
  } catch {
    /* localStorage may be unavailable (private mode); ignore */
  }
  try {
    window.dispatchEvent(new CustomEvent(ALERT_SOUND_EVENT, { detail: v }));
  } catch {
    /* noop */
  }
}

export function subscribeAlertSoundEnabled(handler) {
  const onCustom = (e) => handler(!!e.detail);
  const onStorage = (e) => {
    if (e.key === ALERT_SOUND_KEY) handler(getAlertSoundEnabled());
  };
  window.addEventListener(ALERT_SOUND_EVENT, onCustom);
  window.addEventListener('storage', onStorage);
  return () => {
    window.removeEventListener(ALERT_SOUND_EVENT, onCustom);
    window.removeEventListener('storage', onStorage);
  };
}
