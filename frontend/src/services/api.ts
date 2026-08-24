import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'

export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({ baseUrl: '/api', credentials: 'include' }),
  tagTypes: ['User'],
  endpoints: (builder) => ({
    getHealth: builder.query<{ status: string; version: string }, void>({
      query: () => '/health',
    }),
  }),
})

export const { useGetHealthQuery } = api
