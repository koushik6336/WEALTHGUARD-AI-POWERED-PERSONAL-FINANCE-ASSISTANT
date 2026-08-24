import { useState, useEffect } from 'react';
import { useLocation } from 'wouter';
import { API_BASE, formatRupee, getGreeting } from '@/lib/helpers';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

interface DashboardData {
  user_id: string;
  name: string;
  is_new: boolean;
  health_score: number;
  summary_line: string;
  alert_line: string | null;
  budget: {
    categories: Array<{ category: string; limit: number; spent: number; pct_used: number }>;
    total_limit: number; total_spent: number; overall_pct: number;
    days_left_in_month: number; worst_category: string;
    worst_category_pct: number; over_budget_amount: number;
  };
  investment: {
    by_type: Array<{ type: string; invested: number; current_value: number; gain_pct: number }>;
    total_invested: number; total_current_value: number; total_gain_pct: number;
    allocation: Array<{ type: string; pct_of_portfolio: number }>;
  };
  goals: Array<{ goal_name: string; target_amount: number; current_amount: number; progress_pct: number; target_date: string; required_monthly_saving: number }>;
  transactions: Array<{ merchant: string; category: string; amount: number; date: string }>;
  tax: { annual_salary: number; invested_80c: number; remaining_80c: number };
  fraud: { clear: boolean; alert_count: number; total_checked: number };
}



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
const categoryLabel = (cat: string) => CATEGORY_LABELS[cat] || cat.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());

export default function Dashboard() {
  const [, setLocation] = useLocation();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Chat simulator
  const [chatInput, setChatInput] = useState('');
  const [chatResult, setChatResult] = useState<string | null>(null);
  const [chatLoading, setChatLoading] = useState(false);

  const userId = localStorage.getItem('wg_active_user');
  const userName = localStorage.getItem('wg_active_name') || 'User';

  useEffect(() => {
    if (!userId) {
      setLocation('/login');
      return;
    }

    const fetchData = async () => {
      try {
        const res = await fetch(`${API_BASE}/dashboard-full?user_id=${userId}`);
        if (!res.ok) throw new Error('Failed to fetch dashboard data');
        const json = await res.json();
        
        if (json.is_new) {
          setLocation('/onboarding');
          return;
        }
        
        setData(json);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [userId, setLocation]);

  const handleLogout = () => {
    localStorage.removeItem('wg_active_user');
    localStorage.removeItem('wg_active_name');
    localStorage.removeItem('wg_onboard_preview');
    setLocation('/login');
  };

  const handleSimulatorChat = async (e?: React.FormEvent, presetPrompt?: string) => {
    if (e) e.preventDefault();
    const prompt = presetPrompt || chatInput;
    if (!prompt) return;

    setChatLoading(true);
    setChatResult(null);
    if (!presetPrompt) setChatInput('');

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, message: prompt })
      });
      const json = await res.json();
      setChatResult(json.response || json.reply || "I analyzed that scenario, but couldn't generate a clear insight.");
    } catch (err) {
      setChatResult("Failed to reach simulator. Please try again later.");
    } finally {
      setChatLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 85) return 'text-emerald-500 border-emerald-500';
    if (score >= 70) return 'text-success border-success';
    if (score >= 55) return 'text-orange-400 border-orange-400';
    if (score >= 40) return 'text-warning border-warning';
    return 'text-destructive border-destructive';
  };
  const getScoreBg = (score: number) => {
    if (score >= 85) return 'bg-emerald-500/10';
    if (score >= 70) return 'bg-success/10';
    if (score >= 55) return 'bg-orange-400/10';
    if (score >= 40) return 'bg-warning/10';
    return 'bg-destructive/10';
  };
  const getScoreLabel = (score: number) => {
    if (score >= 85) return 'Excellent';
    if (score >= 70) return 'Good';
    if (score >= 55) return 'Needs Attention';
    if (score >= 40) return 'Poor';
    return 'Danger Zone';
  };
  const getScoreDesc = (score: number) => {
    if (score >= 85) return "Excellent! You're managing your finances very well.";
    if (score >= 70) return "You're in good financial shape.";
    if (score >= 55) return 'A few areas need your attention.';
    if (score >= 40) return 'Your finances need significant improvement.';
    return 'Your finances need immediate attention.';
  };

  const getIconForInvestment = (type: string) => {
    const t = type.toLowerCase();
    if (t.includes('mutual') || t.includes('stock')) return <i className="ti ti-chart-line" style={{fontSize: "18px"}} />;
    if (t.includes('gold')) return <i className="ti ti-building-bank" style={{fontSize: "18px"}} />;
    return <i className="ti ti-building-bank" style={{fontSize: "18px"}} />;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background p-4 md:p-8 space-y-6">
        <header className="flex justify-between items-center mb-8">
          <Skeleton className="h-10 w-32 bg-card-border" />
          <Skeleton className="h-10 w-10 rounded-full bg-card-border" />
        </header>
        <div className="space-y-4">
          <Skeleton className="h-24 w-full md:w-1/2 bg-card-border" />
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-32 bg-card-border" />)}
          </div>
          <div className="grid md:grid-cols-2 gap-6 mt-6">
            <Skeleton className="h-64 bg-card-border" />
            <Skeleton className="h-64 bg-card-border" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="p-6 text-center space-y-4 border-destructive/20 max-w-sm">
          <i className="ti ti-alert-triangle w-12 h-12 text-destructive mx-auto" style={{fontSize: "3rem"}} />
          <h2 className="text-lg font-semibold">Could not load dashboard</h2>
          <p className="text-muted-foreground text-sm">{error || "Unknown error occurred"}</p>
          <Button onClick={() => window.location.reload()} variant="outline" className="w-full">
            Retry
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground pb-20">
      {/* Top Nav */}
      <nav className="sticky top-0 z-50 bg-background/80 backdrop-blur-md border-b border-border/50 px-4 md:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-brand rounded-md flex items-center justify-center">
            <span className="text-white font-bold text-sm font-serif">W</span>
          </div>
          <span className="font-semibold tracking-tight hidden sm:inline-block">WealthGuard</span>
        </div>

        <div className="hidden md:flex items-center gap-6 text-sm font-medium text-muted-foreground">
          <span className="text-foreground cursor-pointer" onClick={() => setLocation('/dashboard')}>Dashboard</span>
          <span className="hover:text-foreground cursor-pointer transition-colors" onClick={() => setLocation('/budget')}>Budget</span>
          <span className="hover:text-foreground cursor-pointer transition-colors" onClick={() => setLocation('/invest')}>Invest</span>
          <span className="hover:text-foreground cursor-pointer transition-colors" onClick={() => setLocation('/tax')}>Tax</span>
          <span className="hover:text-foreground cursor-pointer transition-colors" onClick={() => setLocation('/goals')}>Goals</span>
        </div>

        <div className="flex items-center gap-4">
          <Popover>
            <PopoverTrigger asChild>
              <button className="w-9 h-9 rounded-full bg-secondary border border-border flex items-center justify-center text-sm font-medium hover:ring-2 hover:ring-brand/50 transition-all">
                {userName.charAt(0).toUpperCase()}
              </button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-48 p-2">
              <div className="px-2 py-1.5 mb-1 border-b border-border">
                <p className="font-medium truncate">{userName}</p>
                <p className="text-xs text-muted-foreground truncate">{userId}</p>
              </div>
              <Button variant="ghost" className="w-full justify-start text-destructive hover:text-destructive hover:bg-destructive/10" onClick={handleLogout}>
                <i className="ti ti-logout mr-2 h-4 w-4" style={{fontSize: "1rem"}} />
                Sign out
              </Button>
            </PopoverContent>
          </Popover>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-4 md:px-8 py-8 space-y-8">
        
        {/* Header section */}
        <section className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">
            {getGreeting()}, {userName.split(' ')[0]}
          </h1>
          <p className="text-muted-foreground">Here is your financial snapshot for today.</p>
        </section>

        {/* Alert Banner */}
        {data.alert_line && (
          <div className="bg-destructive/10 border border-destructive/20 text-destructive-foreground p-4 rounded-lg flex items-start gap-3 shadow-sm">
            <i className="ti ti-alert-triangle w-5 h-5 text-destructive mt-0.5 shrink-0" style={{fontSize: "1.25rem"}} />
            <p className="text-sm font-medium text-destructive/90">{data.alert_line}</p>
          </div>
        )}

        {/* Health Score & Quick Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          
          <Card className="md:col-span-2 p-5 border-card-border bg-card flex items-center gap-6 hover:border-brand/30 transition-colors cursor-pointer group">
            <div className={cn("w-20 h-20 rounded-full border-4 flex items-center justify-center shrink-0", getScoreColor(data.health_score), getScoreBg(data.health_score))}>
              <span className="text-2xl font-bold">{data.health_score}</span>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-semibold text-lg group-hover:text-brand transition-colors">Financial Health</h3>
                <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full", getScoreColor(data.health_score), getScoreBg(data.health_score))}>{getScoreLabel(data.health_score)}</span>
                <Popover>
                  <PopoverTrigger asChild>
                    <button className="text-muted-foreground hover:text-foreground transition-colors">
                      <i className="ti ti-info-circle" style={{fontSize:"1rem"}} />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent className="w-64 p-4 bg-card border-card-border text-sm">
                    <p className="font-semibold mb-3">Score Bands</p>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-emerald-500 shrink-0"></span><span>85–100 <span className="text-muted-foreground">Excellent</span></span></div>
                      <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-success shrink-0"></span><span>70–84 <span className="text-muted-foreground">Good</span></span></div>
                      <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-orange-400 shrink-0"></span><span>55–69 <span className="text-muted-foreground">Needs Attention</span></span></div>
                      <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-warning shrink-0"></span><span>40–54 <span className="text-muted-foreground">Poor</span></span></div>
                      <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-destructive shrink-0"></span><span>0–39 <span className="text-muted-foreground">Danger Zone</span></span></div>
                    </div>
                    <p className="text-xs text-muted-foreground mt-3">Score is calculated based on your budget usage, savings rate, investment activity, and goal progress.</p>
                  </PopoverContent>
                </Popover>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">{getScoreDesc(data.health_score)}</p>
            </div>
          </Card>

          <Card className="p-5 border-card-border bg-card flex flex-col justify-between">
            <div className="flex justify-between items-start mb-4">
              <div className="p-2 bg-secondary rounded-md">
                <i className="ti ti-chart-pie w-4 h-4 text-muted-foreground" style={{fontSize: "1rem"}} />
              </div>
              <span className="text-xs font-medium text-muted-foreground uppercase">Budget</span>
            </div>
            <div>
              <div className="flex items-baseline gap-2">
                <span className={cn("text-2xl font-bold", data.budget.overall_pct > 100 ? "text-destructive" : "")}>
                  {data.budget.overall_pct}%
                </span>
                <span className="text-sm text-muted-foreground">used</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1 truncate">
                {data.budget.days_left_in_month} days left
              </p>
            </div>
          </Card>

          <Card className="p-5 border-card-border bg-card flex flex-col justify-between">
            <div className="flex justify-between items-start mb-4">
              <div className="p-2 bg-secondary rounded-md">
                <i className="ti ti-activity w-4 h-4 text-muted-foreground" style={{fontSize: "1rem"}} />
              </div>
              <span className="text-xs font-medium text-muted-foreground uppercase">Returns</span>
            </div>
            <div>
              <div className="flex items-baseline gap-2">
                <span className={cn("text-2xl font-bold", data.investment.total_gain_pct >= 0 ? "text-success" : "text-destructive")}>
                  {data.investment.total_gain_pct > 0 ? '+' : ''}{data.investment.total_gain_pct}%
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-1 truncate">
                Overall portfolio
              </p>
            </div>
          </Card>

          <Card className="p-5 border-card-border bg-card flex flex-col justify-between">
            <div className="flex justify-between items-start mb-4">
              <div className="p-2 bg-secondary rounded-md">
                <i className="ti ti-building-bank w-4 h-4 text-muted-foreground" style={{fontSize: "1rem"}} />
              </div>
              <span className="text-xs font-medium text-muted-foreground uppercase">Tax 80C</span>
            </div>
            <div>
              <div className="flex items-baseline gap-1">
                <span className="text-lg font-bold">{formatRupee(data.tax.remaining_80c)}</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">Room left</p>
            </div>
          </Card>

          <Card className="p-5 border-card-border bg-card flex flex-col justify-between">
            <div className="flex justify-between items-start mb-4">
              <div className="p-2 bg-secondary rounded-md">
                <i className="ti ti-shield-check w-4 h-4 text-muted-foreground" style={{fontSize: "1rem"}} />
              </div>
              <span className="text-xs font-medium text-muted-foreground uppercase">Security</span>
            </div>
            <div>
              <div className="flex items-baseline gap-2">
                <span className={cn("text-lg font-bold", data.fraud.clear ? "text-success" : "text-destructive")}>
                  {data.fraud.clear ? "Clear" : `${data.fraud.alert_count} Alerts`}
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-1 truncate">
                {data.fraud.total_checked} txns checked
              </p>
              <button onClick={() => setLocation('/security')} className="text-xs text-brand mt-1 hover:underline">
                View login history
              </button>
            </div>
          </Card>

          <Card className="md:col-span-2 p-5 bg-gradient-to-br from-primary/10 to-transparent border-primary/20 flex items-center justify-between cursor-pointer hover:border-primary/40 transition-colors">
            <div>
              <h3 className="font-semibold text-lg text-primary mb-1">Full Report Available</h3>
              <p className="text-sm text-muted-foreground">Deep dive into your month's finances.</p>
            </div>
            <Button variant="secondary" className="bg-primary/20 text-primary hover:bg-primary/30 shrink-0">
              <span onClick={() => setLocation('/report')} className="cursor-pointer hover:text-brand transition-colors">View Report</span>
            </Button>
          </Card>

        </div>

        <div className="grid md:grid-cols-2 gap-8">
          
          {/* Spending Column */}
          <div className="space-y-6">
            <div className="flex items-center justify-between border-b border-border/50 pb-2">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <i className="ti ti-credit-card w-5 h-5 text-muted-foreground" style={{fontSize: "1.25rem"}} />
                Budget vs Spend
              </h2>
            </div>
            
            <Card className="p-5 border-card-border bg-card space-y-5">
              {data.budget.categories.map((cat, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="font-medium">{categoryLabel(cat.category)}</span>
                    <span className="text-muted-foreground">
                      <span className={cat.pct_used > 100 ? "text-destructive font-medium" : "text-foreground"}>
                        {formatRupee(cat.spent)}
                      </span>
                      {" / "}{formatRupee(cat.limit)}
                    </span>
                  </div>
                  <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                    <div 
                      className={cn("h-full rounded-full transition-all duration-1000", cat.pct_used > 100 ? "bg-destructive" : "bg-primary")}
                      style={{ width: `${Math.min(cat.pct_used, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </Card>

            <div className="flex items-center justify-between border-b border-border/50 pb-2 mt-8">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <i className="ti ti-activity w-5 h-5 text-muted-foreground" style={{fontSize: "1.25rem"}} />
                Recent Transactions
              </h2>
            </div>

            <Card className="border-card-border bg-card divide-y divide-border/50">
              {data.transactions.slice(0, 5).map((txn, i) => (
                <div key={i} className="p-4 flex justify-between items-center hover:bg-secondary/20 transition-colors">
                  <div>
                    <p className="font-medium text-sm">{txn.merchant}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-muted-foreground">{txn.date}</span>
                      <span className="w-1 h-1 bg-border rounded-full" />
                      <span className="text-xs text-muted-foreground capitalize">{txn.category}</span>
                    </div>
                  </div>
                  <span className="font-medium text-sm text-foreground">
                    {formatRupee(txn.amount)}
                  </span>
                </div>
              ))}
            </Card>
          </div>

          {/* Investments & Goals Column */}
          <div className="space-y-6">
            
            <div className="flex items-center justify-between border-b border-border/50 pb-2">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <i className="ti ti-chart-line w-5 h-5 text-muted-foreground" style={{fontSize: "1.25rem"}} />
                Your Investments
              </h2>
              <span className="text-sm font-medium">
                Total: {formatRupee(data.investment.total_current_value)}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {data.investment.by_type.map((inv, i) => (
                <Card key={i} className="p-4 border-card-border bg-card hover:border-border transition-colors">
                  <div className="flex justify-between items-start mb-3">
                    <div className="p-2 bg-secondary rounded-lg">
                      {getIconForInvestment(inv.type)}
                    </div>
                    <span className={cn("text-xs font-medium px-2 py-1 rounded-full", inv.gain_pct >= 0 ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive")}>
                      {inv.gain_pct > 0 ? '+' : ''}{inv.gain_pct}%
                    </span>
                  </div>
                  <h3 className="text-sm font-medium text-muted-foreground capitalize mb-1">{inv.type}</h3>
                  <p className="text-lg font-bold">{formatRupee(inv.current_value)}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Invested: {formatRupee(inv.invested)}
                  </p>
                </Card>
              ))}
            </div>

            <div className="flex items-center justify-between border-b border-border/50 pb-2 mt-8">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <i className="ti ti-target-arrow w-5 h-5 text-muted-foreground" style={{fontSize: "1.25rem"}} />
                Active Goals
              </h2>
            </div>

            <div className="space-y-4">
              {data.goals.map((goal, i) => {
                const targetDate = new Date(goal.target_date);
                const today = new Date();
                const monthsDiff = (targetDate.getFullYear() - today.getFullYear()) * 12 + (targetDate.getMonth() - today.getMonth());
                
                // Very rough estimation for "on track" based on progress vs time left
                // Assuming max time was 60 months, just an example heuristic
                const expectedPct = Math.max(0, Math.min(100, 100 - (monthsDiff * 1.5)));
                const isBehind = goal.progress_pct < expectedPct - 10;

                return (
                  <Card key={i} className="p-5 border-card-border bg-card">
                    <div className="flex justify-between items-center mb-3">
                      <h3 className="font-semibold text-sm">{goal.goal_name}</h3>
                      <span className="text-sm font-bold">{goal.progress_pct}%</span>
                    </div>
                    <div className="h-2 w-full bg-secondary rounded-full overflow-hidden mb-3">
                      <div 
                        className="h-full bg-brand rounded-full transition-all duration-1000"
                        style={{ width: `${goal.progress_pct}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">
                        {formatRupee(goal.current_amount)} / {formatRupee(goal.target_amount)}
                      </span>
                      <span className={cn("font-medium", isBehind ? "text-warning" : "text-success")}>
                        {isBehind ? "Slightly behind" : "On track"}
                      </span>
                    </div>
                  </Card>
                );
              })}
            </div>

            {/* AI Simulator */}
            <Card className="mt-8 border-brand/30 bg-card overflow-hidden">
              <div className="p-4 bg-brand/5 border-b border-brand/10">
                <h3 className="font-semibold flex items-center gap-2 text-brand">
                  <i className="ti ti-message-circle w-4 h-4" style={{fontSize: "1rem"}} />
                  What-if Simulator
                </h3>
                <button onClick={() => setLocation('/chat')} className="text-xs text-muted-foreground hover:text-brand transition-colors">
                  Open full chat →
                </button>
              </div>
              <div className="p-5 space-y-4">
                <button 
                  onClick={(e) => handleSimulatorChat(e, "What if I cut shopping by Rs.2,000 a month?")}
                  className="w-full text-left p-3 rounded-lg border border-border bg-secondary/30 hover:bg-secondary/80 transition-colors text-sm text-muted-foreground hover:text-foreground"
                >
                  <span className="text-brand mr-2">Try it:</span> 
                  "What if I cut shopping by Rs.2,000 a month?"
                </button>
                
                <form onSubmit={handleSimulatorChat} className="flex gap-2">
                  <Input 
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask another scenario..."
                    className="bg-background border-border"
                  />
                  <Button type="submit" disabled={chatLoading || (!chatInput && !chatLoading)} className="shrink-0 bg-brand hover:bg-brand/90 text-white">
                    {chatLoading ? <i className="ti ti-loader-2 w-4 h-4 animate-spin" style={{fontSize: "1rem"}} /> : <i className="ti ti-send w-4 h-4" style={{fontSize: "1rem"}} />}
                  </Button>
                </form>

                {chatResult && (
                  <div className="mt-4 p-4 rounded-lg bg-secondary/50 border border-border text-sm leading-relaxed animate-in fade-in slide-in-from-bottom-2">
                    {chatResult}
                  </div>
                )}
              </div>
            </Card>

          </div>
        </div>
      </main>

    </div>
  );
}
