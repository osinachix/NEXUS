export type ToolStatus = 'active' | 'unavailable'
export type ToolExecutionType = 'native'
export type ToolActivityType = 'tool_completed' | 'tool_denied' | 'tool_failed'

export interface ToolDefinition {
  id: string
  name: string
  description: string
  status: ToolStatus
  execution_type: ToolExecutionType
  allowed_agents: string[]
  controls: string[]
}

export interface ToolActivityEvent {
  request_id: string
  tool: string
  event_type: ToolActivityType
  agent: string | null
  timestamp: string
  duration_ms: number | null
  success: boolean | null
  reason: string | null
  error_type: string | null
}

export interface ToolActivityResponse {
  items: ToolActivityEvent[]
  total: number
  limit: number
}
