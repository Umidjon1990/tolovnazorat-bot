from fastapi import APIRouter

router = APIRouter(prefix="/api/courses", tags=["courses"])

COURSES = [
    {"id": 1, "name": "A0 Standard", "type": "standard", "level": "A0", "emoji": "📗"},
    {"id": 2, "name": "A0 Premium", "type": "premium", "level": "A0", "emoji": "⭐"},
    {"id": 3, "name": "A1 Standard", "type": "standard", "level": "A1", "emoji": "📘"},
    {"id": 4, "name": "A1 Premium", "type": "premium", "level": "A1", "emoji": "⭐"},
    {"id": 5, "name": "A2 Standard", "type": "standard", "level": "A2", "emoji": "📙"},
    {"id": 6, "name": "A2 Premium", "type": "premium", "level": "A2", "emoji": "⭐"},
    {"id": 7, "name": "B1 Standard", "type": "standard", "level": "B1", "emoji": "📕"},
    {"id": 8, "name": "B1 Premium", "type": "premium", "level": "B1", "emoji": "⭐"},
    {"id": 9, "name": "B2 Standard", "type": "standard", "level": "B2", "emoji": "📔"},
    {"id": 10, "name": "B2 Premium", "type": "premium", "level": "B2", "emoji": "⭐"},
    {"id": 11, "name": "CEFR PRO Standard", "type": "standard", "level": "PRO", "emoji": "🎓"},
    {"id": 12, "name": "CEFR PRO Premium", "type": "premium", "level": "PRO", "emoji": "⭐"},
    {"id": 13, "name": "Grammatika Standard", "type": "standard", "level": "GRAM", "emoji": "📚"},
    {"id": 14, "name": "Grammatika Premium", "type": "premium", "level": "GRAM", "emoji": "⭐"}
]

@router.get("")
async def get_courses():
    """Get all 14 courses"""
    return {"courses": COURSES}

@router.get("/{course_id}")
async def get_course(course_id: int):
    """Get course by ID"""
    course = next((c for c in COURSES if c["id"] == course_id), None)
    if not course:
        return {"error": "Course not found"}, 404
    return {"course": course}
