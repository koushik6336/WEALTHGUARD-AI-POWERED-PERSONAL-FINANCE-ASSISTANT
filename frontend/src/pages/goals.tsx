import { useState, useEffect } from 'react';
import { useLocation } from 'wouter';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { API_BASE, formatRupee } from '@/lib/helpers';
import { cn } from '@/lib/utils';

const PRESETS = [
  { type: 'emergency_fund', label: 'Emergency Fund', icon: 'ti-shield' },
  { type: 'buy_car', label: 'Buy a Car', icon: 'ti-car' },
  { type: 'buy_house', label: 'Buy a House', icon: 'ti-home' },
  { type: 'education', label: 'Higher Education', icon: 'ti-school' },
  { type: 'retirement', label: 'Retirement', icon: 'ti-beach' },
  { type: 'wedding', label: 'Wedding', icon: 'ti-heart' },
  { type: 'vacation', label: 'Vacation / Travel', icon: 'ti-plane' },
  { type: 'debt_payoff', label: 'Debt Payoff', icon: 'ti-credit-card-off' },
  { type: 'gadget', label: 'Gadget / Big Purchase', icon: 'ti-device-mobile' },
  { type: 'custom', label: 'Create Your Own', icon: 'ti-plus' },
];

export default function Goals() {
  const [, setLocation] = useLocation();
  const userId = localStorage.getItem('wg_active_user');
  const [goals, setGoals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [selectedType, setSelectedType] = useState('');
  const [goalName, setGoalName] = useState('');
  const [targetAmount, setTargetAmount] = useState('');
  const [targetDate, setTargetDate] = useState('');
  const [currentAmount, setCurrentAmount] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchGoals = async () => {
    try {
      const res = await fetch(`${API_BASE}/goals?user_id=${userId}`);
      const json = await res.json();
      setGoals(json.goals || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    if (!userId) { setLocation('/login'); return; }
    fetchGoals();
  }, [userId]);

  const handlePresetSelect = (preset: any) => {
    setSelectedType(preset.type);
    setGoalName(preset.type === 'custom' ? '' : preset.label);
    setShowForm(true);
  };

  const handleSubmit = async () => {
    if (!goalName || !targetAmount) return;
    setSubmitting(true);
    try {
      await fetch(`${API_BASE}/goals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          goal_type: selectedType,
          goal_name: goalName,
          target_amount: parseFloat(targetAmount),
          target_date: targetDate || null,
          current_amount: parseFloat(currentAmount || '0')
        })
      });
      setShowForm(false);
      setGoalName('');
      setTargetAmount('');
      setTargetDate('');
      setCurrentAmount('');
      await fetchGoals();
    } catch (e) { console.error(e); }
    finally { setSubmitting(false); }
  };

  const handleUpdateProgress = async (goal: any, newAmount: string) => {
    await fetch(`${API_BASE}/goals`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, goal_name: goal.goal_name, current_amount: parseFloat(newAmount) })
    });
    await fetchGoals();
  };

  return (
    <div className="min-h-screen bg-background text-foreground pb-20">
      <div className="max-w-2xl mx-auto p-6">
        <button onClick={() => setLocation('/dashboard')} className="text-muted-foreground text-sm mb-6 flex items-center gap-1">
          <i className="ti ti-arrow-left" style={{fontSize:"1rem"}} /> Back to Dashboard
        </button>
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Goals</h1>
          <Button onClick={() => setShowForm(!showForm)} size="sm">
            <i className="ti ti-plus mr-1" style={{fontSize:"0.9rem"}} /> Add Goal
          </Button>
        </div>

        {/* Preset Selection */}
        {showForm && !selectedType && (
          <Card className="p-5 border-card-border bg-card mb-6">
            <h2 className="font-semibold mb-4">What are you saving for?</h2>
            <div className="grid grid-cols-2 gap-3">
              {PRESETS.map(preset => (
                <button key={preset.type}
                  onClick={() => handlePresetSelect(preset)}
                  className="flex items-center gap-3 p-3 rounded-lg border border-border hover:border-brand hover:bg-brand/5 transition-colors text-left">
                  <i className={cn("ti", preset.icon, "text-brand")} style={{fontSize:"1.2rem"}} />
                  <span className="text-sm font-medium">{preset.label}</span>
                </button>
              ))}
            </div>
          </Card>
        )}

        {/* Goal Form */}
        {showForm && selectedType && (
          <Card className="p-5 border-card-border bg-card mb-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="font-semibold">Goal Details</h2>
              <button onClick={() => setSelectedType('')} className="text-muted-foreground text-sm">← Back</button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-muted-foreground mb-1 block">Goal Name</label>
                <input type="text" value={goalName} onChange={e => setGoalName(e.target.value)}
                  placeholder="e.g. Emergency Fund"
                  className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
              </div>
              <div>
                <label className="text-sm text-muted-foreground mb-1 block">Target Amount (Rs.)</label>
                <input type="number" value={targetAmount} onChange={e => setTargetAmount(e.target.value)}
                  placeholder="e.g. 100000"
                  className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
              </div>
              <div>
                <label className="text-sm text-muted-foreground mb-1 block">Already Saved (Rs.) — optional</label>
                <input type="number" value={currentAmount} onChange={e => setCurrentAmount(e.target.value)}
                  placeholder="e.g. 10000"
                  className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
              </div>
              <div>
                <label className="text-sm text-muted-foreground mb-1 block">Target Date — optional</label>
                <input type="date" value={targetDate} onChange={e => setTargetDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
              </div>
              <Button onClick={handleSubmit} disabled={submitting || !goalName || !targetAmount} className="w-full">
                {submitting ? 'Creating...' : 'Create Goal'}
              </Button>
            </div>
          </Card>
        )}

        {/* Active Goals */}
        {loading ? <p className="text-muted-foreground text-sm">Loading...</p> : (
          <div className="space-y-4">
            {goals.length === 0 && !showForm && (
              <Card className="p-8 border-card-border bg-card text-center">
                <i className="ti ti-target text-muted-foreground mb-3" style={{fontSize:"2rem"}} />
                <p className="text-muted-foreground mb-4">No goals yet — tap + Add Goal to get started</p>
              </Card>
            )}
            {goals.map((goal, i) => (
              <Card key={i} className="p-5 border-card-border bg-card">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="font-semibold">{goal.goal_name}</h3>
                    {goal.target_date && <p className="text-xs text-muted-foreground">Target: {new Date(goal.target_date).toLocaleDateString('en-IN', {day:'numeric',month:'short',year:'numeric'})}</p>}
                  </div>
                  <span className="text-sm font-medium text-brand">{goal.progress_pct}%</span>
                </div>
                <div className="h-2 w-full bg-secondary rounded-full overflow-hidden mb-3">
                  <div className="h-full bg-brand rounded-full transition-all duration-1000"
                    style={{width: `${Math.min(goal.progress_pct, 100)}%`}} />
                </div>
                <div className="flex justify-between text-sm text-muted-foreground mb-3">
                  <span>Saved: {formatRupee(goal.current_amount)}</span>
                  <span>Target: {formatRupee(goal.target_amount)}</span>
                </div>
                <div className="flex gap-2">
                  <input type="number" placeholder="Update saved amount"
                    className="flex-1 px-3 py-1.5 rounded-md bg-background border border-border text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-brand"
                    onBlur={e => { if (e.target.value) handleUpdateProgress(goal, e.target.value); e.target.value = ''; }} />
                  <Button size="sm" variant="outline" onClick={() => {}}>Update</Button>
                </div>
              </Card>
            ))}
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
        <button onClick={() => setLocation('/tax')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-receipt-tax" style={{fontSize:"1.2rem"}} />
          <span className="text-xs">Tax</span>
        </button>
        <button onClick={() => setLocation('/goals')} className="flex flex-col items-center gap-1 px-3 py-1 text-brand">
          <i className="ti ti-target" style={{fontSize:"1.2rem"}} />
          <span className="text-xs font-medium">Goals</span>
        </button>
      </nav>
    </div>
  );
}
