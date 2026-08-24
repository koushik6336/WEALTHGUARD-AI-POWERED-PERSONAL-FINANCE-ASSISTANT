import { useState, useEffect, useRef } from 'react';
import { useLocation } from 'wouter';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { API_BASE, formatRupee } from '@/lib/helpers';
import { cn } from '@/lib/utils';

export default function Invest() {
  const [, setLocation] = useLocation();
  const userId = localStorage.getItem('wg_active_user');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showCAS, setShowCAS] = useState(false);
  const [schemeName, setSchemeName] = useState('');
  const [amountInvested, setAmountInvested] = useState('');
  const [currentValue, setCurrentValue] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [casPassword, setCasPassword] = useState('');
  const [casFile, setCasFile] = useState<File | null>(null);
  const [casLoading, setCasLoading] = useState(false);
  const [casPreview, setCasPreview] = useState<any[]>([]);
  const [casError, setCasError] = useState('');
  const [casConfirmed, setCasConfirmed] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const fetchData = async () => {
    try {
      const res = await fetch(`${API_BASE}/portfolio-summary?user_id=${userId}`);
      const json = await res.json();
      setData(json);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    if (!userId) { setLocation('/login'); return; }
    fetchData();
  }, [userId]);

  const handleManualSubmit = async () => {
    if (!schemeName || !amountInvested) return;
    setSubmitting(true);
    try {
      await fetch(`${API_BASE}/portfolio-summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, scheme_name: schemeName, amount_invested: parseFloat(amountInvested), current_value: parseFloat(currentValue || amountInvested) })
      });
      setSchemeName(''); setAmountInvested(''); setCurrentValue('');
      setSuccess(true); setShowForm(false);
      await fetchData();
      setTimeout(() => setSuccess(false), 2000);
    } catch (e) { console.error(e); }
    finally { setSubmitting(false); }
  };

  const handleCASUpload = async () => {
    if (!casFile) return;
    setCasLoading(true); setCasError('');
    try {
      const arrayBuffer = await casFile.arrayBuffer();
      const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
      const res = await fetch(`${API_BASE}/import-cas`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, pdf_base64: base64, password: casPassword })
      });
      const json = await res.json();
      if (json.error) { setCasError(json.error); return; }
      setCasPreview(json.holdings || []);
    } catch (e) { setCasError('Upload failed. Please try again.'); }
    finally { setCasLoading(false); }
  };

  const handleCASConfirm = async () => {
    setCasLoading(true);
    try {
      const arrayBuffer = await casFile!.arrayBuffer();
      const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
      await fetch(`${API_BASE}/import-cas`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, pdf_base64: base64, password: casPassword, confirm: true, preview_data: casPreview })
      });
      setCasConfirmed(true); setShowCAS(false); setCasPreview([]);
      await fetchData();
    } catch (e) { setCasError('Import failed.'); }
    finally { setCasLoading(false); }
  };

  return (
    <div className="min-h-screen bg-background text-foreground pb-20">
      <div className="max-w-2xl mx-auto p-6">
        <button onClick={() => setLocation('/dashboard')} className="text-muted-foreground text-sm mb-6 flex items-center gap-1">
          <i className="ti ti-arrow-left" style={{fontSize:"1rem"}} /> Back to Dashboard
        </button>
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Investments</h1>
          <div className="flex gap-2">
            <Button onClick={() => { setShowCAS(!showCAS); setShowForm(false); }} size="sm" variant="outline">
              <i className="ti ti-file-upload mr-1" style={{fontSize:"0.9rem"}} /> Import CAS
            </Button>
            <Button onClick={() => { setShowForm(!showForm); setShowCAS(false); }} size="sm">
              <i className="ti ti-plus mr-1" style={{fontSize:"0.9rem"}} /> Add
            </Button>
          </div>
        </div>

        {/* CAS Upload */}
        {showCAS && (
          <Card className="p-5 border-card-border bg-card mb-6">
            <h2 className="font-semibold mb-2">Import CAS Statement</h2>
            <p className="text-xs text-muted-foreground mb-4">Upload your CAMS/KFintech Consolidated Account Statement PDF to auto-import all mutual fund holdings.</p>
            {casPreview.length === 0 ? (
              <div className="space-y-3">
                <div>
                  <label className="text-sm text-muted-foreground mb-1 block">CAS PDF File</label>
                  <input ref={fileRef} type="file" accept=".pdf"
                    onChange={e => setCasFile(e.target.files?.[0] || null)}
                    className="w-full text-sm text-muted-foreground file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-sm file:bg-brand file:text-white" />
                </div>
                <div>
                  <label className="text-sm text-muted-foreground mb-1 block">PDF Password (PAN+DOB e.g. ABCDE1234F01011990)</label>
                  <input type="text" value={casPassword} onChange={e => setCasPassword(e.target.value)}
                    placeholder="e.g. ABCDE1234F01011990"
                    className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
                </div>
                {casError && <p className="text-sm text-destructive">{casError}</p>}
                <Button onClick={handleCASUpload} disabled={casLoading || !casFile} className="w-full">
                  {casLoading ? 'Parsing PDF...' : 'Parse CAS'}
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-success font-medium">Found {casPreview.length} holdings — review before importing:</p>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {casPreview.map((h, i) => (
                    <div key={i} className="flex justify-between text-sm border-b border-border/30 pb-1">
                      <span className="text-muted-foreground truncate mr-2">{h.scheme_name}</span>
                      <span className="shrink-0">{formatRupee(h.current_value)}</span>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2">
                  <Button onClick={() => setCasPreview([])} variant="outline" className="flex-1">Re-upload</Button>
                  <Button onClick={handleCASConfirm} disabled={casLoading} className="flex-1">
                    {casLoading ? 'Importing...' : 'Confirm Import'}
                  </Button>
                </div>
              </div>
            )}
          </Card>
        )}

        {/* Manual Add Form */}
        {showForm && (
          <Card className="p-5 border-card-border bg-card mb-6">
            <h2 className="font-semibold mb-4">Add Investment Manually</h2>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-muted-foreground mb-1 block">Fund / Scheme Name</label>
                <input type="text" value={schemeName} onChange={e => setSchemeName(e.target.value)}
                  placeholder="e.g. Parag Parikh Flexi Cap"
                  className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
              </div>
              <div>
                <label className="text-sm text-muted-foreground mb-1 block">Amount Invested (Rs.)</label>
                <input type="number" value={amountInvested} onChange={e => setAmountInvested(e.target.value)}
                  placeholder="e.g. 50000"
                  className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
              </div>
              <div>
                <label className="text-sm text-muted-foreground mb-1 block">Current Value (Rs.) — optional</label>
                <input type="number" value={currentValue} onChange={e => setCurrentValue(e.target.value)}
                  placeholder="Leave blank if same as invested"
                  className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
              </div>
              <Button onClick={handleManualSubmit} disabled={submitting || !schemeName || !amountInvested} className="w-full">
                {submitting ? 'Adding...' : 'Add Investment'}
              </Button>
            </div>
          </Card>
        )}

        {(success || casConfirmed) && (
          <div className="mb-4 p-3 rounded-lg bg-success/10 border border-success/30 text-sm text-success">
            ✓ {casConfirmed ? 'Portfolio imported successfully!' : 'Investment added successfully!'}
          </div>
        )}

        {loading ? <p className="text-muted-foreground text-sm">Loading...</p> : (
          <div className="space-y-4">
            {data && data.total_invested > 0 && (
              <Card className="p-5 border-card-border bg-card">
                <h2 className="font-semibold mb-4">Portfolio Summary</h2>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Invested</p>
                    <p className="font-bold">{formatRupee(data.total_invested)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Current Value</p>
                    <p className="font-bold">{formatRupee(data.total_current_value)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Returns</p>
                    <p className={cn("font-bold", data.overall_return_pct >= 0 ? "text-success" : "text-destructive")}>
                      {data.overall_return_pct >= 0 ? '▲' : '▼'} {Math.abs(data.overall_return_pct)}%
                    </p>
                  </div>
                </div>
              </Card>
            )}

            {data && data.holdings.length > 0 ? (
              <Card className="p-5 border-card-border bg-card">
                <h2 className="font-semibold mb-4">Your Holdings</h2>
                <div className="space-y-4">
                  {data.holdings.map((h: any, i: number) => (
                    <div key={i} className="border-b border-border/30 pb-3 last:border-0 last:pb-0">
                      <div className="flex justify-between items-start mb-1">
                        <p className="font-medium text-sm">{h.scheme_name}</p>
                        <span className={cn("text-sm font-semibold", h.return_pct >= 0 ? "text-success" : "text-destructive")}>
                          {h.return_pct >= 0 ? '▲' : '▼'} {Math.abs(h.return_pct)}%
                        </span>
                      </div>
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>Invested: {formatRupee(h.amount_invested)}</span>
                        <span>Current: {formatRupee(h.current_value)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            ) : (
              <Card className="p-8 border-card-border bg-card text-center">
                <i className="ti ti-chart-line text-muted-foreground mb-3" style={{fontSize:"2rem"}} />
                <p className="text-muted-foreground mb-4">No investments added yet</p>
                <div className="flex gap-2 justify-center">
                  <Button onClick={() => setShowCAS(true)} variant="outline" size="sm">
                    <i className="ti ti-file-upload mr-1" style={{fontSize:"0.9rem"}} /> Import CAS
                  </Button>
                  <Button onClick={() => setShowForm(true)} size="sm">
                    <i className="ti ti-plus mr-1" style={{fontSize:"0.9rem"}} /> Add Manually
                  </Button>
                </div>
              </Card>
            )}
          </div>
        )}
      </div>

      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur-md border-t border-border/50 flex items-center justify-around px-2 py-2 z-50">
        <button onClick={() => setLocation('/dashboard')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-layout-dashboard" style={{fontSize:"1.2rem"}} /><span className="text-xs">Dashboard</span>
        </button>
        <button onClick={() => setLocation('/budget')} className="flex flex-col items-center gap-1 px-3 py-1 text-muted-foreground hover:text-foreground">
          <i className="ti ti-wallet" style={{fontSize:"1.2rem"}} /><span className="text-xs">Budget</span>
        </button>
        <button onClick={() => setLocation('/invest')} className="flex flex-col items-center gap-1 px-3 py-1 text-brand">
          <i className="ti ti-chart-line" style={{fontSize:"1.2rem"}} /><span className="text-xs font-medium">Invest</span>
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
