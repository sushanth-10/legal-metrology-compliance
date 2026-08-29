import { useState } from 'react';
import { Bell, Shield, Globe, Moon, Save } from 'lucide-react';
import { useApp } from '@/store';
import { PageHeader } from '@/components/ui';

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!on)}
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
  const { user, role } = useApp();
  const [notifications, setNotifications] = useState(true);
  const [scanAlerts, setScanAlerts] = useState(true);
  const [complaintAlerts, setComplaintAlerts] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [language, setLanguage] = useState('English');

  return (
    <div className="max-w-3xl mx-auto">
      <PageHeader title="Settings" subtitle="Manage your preferences and account options." />

      {/* Account info */}
      <div className="card p-5 mb-5">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <p className="font-semibold text-ink-900">{user.name}</p>
            <p className="text-xs text-ink-500">
              {role === 'officer' ? 'Legal Metrology Officer' : 'Consumer'} • {user.email}
            </p>
          </div>
        </div>
      </div>

      {/* Notifications */}
      <div className="card p-5 mb-5">
        <div className="flex items-center gap-2 mb-4">
          <Bell className="w-4 h-4 text-brand-600" />
          <h3 className="font-semibold text-ink-900">Notifications</h3>
        </div>
        <div className="space-y-1">
          {[
            { label: 'Push notifications', desc: 'Receive alerts on this device', v: notifications, set: setNotifications },
            { label: 'Scan result alerts', desc: 'Notify when a scan completes', v: scanAlerts, set: setScanAlerts },
            { label: 'Complaint updates', desc: 'Notify on complaint status changes', v: complaintAlerts, set: setComplaintAlerts },
          ].map((row) => (
            <div key={row.label} className="flex items-center justify-between py-3 border-b border-ink-100 last:border-0">
              <div>
                <p className="text-sm font-medium text-ink-800">{row.label}</p>
                <p className="text-xs text-ink-500">{row.desc}</p>
              </div>
              <Toggle on={row.v} onChange={row.set} />
            </div>
          ))}
        </div>
      </div>

      {/* Preferences */}
      <div className="card p-5 mb-5">
        <div className="flex items-center gap-2 mb-4">
          <Globe className="w-4 h-4 text-brand-600" />
          <h3 className="font-semibold text-ink-900">Preferences</h3>
        </div>
        <div className="space-y-4">
          <div>
            <label className="label">Language</label>
            <select value={language} onChange={(e) => setLanguage(e.target.value)} className="input">
              <option>English</option>
              <option>हिन्दी (Hindi)</option>
              <option>ಕನ್ನಡ (Kannada)</option>
              <option>தமிழ் (Tamil)</option>
            </select>
          </div>
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-2">
              <Moon className="w-4 h-4 text-ink-500" />
              <div>
                <p className="text-sm font-medium text-ink-800">Dark mode</p>
                <p className="text-xs text-ink-500">Use a darker theme (coming soon)</p>
              </div>
            </div>
            <Toggle on={darkMode} onChange={setDarkMode} />
          </div>
        </div>
      </div>

      {/* Security */}
      <div className="card p-5 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-4 h-4 text-brand-600" />
          <h3 className="font-semibold text-ink-900">Security</h3>
        </div>
        <div className="space-y-2">
          <button className="btn-secondary w-full justify-between">
            Change password <span className="text-ink-400">→</span>
          </button>
          <button className="btn-secondary w-full justify-between">
            Two-factor authentication <span className="text-ink-400">→</span>
          </button>
          <button className="btn-secondary w-full justify-between text-danger-600 hover:bg-danger-50">
            Delete account <span className="text-danger-400">→</span>
          </button>
        </div>
      </div>

      <div className="flex justify-end">
        <button className="btn-primary px-6 py-3">
          <Save className="w-4 h-4" /> Save Changes
        </button>
      </div>
    </div>
  );
}
