import { useState, useEffect } from 'react';
import { useLocation } from 'wouter';
import { Card } from '@/components/ui/card';
import { API_BASE, formatRupee } from '@/lib/helpers';
import { cn } from '@/lib/utils';

export default function Tax() {
  const [, setLocation] = useLocation();
  const userId = localStorage.getItem('wg_active_user');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!userId) { setLocation('/login'); return; }
    fetch(`${API_BASE}/tax-comparison?user_id=${userId}`)
      .then(r => r.json())
      .then(json => setData(json))
      .catch(e => console.error(e))
      .finally(() => setLoading(false));
  }, [userId]);

  return (
    <div className="min-h-screen bg-background text-foreground pb-20">
      <div className="max-w-2xl mx-auto p-6">
        <button onClick={() => setLocation('/dashboard')} className="text-muted-foreground text-sm mb-6 flex items-center gap-1">
          <i className="ti ti-arrow-left" style={{fontSize:"1rem"}} /> Back to Dashboard
        </button>
        <h1 className="text-2xl font-bold mb-6">Tax</h1>

        {loading ? <p className="text-muted-foreground text-sm">Loading...</p> : !data ? (
          <p className="text-muted-foreground text-sm">Could not load tax data.</p>
        ) : (
          <div className="space-y-4">

            {/* Recommendation Banner */}
            <Card className="p-5 border-card-border bg-card">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-full bg-brand/10 flex items-center justify-center">
                  <i className="ti ti-receipt-tax text-brand" style={{fontSize:"1.2rem"}} />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase font-medium">Recommended</p>
                  <h2 className="text-lg font-bold">{data.recommended_regime} Regime</h2>
                </div>
              </div>
              <p className="text-sm text-muted-foreground">
                You save <span className="text-success font-semibold">{formatRupee(data.savings)}</span> this year by choosing the {data.recommended_regime} Regime.
              </p>
              <p className="text-xs text-muted-foreground mt-2">* This is an estimate. Consult a CA for exact filing.</p>
            </Card>

            {/* Regime Comparison */}
            <Card className="p-5 border-card-border bg-card">
              <h2 className="font-semibold mb-4">Regime Comparison</h2>
              <div className="grid grid-cols-2 gap-4">
                <div className={cn("p-4 rounded-lg border-2 transition-colors",
                  data.recommended_regime === 'Old' ? "border-brand bg-brand/5" : "border-border")}>
                  <p className="text-xs text-muted-foreground uppercase font-medium mb-1">Old Regime</p>
                  <p className="text-2xl font-bold">{formatRupee(data.old_regime_tax)}</p>
                  <p className="text-xs text-muted-foreground mt-1">With 80C deductions</p>
                  {data.recommended_regime === 'Old' && <span className="text-xs text-brand font-medium">✓ Recommended</span>}
                </div>
                <div className={cn("p-4 rounded-lg border-2 transition-colors",
                  data.recommended_regime === 'New' ? "border-brand bg-brand/5" : "border-border")}>
                  <p className="text-xs text-muted-foreground uppercase font-medium mb-1">New Regime</p>
                  <p className="text-2xl font-bold">{formatRupee(data.new_regime_tax)}</p>
                  <p className="text-xs text-muted-foreground mt-1">No deductions</p>
                  {data.recommended_regime === 'New' && <span className="text-xs text-brand font-medium">✓ Recommended</span>}
                </div>
              </div>
            </Card>

            {/* 80C Summary */}
            <Card className="p-5 border-card-border bg-card">
              <h2 className="font-semibold mb-4">Section 80C</h2>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Annual Income</span>
                  <span className="font-medium">{formatRupee(data.annual_salary)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">80C Invested</span>
                  <span className="font-medium">{formatRupee(data.invested_80c)}</span>
                </div>
                <div className="flex justify-between text-sm border-t border-border/30 pt-2">
                  <span className="text-muted-foreground">80C Room Left</span>
                  <span className={cn("font-semibold", data.remaining_80c > 0 ? "text-warning" : "text-success")}>
                    {formatRupee(data.remaining_80c)}
                  </span>
                </div>
              </div>
              {data.remaining_80c > 0 && (
                <div className="mt-3 p-3 rounded-lg bg-warning/10 border border-warning/30 text-sm text-warning">
                  <i className="ti ti-bulb mr-1" style={{fontSize:"0.9rem"}} />
                  Invest {formatRupee(data.remaining_80c)} more in ELSS/PPF to maximize 80C savings under Old Regime.
                </div>
              )}
            </Card>
          </div>
        )}
      </div>

      {/* Mobile Bottom Nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur-md border-t border-border/50 flex items-center justify-around px-2 py-2 z-50">
        <button onClick={() => setLocation('/dashboard')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-layout-dashboard" style={{fontSize:"1.2rem"}} />
          <span className="text-xs">Dashboard</span>
        </button>
        <button onClick={() => setLocation('/budget')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-wallet" style={{fontSize:"1.2rem"}} />
          <span className="text-xs">Budget</span>
        </button>
        <button onClick={() => setLocation('/invest')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-chart-line" style={{fontSize:"1.2rem"}} />
          <span className="text-xs">Invest</span>
        </button>
        <button onClick={() => setLocation('/tax')} className="flex flex-col items-center gap-1 px-3 py-1 text-brand">
          <i className="ti ti-receipt-tax" style={{fontSize:"1.2rem"}} />
          <span className="text-xs font-medium">Tax</span>
        </button>
        <button onClick={() => setLocation('/goals')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-target" style={{fontSize:"1.2rem"}} />
          <span className="text-xs">Goals</span>
        </button>
      </nav>
    </div>
  );
}
