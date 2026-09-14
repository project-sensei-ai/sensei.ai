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

export type SourceType = 'github' | 'file' | 'url' | 'confluence' | 'jira' | 'slack' | 'meeting'
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

export interface Member {
  id: string
  workspace_id: string
  user_id: string
  role: WorkspaceRole
  status: 'active' | 'invited'
  email?: string
  name?: string
  picture?: string | null
  invited_at: string | null
  joined_at: string | null
  /** null = every source; a list narrows what they are answered from. */
  source_access?: string[] | null
  /** Owners only, and only while the invite is unused. */
  invite_url?: string
}

export interface ChangeDigest {
  id: string
  headline: string
  detail: string
  affects: string[]
  severity: 'notable' | 'minor'
  sources: string[]
  at: string | null
  acknowledged: boolean
}

export interface BriefSection { heading: string; body: string; sources: string[] }
export interface ReadingItem { title: string; source: string; why: string }
export interface PersonToMeet { name: string; why: string }

export interface BriefBody {
  headline: string
  sections: BriefSection[]
  reading_list: ReadingItem[]
  people_to_meet: PersonToMeet[]
  open_questions: string[]
}

export interface Brief {
  id: string
  workspace_id: string
  user_id: string
  person_name: string | null
  person_email: string | null
  status: 'generating' | 'ready' | 'error'
  brief: BriefBody | null
  error_message: string | null
  /** Set when the project moved after this brief was written. */
  stale_reason?: string | null
  stale_at?: string | null
  /** The last refresh failed; the brief shown is the last good one. */
  refresh_error?: string | null
  created_at: string | null
  updated_at: string | null
}

export type GapKind = 'missing_document' | 'unowned_area' | 'dangling_reference' | 'thin_coverage'
export type Severity = 'high' | 'medium' | 'low'

export interface Gap {
  id: string
  title: string
  kind: GapKind
  detail: string
  evidence: string[]
  severity: Severity
  can_draft: boolean
  draft_from: string[]
}

export interface GapReport {
  id: string
  status: 'scanning' | 'ready' | 'error'
  summary: string | null
  gaps: Gap[]
  error_message: string | null
  refresh_error?: string | null
  updated_at: string | null
}

export interface DraftBody {
  title: string
  body_markdown: string
  sources_used: string[]
  assumptions: string[]
}

export interface Draft {
  id: string
  gap_id: string
  gap_title: string | null
  status: 'drafting' | 'ready' | 'error'
  draft: DraftBody | null
  error_message: string | null
  updated_at: string | null
}

export interface Grant {
  id: string
  type: SourceType
  label: string
  status: SourceStatus
  connected_at: string | null
  chunks: number
  credential_state: 'encrypted' | 'plaintext' | 'none' | null
  credential?: string
  ceiling?: string
  floor?: string
  cannot?: string[]
  revoke?: string
  improve?: string | null
}

export interface TrustOverview {
  workspace: { name: string; role: WorkspaceRole }
  grants: Grant[]
  tools: ToolGrant[]
  people: {
    name: string | null
    email: string | null
    role: string
    status: string
    /** How many sources they can be answered from; null = all. */
    sees: number | null
  }[]
  coverage: {
    sources: number
    tools: number
    write_enabled: number
    indexed_chunks: number
    people_with_access: number
    pending_invites: number
  }
  never: string[]
  encryption_configured: boolean
  can_manage: boolean
}

export interface Unanswered {
  id: string
  question: string
  asked_by_name: string | null
  times_asked: number
  status: 'open' | 'answered' | 'dismissed'
  answer: string | null
  answered_by: string | null
  answered_at: string | null
  last_asked_at: string | null
}

export interface LedgerStats {
  open: number
  answered_by_humans: number
  dismissed: number
  answers_given: number
  answers_with_sources: number
  without_a_human_pct: number
}

export interface ActivityEvent {
  at: string | null
  kind: 'brief' | 'audit' | 'draft' | 'source' | 'readiness'
  title: string
  detail: string
  /** True when the agent started this itself, rather than a person asking. */
  unprompted: boolean
}

export interface AddMemberResult {
  email: string
  status: 'invited' | 'skipped'
  detail?: string
  emailed?: boolean
  invite_url?: string
}

export interface ToolSpec {
  name: string
  server_name: string
  description: string
  access: 'read' | 'write'
}

export type GrantKind = 'mcp_http' | 'mcp_sse' | 'mcp_stdio' | 'mcp_oauth'

export interface ToolGrant {
  id: string
  workspace_id: string
  name: string
  kind: GrantKind
  url: string | null
  command: string | null
  args: string[]
  allow_write: boolean
  disabled_tools: string[]
  tools: ToolSpec[]
  read_count: number
  write_count: number
  status: 'connected' | 'error' | 'disabled' | 'authorizing'
  error_message: string | null
  auth?: 'oauth' | 'token'
  needs_reauth?: boolean
  created_at: string | null
  last_used_at: string | null
  uses: number
  credential_state?: 'encrypted' | 'plaintext' | 'none'
  has_credential?: boolean
}

export interface ConnectToolInput {
  name: string
  kind: GrantKind
  url?: string
  authorization?: string
  headers?: Record<string, string>
  command?: string
  args?: string[]
  env?: Record<string, string>
  allow_write?: boolean
}

export interface Artifact {
  id: string
  title: string
  filename: string
  kind: 'spreadsheet' | 'document' | string
  mime: string
  size: number
  summary: string | null
  created_at: string | null
  url: string
}

export interface MeetingUtterance {
  speaker: string
  text: string
  at: string
}

export interface MeetingReply {
  id: string
  at: string
  kind: 'answer' | 'correction' | 'silent'
  trigger: string
  text: string
  citations: ChatCitation[]
  confidence: number
  reason: string
}

export interface Meeting {
  id: string
  workspace_id: string
  title: string
  status: 'live' | 'ended'
  mode: 'companion' | 'meet_bot'
  meet_url?: string | null
  bot_status?: string | null
  started_at: string | null
  ended_at: string | null
  utterance_count: number
  reply_count: number
  transcript?: MeetingUtterance[]
  replies?: MeetingReply[]
  summary?: string | null
  source_id?: string | null
}

export interface ReadinessItem {
  question: string
  why: string
  answerable: boolean
  answer: string
  source: string
}

export interface Readiness {
  status: 'running' | 'ready' | 'error'
  score: number
  total: number
  items: ReadinessItem[]
  error_message: string | null
  refresh_error?: string | null
  updated_at: string | null
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
  artifacts?: Artifact[]
  tools_used?: string[]
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
  | { type: 'jira'; base_url: string; email: string; api_token: string; project_key: string; label?: string }
  | { type: 'slack'; token: string; channel: string; label?: string }

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

    getMembers: builder.query<{ members: Member[]; can_manage: boolean }, void>({
      query: () => '/workspaces/members',
      providesTags: ['Member'],
    }),

    addMembers: builder.mutation<
      { results: AddMemberResult[]; email_configured: boolean },
      { emails: string[] }
    >({
      query: (body) => ({ url: '/workspaces/members', method: 'POST', body }),
      invalidatesTags: ['Member'],
    }),

    getMyBrief: builder.query<{ brief: Brief | null }, void>({
      // Poll while the agent is still researching.
      query: () => '/briefs/me',
      providesTags: ['Brief'],
    }),

    getBriefs: builder.query<{ briefs: Brief[] }, void>({
      query: () => '/briefs',
      providesTags: ['Brief'],
    }),

    regenerateBrief: builder.mutation<{ message: string; user_id: string }, string | void>({
      query: (userId) => ({
        url: `/briefs/regenerate${userId ? `?user_id=${userId}` : ''}`,
        method: 'POST',
      }),
      invalidatesTags: ['Brief'],
    }),

    getGaps: builder.query<{ report: GapReport | null }, void>({
      query: () => '/gaps',
      providesTags: ['Gap'],
    }),

    rescanGaps: builder.mutation<{ message: string }, void>({
      query: () => ({ url: '/gaps/scan', method: 'POST' }),
      invalidatesTags: ['Gap'],
    }),

    requestDraft: builder.mutation<{ message: string }, string>({
      query: (gapId) => ({ url: `/gaps/${gapId}/draft`, method: 'POST' }),
      invalidatesTags: (_r, _e, gapId) => [{ type: 'Draft', id: gapId }],
    }),

    getDraft: builder.query<{ draft: Draft | null }, string>({
      query: (gapId) => `/gaps/${gapId}/draft`,
      providesTags: (_r, _e, gapId) => [{ type: 'Draft', id: gapId }],
    }),

    getDigests: builder.query<{ digests: ChangeDigest[] }, void>({
      query: () => '/watch',
      providesTags: ['Digest'],
    }),

    checkForChanges: builder.mutation<
      { checked: boolean; changed: boolean; material: boolean; message?: string; headline?: string },
      void
    >({
      query: () => ({ url: '/watch/check', method: 'POST' }),
      invalidatesTags: ['Digest', 'Brief', 'Activity'],
    }),

    ackDigest: builder.mutation<void, string>({
      query: (id) => ({ url: `/watch/${id}/ack`, method: 'POST' }),
      invalidatesTags: ['Digest'],
    }),

    getTrust: builder.query<TrustOverview, void>({
      query: () => '/trust',
      providesTags: ['Trust'],
    }),

    getLedger: builder.query<
      { entries: Unanswered[]; can_answer: boolean; stats: LedgerStats },
      void
    >({
      query: () => '/answers',
      providesTags: ['Answer'],
    }),

    answerQuestion: builder.mutation<{ message: string }, { id: string; text: string }>({
      query: ({ id, text }) => ({ url: `/answers/${id}`, method: 'POST', body: { text } }),
      invalidatesTags: ['Answer', 'Activity'],
    }),

    dismissQuestion: builder.mutation<void, string>({
      query: (id) => ({ url: `/answers/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Answer'],
    }),

    getActivity: builder.query<{ events: ActivityEvent[]; unprompted_count: number }, void>({
      query: () => '/activity',
      providesTags: ['Activity'],
    }),

    setSourceAccess: builder.mutation<
      { user_id: string; source_access: string[] | null },
      { userId: string; sourceIds: string[] | null }
    >({
      query: ({ userId, sourceIds }) => ({
        url: `/workspaces/members/${userId}/sources`,
        method: 'PUT',
        body: { source_ids: sourceIds },
      }),
      invalidatesTags: ['Member', 'Trust'],
    }),

    removeMember: builder.mutation<void, string>({
      query: (userId) => ({ url: `/workspaces/members/${userId}`, method: 'DELETE' }),
      invalidatesTags: ['Member'],
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

    // ── Tool grants ────────────────────────────────────────────────────────────

    getTools: builder.query<{ grants: ToolGrant[]; can_manage: boolean }, void>({
      query: () => '/tools',
      providesTags: ['Tool'],
    }),

    connectTool: builder.mutation<{ grant: ToolGrant }, ConnectToolInput>({
      query: (body) => ({ url: '/tools', method: 'POST', body }),
      invalidatesTags: ['Tool', 'Trust'],
    }),

    updateTool: builder.mutation<
      { grant: ToolGrant },
      { id: string; allow_write?: boolean; disabled_tools?: string[]; name?: string }
    >({
      query: ({ id, ...body }) => ({ url: `/tools/${id}`, method: 'PATCH', body }),
      invalidatesTags: ['Tool', 'Trust'],
    }),

    testTool: builder.mutation<{ grant: ToolGrant }, string>({
      query: (id) => ({ url: `/tools/${id}/test`, method: 'POST' }),
      invalidatesTags: ['Tool', 'Trust'],
    }),

    revokeTool: builder.mutation<void, string>({
      query: (id) => ({ url: `/tools/${id}`, method: 'DELETE' }),
      invalidatesTags: ['Tool', 'Trust'],
    }),

    getOAuthPresets: builder.query<{ presets: { id: string; name: string; url: string; blurb: string }[] }, void>({
      query: () => '/tools/oauth/presets',
    }),

    startOAuth: builder.mutation<{ grant_id: string; auth_url: string }, { name: string; url: string; allow_write?: boolean }>({
      query: (body) => ({ url: '/tools/oauth/start', method: 'POST', body }),
      invalidatesTags: ['Tool'],
    }),

    getReadiness: builder.query<{ readiness: Readiness | null }, void>({
      query: () => '/readiness',
      providesTags: ['Readiness'],
    }),

    rerunReadiness: builder.mutation<{ message: string }, void>({
      query: () => ({ url: '/readiness/run', method: 'POST' }),
      invalidatesTags: ['Readiness', 'Activity', 'Answer'],
    }),

    getArtifacts: builder.query<{ artifacts: Artifact[] }, void>({
      query: () => '/artifacts',
      providesTags: ['Artifact'],
    }),

    // ── Meetings ───────────────────────────────────────────────────────────────

    listMeetings: builder.query<{ meetings: Meeting[] }, void>({
      query: () => '/meetings',
      providesTags: ['Meeting'],
    }),

    getMeeting: builder.query<{ meeting: Meeting }, string>({
      query: (id) => `/meetings/${id}`,
      providesTags: (_r, _e, id) => [{ type: 'Meeting', id }],
    }),

    startMeeting: builder.mutation<{ meeting: Meeting }, { title: string; mode?: 'companion' | 'meet_bot'; meet_url?: string }>({
      query: (body) => ({ url: '/meetings', method: 'POST', body }),
      invalidatesTags: ['Meeting'],
    }),

    endMeeting: builder.mutation<{ meeting: Meeting }, string>({
      query: (id) => ({ url: `/meetings/${id}/end`, method: 'POST' }),
      invalidatesTags: (_r, _e, id) => ['Meeting', { type: 'Meeting', id }, 'Source', 'Activity'],
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
  useGetMembersQuery,
  useAddMembersMutation,
  useSetSourceAccessMutation,
  useRemoveMemberMutation,
  useGetMyBriefQuery,
  useGetBriefsQuery,
  useRegenerateBriefMutation,
  useGetActivityQuery,
  useGetDigestsQuery,
  useCheckForChangesMutation,
  useAckDigestMutation,
  useGetTrustQuery,
  useGetLedgerQuery,
  useAnswerQuestionMutation,
  useDismissQuestionMutation,
  useGetGapsQuery,
  useRescanGapsMutation,
  useRequestDraftMutation,
  useGetDraftQuery,
  useJoinWorkspaceMutation,
  useDeleteSourceMutation,
  useListChatSessionsQuery,
  useCreateChatSessionMutation,
  useGetChatSessionQuery,
  useArchiveChatSessionMutation,
  useSendMessageMutation,
  useGetToolsQuery,
  useConnectToolMutation,
  useUpdateToolMutation,
  useTestToolMutation,
  useRevokeToolMutation,
  useGetOAuthPresetsQuery,
  useStartOAuthMutation,
  useGetArtifactsQuery,
  useGetReadinessQuery,
  useRerunReadinessMutation,
  useListMeetingsQuery,
  useGetMeetingQuery,
  useStartMeetingMutation,
  useEndMeetingMutation,
} = onboardingApi
