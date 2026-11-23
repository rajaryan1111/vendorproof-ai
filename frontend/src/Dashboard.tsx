import { useEffect, useState } from 'react'
import { readHealth } from './api'

type State = 'Checking connection' | 'Connected' | 'Unavailable'
export function Dashboard() {
  const [state, setState] = useState<State>('Checking connection')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const timeout = setTimeout(() => controller.abort(), 8000)
    readHealth(controller.signal).then(() => { if (active) setState('Connected') }, () => { if (active) setState('Unavailable') }).finally(() => clearTimeout(timeout))
    return () => { active = false; clearTimeout(timeout); controller.abort() }
  }, [attempt])
  return <><h1>Workspace overview</h1><section aria-labelledby="connection"><h2 id="connection">Service connection</h2><div className="service"><div><strong>VendorProof API</strong><p>Application health · v1</p></div><span role="status" data-state={state}>{state}</span></div>{state === 'Unavailable' && <p>Check that the API is running and the configured address is reachable.</p>}<button disabled={state === 'Checking connection'} onClick={() => { setState('Checking connection'); setAttempt(n => n + 1) }}>Check again</button></section></>
}
