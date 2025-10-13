import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { coursesAPI, userAPI } from '../utils/api'

export default function Courses() {
  const navigate = useNavigate()
  const [courses, setCourses] = useState([])
  const [loading, setLoading] = useState(true)
  const [selecting, setSelecting] = useState(false)

  useEffect(() => {
    loadCourses()
  }, [])

  const loadCourses = async () => {
    try {
      const { data } = await coursesAPI.getAll()
      setCourses(data.courses)
    } catch (error) {
      alert('Kurslarni yuklashda xatolik')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectCourse = async (courseName) => {
    setSelecting(true)
    try {
      await userAPI.selectCourse(courseName)
      navigate('/phone')
    } catch (error) {
      alert('Xatolik: ' + error.message)
    } finally {
      setSelecting(false)
    }
  }

  if (loading) return <div style={styles.loading}>Yuklanmoqda...</div>

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>📚 KURS TANLANG</h2>
      <div style={styles.grid}>
        {courses.map(course => (
          <button
            key={course.id}
            onClick={() => handleSelectCourse(course.name)}
            disabled={selecting}
            style={{
              ...styles.courseButton,
              backgroundColor: course.type === 'premium' ? '#FFD700' : '#0088cc'
            }}
          >
            <div style={styles.emoji}>{course.emoji}</div>
            <div style={styles.courseName}>{course.name}</div>
          </button>
        ))}
      </div>
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
  loading: {
    textAlign: 'center',
    padding: '50px',
    fontSize: '18px'
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: '15px'
  },
  courseButton: {
    padding: '20px 10px',
    border: 'none',
    borderRadius: '12px',
    color: 'white',
    cursor: 'pointer',
    fontWeight: 'bold',
    fontSize: '14px',
    textAlign: 'center',
    transition: 'transform 0.2s',
    ':active': {
      transform: 'scale(0.95)'
    }
  },
  emoji: {
    fontSize: '32px',
    marginBottom: '8px'
  },
  courseName: {
    fontSize: '13px',
    lineHeight: '1.2'
  }
}
