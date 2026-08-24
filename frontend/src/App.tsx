import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import NotFound from '@/pages/not-found';
import { Route, Switch, Router as WouterRouter } from 'wouter';
import { useEffect } from 'react';
import Login from '@/pages/login';
import Onboarding from '@/pages/onboarding';
import Confirm from '@/pages/confirm';
import Dashboard from '@/pages/dashboard';
import Budget from '@/pages/budget';
import Invest from '@/pages/invest';
import Tax from '@/pages/tax';
import Goals from '@/pages/goals';
import Report from '@/pages/report';
import ChatPage from '@/pages/chat';
import Security from '@/pages/security';
import Settings from '@/pages/settings';

const queryClient = new QueryClient();

function Router() {
  return (
    <Switch>
      <Route path="/" component={Dashboard} />
      <Route path="/login" component={Login} />
      <Route path="/onboarding" component={Onboarding} />
      <Route path="/confirm" component={Confirm} />
      <Route path="/dashboard" component={Dashboard} />
      <Route path="/budget" component={Budget} />
      <Route path="/invest" component={Invest} />
      <Route path="/tax" component={Tax} />
      <Route path="/goals" component={Goals} />
      <Route path="/report" component={Report} />
      <Route path="/chat" component={ChatPage} />
      <Route path="/security" component={Security} />
      <Route path="/settings" component={Settings} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  useEffect(() => {
    document.documentElement.classList.add('dark');
  }, []);
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Router />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
