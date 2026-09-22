import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { clearToken, setToken } from '@/api/client'

export type UserRole = 'admin' | 'developer' | 'operator' | 'viewer'

export interface AuthUser {
  user_id: string
  email: string
  role: UserRole
}

interface AuthState {
  user: AuthUser | null
  token: string | null
  setAuth: (user: AuthUser, token: string) => void
  logout: () => void
  isAuthenticated: () => boolean
  hasRole: (min: UserRole) => boolean
}

const ROLE_RANK: Record<UserRole, number> = {
  admin: 4, developer: 3, operator: 2, viewer: 1,
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,

      setAuth: (user, token) => {
        setToken(token)
        set({ user, token })
      },

      logout: () => {
        clearToken()
        set({ user: null, token: null })
      },

      isAuthenticated: () => get().token !== null && get().user !== null,

      hasRole: (min: UserRole) => {
        const user = get().user
        if (!user) return false
        return ROLE_RANK[user.role] >= ROLE_RANK[min]
      },
    }),
    {
      name: 'sangam_auth',
      partialize: (state) => ({ token: state.token, user: state.user }),
    },
  ),
)
