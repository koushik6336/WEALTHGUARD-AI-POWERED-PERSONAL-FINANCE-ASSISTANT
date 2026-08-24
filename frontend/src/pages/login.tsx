import { useState } from 'react';
import { useLocation } from 'wouter';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Label } from '@/components/ui/label';
import { API_BASE } from '@/lib/helpers';

export default function Login() {
  const [, setLocation] = useLocation();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Login form
  const [loginId, setLoginId] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Signup form
  const [signupName, setSignupName] = useState('');
  const [signupId, setSignupId] = useState('');
  const [signupEmail, setSignupEmail] = useState('');
  const [signupPassword, setSignupPassword] = useState('');
  const [signupConfirm, setSignupConfirm] = useState('');

  const onLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginId || !loginPassword) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: loginId, password: loginPassword })
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        setError(data.error || 'Invalid credentials');
        return;
      }
      localStorage.setItem('wg_active_user', data.user_id);
      localStorage.setItem('wg_active_name', data.name);
      // Check if user has onboarding data
      const dashRes = await fetch(`${API_BASE}/dashboard-full?user_id=${data.user_id}`);
      const dashData = await dashRes.json();
      if (dashData.is_new) {
        setLocation('/onboarding');
      } else {
        setLocation('/dashboard');
      }
    } catch (err: any) {
      setError('Something went wrong. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const onSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!signupId || !signupName || !signupEmail || !signupPassword) return;
    if (signupPassword !== signupConfirm) {
      setError('Passwords do not match');
      return;
    }
    if (signupPassword.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: signupId, name: signupName, email: signupEmail, password: signupPassword })
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        setError(data.error || 'Signup failed');
        return;
      }
      localStorage.setItem('wg_active_user', signupId);
      localStorage.setItem('wg_active_name', signupName);
      setLocation('/onboarding');
    } catch (err: any) {
      setError('Something went wrong. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4 text-foreground">
      <div className="w-full max-w-md space-y-8">
        <div className="flex flex-col items-center justify-center text-center">
          <div className="w-12 h-12 bg-brand rounded-lg flex items-center justify-center mb-4">
            <span className="text-white font-bold text-2xl font-serif">W</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">WealthGuard</h1>
          <p className="text-muted-foreground mt-2">Your personal finance assistant</p>
        </div>

        <Card className="p-6 border-card-border bg-card shadow-lg">
          <Tabs defaultValue="login" className="w-full">
            <TabsList className="grid w-full grid-cols-2 mb-6 bg-secondary">
              <TabsTrigger value="login">Sign in</TabsTrigger>
              <TabsTrigger value="signup">Create account</TabsTrigger>
            </TabsList>

            <TabsContent value="login">
              <form onSubmit={onLogin} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="loginId">User ID</Label>
                  <input id="loginId" placeholder="e.g. rahul123" value={loginId}
                    onChange={e => setLoginId(e.target.value)} required
                    className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="loginPassword">Password</Label>
                  <input id="loginPassword" type="password" placeholder="Your password" value={loginPassword}
                    onChange={e => setLoginPassword(e.target.value)} required
                    className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
                </div>
                {error && <p className="text-sm text-destructive">{error}</p>}
                <Button type="submit" className="w-full" disabled={isLoading || !loginId || !loginPassword}>
                  {isLoading && <i className="ti ti-loader-2 mr-2 animate-spin" style={{fontSize:"1rem"}} />}
                  Sign in
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="signup">
              <form onSubmit={onSignup} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="signupName">Full Name</Label>
                  <input id="signupName" placeholder="e.g. Rahul Sharma" value={signupName}
                    onChange={e => setSignupName(e.target.value)} required
                    className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="signupId">User ID</Label>
                  <input id="signupId" placeholder="Choose a unique ID" value={signupId}
                    onChange={e => setSignupId(e.target.value)} required
                    className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="signupEmail">Email</Label>
                  <input id="signupEmail" type="email" placeholder="your@email.com" value={signupEmail}
                    onChange={e => setSignupEmail(e.target.value)} required
                    className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="signupPassword">Password</Label>
                  <input id="signupPassword" type="password" placeholder="Min 6 characters" value={signupPassword}
                    onChange={e => setSignupPassword(e.target.value)} required
                    className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="signupConfirm">Confirm Password</Label>
                  <input id="signupConfirm" type="password" placeholder="Repeat password" value={signupConfirm}
                    onChange={e => setSignupConfirm(e.target.value)} required
                    className="w-full px-3 py-2 rounded-md bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand" />
                </div>
                {error && <p className="text-sm text-destructive">{error}</p>}
                <Button type="submit" className="w-full" disabled={isLoading || !signupId || !signupName || !signupEmail || !signupPassword}>
                  {isLoading && <i className="ti ti-loader-2 mr-2 animate-spin" style={{fontSize:"1rem"}} />}
                  Create account
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        </Card>
      </div>
    </div>
  );
}
