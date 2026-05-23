import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import RoomsPage from './pages/RoomsPage'
import LobbyPage from './pages/LobbyPage'
import GamePage from './pages/GamePage'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('token')
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/rooms" element={<RequireAuth><RoomsPage /></RequireAuth>} />
        <Route path="/lobby/:roomId" element={<RequireAuth><LobbyPage /></RequireAuth>} />
        <Route path="/game/:roomId" element={<RequireAuth><GamePage /></RequireAuth>} />
        <Route path="*" element={<Navigate to="/rooms" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
