import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register, getMe } from '../api'

export default function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)
    try {
      if (mode === 'register') {
        await register(email, password)
        setSuccess('Аккаунт создан! Входим...')
      }
      const { access_token } = await login(email, password)
      localStorage.setItem('token', access_token)
      const me = await getMe()
      localStorage.setItem('userId', me.id)
      localStorage.setItem('email', me.email)
      navigate('/rooms')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
      <div className="card-surface" style={{ width: 360 }}>
        <h1 style={{ textAlign: 'center', marginBottom: 24 }}>🃏 Bridge</h1>

        <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
          <button
            className={mode === 'login' ? 'btn-primary' : 'btn-secondary'}
            style={{ flex: 1 }}
            onClick={() => setMode('login')}
          >Войти</button>
          <button
            className={mode === 'register' ? 'btn-primary' : 'btn-secondary'}
            style={{ flex: 1 }}
            onClick={() => setMode('register')}
          >Регистрация</button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            autoFocus
          />
          <input
            type="password"
            placeholder="Пароль"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            minLength={3}
          />
          <button type="submit" className="btn-primary" disabled={loading} style={{ marginTop: 4 }}>
            {loading ? 'Загрузка...' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
          </button>
        </form>

        {error && <div className="error-msg">{error}</div>}
        {success && <div className="success-msg">{success}</div>}
      </div>
    </div>
  )
}
