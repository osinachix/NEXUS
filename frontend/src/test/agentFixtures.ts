import type { Agent } from '@/types/agent'

/**
 * A realistic stand-in for `GET /v1/agents` (see agents.py's
 * `_build_registry`), shared across tests that need registry data
 * without re-deriving it in every file.
 */
export const MOCK_AGENTS: Agent[] = [
  {
    id: 'logical',
    name: 'Logical',
    description: 'Fact-based reasoning and information retrieval. Can fetch live web pages via a policy-gated tool.',
    status: 'active',
    execution_mode: ['auto_route', 'direct'],
    tools: ['fetch'],
    capabilities: ['reasoning', 'web_retrieval'],
    tags: ['reference'],
    version: '1.0.0',
  },
  {
    id: 'math',
    name: 'Math',
    description: 'Solves problems step by step and states the final answer.',
    status: 'active',
    execution_mode: ['auto_route', 'direct'],
    tools: [],
    capabilities: ['mathematical_reasoning'],
    tags: ['reference'],
    version: '1.0.0',
  },
  {
    id: 'coding',
    name: 'Coding',
    description: 'Writes, explains, debugs, and reviews code.',
    status: 'active',
    execution_mode: ['auto_route', 'direct'],
    tools: [],
    capabilities: ['coding', 'software_reasoning'],
    tags: ['reference'],
    version: '1.0.0',
  },
  {
    id: 'counselor',
    name: 'Counselor',
    description: 'Empathetic, reflective responses to emotional messages.',
    status: 'active',
    execution_mode: ['auto_route', 'direct'],
    tools: [],
    capabilities: ['conversational_support'],
    tags: ['reference'],
    version: '1.0.0',
  },
]
