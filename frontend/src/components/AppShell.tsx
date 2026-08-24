import { useState, type FormEvent, type ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useDispatch } from 'react-redux'
import {
  ChevronsUpDown,
  Database,
  FolderGit2,
  KeyRound,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Moon,
  Sun,
} from 'lucide-react'

import { api } from '@/services/api'
import {
  errorMessage,
  useGetMeQuery,
  useLogoutMutation,
  useSetPasswordMutation,
} from '@/services/authApi'
import { useTheme } from '@/components/ThemeProvider'
import { useIsMobile } from '@/hooks/use-mobile'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
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
  SidebarRail,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'

const navMain = [{ title: 'Dashboard', icon: LayoutDashboard, to: '/dashboard' }]

// ponytail: placeholder entries — wire to real pages when they exist
const navSoon = [
  { title: 'Sources', icon: FolderGit2 },
  { title: 'Memory', icon: Database },
  { title: 'Chat', icon: MessageSquare },
]

function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Toggle theme"
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
    >
      {theme === 'dark' ? <Sun /> : <Moon />}
    </Button>
  )
}

function UserFooter() {
  const navigate = useNavigate()
  const dispatch = useDispatch()
  const { data } = useGetMeQuery()
  const [logout] = useLogoutMutation()
  const [setPassword, { isLoading: isSettingPassword }] =
    useSetPasswordMutation()
  const [newPassword, setNewPassword] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const isMobile = useIsMobile()
  const user = data?.user

  if (!user) return null

  const initials = user.name
    .split(' ')
    .map((part) => part.charAt(0).toUpperCase())
    .slice(0, 2)
    .join('')

  const handleLogout = async () => {
    await logout().unwrap().catch((err) => errorMessage(err))
    dispatch(api.util.resetApiState())
    navigate('/login')
  }

  const handleSetPassword = async (e: FormEvent) => {
    e.preventDefault()
    setPasswordError(null)
    try {
      await setPassword({
        password: newPassword,
        current_password: user.has_password ? currentPassword : undefined,
      }).unwrap()
      setNewPassword('')
      setCurrentPassword('')
    } catch (err) {
      setPasswordError(errorMessage(err))
    }
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <Avatar className="size-8 rounded-lg">
                {user.picture && (
                  <AvatarImage src={user.picture} alt={user.name} />
                )}
                <AvatarFallback className="rounded-lg">
                  {initials || '?'}
                </AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">{user.name}</span>
                <span className="truncate text-xs text-muted-foreground">
                  {user.email}
                </span>
              </div>
              <ChevronsUpDown className="ml-auto size-4 text-muted-foreground" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            side={isMobile ? 'bottom' : 'right'}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="truncate">
              {user.email}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <form
              onSubmit={handleSetPassword}
              onKeyDown={(e) => e.stopPropagation()}
              className="px-2 py-1.5"
            >
              <p className="text-muted-foreground mb-2 flex items-center gap-1.5 text-xs font-medium">
                <KeyRound className="w-4 h-4" />
                {user.has_password ? 'Change password' : 'Add a password'}
              </p>
              {user.has_password && (
                <Input
                  type="password"
                  required
                  autoComplete="current-password"
                  placeholder="Current password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="mb-2 h-8 bg-background text-xs"
                />
              )}
              <div className="flex gap-2">
                <Input
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  placeholder="At least 8 characters"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="h-8 min-w-0 flex-1 bg-background text-xs"
                />
                <Button
                  type="submit"
                  size="sm"
                  disabled={isSettingPassword}
                  className="h-8 shrink-0 text-xs"
                >
                  {isSettingPassword ? 'Saving…' : 'Save'}
                </Button>
              </div>
              {passwordError && (
                <p role="alert" className="text-destructive mt-1.5 text-xs">
                  {passwordError}
                </p>
              )}
            </form>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout}>
              <LogOut />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

function AppSidebar() {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <a href="/">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold">
                  S
                </span>
                <span className="truncate font-semibold group-data-[collapsible=icon]:hidden">
                  Sensei
                </span>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Platform</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navMain.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <NavLink to={item.to}>
                    {({ isActive }) => (
                      <SidebarMenuButton isActive={isActive} tooltip={item.title}>
                        <item.icon />
                        <span>{item.title}</span>
                      </SidebarMenuButton>
                    )}
                  </NavLink>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>Coming soon</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navSoon.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton disabled tooltip={item.title}>
                    <item.icon />
                    <span>{item.title}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <UserFooter />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <TooltipProvider>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background px-4">
            <SidebarTrigger />
            <Separator orientation="vertical" className="mr-1 h-4!" />
            <span className="text-sm font-medium">Dashboard</span>
            <div className="ml-auto flex items-center gap-1">
              <ThemeToggle />
            </div>
          </header>
          <main className="flex flex-1 flex-col gap-6 p-6">{children}</main>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
