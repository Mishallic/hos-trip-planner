import { useEffect, useState } from 'react'

type ApiStatus = 'checking' | 'ok' | 'down'

function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')

  useEffect(() => {
    fetch('/api/health')
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((body: { status: string }) => setApiStatus(body.status === 'ok' ? 'ok' : 'down'))
      .catch(() => setApiStatus('down'))
  }, [])

  return (
    <main>
      <h1>HOS Trip Planner</h1>
      <p>Plan a trip and get hours-of-service compliant stops and daily logs.</p>
      <p>API: {apiStatus}</p>
    </main>
  )
}

export default App
