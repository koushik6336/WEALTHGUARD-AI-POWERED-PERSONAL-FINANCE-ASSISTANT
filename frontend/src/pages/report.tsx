import { useState, useEffect } from 'react';
import { useLocation } from 'wouter';
import { Card } from '@/components/ui/card';
import { API_BASE, formatRupee } from '@/lib/helpers';
import { cn } from '@/lib/utils';

const CATEGORY_LABELS: Record<string, string> = {
  rent_emi: "Rent / EMI", food: "Food", transport: "Transport",
  shopping: "Shopping", entertainment: "Entertainment", utilities: "Utilities",
  health: "Health", education: "Education", other: "Other",
};

export default function Report() {
  const [, setLocation] = useLocation();
  const userId = localStorage.getItem('wg_active_user');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!userId) { setLocation('/login'); return; }
    fetch(`${API_BASE}/full-report?user_id=${userId}`)
      .then(r => r.json())
      .then(json => setData(json))
      .catch(e => console.error(e))
      .finally(() => setLoading(false));
  }, [userId]);

  if (loading) return <div className="min-h-screen bg-background flex items-center justify-center"><p className="text-muted-foreground">Loading report...</p></div>;
  if (!data) return <div className="min-h-screen bg-background flex items-center justify-center"><p className="text-muted-foreground">Could not load report.</p></div>;

  const date = new Date(data.generated_at);
  const monthYear = date.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });

  return (
    <div className="min-h-screen bg-background text-foreground pb-20">
      <div className="max-w-2xl mx-auto p-6">
        <button onClick={() => setLocation('/dashboard')} className="text-muted-foreground text-sm mb-6 flex items-center gap-1">
          <i className="ti ti-arrow-left" style={{fontSize:"1rem"}} /> Back to Dashboard
        </button>
        <div className="mb-6">
          <h1 className="text-2xl font-bold">Full Financial Report</h1>
          <p className="text-muted-foreground text-sm">{monthYear} · {data.name}</p>
        </div>

        {/* Income Summary */}
        <Card className="p-5 border-card-border bg-card mb-4">
          <h2 className="font-semibold mb-3 flex items-center gap-2">
            <i className="ti ti-cash text-brand" style={{fontSize:"1rem"}} /> Income
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">Monthly Salary</p>
              <p className="font-bold">{formatRupee(data.monthly_salary)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Annual Salary</p>
              <p className="font-bold">{formatRupee(data.annual_salary)}</p>
            </div>
          </div>
        </Card>

        {/* Budget */}
        <Card className="p-5 border-card-border bg-card mb-4">
          <h2 className="font-semibold mb-3 flex items-center gap-2">
            <i className="ti ti-wallet text-brand" style={{fontSize:"1rem"}} /> Budget This Month
          </h2>
          <div className="flex justify-between text-sm font-semibold mb-3 border-b border-border/30 pb-2">
            <span>Total Spent</span>
            <span>{formatRupee(data.budget.total_spent)}</span>
          </div>
          {data.budget.by_category.length > 0 ? (
            <div className="space-y-2">
              {data.budget.by_category.map((cat: any, i: number) => (
                <div key={i} className="flex justify-between text-sm">
                  <span className="text-muted-foreground">{CATEGORY_LABELS[cat.category] || cat.category}</span>
                  <span>{formatRupee(cat.spent)}</span>
                </div>
              ))}
            </div>
          ) : <p className="text-muted-foreground text-sm">No spend logged this month.</p>}
        </Card>

        {/* Investments */}
        <Card className="p-5 border-card-border bg-card mb-4">
          <h2 className="font-semibold mb-3 flex items-center gap-2">
            <i className="ti ti-chart-line text-brand" style={{fontSize:"1rem"}} /> Investments
          </h2>
          <div className="grid grid-cols-3 gap-4 mb-3 border-b border-border/30 pb-3">
            <div>
              <p className="text-xs text-muted-foreground">Invested</p>
              <p className="font-bold">{formatRupee(data.investments.total_invested)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Current</p>
              <p className="font-bold">{formatRupee(data.investments.total_current_value)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Returns</p>
              <p className={cn("font-bold", data.investments.overall_return_pct >= 0 ? "text-success" : "text-destructive")}>
                {data.investments.overall_return_pct >= 0 ? '▲' : '▼'} {Math.abs(data.investments.overall_return_pct)}%
              </p>
            </div>
          </div>
          {data.investments.holdings.map((h: any, i: number) => (
            <div key={i} className="flex justify-between text-sm border-b border-border/20 pb-2 mb-2 last:border-0 last:mb-0 last:pb-0">
              <span className="text-muted-foreground truncate mr-2">{h.scheme_name}</span>
              <span className={cn("shrink-0 font-medium", h.return_pct >= 0 ? "text-success" : "text-destructive")}>
                {h.return_pct >= 0 ? '▲' : '▼'}{Math.abs(h.return_pct)}%
              </span>
            </div>
          ))}
        </Card>

        {/* Goals */}
        <Card className="p-5 border-card-border bg-card mb-4">
          <h2 className="font-semibold mb-3 flex items-center gap-2">
            <i className="ti ti-target text-brand" style={{fontSize:"1rem"}} /> Goals
          </h2>
          {data.goals.length > 0 ? data.goals.map((goal: any, i: number) => (
            <div key={i} className="mb-3 last:mb-0">
              <div className="flex justify-between text-sm mb-1">
                <span className="font-medium">{goal.goal_name}</span>
                <span className="text-muted-foreground">{goal.progress_pct}%</span>
              </div>
              <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                <div className="h-full bg-brand rounded-full" style={{width: `${Math.min(goal.progress_pct, 100)}%`}} />
              </div>
              <div className="flex justify-between text-xs text-muted-foreground mt-1">
                <span>Saved: {formatRupee(goal.current_amount)}</span>
                <span>Target: {formatRupee(goal.target_amount)}</span>
              </div>
            </div>
          )) : <p className="text-muted-foreground text-sm">No active goals.</p>}
        </Card>

        {/* Tax */}
        <Card className="p-5 border-card-border bg-card mb-4">
          <h2 className="font-semibold mb-3 flex items-center gap-2">
            <i className="ti ti-receipt-tax text-brand" style={{fontSize:"1rem"}} /> Tax Summary
          </h2>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Annual Income</span>
              <span>{formatRupee(data.tax.annual_salary)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">80C Invested</span>
              <span>{formatRupee(data.tax.invested_80c)}</span>
            </div>
            <div className="flex justify-between border-t border-border/30 pt-2">
              <span className="text-muted-foreground">80C Room Left</span>
              <span className={cn("font-semibold", data.tax.remaining_80c > 0 ? "text-warning" : "text-success")}>
                {formatRupee(data.tax.remaining_80c)}
              </span>
            </div>
          </div>
        </Card>

        <p className="text-xs text-muted-foreground text-center">Generated {new Date(data.generated_at).toLocaleString('en-IN')}</p>
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
