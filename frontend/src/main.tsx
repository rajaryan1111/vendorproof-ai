import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { Dashboard } from './Dashboard'
import './style.css'

createRoot(document.getElementById('root')!).render(<BrowserRouter><aside><strong>VendorProof AI</strong><nav><Link to="/">Overview</Link></nav></aside><main><header>Workspace</header><Routes><Route path="/" element={<Dashboard/>}/><Route path="*" element={<><h1>Page unavailable</h1><Link to="/">Return to overview</Link></>}/></Routes></main></BrowserRouter>)
