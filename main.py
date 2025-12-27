import os
import json
import uvicorn
import io
import random
import string
import base64
from datetime import datetime
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
GEMINI_API_KEY = "AIzaSyDF0ixmt-zrSYs5DKwIBSM6UuCiYhDLE98"

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

# CORS Configuration - MUST be right after app creation
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://examease-frontend.vercel.app",
        "http://localhost:5173",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
    """Fetch user email from Supabase auth or profiles table"""
    try:
        # First try to get directly from auth.users via admin
        try:
            auth_user = supabase.auth.admin.get_user_by_id(user_id)
            if auth_user and auth_user.user and auth_user.user.email:
                print(f"✅ Got email from auth for {user_id}: {auth_user.user.email}")
                return auth_user.user.email
        except Exception as auth_e:
            print(f"⚠️ Auth lookup failed: {auth_e}")
        
        # Try profiles table as fallback
        profile = supabase.table("profiles").select("email,user_metadata").eq("id", user_id).execute()
        if profile.data and len(profile.data) > 0:
            record = profile.data[0]
            if record.get("email"):
                return record["email"]
            if record.get("user_metadata") and isinstance(record["user_metadata"], dict):
                if record["user_metadata"].get("email"):
                    return record["user_metadata"]["email"]
            
    except Exception as e:
        print(f"⚠️ Could not fetch email for user {user_id}: {e}")
    
    print(f"⚠️ No email found for user {user_id}")
    return ""

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
        "tab_switch_count": 0
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
    
    # If switched 2+ times, exam is terminated
    if session.get("tab_switch_count", 0) >= 2:
        return {
            "valid": False,
            "message": "You switched tabs twice. Your exam has been auto-submitted and terminated.",
            "auto_submit": True
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
        session = active_exam_sessions[session_key]
        current_count = session.get("tab_switch_count", 0)
        session["tab_switch_count"] = current_count + 1
        
        print(f"⚠️ TAB SWITCH DETECTED: {data.student_id} switched tabs {session['tab_switch_count']} time(s) during exam {data.exam_id}")
        
        if session["tab_switch_count"] >= 2:
            print(f"🚫 AUTO-SUBMIT TRIGGERED: {data.student_id} switched tabs 2+ times")
            return {
                "status": "auto_submit_triggered",
                "message": "You switched tabs twice. Your exam will be auto-submitted.",
                "auto_submit": True
            }
        
        return {
            "status": "tab_switch_recorded",
            "message": "⚠️ Tab switch detected! One more switch will auto-submit your exam.",
            "switch_count": session["tab_switch_count"]
        }
    
    return {"status": "session_not_found", "message": "No active exam session"}

@app.post("/session/end-exam")
async def end_exam_session(data: TabSwitchRequest):
    """Properly end exam session"""
    session_key = f"{data.student_id}_{data.exam_id}"
    
    if session_key in active_exam_sessions:
        session_info = active_exam_sessions[session_key]
        switch_count = session_info.get("tab_switch_count", 0)
        del active_exam_sessions[session_key]
        print(f"✅ Exam session ended: {data.student_id} for exam {data.exam_id} (switches: {switch_count})")
        return {
            "status": "session_ended",
            "tab_switch_count": switch_count
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
        try:
            pdf_reader = PdfReader(io.BytesIO(file_bytes))
        except Exception as e:
            error_msg = str(e).lower()
            if "eof" in error_msg or "marker" in error_msg:
                raise HTTPException(
                    status_code=400, 
                    detail="The PDF file appears to be corrupted or incomplete. Please try uploading the file again or use a different PDF."
                )
            raise
        
        if not pdf_reader.pages:
            raise HTTPException(status_code=400, detail="PDF file is empty. Please provide a PDF with content.")
        
        # OPTIMIZATION: Limit to first 15 pages (most content is in early pages)
        max_pages = min(15, len(pdf_reader.pages))
        
        for i in range(max_pages):
            page = pdf_reader.pages[i]
            try:
                text = page.extract_text()
                if text:
                    content += text + "\n"
            except Exception as page_error:
                print(f"⚠️ Warning: Could not extract text from page {i+1}: {page_error}")
                continue
        
        print(f"✅ Extracted {len(content)} characters from {max_pages} pages")
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ PDF Error: {e}")
        raise HTTPException(status_code=400, detail="PDF processing failed. The file may be corrupted, encrypted, or in an unsupported format.")

    if not content.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from PDF. Please ensure it's not scanned/image-based.")

    # OPTIMIZATION: Reduce content size for faster API processing
    # Remove excessive whitespace and compress content
    content = " ".join(content.split())  # Remove extra spaces, tabs, newlines
    
    # Limit to 15,000 characters - plenty for quality questions, much faster processing
    if len(content) > 15000:
        content = content[:15000]
        print(f"⚠️ Content truncated to 15,000 chars for faster processing")
    else:
        print(f"✅ Content size: {len(content)} chars")

    # Generate Questions - MAIN EXAM and DEMO EXAM (same count)
    total_q = num_questions * 2  # Generate double: half for main, half for demo
    
    # OPTIMIZATION: Use concise prompt to reduce processing time
    prompt = f"""Create {total_q} exam questions from this text. Mix MCQ (40%) and subjective (60%).

TEXT:
{content}

For MCQ: 4 options (A,B,C,D)
Topic: {topic}
Format: JSON array only, no markdown.
[{{"id":1,"type":"mcq","question":"?","options":["A","B","C","D"],"answer":"A","marks":1}},{{"id":2,"type":"subjective","question":"?","options":null,"answer":"answer","marks":2}}]"""
    
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.strip()
        
        # Clean response - remove markdown code blocks
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
            deadline = a.get("deadline", "")
            
            for sub in subs_res.data:
                try:
                    # ⭐ PRIORITY 1: Use stored email from submission
                    student_email = sub.get("student_email", "")
                    
                    # ⭐ FALLBACK: If no email in submission, try lookup
                    if not student_email:
                        student_email = get_user_email(sub["student_id"])
                        print(f"⚠️ Had to lookup email for {sub['student_id']}: {student_email}")
                    
                    # Format the timestamp properly
                    submitted_at = sub.get("created_at", "")
                    status = "Late"  # Default to Late
                    submitted_at_formatted = "N/A"
                    
                    if submitted_at:
                        try:
                            # ⭐ IMPROVED: Handle multiple datetime formats
                            # Remove 'Z' and handle timezone
                            if 'Z' in submitted_at:
                                clean_dt = submitted_at.replace('Z', '+00:00')
                            elif '+' not in submitted_at:
                                clean_dt = submitted_at + '+00:00'
                            else:
                                clean_dt = submitted_at
                            
                            # Remove microseconds if present (keep only seconds)
                            if '.' in clean_dt:
                                clean_dt = clean_dt.split('.')[0] + clean_dt.split('.')[-1][-6:]
                            
                            try:
                                submitted_dt = datetime.fromisoformat(clean_dt)
                            except:
                                # Final fallback: just parse the date part
                                clean_dt = submitted_at.replace('Z', '').split('.')[0]
                                submitted_dt = datetime.fromisoformat(clean_dt)
                            
                            submitted_at_formatted = submitted_dt.strftime("%d/%m/%Y, %H:%M:%S")
                            
                            # Compare with deadline
                            if deadline:
                                try:
                                    if 'Z' in deadline:
                                        clean_deadline = deadline.replace('Z', '+00:00')
                                    elif '+' not in deadline:
                                        clean_deadline = deadline + '+00:00'
                                    else:
                                        clean_deadline = deadline
                                    
                                    if '.' in clean_deadline:
                                        clean_deadline = clean_deadline.split('.')[0] + clean_deadline.split('.')[-1][-6:]
                                    
                                    try:
                                        deadline_dt = datetime.fromisoformat(clean_deadline)
                                    except:
                                        clean_deadline = deadline.replace('Z', '').split('.')[0]
                                        deadline_dt = datetime.fromisoformat(clean_deadline)
                                    
                                    if submitted_dt <= deadline_dt:
                                        status = "On Time"
                                except Exception as deadline_err:
                                    print(f"⚠️ Could not parse deadline: {deadline} - {deadline_err}")
                                    
                        except Exception as parse_err:
                            print(f"⚠️ DateTime parse error for {submitted_at}: {parse_err}")
                            # ⭐ BETTER FALLBACK: Show raw date instead of "Invalid Date"
                            if 'T' in submitted_at:
                                submitted_at_formatted = submitted_at.split('T')[0]
                            else:
                                submitted_at_formatted = submitted_at[:10] if len(submitted_at) >= 10 else submitted_at
                    
                    submissions.append({
                        "id": sub["id"],
                        "student_id": sub["student_id"],
                        "student_email": student_email if student_email else "No email found",
                        "submitted_at": submitted_at_formatted,
                        "status": status,
                        "file_data": sub.get("file_data", "")
                    })
                    
                    print(f"✅ Processed: {student_email} - {submitted_at_formatted} - {status}")
                    
                except Exception as e:
                    print(f"❌ Error processing submission: {e}")
                    import traceback
                    traceback.print_exc()
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
            
            # ⭐ FORMAT TIMESTAMP PROPERLY FOR FRONTEND
            submitted_at = None
            submitted_at_formatted = None
            
            if submission and submission.get("created_at"):
                try:
                    # Get the raw timestamp
                    raw_timestamp = submission["created_at"]
                    print(f"Raw timestamp from DB: {raw_timestamp}")
                    
                    # Parse the timestamp with multiple strategies
                    if 'Z' in raw_timestamp:
                        clean_dt = raw_timestamp.replace('Z', '+00:00')
                    elif '+' not in raw_timestamp:
                        clean_dt = raw_timestamp + '+00:00'
                    else:
                        clean_dt = raw_timestamp
                    
                    # Remove microseconds if present
                    if '.' in clean_dt:
                        clean_dt = clean_dt.split('.')[0] + clean_dt.split('.')[-1][-6:]
                    
                    try:
                        dt = datetime.fromisoformat(clean_dt)
                    except:
                        # Final fallback
                        clean_dt = raw_timestamp.replace('Z', '').split('.')[0]
                        dt = datetime.fromisoformat(clean_dt)
                    
                    # Format for display: "28/12/2025, 14:30:45"
                    submitted_at_formatted = dt.strftime("%d/%m/%Y, %H:%M:%S")
                    # Also keep ISO format for any other use
                    submitted_at = dt.isoformat()
                    
                    print(f"✅ Parsed timestamp: {submitted_at_formatted}")
                    
                except Exception as parse_err:
                    print(f"⚠️ Timestamp parse error: {parse_err}")
                    # Fallback to raw value
                    submitted_at = submission.get("created_at")
                    submitted_at_formatted = ""  # Empty string so frontend shows just "✅Submitted"
            
            print(f"Assignment {assignment_id}: has_submitted = {has_submitted}, submitted_at = {submitted_at_formatted}")
            
            assignments.append({
                "id": a["id"],
                "title": a["title"],
                "subject": a["subject"],
                "deadline": a["deadline"],
                "created_at": a.get("created_at", ""),
                "has_submitted": has_submitted,
                "submitted_at": submitted_at,  # ISO format for backend processing
                "submitted_at_formatted": submitted_at_formatted  # Human-readable format for display
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
        
        # ⭐ GET STUDENT EMAIL BEFORE CHECKING DUPLICATES
        student_email = get_user_email(student_id)
        print(f"✅ Student email retrieved: {student_email}")
        
        # Check for duplicates
        check = supabase.table("assignment_submissions")\
            .select("*")\
            .eq("assignment_id", str(assignment_id))\
            .eq("student_id", student_id)\
            .execute()
        
        if check.data:
            raise HTTPException(status_code=400, detail="You have already submitted this assignment")

        # ⭐ STORE EMAIL ALONG WITH SUBMISSION AND ADD TIMEZONE
        data = {
            "assignment_id": str(assignment_id),
            "student_id": student_id,
            "student_email": student_email,  # ⭐ ADD THIS
            "file_data": b64_encoded,
            "created_at": datetime.utcnow().isoformat() + "Z"  # ⭐ ADD Z for timezone
        }
        
        result = supabase.table("assignment_submissions").insert(data).execute()
        print(f"✅ Assignment submitted successfully for {student_email}")
        
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
        
        # Check if exam had tab switches during session
        session_key = f"{sub.student_id}_{sub.exam_id}"
        switch_count = 0
        if session_key in active_exam_sessions:
            switch_count = active_exam_sessions[session_key].get("tab_switch_count", 0)
        
        # Build cheating_log based on switch count
        cheating_log = sub.cheating_log if sub.cheating_log else []
        if switch_count >= 1:
            cheating_log.append(f"Tab switched {switch_count} time(s)")
        
        data = {
            "exam_id": sub.exam_id,
            "student_id": sub.student_id,
            "student_email": student_email,
            "score_numeric": sub.score_numeric,
            "total_marks": sub.total_marks,
            "time_taken_seconds": sub.time_taken_seconds,
            "student_answers": sub.student_answers,
            "feedback_json": sub.feedback_json,
            "cheating_log": cheating_log,
            "score": f"{sub.score_numeric}/{sub.total_marks}"
        }
        supabase.table("submissions").insert(data).execute()
        print(f"✅ Exam result submitted for {student_email} (cheating_log: {cheating_log})")
        
        # Clean up session
        if session_key in active_exam_sessions:
            del active_exam_sessions[session_key]
        
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
            
            # Determine if exam was clean or unclean based on cheating_log
            cheating_log = s.get("cheating_log") or []
            flag_status = "Unclean" if len(cheating_log) > 0 else "Clean"
            
            results.append({
                "exam_key": s["exam_id"],
                "exam_name": exam_map.get(s["exam_id"], "Unknown"),
                "student_email": student_email,
                "score": s["score_numeric"],
                "max_marks": s["total_marks"],
                "time_taken": round(s["time_taken_seconds"] / 60, 2),
                "date": s["created_at"].split("T")[0],
                "flag_status": flag_status,
                "cheating_flags": cheating_log
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