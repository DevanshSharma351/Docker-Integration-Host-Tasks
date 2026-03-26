import { useAuth } from '../context/AuthContext';
import { useMemo, useState } from 'react';
import { imageService } from '../services/imageService';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  Terminal,
  Wrench,
  CircleAlert,
  LogOut,
  SunMedium,
  Moon,
  User,
  ChevronDown,
  Search,
  Rocket,
} from 'lucide-react';

export default function Dashboard({ theme, toggleTheme }) {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('build');
  const [hostId, setHostId] = useState('1');
  const [tag, setTag] = useState('');
  const [dockerfile, setDockerfile] = useState('FROM alpine:3.20\nRUN echo "hello from build pipeline"\nCMD ["sh"]');
  const [contextZip, setContextZip] = useState(null);
  const [pull, setPull] = useState(false);
  const [nocache, setNocache] = useState(false);
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState('');
  const [isBuilding, setIsBuilding] = useState(false);

  const canBuild = useMemo(() => {
    return hostId.trim() && (dockerfile.trim() || contextZip);
  }, [hostId, dockerfile, contextZip]);

  const appendLog = (event) => {
    setLogs((prev) => [...prev, event]);
  };

  const prettyLine = (entry) => {
    if (entry?.stream) return entry.stream.trimEnd();
    if (entry?.error) return `[${entry.error}] ${entry.detail || 'Build failed'}`;
    if (entry?.status === 'done') return `Build complete: ${entry.image_id}`;
    return JSON.stringify(entry);
  };

  const handleBuild = async (e) => {
    e.preventDefault();
    setError('');
    setLogs([]);
    setIsBuilding(true);

    try {
      await imageService.buildImageStream({
        hostId: hostId.trim(),
        tag,
        dockerfile,
        contextZip,
        pull,
        nocache,
        onEvent: appendLog,
      });
    } catch (err) {
      setError(err.message || 'Unable to start image build.');
    } finally {
      setIsBuilding(false);
    }
  };

  const navItems = [
    { id: 'build', label: 'Build Pipeline', icon: Wrench },
    { id: 'profile', label: 'Profile', icon: User },
  ];

  const initials = (user?.username || 'U').slice(0, 2).toUpperCase();

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon" variant="inset">
        <SidebarHeader>
          <div className="flex items-center gap-3 rounded-lg px-2 py-2">
            <div className="rounded-lg bg-primary/15 p-2 text-primary">
              <Rocket className="size-4" />
            </div>
            <div className="grid leading-tight group-data-[collapsible=icon]:hidden">
              <span className="text-sm font-semibold">Docker Console</span>
              <span className="text-xs text-muted-foreground">Integration Host</span>
            </div>
          </div>
          <Separator className="my-1" />
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Workspace</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {navItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <SidebarMenuItem key={item.id}>
                      <SidebarMenuButton
                        isActive={activeTab === item.id}
                        tooltip={item.label}
                        onClick={() => setActiveTab(item.id)}
                      >
                        <Icon className="size-4" />
                        <span>{item.label}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>

          <SidebarGroup>
            <SidebarGroupLabel>Session</SidebarGroupLabel>
            <SidebarGroupContent>
              <div className="rounded-lg border border-sidebar-border bg-sidebar-accent/40 p-3 group-data-[collapsible=icon]:hidden">
                <p className="text-xs font-medium text-sidebar-foreground/80">Signed in as</p>
                <p className="mt-1 truncate text-sm font-semibold text-sidebar-foreground">{user?.username}</p>
                <p className="mt-1 truncate text-xs text-sidebar-foreground/70">{user?.email || 'No email'}</p>
                <Badge variant="outline" className="mt-3 uppercase">{user?.role}</Badge>
              </div>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>

        <SidebarFooter>
          <DropdownMenu>
            <DropdownMenuTrigger className="flex w-full items-center gap-2 rounded-lg border border-sidebar-border px-2 py-2 text-left hover:bg-sidebar-accent/60">
              <Avatar size="sm">
                <AvatarFallback>{initials}</AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
                <p className="truncate text-sm font-medium">{user?.username}</p>
                <p className="truncate text-xs text-muted-foreground">{theme === 'dark' ? 'Dark theme' : 'Light theme'}</p>
              </div>
              <ChevronDown className="size-4 text-muted-foreground group-data-[collapsible=icon]:hidden" />
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top" align="start" className="min-w-56">
              <DropdownMenuItem onClick={toggleTheme}>
                {theme === 'dark' ? <SunMedium className="size-4" /> : <Moon className="size-4" />}
                {theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={logout}>
                <LogOut className="size-4" />
                Logout
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarFooter>
      </Sidebar>

      <SidebarInset className="bg-muted/25">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur md:px-6">
          <SidebarTrigger className="shrink-0" />
          <div className="relative max-w-sm flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input value="Build pipeline workspace" readOnly className="pl-9 text-sm" />
          </div>
          <Badge variant="outline" className="hidden sm:inline-flex">Module 3</Badge>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 space-y-4 p-4 md:p-6">
          {activeTab === 'build' && (
            <>
              <Card className="border-border/70 bg-card/95">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-xl">
                    <Wrench className="size-5" />
                    Automated Build Pipeline
                  </CardTitle>
                  <CardDescription>Build from Dockerfile text or ZIP context and stream logs in real time.</CardDescription>
                </CardHeader>

                <CardContent className="space-y-5">
                  <form onSubmit={handleBuild} className="space-y-5">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="host-id">Host ID</Label>
                        <Input
                          id="host-id"
                          type="number"
                          min="1"
                          value={hostId}
                          onChange={(e) => setHostId(e.target.value)}
                          required
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="tag">Tag (optional)</Label>
                        <Input
                          id="tag"
                          type="text"
                          value={tag}
                          onChange={(e) => setTag(e.target.value)}
                          placeholder="myorg/myapp:latest"
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="dockerfile">Dockerfile Text</Label>
                      <Textarea
                        id="dockerfile"
                        rows={10}
                        value={dockerfile}
                        onChange={(e) => setDockerfile(e.target.value)}
                        className="font-mono text-sm"
                        placeholder={'FROM alpine\nRUN echo "hello"'}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="context-zip">ZIP Build Context (optional)</Label>
                      <Input
                        id="context-zip"
                        type="file"
                        accept=".zip,application/zip"
                        onChange={(e) => setContextZip(e.target.files?.[0] || null)}
                      />
                    </div>

                    <div className="flex flex-wrap items-center gap-6">
                      <div className="flex items-center gap-2">
                        <Checkbox
                          id="pull"
                          checked={pull}
                          onCheckedChange={(checked) => setPull(Boolean(checked))}
                        />
                        <Label htmlFor="pull">Pull latest base images</Label>
                      </div>

                      <div className="flex items-center gap-2">
                        <Checkbox
                          id="nocache"
                          checked={nocache}
                          onCheckedChange={(checked) => setNocache(Boolean(checked))}
                        />
                        <Label htmlFor="nocache">Disable cache</Label>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <Button type="submit" disabled={!canBuild || isBuilding}>
                        {isBuilding ? 'Building...' : 'Start Build'}
                      </Button>
                      <p className="text-xs text-muted-foreground">
                        Endpoint: /api/hosts/{'{host_id}'}/images/build/
                      </p>
                    </div>
                  </form>

                  {error && (
                    <Alert variant="destructive">
                      <CircleAlert className="size-4" />
                      <AlertTitle>Build Error</AlertTitle>
                      <AlertDescription>{error}</AlertDescription>
                    </Alert>
                  )}
                </CardContent>
              </Card>

              <Card className="border-border/70 bg-card/95">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Terminal className="size-4" />
                    Build Stream
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-80 rounded-xl border bg-slate-950 p-4">
                    <div className="space-y-1 font-mono text-xs text-emerald-300">
                      {logs.length === 0 ? (
                        <div className="text-slate-500">No build output yet.</div>
                      ) : (
                        logs.map((entry, idx) => (
                          <div key={`${idx}-${prettyLine(entry)}`} className="whitespace-pre-wrap break-words">
                            {prettyLine(entry)}
                          </div>
                        ))
                      )}
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>
            </>
          )}

          {activeTab === 'profile' && (
            <Card className="border-border/70 bg-card/95">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-xl">Profile & Session</CardTitle>
                <CardDescription>Account metadata and environment details.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-lg border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Username</p>
                  <p className="mt-1 font-semibold">{user?.username}</p>
                </div>
                <div className="rounded-lg border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Email</p>
                  <p className="mt-1 font-semibold">{user?.email || 'Not provided'}</p>
                </div>
                <div className="rounded-lg border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Role</p>
                  <Badge variant="secondary" className="mt-1 uppercase">{user?.role}</Badge>
                </div>
                <div className="rounded-lg border p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Theme</p>
                  <p className="mt-1 font-semibold">{theme === 'dark' ? 'Dark' : 'Light'}</p>
                </div>
              </CardContent>
            </Card>
          )}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
