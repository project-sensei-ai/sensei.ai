import { api } from './api'

export interface User {
  id: string
  email: string
  name: string
  picture: string | null
  has_password: boolean
}

interface AuthResponse {
  user: User
}

interface RegisterArgs {
  name: string
  email: string
  password: string
}

interface CredentialsArgs {
  email: string
  password: string
}

export function errorMessage(err: unknown): string {
  const detail = (err as { data?: { detail?: unknown } })?.data?.detail
  if (typeof detail === 'string') return detail
  return 'Something went wrong. Please try again.'
}

export const authApi = api.injectEndpoints({
  endpoints: (builder) => ({
    register: builder.mutation<AuthResponse, RegisterArgs>({
      query: (body) => ({ url: '/auth/register', method: 'POST', body }),
      invalidatesTags: ['User'],
    }),
    login: builder.mutation<AuthResponse, CredentialsArgs>({
      query: (body) => ({ url: '/auth/login', method: 'POST', body }),
      invalidatesTags: ['User'],
    }),
    googleAuth: builder.mutation<AuthResponse, { credential: string }>({
      query: (body) => ({ url: '/auth/google', method: 'POST', body }),
      invalidatesTags: ['User'],
    }),
    getMe: builder.query<AuthResponse, void>({
      query: () => '/auth/me',
      providesTags: ['User'],
    }),
    logout: builder.mutation<{ message: string }, void>({
      query: () => ({ url: '/auth/logout', method: 'POST' }),
      invalidatesTags: ['User'],
    }),
    setPassword: builder.mutation<
      { message: string },
      { password: string; current_password?: string }
    >({
      query: (body) => ({ url: '/auth/set-password', method: 'POST', body }),
      invalidatesTags: ['User'],
    }),
  }),
})

export const {
  useRegisterMutation,
  useLoginMutation,
  useGoogleAuthMutation,
  useGetMeQuery,
  useLogoutMutation,
  useSetPasswordMutation,
} = authApi
