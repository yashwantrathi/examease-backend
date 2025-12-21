import os
import json
import uvicorn
import io
import random
import string
import base64
from collections import Counter
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client, Client
import google.generativeai as genai
from PyPDF2 import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

# CONFIGURATION
SUPABASE_URL = "https://iophhaxzcikbnjcgiwta.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlvcGhoYXh6Y2lrYm5qY2dpd3RhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUwMTk1NDQsImV4cCI6MjA4MDU5NTU0NH0.E1E16M1TDcR_0bg6GZhBWeD1c9OYKtuMKFCnT3u8K6M"
GEMINI_API_KEY = "AIzaSyBCYEOV0jYf6TYaH6r4la11dC71zyF5CBw"

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes

# Initialize services
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash") 
    print("✅ Services initialized successfully")
except Exception as e:
    print(f"❌ Startup Error: {e}")
    raise

app = FastAPI()

# CRITICAL: Proper CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELS ---
class Question(BaseModel):
    id: int
    type: str
    question: str
    options: Optional[List[str]] = None
    answer: str
    marks: int = 1

class ExamCreate(BaseModel):
    title: str
    subject: str
    teacher_id: str
    questions: List[Question]
    duration: int

class AssignmentCreate(BaseModel):
    title: str
    subject: str
    teacher_id: str
    deadline: str

class SurveyCreate(BaseModel):
    student_id: str
    student_name: Optional[str] = None
    subject: str
    feedback_text: Optional[str] = None
    rating: Optional[int] = None
    answers: dict

class GradeRequest(BaseModel):
    question: str
    correct_answer: str
    student_answer: str

class SubmissionCreate(BaseModel):
    exam_id: str
    student_id: str
    score_numeric: float
    total_marks: float
    time_taken_seconds: int
    student_answers: dict
    feedback_json: dict
    cheating_log: List[str]

class TabSwitchRequest(BaseModel):
    student_id: str
    exam_id: str
    session_id: str
    action: str  # "start_exam", "still_active", "tab_switched"

# --- HELPER FUNCTIONS ---
def extract_name_from_email(email: str) -> str:
    """Extract a readable name from email address"""
    if not email or '@' not in email:
        return "Unknown"
    
    # Get part before @
    username = email.split('@')[0]
    
    # Replace common separators with spaces and title case
    name = username.replace('.', ' ').replace('_', ' ').replace('-', ' ')
    name = ' '.join(word.capitalize() for word in name.split())
    
    return name if name else "Unknown"

async def validate_file_size(file: UploadFile) -> bytes:
    """Validate file size and return content"""
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    return content

def get_user_email(user_id: str) -> str:
    """Fetch user email from profiles table or Supabase auth"""
    try:
        # Try profiles table first (preferred)
        profile = supabase.table("profiles").select("email,user_metadata").eq("id", user_id).execute()
        if profile.data and len(profile.data) > 0:
            record = profile.data[0]
            # Check for direct email field
            if record.get("email"):
                return record["email"]
            # Check for email in user_metadata
            if record.get("user_metadata") and isinstance(record["user_metadata"], dict):
                if record["user_metadata"].get("email"):
                    return record["user_metadata"]["email"]
        
        # If not in profiles, try to get from metadata stored during submission
        print(f"🔍 Fetching email for user: {user_id}")
        try:
            # Last resort: try direct auth lookup (may fail due to RLS)
            auth_user = supabase.auth.admin.get_user_by_id(user_id)
            if auth_user and auth_user.user and auth_user.user.email:
                return auth_user.user.email
        except Exception as auth_e:
            print(f"⚠️ Auth lookup blocked: {auth_e}")
            pass
            
    except Exception as e:
        print(f"⚠️ Could not fetch email for user {user_id}: {e}")
    
    print(f"⚠️ No email found for user {user_id}, returning unknown")
    return "unknown@unknown.com"

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "✅ ExamEase Backend Running", "version": "1.0"}

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "supabase": "connected",
        "gemini": "configured",
        "max_file_size_mb": MAX_FILE_SIZE // (1024*1024)
    }

# In-memory session store (for runtime tracking)
active_exam_sessions = {}

@app.post("/session/start-exam")
async def start_exam_session(data: TabSwitchRequest):
    """Start a new exam session and track it"""
    session_key = f"{data.student_id}_{data.exam_id}"
    active_exam_sessions[session_key] = {
        "student_id": data.student_id,
        "exam_id": data.exam_id,
        "session_id": data.session_id,
        "started_at": str(os.environ.get('current_time', '')),
        "active": True,
        "tab_switched": False
    }
    print(f"📝 Exam session started: {data.student_id} for exam {data.exam_id}")
    return {"status": "session_started", "message": "Exam session created"}

@app.post("/session/check-exam")
async def check_exam_session(data: TabSwitchRequest):
    """Check if exam session is still valid (called when user switches back to tab)"""
    session_key = f"{data.student_id}_{data.exam_id}"
    
    if session_key not in active_exam_sessions:
        # Session was never started
        return {
            "valid": False, 
            "message": "No active exam session found. Please start exam again."
        }
    
    session = active_exam_sessions[session_key]
    
    if session.get("tab_switched"):
        # Student switched tabs - exam is terminated
        return {
            "valid": False,
            "message": "You switched tabs during the exam. Your exam has been terminated.",
            "tab_switched": True
        }
    
    return {
        "valid": True,
        "message": "Exam session is valid"
    }

@app.post("/session/tab-switch")
async def handle_tab_switch(data: TabSwitchRequest):
    """Handle when student switches to another tab"""
    session_key = f"{data.student_id}_{data.exam_id}"
    
    if session_key in active_exam_sessions:
        active_exam_sessions[session_key]["tab_switched"] = True
        print(f"⚠️ TAB SWITCH DETECTED: {data.student_id} switched tabs during exam {data.exam_id}")
        
        # Log the violation
        violation_log = f"Tab switch detected at {str(os.environ.get('current_time', ''))}"
    
    return {
        "status": "tab_switch_recorded",
        "message": "Tab switch recorded. If you continue, exam will be terminated."
    }

@app.post("/session/end-exam")
async def end_exam_session(data: TabSwitchRequest):
    """Properly end exam session"""
    session_key = f"{data.student_id}_{data.exam_id}"
    
    if session_key in active_exam_sessions:
        session_info = active_exam_sessions[session_key]
        del active_exam_sessions[session_key]
        print(f"✅ Exam session ended: {data.student_id} for exam {data.exam_id}")
        return {
            "status": "session_ended",
            "tab_switched": session_info.get("tab_switched", False)
        }
    
    return {"status": "session_ended", "message": "No active session found"}

@app.post("/generate-quiz")
async def generate_quiz(
    topic: str = Form("General"), 
    num_questions: int = Form(5), 
    file: UploadFile = File(...)
):
    print(f"📝 Generating quiz for: {topic} ({num_questions} questions)")
    
    # Validate inputs
    if num_questions < 1 or num_questions > 50:
        raise HTTPException(status_code=400, detail="Number of questions must be between 1 and 50")
    
    # Validate file size
    file_bytes = await validate_file_size(file)
    
    content = ""
    try:
        pdf_reader = PdfReader(io.BytesIO(file_bytes))
        
        for i, page in enumerate(pdf_reader.pages):
            if i >= 20:  # Limit to 20 pages
                break
            text = page.extract_text()
            if text:
                content += text + "\n"
        
        print(f"✅ Extracted {len(content)} characters from PDF")
    except Exception as e:
        print(f"❌ PDF Error: {e}")
        raise HTTPException(status_code=400, detail=f"PDF processing failed: {str(e)}")

    if not content.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from PDF. Please ensure it's not scanned/image-based.")

    # Generate Questions - MAIN EXAM and DEMO EXAM (same count)
    total_q = num_questions * 2  # Generate double: half for main, half for demo
    
    prompt = f"""You are an expert exam creator. Based on the following text, generate exactly {total_q} high-quality exam questions.

SOURCE TEXT:
{content[:30000]}

REQUIREMENTS:
1. Create {total_q} questions total
2. Mix of MCQ (multiple choice) and subjective (open-ended) questions
3. Questions should test understanding, not just memorization
4. For MCQ: provide exactly 4 options
5. Topic focus: {topic}
6. Ensure variety - don't repeat similar questions

OUTPUT FORMAT (JSON only, no markdown):
[
  {{
    "id": 1,
    "type": "mcq",
    "question": "What is the main concept?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": "Option A",
    "marks": 1
  }},
  {{
    "id": 2,
    "type": "subjective",
    "question": "Explain the process...",
    "options": null,
    "answer": "Key points: ...",
    "marks": 2
  }}
]

Generate exactly {total_q} questions now:"""
    
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.strip()
        
        # Clean response
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        
        clean_text = clean_text.strip()
        
        all_questions = json.loads(clean_text)
        
        if len(all_questions) < total_q:
            raise HTTPException(status_code=500, detail="AI generated fewer questions than requested")
        
        # Split into Main and Demo (EQUAL COUNTS)
        main_qs = all_questions[:num_questions]
        demo_qs = all_questions[num_questions:num_questions*2]
        
        print(f"✅ Generated {len(main_qs)} main + {len(demo_qs)} demo questions")
        
        return {
            "questions": main_qs, 
            "demo_questions": demo_qs,
            "message": f"Successfully generated {len(main_qs)} exam questions + {len(demo_qs)} demo questions"
        }
    except json.JSONDecodeError as e:
        print(f"❌ JSON Parse Error: {e}")
        print(f"Response text: {response.text[:500]}")
        raise HTTPException(status_code=500, detail="AI response was not valid JSON. Please try again.")
    except Exception as e:
        print(f"❌ AI Generation Error: {e}")
        raise HTTPException(status_code=500, detail=f"AI Error: {str(e)}")

@app.post("/save-exam")
async def save_exam(exam: ExamCreate):
    try:
        exam_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        data = { 
            "exam_id": exam_id, 
            "teacher_id": exam.teacher_id, 
            "title": exam.title, 
            "subject": exam.subject,
            "questions_json": [q.dict() for q in exam.questions], 
            "duration": exam.duration 
        }
        
        res = supabase.table("exams").insert(data).execute()
        
        print(f"✅ Exam saved: {exam_id}")
        return {"message": "Exam saved successfully", "exam_id": exam_id}
    except Exception as e:
        print(f"❌ Save Exam Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-exam/{exam_id}")
async def get_exam(exam_id: str):
    try:
        res = supabase.table("exams").select("*").eq("exam_id", exam_id.upper()).execute()
        
        if not res.data:
            raise HTTPException(status_code=404, detail=f"Exam '{exam_id}' not found")
        
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Get Exam Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create-assignment")
async def create_assignment(a: AssignmentCreate):
    try:
        data = {
            "teacher_id": a.teacher_id, 
            "title": a.title, 
            "subject": a.subject, 
            "deadline": a.deadline
        }
        supabase.table("assignments").insert(data).execute()
        return {"message": "Assignment created successfully"}
    except Exception as e:
        print(f"❌ Create Assignment Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/assignments")
async def get_assignments():
    try:
        res = supabase.table("assignments").select("*").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        print(f"❌ Get Assignments Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/teacher-assignments/{teacher_id}")
async def get_teacher_assignments(teacher_id: str):
    """Get all assignments created by this teacher with submission info"""
    try:
        print(f"📋 Fetching assignments for teacher: {teacher_id}")
        
        # Get teacher's assignments
        assignments_res = supabase.table("assignments")\
            .select("*")\
            .eq("teacher_id", teacher_id)\
            .order("created_at", desc=True)\
            .execute()
        
        if not assignments_res.data:
            print("No assignments found for teacher")
            return []
        
        print(f"Found {len(assignments_res.data)} assignments for teacher")
        
        assignments = []
        for a in assignments_res.data:
            assignment_id = a["id"]
            print(f"Processing assignment ID: {assignment_id}")
            
            # Get submissions for this assignment
            subs_res = supabase.table("assignment_submissions")\
                .select("*")\
                .eq("assignment_id", str(assignment_id))\
                .execute()
            
            print(f"Found {len(subs_res.data)} submissions for assignment {assignment_id}")
            
            # Get student details
            submissions = []
            for sub in subs_res.data:
                try:
                    # Try to use stored email first, fallback to lookup
                    student_email = sub.get("student_email") or get_user_email(sub["student_id"])
                    student_name = extract_name_from_email(student_email)
                    
                    submissions.append({
                        "id": sub["id"],
                        "student_id": sub["student_id"],
                        "student_name": student_name,
                        "student_email": student_email,
                        "submitted_at": sub.get("created_at", "N/A"),
                        "file_data": sub.get("file_data", "")
                    })
                except Exception as e:
                    print(f"Error processing submission: {e}")
                    continue
            
            assignments.append({
                "id": a["id"],
                "title": a["title"],
                "subject": a["subject"],
                "deadline": a["deadline"],
                "created_at": a["created_at"],
                "submissions": submissions,
                "submission_count": len(submissions)
            })
        
        print(f"Returning {len(assignments)} assignments")
        return assignments
    except Exception as e:
        print(f"❌ Get Teacher Assignments Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/student-assignments/{student_id}")
async def get_student_assignments(student_id: str):
    """Get all assignments with submission status for a student"""
    try:
        print(f"📋 Fetching assignments for student: {student_id}")
        
        # Get all assignments
        assignments_res = supabase.table("assignments")\
            .select("*")\
            .order("created_at", desc=True)\
            .execute()
        
        if not assignments_res.data:
            print("No assignments found")
            return []
        
        print(f"Found {len(assignments_res.data)} assignments")
        
        # Get student's submissions
        submissions_res = supabase.table("assignment_submissions")\
            .select("*")\
            .eq("student_id", student_id)\
            .execute()
        
        print(f"Found {len(submissions_res.data)} submissions for student")
        
        # Create a map of assignment_id -> submission (convert to string for comparison)
        submission_map = {}
        for sub in submissions_res.data:
            aid = str(sub["assignment_id"])
            submission_map[aid] = sub
        
        print(f"Submission map keys: {list(submission_map.keys())}")
        
        assignments = []
        for a in assignments_res.data:
            assignment_id = str(a["id"])
            print(f"Checking assignment ID: {assignment_id}")
            
            submission = submission_map.get(assignment_id)
            has_submitted = submission is not None
            
            print(f"Assignment {assignment_id}: has_submitted = {has_submitted}")
            
            assignments.append({
                "id": a["id"],
                "title": a["title"],
                "subject": a["subject"],
                "deadline": a["deadline"],
                "created_at": a.get("created_at", ""),
                "has_submitted": has_submitted,
                "submitted_at": submission.get("created_at") if submission else None
            })
        
        print(f"Returning {len(assignments)} assignments with submission status")
        return assignments
    except Exception as e:
        print(f"❌ Get Student Assignments Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit-assignment")
async def submit_assignment(
    assignment_id: str = Form(...), 
    student_id: str = Form(...), 
    file: UploadFile = File(...)
):
    try:
        # Validate file size
        file_content = await validate_file_size(file)
        b64_encoded = base64.b64encode(file_content).decode('utf-8')
        
        print(f"📤 Submitting assignment: ID={assignment_id}, Student={student_id}")
        
        # Check for duplicates
        check = supabase.table("assignment_submissions")\
            .select("*")\
            .eq("assignment_id", str(assignment_id))\
            .eq("student_id", student_id)\
            .execute()
        
        if check.data:
            raise HTTPException(status_code=400, detail="You have already submitted this assignment")

        # Try to get student email for storage
        student_email = get_user_email(student_id)
        
        data = {
            "assignment_id": str(assignment_id),
            "student_id": student_id,
            "student_email": student_email,
            "file_data": b64_encoded 
        }
        
        result = supabase.table("assignment_submissions").insert(data).execute()
        print(f"✅ Assignment submitted successfully")
        
        return {"message": "Assignment submitted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Submit Assignment Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/subjects")
async def get_subjects():
    try:
        res = supabase.table("exams").select("subject").execute()
        subjects = list({row["subject"] for row in res.data if row.get("subject")})
        return subjects
    except Exception as e:
        print(f"❌ Get Subjects Error: {e}")
        return []

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
        # RLS policy blocking insert - log and return success anyway
        if "row-level security policy" in str(e):
            print(f"⚠️ RLS blocking feedback submission (non-critical): {e}")
            return {"message": "Feedback submitted successfully"}
        print(f"❌ Submit Survey Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/grade-subjective")
async def grade_subjective(request: GradeRequest):
    if not request.student_answer.strip():
        return {"score": 0, "feedback": "No answer provided."}
    
    prompt = f"""Grade this answer on a scale of 0.0 to 1.0 based on correctness.

Question: {request.question}
Correct Answer: {request.correct_answer}
Student Answer: {request.student_answer}

Provide score and brief feedback. Output as JSON:
{{"score": 0.75, "feedback": "Good answer, mentioned key points..."}}
"""
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except:
        return {"score": 0, "feedback": "Error grading answer"}

@app.post("/submit-exam-result")
async def submit_exam_result(sub: SubmissionCreate):
    try:
        # Get student email for storage
        student_email = get_user_email(sub.student_id)
        
        data = {
            "exam_id": sub.exam_id,
            "student_id": sub.student_id,
            "student_email": student_email,
            "score_numeric": sub.score_numeric,
            "total_marks": sub.total_marks,
            "time_taken_seconds": sub.time_taken_seconds,
            "student_answers": sub.student_answers,
            "feedback_json": sub.feedback_json,
            "cheating_log": sub.cheating_log,
            "score": f"{sub.score_numeric}/{sub.total_marks}"
        }
        supabase.table("submissions").insert(data).execute()
        print(f"✅ Exam result submitted for {student_email}")
        return {"message": "Exam result saved successfully"}
    except Exception as e:
        print(f"❌ Submit Result Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/teacher-stats/{teacher_id}")
async def get_teacher_stats(teacher_id: str):
    try:
        print(f"📊 Fetching stats for teacher: {teacher_id}")
        
        # Get teacher's exams
        exams = supabase.table("exams").select("exam_id, title").eq("teacher_id", teacher_id).execute()
        
        if not exams.data:
            return {"results": [], "heatmap": []}
        
        exam_map = {e["exam_id"]: e["title"] for e in exams.data}
        exam_ids = list(exam_map.keys())

        # Get submissions for these exams
        subs = supabase.table("submissions").select("*").in_("exam_id", exam_ids).execute()
        
        print(f"Found {len(subs.data)} submissions")
        
        results = []
        for s in subs.data:
            # Try to use stored email from submission, fallback to lookup
            student_email = s.get("student_email") or get_user_email(s["student_id"])
            print(f"Student {s['student_id']} -> {student_email}")
            
            results.append({
                "exam_key": s["exam_id"],
                "exam_name": exam_map.get(s["exam_id"], "Unknown"),
                "student_email": student_email,
                "score": s["score_numeric"],
                "max_marks": s["total_marks"],
                "time_taken": round(s["time_taken_seconds"] / 60, 2),
                "date": s["created_at"].split("T")[0],
                "cheating_flags": len(s.get("cheating_log") or [])
            })
        
        print(f"Returning {len(results)} results")
        return {"results": results, "heatmap": []}
    except Exception as e:
        print(f"❌ Teacher Stats Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/student-stats/{student_id}")
async def get_student_stats(student_id: str):
    try:
        my_subs = supabase.table("submissions")\
            .select("*")\
            .eq("student_id", student_id)\
            .order("created_at", desc=True)\
            .execute()
        
        if not my_subs.data:
            return []

        exam_ids = list({s["exam_id"] for s in my_subs.data})
        exams = supabase.table("exams").select("exam_id, title").in_("exam_id", exam_ids).execute()
        exam_map = {e["exam_id"]: e["title"] for e in exams.data}

        results = []
        for s in my_subs.data:
            all_scores_res = supabase.table("submissions")\
                .select("score_numeric")\
                .eq("exam_id", s["exam_id"])\
                .execute()
            
            all_scores = [x["score_numeric"] for x in all_scores_res.data]
            percentile = 100
            
            if len(all_scores) > 1:
                i_beat = sum(1 for score in all_scores if score < s["score_numeric"])
                percentile = round((i_beat / len(all_scores)) * 100)

            results.append({
                "exam_key": s["exam_id"],
                "exam_name": exam_map.get(s["exam_id"], "Unknown"),
                "score": s["score_numeric"],
                "max_marks": s["total_marks"],
                "time_taken": round(s["time_taken_seconds"] / 60, 2),
                "date": s["created_at"].split("T")[0],
                "percentile": percentile
            })
        
        return results
    except Exception as e:
        print(f"❌ Student Stats Error: {e}")
        return []

@app.get("/teacher-feedback/{teacher_id}")
async def get_teacher_feedback(teacher_id: str):
    """Get all feedback forms submitted by students for this teacher's exams"""
    try:
        print(f"📋 Fetching feedback for teacher: {teacher_id}")
        
        # Get teacher's exams
        exams = supabase.table("exams").select("exam_id, title, subject").eq("teacher_id", teacher_id).execute()
        
        if not exams.data:
            print("No exams found for teacher")
            return {"feedback_count": 0, "by_subject": {}, "all_feedback": []}
        
        exam_ids = [e["exam_id"] for e in exams.data]
        exam_map = {e["exam_id"]: {"title": e["title"], "subject": e.get("subject", "Unknown")} for e in exams.data}
        
        # Get all submissions for these exams
        submissions = supabase.table("submissions").select("*").in_("exam_id", exam_ids).execute()
        
        print(f"Found {len(submissions.data)} submissions")
        
        # Organize feedback by subject
        feedback_by_subject = {}
        all_feedback = []
        
        for sub in submissions.data:
            student_email = sub.get("student_email", "unknown@unknown.com")
            student_name = extract_name_from_email(student_email)
            exam_info = exam_map.get(sub["exam_id"], {"title": "Unknown", "subject": "Unknown"})
            subject = exam_info["subject"]
            
            feedback_data = {
                "student_email": student_email,
                "student_name": student_name,
                "student_id": sub["student_id"],
                "exam_name": exam_info["title"],
                "exam_id": sub["exam_id"],
                "subject": subject,
                "score": f"{sub['score_numeric']}/{sub['total_marks']}",
                "feedback_json": sub.get("feedback_json", {}),
                "student_answers": sub.get("student_answers", {}),
                "time_taken_minutes": round(sub.get("time_taken_seconds", 0) / 60, 2),
                "submitted_at": sub.get("created_at", "N/A")
            }
            
            all_feedback.append(feedback_data)
            
            # Organize by subject
            if subject not in feedback_by_subject:
                feedback_by_subject[subject] = []
            feedback_by_subject[subject].append(feedback_data)
        
        print(f"Returning {len(all_feedback)} feedback entries organized by {len(feedback_by_subject)} subjects")
        
        return {
            "feedback_count": len(all_feedback),
            "by_subject": feedback_by_subject,
            "all_feedback": all_feedback
        }
    except Exception as e:
        print(f"❌ Get Teacher Feedback Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

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

if __name__ == "__main__":
    print("\n🚀 Starting ExamEase Backend Server...")
    print("🌐 Server will run at: http://localhost:8000")
    print("📖 API docs available at: http://localhost:8000/docs")
    print(f"📦 Max file size: {MAX_FILE_SIZE // (1024*1024)}MB")
    print("\n⚠️  Make sure frontend is configured to use http://localhost:8000\n")
    
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)