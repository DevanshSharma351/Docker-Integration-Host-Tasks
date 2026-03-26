import { useEffect, useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './components/Login';
import Register from './components/Register';
import Dashboard from './components/Dashboard';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Moon, SunMedium } from 'lucide-react';

function useThemeMode() {
  const getInitialTheme = () => {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light';
  };

  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('theme', theme);
  }, [theme]);

  return {
    theme,
    toggleTheme: () => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark')),
  };
}

function AppContent() {
  const { user, loading } = useAuth();
  const [showRegister, setShowRegister] = useState(false);
  const { theme, toggleTheme } = useThemeMode();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">Loading session...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-muted/30 p-4">
        <div className="pointer-events-none absolute -top-28 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-primary/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 right-16 h-64 w-64 rounded-full bg-foreground/10 blur-3xl" />

        <Card className="relative w-full max-w-4xl overflow-hidden border p-0 shadow-xl">
          <CardContent className="grid p-0 md:grid-cols-2">
            <div className="p-6 md:p-8">
              <CardHeader className="space-y-4 px-0 pt-0">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-2xl font-bold">
                    {showRegister ? 'Create your account' : 'Sign in'}
                  </CardTitle>
                  <Button variant="outline" size="sm" onClick={toggleTheme}>
                    {theme === 'dark' ? <SunMedium className="size-4" /> : <Moon className="size-4" />}
                    {theme === 'dark' ? 'Light' : 'Dark'}
                  </Button>
                </div>
                <CardDescription>
                  {showRegister
                    ? 'Register to access hosts, registries, and build pipelines.'
                    : 'Welcome back. Continue to your Docker host workspace.'}
                </CardDescription>
              </CardHeader>

              {showRegister ? <Register /> : <Login />}

              <Button
                variant="ghost"
                className="mt-4 w-full"
                onClick={() => setShowRegister(!showRegister)}
              >
                {showRegister ? 'Already have an account? Login' : "Need an account? Register"}
              </Button>
            </div>

            <div className="relative hidden border-l bg-muted md:block">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,hsl(var(--primary)/0.22),transparent_45%),radial-gradient(circle_at_80%_70%,hsl(var(--foreground)/0.16),transparent_50%)]" />
              <div className="relative z-10 flex h-full items-end p-8">
                <div className="max-w-xs rounded-xl border bg-background/75 p-4 backdrop-blur">
                  <p className="text-sm font-medium">Docker Integration Host</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Secure registry access, image builds, and host-level operations in one place.
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return <Dashboard theme={theme} toggleTheme={toggleTheme} />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
