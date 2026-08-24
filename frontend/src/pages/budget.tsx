import { useState, useEffect } from 'react';
import { useLocation } from 'wouter';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { API_BASE, formatRupee } from '@/lib/helpers';
import { cn } from '@/lib/utils';

const CATEGORY_LABELS: Record<string, string> = {
  rent_emi: "Rent / EMI",
  food: "Food",
  transport: "Transport",
  shopping: "Shopping",
  entertainment: "Entertainment",
  utilities: "Utilities",
  health: "Health",
  education: "Education",
  other: "Other",
};

const CATEGORY_ICONS: Record<string, string> = {
  food: "ti-tools-kitchen-2",
  transport: "ti-car",
  shopping: "ti-shopping-bag",
  entertainment: "ti-device-tv",
  utilities: "ti-bolt",
  health: "ti-heart",
  education: "ti-book",
  other: "ti-dots",
};

export default function Budget() {
  const [, setLocation] = useLocation();
  const userId = localStorage.getItem('wg_active_user');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('food');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const fetchData = async () => {
    try {
      const res = await fetch(`${API_BASE}/log-spend?user_id=${userId}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!userId) { setLocation('/login'); return; }
    fetchData();
  }, [userId]);

  const handleSubmit = async () => {
    console.log('handleSubmit called, amount:', amount, 'category:', category, 'userId:', userId);
    if (!amount) { console.log('No amount, returning'); return; }
    setSubmitting(true);
    try {
      await fetch(`${API_BASE}/log-spend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, amount: parseFloat(amount), category, note })
      });
      setAmount('');
      setNote('');
      setSuccess(true);
      await fetchData();
      setTimeout(() => setSuccess(false), 2000);
    } catch (e) {
      console.error(e);
    } finally {
      setSubmitting(false);
    }
  };

  const categories = ['food', 'transport', 'shopping', 'entertainment', 'utilities', 'health', 'other'];

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    if (d.toDateString() === today.toDateString()) return 'Today';
    if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
  };

  return (
    <div className="min-h-screen bg-background text-foreground pb-20">
      <div className="max-w-2xl mx-auto p-6">
        <button onClick={() => setLocation('/dashboard')} className="text-muted-foreground text-sm mb-6 flex items-center gap-1">
          <i className="ti ti-arrow-left" style={{fontSize:"1rem"}} /> Back to Dashboard
        </button>
        <h1 className="text-2xl font-bold mb-6">Budget</h1>

        {/* Yesterday nudge */}
        {data && !data.yesterday_logged && (
          <div className="mb-4 p-3 rounded-lg bg-warning/10 border border-warning/30 text-sm text-warning flex items-center gap-2">
            <i className="ti ti-alert-circle" style={{fontSize:"1rem"}} />
            You haven't logged yesterday's spend — add it now?
          </div>
        )}

        {/* Quick Entry */}
        <Card className="p-5 border-card-border bg-card mb-6">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <i className="ti ti-plus" style={{fontSize:"1rem"}} /> Log Today's Spend
          </h2>
          <div className="space-y-3">
            <input
              type="number"
              placeholder="Amount (Rs.)"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand"
            />
            <div className="flex flex-wrap gap-2">
              {categories.map(cat => (
                <button key={cat}
                  onClick={() => setCategory(cat)}
                  className={cn("px-3 py-1 rounded-full text-xs font-medium border transition-colors flex items-center gap-1",
                    category === cat ? "bg-brand text-white border-brand" : "border-border text-muted-foreground hover:text-foreground"
                  )}>
                  <i className={cn("ti", CATEGORY_ICONS[cat])} style={{fontSize:"0.75rem"}} />
                  {CATEGORY_LABELS[cat]}
                </button>
              ))}
            </div>
            <input
              type="text"
              placeholder="Note (optional)"
              value={note}
              onChange={e => setNote(e.target.value)}
              className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand"
            />
            <Button onClick={handleSubmit} disabled={submitting} className="w-full">
              {success ? '✓ Logged!' : submitting ? 'Logging...' : 'Log Spend'}
            </Button>
          </div>
        </Card>

        {/* Monthly Summary */}
        <Card className="p-5 border-card-border bg-card mb-6">
          <h2 className="font-semibold mb-4">This Month's Summary</h2>
          {loading ? <p className="text-muted-foreground text-sm">Loading...</p> : (
            <div className="space-y-2">
              <div className="flex justify-between text-sm font-semibold border-b border-border/30 pb-2 mb-3">
                <span>Total Spent</span>
                <span>{formatRupee(data?.total_spent || 0)}</span>
              </div>
              {data?.by_category?.map((cat: any, i: number) => (
                <div key={i} className="flex justify-between items-center text-sm">
                  <div className="flex items-center gap-2">
                    <i className={cn("ti", CATEGORY_ICONS[cat.category] || "ti-dots")} style={{fontSize:"0.9rem"}} />
                    <span className="text-muted-foreground">{CATEGORY_LABELS[cat.category] || cat.category}</span>
                  </div>
                  <span>{formatRupee(cat.spent)}</span>
                </div>
              ))}
              {(!data?.by_category?.length) && (
                <p className="text-muted-foreground text-sm">No entries yet this month.</p>
              )}
            </div>
          )}
        </Card>

        {/* Daily Spend Log */}
        <Card className="p-5 border-card-border bg-card">
          <h2 className="font-semibold mb-4">Daily Spend Log</h2>
          {loading ? <p className="text-muted-foreground text-sm">Loading...</p> : (
            <div className="space-y-4">
              {data?.by_date?.map((day: any, i: number) => (
                <div key={i}>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-semibold">{formatDate(day.date)}</span>
                    <span className="text-xs text-muted-foreground">
                      {formatRupee(day.entries.reduce((sum: number, e: any) => sum + parseFloat(e.amount), 0))}
                    </span>
                  </div>
                  <div className="space-y-2 pl-2 border-l border-border/30">
                    {day.entries.map((entry: any, j: number) => (
                      <div key={j} className="flex justify-between items-center text-sm">
                        <div className="flex items-center gap-2">
                          <i className={cn("ti", CATEGORY_ICONS[entry.category] || "ti-dots")} style={{fontSize:"0.9rem"}} />
                          <span>{CATEGORY_LABELS[entry.category] || entry.category}</span>
                          {entry.note && <span className="text-xs text-muted-foreground">· {entry.note}</span>}
                        </div>
                        <span className="font-medium">{formatRupee(entry.amount)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              {(!data?.by_date?.length) && (
                <p className="text-muted-foreground text-sm">No transactions logged yet — tap + to add one.</p>
              )}
            </div>
          )}
        </Card>
      </div>

      {/* Mobile Bottom Nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur-md border-t border-border/50 flex items-center justify-around px-2 py-2 z-50">
        <button onClick={() => setLocation('/dashboard')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-layout-dashboard" style={{fontSize:"1.2rem"}} />
          <span className="text-xs">Dashboard</span>
        </button>
        <button onClick={() => setLocation('/budget')} className="flex flex-col items-center gap-1 px-3 py-1 text-brand">
          <i className="ti ti-wallet" style={{fontSize:"1.2rem"}} />
          <span className="text-xs font-medium">Budget</span>
        </button>
        <button onClick={() => setLocation('/invest')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-chart-line" style={{fontSize:"1.2rem"}} />
          <span className="text-xs">Invest</span>
        </button>
        <button onClick={() => setLocation('/tax')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-receipt-tax" style={{fontSize:"1.2rem"}} />
          <span className="text-xs">Tax</span>
        </button>
        <button onClick={() => setLocation('/goals')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-target" style={{fontSize:"1.2rem"}} />
          <span className="text-xs">Goals</span>
        </button>
      </nav>
    </div>
  );
}
