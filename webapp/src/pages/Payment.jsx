import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { userAPI } from '../utils/api'
import { closeMiniApp } from '../utils/telegram'

export default function Payment() {
  const navigate = useNavigate()
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile) {
      setFile(selectedFile)
      setPreview(URL.createObjectURL(selectedFile))
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (!file) {
      alert('Iltimos, to\'lov chekini yuklang')
      return
    }

    setLoading(true)
    try {
      await userAPI.submitPayment(file)
      alert('✅ To\'lov yuborildi! Admin tekshiradi.')
      closeMiniApp()
    } catch (error) {
      alert('Xatolik: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>💳 TO'LOV CHEKI</h2>
      <p style={styles.description}>
        To'lov chekini rasmga olib yuklang. <br/>
        Admin tekshirib, guruhga qo'shadi.
      </p>
      
      <form onSubmit={handleSubmit} style={styles.form}>
        <label style={styles.fileLabel}>
          <input
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            style={styles.fileInput}
          />
          <div style={styles.uploadButton}>
            {preview ? '✅ Rasm tanlandi' : '📸 Rasm yuklash'}
          </div>
        </label>

        {preview && (
          <img src={preview} alt="Preview" style={styles.preview} />
        )}

        <button 
          type="submit" 
          disabled={loading || !file}
          style={{
            ...styles.button,
            opacity: (!file || loading) ? 0.5 : 1
          }}
        >
          {loading ? 'Yuklanmoqda...' : '✅ Yuborish'}
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
    gap: '20px'
  },
  fileLabel: {
    cursor: 'pointer'
  },
  fileInput: {
    display: 'none'
  },
  uploadButton: {
    padding: '15px',
    fontSize: '16px',
    fontWeight: 'bold',
    backgroundColor: '#4CAF50',
    color: 'white',
    border: 'none',
    borderRadius: '8px',
    textAlign: 'center'
  },
  preview: {
    width: '100%',
    maxHeight: '300px',
    objectFit: 'contain',
    borderRadius: '8px',
    border: '2px solid #ddd'
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
