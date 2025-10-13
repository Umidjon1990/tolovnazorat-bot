import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { userAPI } from '../utils/api'
import { setMainButton, hideMainButton } from '../utils/telegram'

const CONTRACT_TEXT = `ONLAYN O'QUV SHARTNOMA

Men ushbu shartnoma shartlarini to'liq o'qib chiqdim va quyidagilar bilan roziman:

1. Kursga kirish uchun to'lov amalga oshiriladi
2. Obuna muddati 30 kun
3. Kursdan foydalanish shaxsiy maqsadlarda
4. Qoidalarni buzish guruhdan chiqarilishga sabab bo'ladi

To'lov qilish orqali ushbu shartnomani qabul qilaman.`

export default function Contract() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)

  const handleAccept = async () => {
    setLoading(true)
    try {
      const agreedAt = Math.floor(Date.now() / 1000)
      await userAPI.register({ agreed_at: agreedAt })
      navigate('/courses')
    } catch (error) {
      alert('Xatolik yuz berdi: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>📄 SHARTNOMA</h2>
      <div style={styles.contractBox}>
        <pre style={styles.contractText}>{CONTRACT_TEXT}</pre>
      </div>
      <button 
        onClick={handleAccept} 
        disabled={loading}
        style={styles.button}
      >
        {loading ? 'Yuklanmoqda...' : '✅ Tasdiqlayman'}
      </button>
    </div>
  )
}

const styles = {
  container: {
    padding: '20px',
    maxWidth: '600px',
    margin: '0 auto'
  },
  title: {
    textAlign: 'center',
    color: '#0088cc',
    marginBottom: '20px'
  },
  contractBox: {
    backgroundColor: '#f5f5f5',
    padding: '15px',
    borderRadius: '8px',
    marginBottom: '20px',
    maxHeight: '400px',
    overflowY: 'auto'
  },
  contractText: {
    whiteSpace: 'pre-wrap',
    fontSize: '14px',
    lineHeight: '1.6'
  },
  button: {
    width: '100%',
    padding: '15px',
    fontSize: '16px',
    fontWeight: 'bold',
    backgroundColor: '#0088cc',
    color: 'white',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer'
  }
}
