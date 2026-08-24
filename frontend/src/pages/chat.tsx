import { useState, useEffect, useRef } from 'react';
import { useLocation } from 'wouter';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { API_BASE } from '@/lib/helpers';
import { cn } from '@/lib/utils';

const QUICK_PROMPTS = [
  { label: 'Budget', icon: 'ti-wallet', prompt: 'What if I cut shopping by Rs 2,000 a month?' },
  { label: 'Goals', icon: 'ti-target', prompt: 'What if I save Rs 5,000 more per month toward my goal?' },
  { label: 'Tax', icon: 'ti-receipt-tax', prompt: 'What if I invest my remaining 80C room in ELSS?' },
  { label: 'Invest', icon: 'ti-chart-line', prompt: 'Which category is my expense high and how can I invest more?' },
];

export default function ChatPage() {
  const [, setLocation] = useLocation();
  const userId = localStorage.getItem('wg_active_user');
  const [messages, setMessages] = useState<{role: string, content: string}[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!userId) { setLocation('/login'); return; }
    setMessages([{ role: 'assistant', content: "Hi! I'm your WealthGuard AI assistant. Ask me anything about your finances — budgets, goals, tax, investments, or try a what-if scenario!" }]);
  }, [userId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text?: string) => {
    const msg = text || input;
    if (!msg.trim()) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: msg }]);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, message: msg })
      });
      const json = await res.json();
      setMessages(prev => [...prev, { role: 'assistant', content: json.response || json.reply || "I couldn't process that. Please try again." }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Failed to connect. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col pb-20">
      <div className="max-w-2xl mx-auto w-full flex flex-col flex-1 p-6">
        <button onClick={() => setLocation('/dashboard')} className="text-muted-foreground text-sm mb-4 flex items-center gap-1">
          <i className="ti ti-arrow-left" style={{fontSize:"1rem"}} /> Back to Dashboard
        </button>
        <h1 className="text-2xl font-bold mb-4">What-if Simulator</h1>

        {/* Quick prompts */}
        <div className="flex gap-2 flex-wrap mb-4">
          {QUICK_PROMPTS.map((q, i) => (
            <button key={i} onClick={() => sendMessage(q.prompt)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:border-brand transition-colors">
              <i className={cn("ti", q.icon)} style={{fontSize:"0.8rem"}} />
              {q.label}
            </button>
          ))}
        </div>

        {/* Messages */}
        <Card className="flex-1 p-4 border-card-border bg-card mb-4 overflow-y-auto" style={{minHeight:'300px', maxHeight:'50vh'}}>
          <div className="space-y-4">
            {messages.map((msg, i) => (
              <div key={i} className={cn("flex", msg.role === 'user' ? "justify-end" : "justify-start")}>
                <div className={cn("max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                  msg.role === 'user'
                    ? "bg-brand text-white rounded-br-sm"
                    : "bg-secondary text-foreground rounded-bl-sm"
                )}>
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-secondary rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm text-muted-foreground">
                  <i className="ti ti-loader-2 animate-spin mr-1" style={{fontSize:"0.9rem"}} /> Thinking...
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </Card>

        {/* Input */}
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !loading && sendMessage()}
            placeholder="Ask anything about your finances..."
            className="flex-1 px-4 py-2.5 rounded-xl bg-card border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand text-sm"
          />
          <Button onClick={() => sendMessage()} disabled={loading || !input.trim()} className="rounded-xl px-4">
            <i className="ti ti-send" style={{fontSize:"1rem"}} />
          </Button>
        </div>
      </div>

      {/* Mobile Bottom Nav */}
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
