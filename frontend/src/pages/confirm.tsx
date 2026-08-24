import { useState, useEffect, useRef } from 'react';
import { useLocation } from 'wouter';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { API_BASE, formatRupee } from '@/lib/helpers';
import { Input } from '@/components/ui/input';

export default function Confirm() {
  const [, setLocation] = useLocation();
  const [data, setData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [editingField, setEditingField] = useState<string | null>(null);
  const editInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const saved = localStorage.getItem('wg_onboard_preview');
    if (!saved) {
      setLocation('/onboarding');
      return;
    }
    setData(JSON.parse(saved));
  }, [setLocation]);

  useEffect(() => {
    if (editingField && editInputRef.current) {
      editInputRef.current.focus();
    }
  }, [editingField]);

  if (!data) return null;

  const req = data.req;
  const res = data.res;
  const disposable = req.salary - req.rent_emi - req.expenses;

  const handleEdit = (field: string) => {
    setEditingField(field);
  };

  const handleSaveEdit = (field: string, val: string) => {
    const num = Number(val);
    if (!isNaN(num)) {
      const updatedReq = { ...req, [field]: num };
      const updatedData = { ...data, req: updatedReq };
      setData(updatedData);
      localStorage.setItem('wg_onboard_preview', JSON.stringify(updatedData));
    }
    setEditingField(null);
  };

  const handleConfirm = async () => {
    setIsLoading(true);
    try {
      const payload = { ...req, action: "confirm" };
      await fetch(`${API_BASE}/onboard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      // Once confirmed, clear preview and go to dashboard
      localStorage.removeItem('wg_onboard_preview');
      setLocation('/dashboard');
    } catch (err) {
      console.error(err);
      setIsLoading(false);
    }
  };

  const renderEditableNumber = (field: string, value: number, label: string) => {
    const isEditing = editingField === field;

    return (
      <div className="flex justify-between items-center py-3 border-b border-border/50 last:border-0">
        <span className="text-muted-foreground">{label}</span>
        {isEditing ? (
          <Input
            ref={editInputRef}
            type="number"
            defaultValue={value}
            className="w-32 h-8 text-right bg-background border-border"
            onBlur={(e) => handleSaveEdit(field, e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSaveEdit(field, e.currentTarget.value);
              if (e.key === 'Escape') setEditingField(null);
            }}
          />
        ) : (
          <span 
            className="font-medium cursor-pointer hover:text-brand transition-colors decoration-dashed underline underline-offset-4 decoration-border"
            onClick={() => handleEdit(field)}
          >
            {formatRupee(value)}
          </span>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-background flex flex-col items-center py-12 px-4 text-foreground">
      <div className="w-full max-w-lg space-y-6">
        
        <div className="flex items-center space-x-3 mb-8">
          <div className="w-10 h-10 bg-success/20 text-success rounded-full flex items-center justify-center">
            <i className="ti ti-circle-check" style={{fontSize: "24px"}} />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Analysis Complete</h1>
            <p className="text-sm text-muted-foreground">Review your profile</p>
          </div>
        </div>

        <Card className="p-6 border-brand/20 bg-card shadow-lg relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-1 bg-brand" />
          <p className="text-sm leading-relaxed text-foreground/90 font-medium">
            {res.summary || res.parsed?.summary || "Based on your inputs, we've prepared a baseline financial plan."}
          </p>
        </Card>

        <Card className="border-card-border bg-card shadow-sm">
          <div className="p-4 border-b border-border">
            <h2 className="font-semibold text-sm uppercase tracking-wider text-muted-foreground">Your Numbers</h2>
          </div>
          <div className="px-6 py-2">
            {renderEditableNumber('salary', req.salary, 'Monthly Salary')}
            {renderEditableNumber('rent_emi', req.rent_emi, 'Rent & EMI')}
            {renderEditableNumber('expenses', req.expenses, 'Other Expenses')}
            
            <div className="flex justify-between items-center py-4 border-b border-border/50">
              <span className="text-muted-foreground">Disposable Income</span>
              <span className={`font-semibold ${disposable > 0 ? 'text-success' : 'text-destructive'}`}>
                {formatRupee(disposable)}
              </span>
            </div>

            <div className="flex justify-between items-center py-4 border-b border-border/50">
              <span className="text-muted-foreground">Risk Appetite</span>
              <span className="font-medium capitalize">{req.risk_appetite}</span>
            </div>

            <div className="flex justify-between items-center py-4">
              <span className="text-muted-foreground">Goal: {req.goal_name}</span>
              <span className="font-medium">{formatRupee(req.goal_amount)}</span>
            </div>
          </div>
        </Card>

        <div className="flex flex-col sm:flex-row gap-4 pt-4">
          <Button 
            variant="outline" 
            onClick={() => setLocation('/onboarding')} 
            className="flex-1 border-border"
          >
            <i className="ti ti-arrow-left mr-2 h-4 w-4" style={{fontSize: "1rem"}} />
            Edit details
          </Button>
          <Button 
            onClick={handleConfirm} 
            className="flex-1 bg-primary hover:bg-primary/90"
            disabled={isLoading}
          >
            {isLoading && <i className="ti ti-loader-2 mr-2 h-4 w-4 animate-spin" style={{fontSize: "1rem"}} />}
            Looks good, continue
          </Button>
        </div>

      </div>
    </div>
  );
}
