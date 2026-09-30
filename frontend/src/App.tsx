import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { AgentDetailPage } from '@/features/agents/AgentDetailPage'
import { AgentsPage } from '@/features/agents/AgentsPage'
import { PlaygroundPage } from '@/features/playground/PlaygroundPage'
import { RunDetailPage } from '@/features/runs/RunDetailPage'
import { RunComparisonPage } from '@/features/runs/RunComparisonPage'
import { RunsPage } from '@/features/runs/RunsPage'
import { SessionDetailPage } from '@/features/sessions/SessionDetailPage'
import { SessionsPage } from '@/features/sessions/SessionsPage'
import { EvaluationDetailPage } from '@/features/evaluations/EvaluationDetailPage'
import { EvaluationsPage } from '@/features/evaluations/EvaluationsPage'
import { ToolsPage } from '@/features/tools/ToolsPage'

function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/playground" element={<PlaygroundPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/agents/:agentId" element={<AgentDetailPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/runs/:requestId/compare" element={<RunComparisonPage />} />
        <Route path="/runs/:requestId" element={<RunDetailPage />} />
        <Route path="/sessions" element={<SessionsPage />} />
        <Route path="/sessions/:threadId" element={<SessionDetailPage />} />
        <Route path="/evaluations" element={<EvaluationsPage />} />
        <Route path="/evaluations/:evaluationId" element={<EvaluationDetailPage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}

export default App
