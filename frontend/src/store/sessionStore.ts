import { create } from 'zustand'

interface SessionState {
  sessionId: string | null
  filename: string | null
  sheets: string[]
  setSession: (id: string, filename: string, sheets: string[]) => void
  clearSession: () => void
}

export const useSessionStore = create<SessionState>((set) => ({
  sessionId: null,
  filename: null,
  sheets: [],
  setSession: (id, filename, sheets) => set({ sessionId: id, filename, sheets }),
  clearSession: () => set({ sessionId: null, filename: null, sheets: [] }),
}))
