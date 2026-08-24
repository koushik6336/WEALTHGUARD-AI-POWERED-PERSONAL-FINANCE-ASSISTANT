import { useState } from 'react';
import { useLocation } from 'wouter';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function Settings() {
  const [, setLocation] = useLocation();
  const userId = localStorage.getItem('wg_active_user');
  const userName = localStorage.getItem('wg_active_name') || 'User';
  const [notifications, setNotifications] = useState(true);
  const [budgetAlerts, setBudgetAlerts] = useState(true);
  const [goalReminders, setGoalReminders] = useState(true);

  const handleLogout = () => {
    localStorage.removeItem('wg_active_user');
    localStorage.removeItem('wg_active_name');
    localStorage.removeItem('wg_onboard_preview');
    setLocation('/login');
  };

  return (
    <div className="min-h-screen bg-background text-foreground pb-20">
      <div className="max-w-2xl mx-auto p-6">
        <button onClick={() => setLocation('/dashboard')} className="text-muted-foreground text-sm mb-6 flex items-center gap-1">
          <i className="ti ti-arrow-left" style={{fontSize:"1rem"}} /> Back to Dashboard
        </button>
        <h1 className="text-2xl font-bold mb-6">Settings</h1>

        {/* Profile */}
        <Card className="p-5 border-card-border bg-card mb-4">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <i className="ti ti-user text-brand" style={{fontSize:"1rem"}} /> Profile
          </h2>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Name</span>
              <span className="font-medium">{userName}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">User ID</span>
              <span className="font-medium">{userId}</span>
            </div>
          </div>
        </Card>

        {/* Notifications */}
        <Card className="p-5 border-card-border bg-card mb-4">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <i className="ti ti-bell text-brand" style={{fontSize:"1rem"}} /> Notifications
          </h2>
          <div className="space-y-4">
            {[
              { label: 'Push Notifications', desc: 'Receive alerts on your device', value: notifications, setter: setNotifications },
              { label: 'Budget Alerts', desc: 'Alert when spending exceeds 80%', value: budgetAlerts, setter: setBudgetAlerts },
              { label: 'Goal Reminders', desc: 'Weekly progress updates', value: goalReminders, setter: setGoalReminders },
            ].map((item, i) => (
              <div key={i} className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">{item.label}</p>
                  <p className="text-xs text-muted-foreground">{item.desc}</p>
                </div>
                <button onClick={() => item.setter(!item.value)}
                  className={`w-11 h-6 rounded-full transition-colors ${item.value ? 'bg-brand' : 'bg-secondary'} relative`}>
                  <span className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${item.value ? 'translate-x-6' : 'translate-x-1'}`} />
                </button>
              </div>
            ))}
          </div>
        </Card>

        {/* App */}
        <Card className="p-5 border-card-border bg-card mb-4">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <i className="ti ti-settings text-brand" style={{fontSize:"1rem"}} /> App
          </h2>
          <div className="space-y-3 text-sm">
            <button onClick={() => setLocation('/security')} className="w-full flex justify-between items-center py-2 border-b border-border/30 hover:text-brand transition-colors">
              <span>Security & Login History</span>
              <i className="ti ti-chevron-right" style={{fontSize:"1rem"}} />
            </button>
            <button onClick={() => setLocation('/report')} className="w-full flex justify-between items-center py-2 border-b border-border/30 hover:text-brand transition-colors">
              <span>Full Financial Report</span>
              <i className="ti ti-chevron-right" style={{fontSize:"1rem"}} />
            </button>
            <button onClick={() => setLocation('/chat')} className="w-full flex justify-between items-center py-2 hover:text-brand transition-colors">
              <span>What-if Simulator</span>
              <i className="ti ti-chevron-right" style={{fontSize:"1rem"}} />
            </button>
          </div>
        </Card>

        {/* Danger Zone */}
        <Card className="p-5 border-card-border bg-card mb-4">
          <h2 className="font-semibold mb-4 text-destructive">Account</h2>
          <Button onClick={handleLogout} variant="outline" className="w-full border-destructive text-destructive hover:bg-destructive/10">
            <i className="ti ti-logout mr-2" style={{fontSize:"1rem"}} /> Sign Out
          </Button>
        </Card>

        <p className="text-xs text-muted-foreground text-center">WealthGuard v1.0 · Built with ❤️</p>
      </div>

      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur-md border-t border-border/50 flex items-center justify-around px-2 py-2 z-50">
        <button onClick={() => setLocation('/dashboard')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-layout-dashboard" style={{fontSize:"1.2rem"}} /><span className="text-xs">Dashboard</span>
        </button>
        <button onClick={() => setLocation('/budget')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-wallet" style={{fontSize:"1.2rem"}} /><span className="text-xs">Budget</span>
        </button>
        <button onClick={() => setLocation('/invest')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-chart-line" style={{fontSize:"1.2rem"}} /><span className="text-xs">Invest</span>
        </button>
        <button onClick={() => setLocation('/tax')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-receipt-tax" style={{fontSize:"1.2rem"}} /><span className="text-xs">Tax</span>
        </button>
        <button onClick={() => setLocation('/goals')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-target" style={{fontSize:"1.2rem"}} /><span className="text-xs">Goals</span>
        </button>
      </nav>
    </div>
  );
}
