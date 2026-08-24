import { useState, useEffect } from 'react';
import { useLocation } from 'wouter';
import { Card } from '@/components/ui/card';
import { API_BASE } from '@/lib/helpers';
import { cn } from '@/lib/utils';

export default function Security() {
  const [, setLocation] = useLocation();
  const userId = localStorage.getItem('wg_active_user');
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!userId) { setLocation('/login'); return; }
    fetch(`${API_BASE}/login-history?user_id=${userId}`)
      .then(r => r.json())
      .then(json => setHistory(json.history || []))
      .catch(e => console.error(e))
      .finally(() => setLoading(false));
  }, [userId]);

  return (
    <div className="min-h-screen bg-background text-foreground pb-20">
      <div className="max-w-2xl mx-auto p-6">
        <button onClick={() => setLocation('/dashboard')} className="text-muted-foreground text-sm mb-6 flex items-center gap-1">
          <i className="ti ti-arrow-left" style={{fontSize:"1rem"}} /> Back to Dashboard
        </button>
        <h1 className="text-2xl font-bold mb-6">Security</h1>

        <Card className="p-5 border-card-border bg-card mb-4">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <i className="ti ti-shield-check text-success" style={{fontSize:"1rem"}} /> Account Status
          </h2>
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <i className="ti ti-circle-check text-success" style={{fontSize:"1rem"}} />
              <span>Account Active</span>
            </div>
            <div className="flex items-center gap-2">
              <i className="ti ti-circle-check text-success" style={{fontSize:"1rem"}} />
              <span>Password Protected</span>
            </div>
            <div className="flex items-center gap-2">
              <i className="ti ti-circle-x text-muted-foreground" style={{fontSize:"1rem"}} />
              <span className="text-muted-foreground">2FA not enabled (coming soon)</span>
            </div>
          </div>
        </Card>

        <Card className="p-5 border-card-border bg-card">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <i className="ti ti-history text-brand" style={{fontSize:"1rem"}} /> Login History
          </h2>
          {loading ? <p className="text-muted-foreground text-sm">Loading...</p> : (
            <div className="space-y-3">
              {history.length > 0 ? history.map((h, i) => (
                <div key={i} className={cn("flex items-center justify-between text-sm border-b border-border/30 pb-2 last:border-0", i === 0 ? "text-foreground" : "text-muted-foreground")}>
                  <div className="flex items-center gap-2">
                    <i className="ti ti-device-mobile" style={{fontSize:"1rem"}} />
                    <span>{new Date(h.timestamp).toLocaleString('en-IN', {day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'})}</span>
                  </div>
                  {i === 0 && <span className="text-xs text-success font-medium">Latest</span>}
                </div>
              )) : (
                <p className="text-muted-foreground text-sm">No login history yet.</p>
              )}
            </div>
          )}
        </Card>
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
