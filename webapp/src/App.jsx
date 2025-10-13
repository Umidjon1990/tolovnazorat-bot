import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { initTelegram } from './utils/telegram'
import Contract from './pages/Contract'
import Courses from './pages/Courses'
import Phone from './pages/Phone'
import Payment from './pages/Payment'

function App() {
  useEffect(() => {
    initTelegram()
  }, [])

  return (
    <BrowserRouter>
      <div style={styles.app}>
        <Routes>
          <Route path="/" element={<Contract />} />
          <Route path="/courses" element={<Courses />} />
          <Route path="/phone" element={<Phone />} />
          <Route path="/payment" element={<Payment />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

const styles = {
  app: {
    minHeight: '100vh',
    backgroundColor: '#ffffff',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
  }
}

export default App
