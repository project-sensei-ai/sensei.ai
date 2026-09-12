import { api } from './api'

// ── Types ─────────────────────────────────────────────────────────────────────

export type WorkspaceRole = 'owner' | 'admin' | 'member'

export interface Workspace {
  id: string
  owner_id: string
  name: string
  description: string
  created_at: string
  /** The current user's role in this workspace. Absent on older responses. */
  role?: WorkspaceRole
}

export interface SourceStats {
  chunks_count?: number
  pages_crawled?: number
}

export type SourceType = 'github' | 'file' | 'url' | 'confluence'
export type SourceStatus = 'pending' | 'indexing' | 'ready' | 'error'

export interface Source {
  id: string
  workspace_id: string
  type: SourceType
  label: string
  config: Record<string, unknown>
  status: SourceStatus
  stats: SourceStats
  error_message?: string
  created_at: string
  updated_at: string
}

export interface IngestStatus {
  source_id: string
  status: SourceStatus
  stats: SourceStats
  error_message?: string
}

export interface Invite {
  id: string
  workspace_id: string
  token: string
  invite_url: string
  created_at: string
  expires_at: string
}

export interface ChatCitation {
  index: number
  source_label: string
  excerpt: string
  score: number
}

export interface ChatResponse {
  answer: string
  citations: ChatCitation[]
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  citations?: ChatCitation[]
  created_at: string
}

export interface ChatSession {
  id: string
  workspace_id: string
  title: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface ChatSessionFull extends ChatSession {
  messages: ChatMessage[]
}

// ── Input types ───────────────────────────────────────────────────────────────

export type AddSourceInput =
  | { type: 'github'; pat: string; repo: string; label?: string }
  | { type: 'url'; urls: string[]; label?: string }
  | { type: 'confluence'; base_url: string; email: string; api_token: string; space_key: string; label?: string }

// ── Injected endpoints ────────────────────────────────────────────────────────

const onboardingApi = api.injectEndpoints({
  endpoints: (builder) => ({
    createWorkspace: builder.mutation<{ workspace: Workspace }, { name: string; description?: string }>({
      query: (body) => ({ url: '/workspaces', method: 'POST', body }),
      invalidatesTags: ['Workspace'],
    }),

    getMyWorkspace: builder.query<{ workspace: Workspace }, void>({
      query: () => '/workspaces/me',
      providesTags: [{ type: 'Workspace', id: 'me' }],
    }),

    addSource: builder.mutation<{ source: Source }, AddSourceInput>({
      query: (body) => ({ url: '/sources', method: 'POST', body }),
      invalidatesTags: ['Source'],
    }),

    uploadFile: builder.mutation<{ source: Source }, FormData>({
      query: (formData) => ({ url: '/sources/upload', method: 'POST', body: formData }),
      invalidatesTags: ['Source'],
    }),

    getSources: builder.query<{ sources: Source[] }, void>({
      query: () => '/sources',
      providesTags: ['Source'],
    }),

    triggerIngest: builder.mutation<{ message: string; source_id: string }, string>({
      query: (sourceId) => ({ url: `/ingest/${sourceId}`, method: 'POST' }),
      invalidatesTags: (_r, _e, sourceId) => ['Source', { type: 'IngestStatus', id: sourceId }],
    }),

    getIngestStatus: builder.query<IngestStatus, string>({
      query: (sourceId) => `/ingest/${sourceId}/status`,
      providesTags: (_r, _e, sourceId) => [{ type: 'IngestStatus', id: sourceId }],
    }),

    generateInvite: builder.mutation<{ invite: Invite }, string>({
      query: (workspaceId) => ({ url: `/workspaces/${workspaceId}/invite`, method: 'POST' }),
    }),

    joinWorkspace: builder.mutation<
      { workspace: Workspace; already_member: boolean },
      { token: string }
    >({
      query: (body) => ({ url: '/workspaces/join', method: 'POST', body }),
      invalidatesTags: ['Workspace', 'Source', 'ChatSession'],
    }),

    deleteSource: builder.mutation<void, string>({
      query: (sourceId) => ({ url: `/sources/${sourceId}`, method: 'DELETE' }),
      invalidatesTags: ['Source'],
    }),

    // ── Chat sessions ──────────────────────────────────────────────────────────

    listChatSessions: builder.query<{ sessions: ChatSession[] }, void>({
      query: () => '/chat/sessions',
      providesTags: ['ChatSession'],
    }),

    createChatSession: builder.mutation<{ session: ChatSession }, void>({
      query: () => ({ url: '/chat/sessions', method: 'POST' }),
      invalidatesTags: ['ChatSession'],
    }),

    getChatSession: builder.query<{ session: ChatSessionFull }, string>({
      query: (id) => `/chat/sessions/${id}`,
      providesTags: (_r, _e, id) => [{ type: 'ChatSession', id }],
    }),

    archiveChatSession: builder.mutation<void, string>({
      query: (id) => ({ url: `/chat/sessions/${id}`, method: 'DELETE' }),
      invalidatesTags: (_r, _e, id) => ['ChatSession', { type: 'ChatSession', id }],
    }),

    sendMessage: builder.mutation<ChatResponse, { sessionId: string; question: string }>({
      query: ({ sessionId, question }) => ({
        url: `/chat/sessions/${sessionId}/messages`,
        method: 'POST',
        body: { question },
      }),
      invalidatesTags: (_r, _e, { sessionId }) => [
        'ChatSession',
        { type: 'ChatSession', id: sessionId },
      ],
    }),
  }),
})

export const {
  useCreateWorkspaceMutation,
  useGetMyWorkspaceQuery,
  useAddSourceMutation,
  useUploadFileMutation,
  useGetSourcesQuery,
  useTriggerIngestMutation,
  useGetIngestStatusQuery,
  useGenerateInviteMutation,
  useJoinWorkspaceMutation,
  useDeleteSourceMutation,
  useListChatSessionsQuery,
  useCreateChatSessionMutation,
  useGetChatSessionQuery,
  useArchiveChatSessionMutation,
  useSendMessageMutation,
} = onboardingApi
