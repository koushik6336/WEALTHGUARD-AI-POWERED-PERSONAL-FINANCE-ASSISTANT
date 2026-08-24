import { useState, useEffect } from 'react';
import { useLocation } from 'wouter';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { API_BASE } from '@/lib/helpers';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { motion, AnimatePresence } from 'framer-motion';

const ANALYSIS_MESSAGES = [
  "Analyzing your income and expenses...",
  "Calculating your financial health score...",
  "Preparing your personalized plan..."
];

export default function Onboarding() {
  const [, setLocation] = useLocation();
  const [step, setStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [analysisMsgIndex, setAnalysisMsgIndex] = useState(0);
  
  // Form state
  const [salary, setSalary] = useState('');
  const [rent, setRent] = useState('');
  const [expenses, setExpenses] = useState('');
  const [risk, setRisk] = useState('medium');
  const [goalName, setGoalName] = useState('');
  const [goalAmount, setGoalAmount] = useState('');

  useEffect(() => {
    const userId = localStorage.getItem('wg_active_user');
    if (!userId) {
      setLocation('/login');
      return;
    }

    // Try to load existing data
    const saved = localStorage.getItem('wg_onboard_preview');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.req) {
          setSalary(parsed.req.salary?.toString() || '');
          setRent(parsed.req.rent_emi?.toString() || '');
          setExpenses(parsed.req.expenses?.toString() || '');
          setRisk(parsed.req.risk_appetite || 'medium');
          setGoalName(parsed.req.goal_name || '');
          setGoalAmount(parsed.req.goal_amount?.toString() || '');
        }
      } catch (e) {
        // ignore
      }
    }
  }, [setLocation]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (isLoading) {
      interval = setInterval(() => {
        setAnalysisMsgIndex(prev => (prev + 1) % ANALYSIS_MESSAGES.length);
      }, 1500);
    }
    return () => clearInterval(interval);
  }, [isLoading]);

  const handleNext = () => {
    if (salary && rent && expenses) {
      setStep(2);
    }
  };

  const handleAnalyze = async () => {
    if (!goalName || !goalAmount) return;

    const userId = localStorage.getItem('wg_active_user');
    const name = localStorage.getItem('wg_active_name');

    setIsLoading(true);

    const payload = {
      user_id: userId,
      name,
      salary: Number(salary),
      rent_emi: Number(rent),
      expenses: Number(expenses),
      goal_name: goalName,
      goal_amount: Number(goalAmount),
      risk_appetite: risk,
      action: "preview"
    };

    try {
      const res = await fetch(`${API_BASE}/onboard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const data = await res.json();
      
      localStorage.setItem('wg_onboard_preview', JSON.stringify({
        req: payload,
        res: data
      }));
      
      setTimeout(() => {
        setLocation('/confirm');
      }, 1000); // Give it a little delay so the user sees the animation
      
    } catch (err) {
      console.error(err);
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4 text-foreground">
        <div className="w-16 h-16 relative flex items-center justify-center mb-8">
          <div className="absolute inset-0 rounded-full border-t-2 border-brand animate-spin"></div>
          <div className="w-8 h-8 bg-brand rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm font-serif">W</span>
          </div>
        </div>
        
        <div className="h-8 relative overflow-hidden w-full max-w-sm text-center">
          <AnimatePresence mode="wait">
            <motion.p
              key={analysisMsgIndex}
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: -20, opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="text-muted-foreground absolute inset-x-0"
            >
              {ANALYSIS_MESSAGES[analysisMsgIndex]}
            </motion.p>
          </AnimatePresence>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4 text-foreground">
      <div className="w-full max-w-md space-y-8">
        <div className="flex flex-col items-center text-center">
          <h1 className="text-2xl font-bold tracking-tight">Let's set up your profile</h1>
          <p className="text-muted-foreground mt-2">Step {step} of 2</p>
        </div>

        <Card className="p-6 border-card-border bg-card shadow-lg">
          {step === 1 ? (
            <div className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="salary">Monthly Salary (Rs.)</Label>
                <Input 
                  id="salary" 
                  type="number"
                  placeholder="e.g. 100000" 
                  value={salary}
                  onChange={(e) => setSalary(e.target.value)}
                  className="bg-background border-border"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rent">Monthly Rent / EMI (Rs.)</Label>
                <Input 
                  id="rent" 
                  type="number"
                  placeholder="e.g. 25000" 
                  value={rent}
                  onChange={(e) => setRent(e.target.value)}
                  className="bg-background border-border"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="expenses">Other Monthly Expenses (Rs.)</Label>
                <Input 
                  id="expenses" 
                  type="number"
                  placeholder="e.g. 30000" 
                  value={expenses}
                  onChange={(e) => setExpenses(e.target.value)}
                  className="bg-background border-border"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="risk">Risk Appetite</Label>
                <Select value={risk} onValueChange={setRisk}>
                  <SelectTrigger className="bg-background border-border">
                    <SelectValue placeholder="Select risk level" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low (Conservative)</SelectItem>
                    <SelectItem value="medium">Medium (Balanced)</SelectItem>
                    <SelectItem value="high">High (Aggressive)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button 
                onClick={handleNext} 
                className="w-full" 
                disabled={!salary || !rent || !expenses}
              >
                Continue
              </Button>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="goalName">Top Financial Goal</Label>
                <Input 
                  id="goalName" 
                  placeholder="e.g. Emergency Fund, House Downpayment" 
                  value={goalName}
                  onChange={(e) => setGoalName(e.target.value)}
                  className="bg-background border-border"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="goalAmount">Target Amount (Rs.)</Label>
                <Input 
                  id="goalAmount" 
                  type="number"
                  placeholder="e.g. 500000" 
                  value={goalAmount}
                  onChange={(e) => setGoalAmount(e.target.value)}
                  className="bg-background border-border"
                />
              </div>
              
              <div className="flex gap-3">
                <Button variant="outline" onClick={() => setStep(1)} className="w-1/3">
                  Back
                </Button>
                <Button 
                  onClick={handleAnalyze} 
                  className="flex-1"
                  disabled={!goalName || !goalAmount}
                >
                  Analyze
                </Button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
