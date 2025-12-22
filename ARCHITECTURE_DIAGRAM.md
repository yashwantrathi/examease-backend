# Student Feedback System - Visual Architecture

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        STUDENT MODE                                  │
│                                                                      │
│  Student fills feedback survey:                                     │
│  ├─ Selects Subject (e.g., "Mathematics")                          │
│  ├─ Enters Feedback Text (e.g., "Great course!")                   │
│  ├─ Rates 1-5 stars                                                │
│  └─ Answers survey questions                                        │
│                                                                      │
│          ↓ POST /submit-survey                                      │
│                                                                      │
│  {                                                                   │
│    "student_id": "uuid",                                            │
│    "student_name": "John Doe",                                      │
│    "subject": "Mathematics",                                        │
│    "feedback_text": "Great course!",                                │
│    "rating": 5,                                                     │
│    "answers": { "Q1": "answer1", "Q2": "answer2" }                │
│  }                                                                   │
└─────────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                               │
│                                                                      │
│  POST /submit-survey                                                │
│  ├─ Validates data                                                  │
│  ├─ Extracts student_name if not provided                          │
│  └─ Inserts into feedback_submissions table                         │
└─────────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    DATABASE (Supabase)                               │
│                                                                      │
│  Table: feedback_submissions                                         │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ id   │ student_id │ student_name │ subject │ rating │    │       │
│  ├──────┼────────────┼──────────────┼─────────┼────────┤    │       │
│  │ u123 │   u999    │  John Doe    │  Math   │   5    │    │       │
│  │ u124 │   u998    │  Jane Smith  │  Math   │   4    │    │       │
│  │ u125 │   u997    │  Bob Jones   │  Science│   5    │    │       │
│  └──────┴────────────┴──────────────┴─────────┴────────┘    │       │
│                                                              │       │
│  Indexes:                                                    │       │
│  - feedback_submissions_subject_idx (ON subject)            │       │
│  - feedback_submissions_student_id_idx (ON student_id)      │       │
│  - feedback_submissions_created_at_idx (ON created_at)      │       │
└─────────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                               │
│                                                                      │
│  GET /student-feedback/{subject}                                    │
│  Example: GET /student-feedback/Mathematics                         │
│  ├─ Query feedback_submissions WHERE subject = 'Mathematics'        │
│  ├─ Order by created_at DESC                                        │
│  ├─ Format response with student info + feedback                    │
│  └─ Calculate average_rating                                        │
└─────────────────────────────────────────────────────────────────────┘
                            ↓
                    API Response:
                    {
                      "subject": "Mathematics",
                      "total_feedback": 2,
                      "average_rating": 4.5,
                      "feedback_list": [
                        {
                          "id": "u123",
                          "student_name": "John Doe",
                          "rating": 5,
                          "feedback_text": "Great course!",
                          "submitted_at": "2024-12-21T10:00:00Z"
                        },
                        {
                          "id": "u124",
                          "student_name": "Jane Smith",
                          "rating": 4,
                          "feedback_text": "Good content",
                          "submitted_at": "2024-12-21T09:30:00Z"
                        }
                      ]
                    }
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      TEACHER MODE (Frontend)                         │
│                                                                      │
│  TeacherDashboard Component                                         │
│  ├─ useEffect: Fetch all subject names from assignments/exams       │
│  ├─ For each subject: GET /student-feedback/{subject}              │
│  └─ Store in state: studentFeedback                                │
│                                                                      │
│  Render "💬 Student Feedback Forms" Dashboard:                      │
│  ├─ Iterate through studentFeedback by subject                      │
│  ├─ Show expandable subject sections                                │
│  ├─ Display feedback items with:                                    │
│  │  ├─ Student name                                                 │
│  │  ├─ Rating (⭐ 1-5 with color coding)                            │
│  │  ├─ Feedback text                                                │
│  │  └─ Survey answers                                               │
│  ├─ Show average rating per subject                                │
│  └─ Scrollable if many feedback items                              │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Structure

```
TeacherDashboard
├── State:
│   ├── studentFeedback: { "Math": [...], "Science": [...] }
│   ├── assignments: [...]
│   ├── results: [...]
│   └── expandedSubject: null | "Math" | "Science"
│
├── Functions:
│   ├── fetchStudentFeedback() - Calls GET /student-feedback/{subject}
│   ├── fetchResults() - Gets exam submissions
│   └── fetchAssignments() - Gets assignments
│
└── Render:
    └── div.dashboard-grid (2 columns)
        ├── Dashboard 1: Class Overview
        ├── Dashboard 2: Exam Results
        ├── Dashboard 3: Student Feedback Forms ← NEW!
        │   └── For each subject:
        │       ├── Expandable subject header
        │       └── Feedback items (when expanded):
        │           ├── Student name
        │           ├── Rating (color-coded)
        │           ├── Feedback text
        │           └── Survey answers
        └── Dashboard 4: Assignment Status
```

## Rating Color Scheme

```
Rating 5: ⭐⭐⭐⭐⭐  Green (#d4edda)   "Excellent"
Rating 4: ⭐⭐⭐⭐    Cyan (#d1ecf1)    "Good"
Rating 3: ⭐⭐⭐      Yellow (#fff3cd)  "Average"
Rating 2: ⭐⭐        Red (#f8d7da)     "Poor"
Rating 1: ⭐         Red (#f8d7da)     "Very Poor"
```

## Database Schema

```sql
feedback_submissions
├── id (UUID, PK)
├── student_id (UUID, FK)
├── student_name (TEXT)
├── subject (TEXT) ← Used for grouping in teacher view
├── feedback_text (TEXT)
├── rating (INT, 1-5)
├── answers (JSONB) ← Survey responses
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)

Indexes:
├── feedback_submissions_subject_idx
├── feedback_submissions_student_id_idx
└── feedback_submissions_created_at_idx
```

## Comparison: Before vs After

### BEFORE
```
Teacher Dashboard
├─ Dashboard 1: Class Overview
├─ Dashboard 2: Exam Results
│   └─ Shows exam performance (scores)
├─ Dashboard 3: Feedback by Subject
│   └─ Shows exam feedback (AI-generated feedback on exams)
└─ Dashboard 4: Assignment Status
```

### AFTER
```
Teacher Dashboard
├─ Dashboard 1: Class Overview
├─ Dashboard 2: Exam Results
│   └─ Shows exam performance (scores)
├─ Dashboard 3: Student Feedback Forms ← CHANGED!
│   └─ Shows course feedback (student opinions about the course)
└─ Dashboard 4: Assignment Status
```

## Key Points

1. **Separate from Exam Feedback**: This is NOT about exam performance feedback
   - Exam feedback = AI-generated feedback on how students performed
   - Course feedback = Student opinions about the course/subject

2. **Organized by Subject**: Teachers see feedback grouped by course subject
   - Mathematics feedback separate from Science feedback
   - Easy to see what students think about each course

3. **Expandable Sections**: Teachers can click to expand/collapse subjects
   - Keeps interface clean and organized
   - Only shows details when interested

4. **Ratings & Comments**: Each feedback includes:
   - Star rating (1-5) with color coding
   - Text feedback from student
   - Survey responses
   - Timestamp

5. **Real-time Updates**: As students submit feedback surveys:
   - Data automatically stored in database
   - Teachers can refresh dashboard to see new feedback
   - No manual data entry needed
```

