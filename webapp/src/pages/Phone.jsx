import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { userAPI } from '../utils/api'

export default function Phone() {
  const navigate = useNavigate()
  const [phone, setPhone] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (!/^\+?\d{9,15}$/.test(phone.trim())) {
      alert('Telefon raqam noto\'g\'ri formatda')
      return
    }

    setLoading(true)
    try {
      await userAPI.savePhone(phone.trim())
      navigate('/payment')
    } catch (error) {
      alert('Xatolik: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>📱 TELEFON RAQAM</h2>
      <p style={styles.description}>
        Iltimos, telefon raqamingizni kiriting. <br/>
        Masalan: +998901234567
      </p>
      <form onSubmit={handleSubmit} style={styles.form}>
        <input
          type="tel"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="+998901234567"
          style={styles.input}
          required
        />
        <button 
          type="submit" 
          disabled={loading}
          style={styles.button}
        >
          {loading ? 'Yuklanmoqda...' : '➡️ Davom etish'}
        </button>
      </form>
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
    marginBottom: '10px'
  },
  description: {
    textAlign: 'center',
    color: '#666',
    marginBottom: '30px',
    lineHeight: '1.6'
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '15px'
  },
  input: {
    padding: '15px',
    fontSize: '16px',
    border: '2px solid #ddd',
    borderRadius: '8px',
    outline: 'none'
  },
  button: {
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
