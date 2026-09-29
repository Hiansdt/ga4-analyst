// Mirrors the backend event contract (backend/src/analyst/core/events.py and api/app.py).

export interface Column {
  name: string
  type: string
}

export type Row = Record<string, string | number | boolean | null>

export interface ChartSpec {
  type: 'line' | 'bar' | 'funnel' | 'pie'
  title: string
  x: string
  y: string[]
  rows: Row[]
}

export interface QueryDisplay {
  label?: string
  sql: string
  result_id?: string
  columns?: Column[]
  rows?: Row[]
  total_rows?: number
  error?: string
}

// What the UI shows about the dataset the analyst is connected to (GET /api/dataset).
export interface DatasetInfo {
  name: string
  start: string
  end: string
  example_questions: string[]
}

export interface FollowUpsDisplay {
  questions: string[]
}

export interface Usage {
  input_tokens: number
  output_tokens: number
  cache_read_input_tokens: number
  cache_creation_input_tokens: number
}

export type AgentEvent =
  | { type: 'text_delta'; text: string }
  | { type: 'tool_started'; tool_use_id: string; name: string; input: Record<string, unknown> }
  | {
      type: 'tool_finished'
      tool_use_id: string
      name: string
      is_error: boolean
      display: QueryDisplay | ChartSpec | FollowUpsDisplay | { error: string }
    }
  | { type: 'turn_failed'; message: string }
  | { type: 'turn_completed'; usage: Usage }

export interface StoredTurn {
  question: string
  events: AgentEvent[]
}
