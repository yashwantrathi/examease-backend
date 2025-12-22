# Student Feedback Survey Forms - Complete Setup Guide

## Overview
You now have a complete system for collecting and viewing **student feedback surveys** (course feedback) separately from **exam performance feedback**. Teachers can view all student feedback organized by subject.

## Step 1: Create the Feedback Submissions Table in Supabase

1. Go to your Supabase dashboard: https://app.supabase.com
2. Navigate to **SQL Editor** → **New Query**
3. Copy and paste the contents of `CREATE_FEEDBACK_TABLE.sql`
4. Click **Run**

**What this does:**
- Creates `feedback_submissions` table with fields: `id`, `student_id`, `student_name`, `subject`, `feedback_text`, `rating`, `answers`, `created_at`
- Adds indexes for faster queries
- Sets up Row Level Security (RLS) policies

## Step 2: Update Backend (main.py)

Your backend has been updated with:

### Modified `/submit-survey` endpoint
- Now stores data in `feedback_submissions` table instead of `surveys`
- Captures: `student_id`, `student_name`, `subject`, `feedback_text`, `rating`, `answers`
- Updated `SurveyCreate` model to include all fields

### New `/student-feedback/{subject}` endpoint
- **URL:** `GET http://localhost:8000/student-feedback/{subject}`
- **Purpose:** Fetch all student feedback for a specific subject
- **Returns:**
  ```json
  {
    "subject": "Mathematics",
    "total_feedback": 5,
    "average_rating": 4.2,
    "feedback_list": [
      {
        "id": "uuid",
        "student_id": "uuid",
        "student_name": "John Doe",
        "subject": "Mathematics",
        "feedback_text": "Great course!",
        "rating": 5,
        "answers": { "question1": "answer1" },
        "submitted_at": "2024-12-21T10:00:00Z"
      }
    ]
  }
  ```

## Step 3: Update Frontend - StudentPage Component

When students submit feedback, they now submit to the "Feedback Survey" with this data:

```javascript
const feedbackData = {
  student_id: user.id,
  student_name: user.name || extractNameFromEmail(user.email),
  subject: selectedSubject,  // The course/subject being rated
  feedback_text: feedbackText,  // Their feedback comment
  rating: selectedRating,  // 1-5 stars
  answers: surveyAnswers  // Their responses to survey questions
};

fetch('http://localhost:8000/submit-survey', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(feedbackData)
});
```

## Step 4: Update Frontend - TeacherDashboard Component

1. Replace your current `TeacherDashboard.jsx` with `TeacherDashboard_UPDATED.jsx`
2. The new version includes:
   - **4 dashboards in 2-column layout:**
     1. **👥 Class Overview** - Total students, exams, pending assignments
     2. **📊 Exam Results** - List of recent exam submissions with scores
     3. **💬 Student Feedback Forms** - NEW! All student feedback organized by subject
     4. **📋 Assignment Status** - Assignment submission status
   
   - **Student Feedback Dashboard Features:**
     - Organized by subject (collapsible sections)
     - Shows: Student name, feedback rating (⭐ 1-5), feedback text, survey answers
     - Expandable feedback items with hover effects
     - Color-coded ratings (green for 5⭐, red for 1⭐)
     - Shows feedback count per subject
     - Calculates average rating for each subject

## Data Flow

### Submitting Feedback (Student)
```
Student completes feedback survey 
  ↓
POST /submit-survey 
  ↓
Data stored in feedback_submissions table
  ↓
Includes: student_id, student_name, subject, feedback_text, rating, answers
```

### Viewing Feedback (Teacher)
```
Teacher opens dashboard 
  ↓
Frontend fetches all subjects from assignments/exams 
  ↓
For each subject: GET /student-feedback/{subject}
  ↓
Feedback organized and displayed by subject
  ↓
Teacher can expand/collapse subjects and read feedback
```

## Database Schema

### feedback_submissions table
```sql
Column          | Type      | Description
----------------|-----------|-------------------------------------------
id              | UUID      | Primary key
student_id      | UUID      | Student's user ID
student_name    | TEXT      | Student's name
subject         | TEXT      | Subject/Course name (e.g., "Mathematics")
feedback_text   | TEXT      | Student's feedback comment
rating          | INT       | 1-5 star rating
answers         | JSONB     | Survey question responses
created_at      | TIMESTAMP | When feedback was submitted
updated_at      | TIMESTAMP | Last updated
```

## Testing

### Test the Backend Endpoint

```bash
# From the backend folder, ensure main.py is running:
python main.py

# In another terminal, test the endpoint:
curl "http://localhost:8000/student-feedback/Mathematics"
```

Expected response:
```json
{
  "subject": "Mathematics",
  "total_feedback": 3,
  "average_rating": 4.5,
  "feedback_list": [...]
}
```

### Test the Frontend

1. Start the frontend: `npm run dev`
2. Login as a student
3. Go to "Feedback Survey" section
4. Submit a feedback form with:
   - Subject: "Mathematics"
   - Feedback text: "Great course"
   - Rating: 5 stars
   - Survey answers: Fill in the form
5. Login as a teacher
6. Open "Student Feedback Forms" dashboard
7. Should see the feedback organized by subject

## Important Notes

1. **Subjects must match**: The subject selected in student feedback must match the subject name used in exams/assignments
2. **RLS Security**: Students can only see their own feedback via direct table access, but teachers fetch via the endpoint
3. **Ratings are optional**: `rating` field can be NULL if student doesn't rate
4. **Answers are optional**: If no survey questions, `answers` can be an empty object `{}`
5. **Student name auto-capture**: If not provided in request, it's extracted from the auth.users email

## Troubleshooting

**Issue:** "No student feedback yet" message appears
- **Solution:** Make sure students have submitted feedback with matching subject names

**Issue:** Feedback not showing in teacher dashboard
- **Solution:** 
  1. Verify data in Supabase: Check `feedback_submissions` table
  2. Check browser console for fetch errors
  3. Ensure subject names match exactly (case-sensitive)

**Issue:** Backend error when submitting feedback
- **Solution:** Check main.py console for error messages, ensure `feedback_submissions` table exists

## Summary of Changes

### Backend (main.py)
✅ Updated `SurveyCreate` model with new fields
✅ Modified `/submit-survey` endpoint to use `feedback_submissions` table
✅ Added new `/student-feedback/{subject}` endpoint
✅ Captures student name automatically

### Frontend (TeacherDashboard.jsx)
✅ Added student feedback fetching logic
✅ New "Student Feedback Forms" dashboard with expandable subjects
✅ Color-coded ratings (5-star system)
✅ Shows feedback text and survey answers
✅ Responsive 2-column layout (1 column on mobile)

### Database (Supabase)
✅ New `feedback_submissions` table created
✅ Indexes for performance
✅ RLS policies configured
