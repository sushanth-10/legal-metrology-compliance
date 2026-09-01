import { useState } from 'react';
import { Bell, Shield, Globe, Moon, Save } from 'lucide-react';
import { useApp } from '@/store';
import { PageHeader } from '@/components/ui';
import { languageOptions, translate } from '@/lib/i18n';

function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!on)}
      aria-label={label}
      aria-pressed={on}
      className={`relative w-11 h-6 rounded-full transition-colors ${on ? 'bg-brand-600' : 'bg-ink-200'}`}
    >
      <span
        className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
          on ? 'translate-x-5' : ''
        }`}
      />
    </button>
  );
}

export function Settings() {
  const { user, role, preferences, setPreferences, t, showToast } = useApp();
  const [notifications, setNotifications] = useState(true);
  const [scanAlerts, setScanAlerts] = useState(true);
  const [complaintAlerts, setComplaintAlerts] = useState(false);
  const [darkMode, setDarkMode] = useState(preferences.darkMode);
  const [language, setLanguage] = useState(preferences.language);

  const applyPreferences = () => {
    setPreferences({ darkMode, language });
    showToast('success', translate(language, 'changesSaved'));
  };

  return (
    <div className="max-w-3xl mx-auto">
      <PageHeader title={t('settings')} subtitle={t('settingsSubtitle')} />

      {/* Account info */}
      <div className="card p-5 mb-5">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <p className="font-semibold text-ink-900">{user.name}</p>
            <p className="text-xs text-ink-500">
              {role === 'officer' ? 'Legal Metrology Officer' : role === 'admin' ? 'Administrator' : 'Organization'} • {user.email}
            </p>
          </div>
        </div>
      </div>

      {/* Notifications */}
      <div className="card p-5 mb-5">
        <div className="flex items-center gap-2 mb-4">
          <Bell className="w-4 h-4 text-brand-600" />
          <h3 className="font-semibold text-ink-900">{t('notifications')}</h3>
        </div>
        <div className="space-y-1">
          {[
            { label: t('pushNotifications'), desc: t('pushNotificationsDesc'), v: notifications, set: setNotifications },
            { label: t('scanAlerts'), desc: t('scanAlertsDesc'), v: scanAlerts, set: setScanAlerts },
            { label: t('complaintAlerts'), desc: t('complaintAlertsDesc'), v: complaintAlerts, set: setComplaintAlerts },
          ].map((row) => (
            <div key={row.label} className="flex items-center justify-between py-3 border-b border-ink-100 last:border-0">
              <div>
                <p className="text-sm font-medium text-ink-800">{row.label}</p>
                <p className="text-xs text-ink-500">{row.desc}</p>
              </div>
              <Toggle on={row.v} onChange={row.set} label={row.label} />
            </div>
          ))}
        </div>
      </div>

      {/* Preferences */}
      <div className="card p-5 mb-5">
        <div className="flex items-center gap-2 mb-4">
          <Globe className="w-4 h-4 text-brand-600" />
          <h3 className="font-semibold text-ink-900">{t('preferences')}</h3>
        </div>
        <div className="space-y-4">
          <div>
            <label className="label" htmlFor="language-select">{t('language')}</label>
            <select id="language-select" value={language} onChange={(e) => setLanguage(e.target.value as typeof language)} className="input">
              {languageOptions.map((option) => <option key={option.code} value={option.code}>{option.label}</option>)}
            </select>
          </div>
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-2">
              <Moon className="w-4 h-4 text-ink-500" />
              <div>
                <p className="text-sm font-medium text-ink-800">{t('darkMode')}</p>
                <p className="text-xs text-ink-500">{t('darkModeDesc')}</p>
              </div>
            </div>
            <Toggle on={darkMode} onChange={(enabled) => { setDarkMode(enabled); setPreferences({ darkMode: enabled, language }); }} label={t('darkMode')} />
          </div>
        </div>
      </div>

      {/* Security */}
      <div className="card p-5 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-4 h-4 text-brand-600" />
          <h3 className="font-semibold text-ink-900">{t('security')}</h3>
        </div>
        <div className="space-y-2">
          <button className="btn-secondary w-full justify-between">
          {t('changePassword')} <span className="text-ink-400">→</span>
          </button>
          <button className="btn-secondary w-full justify-between">
          {t('twoFactor')} <span className="text-ink-400">→</span>
          </button>
          <button className="btn-secondary w-full justify-between text-danger-600 hover:bg-danger-50">
          {t('deleteAccount')} <span className="text-danger-400">→</span>
          </button>
        </div>
      </div>

      <div className="flex justify-end">
        <button onClick={applyPreferences} className="btn-primary px-6 py-3">
          <Save className="w-4 h-4" /> {t('saveChanges')}
        </button>
      </div>
    </div>
  );
}
