# Code Changes Reference

## Backend Changes (main.py)

### 1. Updated SurveyCreate Model (Lines 70-76)

**OLD:**
```python
class SurveyCreate(BaseModel):
    student_id: str
    subject: str
    answers: dict
```

**NEW:**
```python
class SurveyCreate(BaseModel):
    student_id: str
    student_name: Optional[str] = None
    subject: str
    feedback_text: Optional[str] = None
    rating: Optional[int] = None
    answers: dict
```

### 2. Updated /submit-survey Endpoint (Lines 608-632)

**OLD:**
```python
@app.post("/submit-survey")
async def submit_survey(s: SurveyCreate):
    try:
        data = {
            "student_id": s.student_id, 
            "subject": s.subject, 
            "answers": s.answers
        }
        supabase.table("surveys").insert(data).execute()
        return {"message": "Survey submitted successfully"}
    except Exception as e:
        print(f"❌ Submit Survey Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**NEW:**
```python
@app.post("/submit-survey")
async def submit_survey(s: SurveyCreate):
    try:
        # Extract student name from email if not provided
        student_name = s.student_name
        if not student_name and s.student_id:
            # Try to get from auth.users or profiles
            try:
                user_res = supabase.auth.admin.get_user(s.student_id)
                student_name = user_res.user.email.split('@')[0] if user_res.user.email else "Student"
            except:
                student_name = "Student"
        
        data = {
            "student_id": s.student_id,
            "student_name": student_name,
            "subject": s.subject,
            "feedback_text": s.feedback_text,
            "rating": s.rating,
            "answers": s.answers
        }
        supabase.table("feedback_submissions").insert(data).execute()
        return {"message": "Feedback submitted successfully"}
    except Exception as e:
        print(f"❌ Submit Survey Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 3. NEW Endpoint: /student-feedback/{subject} (Lines 837-879)

```python
@app.get("/student-feedback/{subject}")
async def get_student_feedback(subject: str):
    """Get all student feedback submissions for a specific subject"""
    try:
        print(f"📋 Fetching student feedback for subject: {subject}")
        
        # Get all feedback submissions for this subject
        result = supabase.table("feedback_submissions")\
            .select("*")\
            .eq("subject", subject)\
            .order("created_at", desc=True)\
            .execute()
        
        feedback_list = result.data if result.data else []
        print(f"Found {len(feedback_list)} feedback submissions for {subject}")
        
        # Format the response
        formatted_feedback = []
        for feedback in feedback_list:
            formatted_feedback.append({
                "id": feedback.get("id"),
                "student_id": feedback.get("student_id"),
                "student_name": feedback.get("student_name", "Unknown"),
                "subject": feedback.get("subject"),
                "feedback_text": feedback.get("feedback_text", ""),
                "rating": feedback.get("rating"),
                "answers": feedback.get("answers", {}),
                "submitted_at": feedback.get("created_at", "N/A")
            })
        
        return {
            "subject": subject,
            "total_feedback": len(formatted_feedback),
            "feedback_list": formatted_feedback,
            "average_rating": sum(f.get("rating", 0) for f in formatted_feedback) / len(formatted_feedback) if formatted_feedback else 0
        }
    except Exception as e:
        print(f"❌ Get Student Feedback Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
```

## Frontend Changes (TeacherDashboard.jsx)

Replace your entire TeacherDashboard.jsx with the new `TeacherDashboard_UPDATED.jsx` file.

**Key features added:**
1. New state: `const [studentFeedback, setStudentFeedback] = useState({})`
2. New function: `fetchStudentFeedback()` - fetches feedback for all subjects
3. New dashboard: Dashboard 3 - "💬 Student Feedback Forms"
4. Expandable subject sections with rating colors
5. Display: Student name, rating, feedback text, survey answers
6. Responsive 2-column grid layout

**New JSX element for feedback display:**
```jsx
{/* Dashboard 3: Student Feedback Forms */}
<div className="dashboard-card" style={{ gridColumn: "1 / -1" }}>
  <div className="dashboard-title">💬 Student Feedback Forms</div>
  <div className="dashboard-scroll-content">
    {Object.entries(studentFeedback).length > 0 ? (
      // Show feedback organized by subject with expandable sections
    ) : (
      <div style={{ color: "#999", textAlign: "center", padding: "20px 0" }}>
        No student feedback yet
      </div>
    )}
  </div>
</div>
```

## Database Changes (Supabase SQL)

Run this SQL in Supabase SQL Editor:

```sql
-- Create feedback_submissions table
CREATE TABLE IF NOT EXISTS feedback_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL,
    student_name TEXT,
    subject TEXT NOT NULL,
    feedback_text TEXT,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    answers JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Add indexes
CREATE INDEX IF NOT EXISTS feedback_submissions_subject_idx ON feedback_submissions(subject);
CREATE INDEX IF NOT EXISTS feedback_submissions_student_id_idx ON feedback_submissions(student_id);
CREATE INDEX IF NOT EXISTS feedback_submissions_created_at_idx ON feedback_submissions(created_at DESC);

-- Enable RLS
ALTER TABLE feedback_submissions ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY "Students can view and insert their own feedback"
ON feedback_submissions
FOR ALL
USING (student_id = auth.uid())
WITH CHECK (student_id = auth.uid());

CREATE POLICY "Service role can access all feedback"
ON feedback_submissions
USING (true)
WITH CHECK (true)
FOR ROLE service_role;
```

## API Endpoint Examples

### Submit Feedback (Student)
```bash
POST http://localhost:8000/submit-survey
Content-Type: application/json

{
  "student_id": "092d83b1-d1d4-48d1-85f0-4e13969cf12b",
  "student_name": "John Doe",
  "subject": "Mathematics",
  "feedback_text": "Great course with excellent examples!",
  "rating": 5,
  "answers": {
    "Q1: Content clarity": "Very clear",
    "Q2: Instructor feedback": "Helpful",
    "Q3: Course pace": "Just right"
  }
}
```

### Get Feedback by Subject (Teacher)
```bash
GET http://localhost:8000/student-feedback/Mathematics

Response:
{
  "subject": "Mathematics",
  "total_feedback": 3,
  "average_rating": 4.67,
  "feedback_list": [
    {
      "id": "uuid",
      "student_id": "uuid",
      "student_name": "John Doe",
      "subject": "Mathematics",
      "feedback_text": "Great course!",
      "rating": 5,
      "answers": {...},
      "submitted_at": "2024-12-21T10:00:00Z"
    }
  ]
}
```

## Files Affected

### Modified:
- `/main.py` - 3 changes (1 model update, 2 endpoint updates)

### New Files:
- `/CREATE_FEEDBACK_TABLE.sql` - Database setup
- `/TeacherDashboard_UPDATED.jsx` - Updated frontend component
- `/STUDENT_FEEDBACK_SETUP.md` - Complete setup guide
- `/STUDENT_FEEDBACK_QUICK_SUMMARY.md` - Quick reference
- `/CODE_CHANGES_REFERENCE.md` - This file

### To Replace:
- Your current `TeacherDashboard.jsx` → Replace with `TeacherDashboard_UPDATED.jsx`

## Line Number Reference (main.py)

| Change | Lines | Type |
|--------|-------|------|
| SurveyCreate model | 70-76 | Updated |
| /submit-survey endpoint | 608-632 | Updated |
| /student-feedback endpoint | 837-879 | New |
