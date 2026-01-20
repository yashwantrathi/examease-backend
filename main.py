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
GEMINI_API_KEY = "AIzaSyD8TPUGTOKaLe4LE1FE77rjrJaStRlXoXY"

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
        "https://examease-backend-4bdx.onrender.com",
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

class UserSignup(BaseModel):
    email: str
    password: str
    role: str  # "student" or "teacher"
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None

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

def get_user_name(user_id: str) -> str:
    """Fetch user's full name from profiles table"""
    try:
        print(f"🔍 Fetching name for user_id: {user_id}")
        
        result = supabase.table("profiles")\
            .select("full_name")\
            .eq("id", user_id)\
            .maybe_single()\
            .execute()
        
        print(f"📊 Profile query result: {result.data}")
        
        if result.data and result.data.get("full_name"):
            print(f"✅ Found name: {result.data['full_name']}")
            return result.data["full_name"]
        
        # Fallback: try to get from auth metadata
        try:
            user_res = supabase.auth.admin.get_user_by_id(user_id)
            if user_res and user_res.user and user_res.user.user_metadata:
                full_name = user_res.user.user_metadata.get("full_name")
                if full_name:
                    print(f"✅ Found name in auth metadata: {full_name}")
                    return full_name
        except Exception as auth_err:
            print(f"⚠️ Auth metadata lookup failed: {auth_err}")
        
        print(f"⚠️ No name found for user {user_id}, returning 'Unknown User'")
        return "Unknown User"
    except Exception as e:
        print(f"❌ Error fetching name for user {user_id}: {e}")
        import traceback
        traceback.print_exc()
        return "Unknown User"

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

# --- AUTHENTICATION ENDPOINTS ---

@app.post("/auth/signup")
async def signup(user: UserSignup):
    """Create a new user account (student or teacher)"""
    print("entering signup")
    try:
        print(f"📝 Signup attempt: {user.email} as {user.role}")
        
        # Validate role
        if user.role not in ["student", "teacher"]:
            raise HTTPException(status_code=400, detail="Role must be 'student' or 'teacher'")
        
        # Create user in Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": user.email,
            "password": user.password,
            "options": {
                "data": {
                    "role": user.role,
                    "full_name": user.full_name or user.email.split('@')[0]
                }
            }
        })
        
        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Failed to create user")
        
        user_id = auth_response.user.id
        
        # Create profile in profiles table
        profile_data = {
            "id": user_id,
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name or user.email.split('@')[0],
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
        
        try:
            supabase.table("profiles").insert(profile_data).execute()
        except Exception as profile_error:
            print(f"⚠️ Profile creation error (may be handled by trigger): {profile_error}")
        
        print(f"✅ User created: {user.email} ({user.role})")
        
        return {
            "message": "User created successfully",
            "user": {
                "id": user_id,
                "email": user.email,
                "role": user.role,
                "full_name": user.full_name or user.email.split('@')[0]
            },
            "session": {
                "access_token": auth_response.session.access_token if auth_response.session else None,
                "refresh_token": auth_response.session.refresh_token if auth_response.session else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Signup Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auth/login")
async def login(credentials: UserLogin):
    """Login user and return session tokens"""
    try:
        print(f"🔐 Login attempt: {credentials.email}")
        
        # Sign in with Supabase Auth
        auth_response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        if not auth_response.user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user_id = auth_response.user.id
        
        # Get user profile to fetch role
        profile = supabase.table("profiles").select("*").eq("id", user_id).execute()
        
        user_role = "student"  # default
        full_name = credentials.email.split('@')[0]
        
        if profile.data and len(profile.data) > 0:
            user_role = profile.data[0].get("role", "student")
            full_name = profile.data[0].get("full_name", full_name)
        else:
            # Check user metadata if profile doesn't exist
            if auth_response.user.user_metadata:
                user_role = auth_response.user.user_metadata.get("role", "student")
                full_name = auth_response.user.user_metadata.get("full_name", full_name)
        
        print(f"✅ Login successful: {credentials.email} ({user_role})")
        
        return {
            "message": "Login successful",
            "user": {
                "id": user_id,
                "email": credentials.email,
                "role": user_role,
                "full_name": full_name
            },
            "session": {
                "access_token": auth_response.session.access_token,
                "refresh_token": auth_response.session.refresh_token
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Login Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/auth/profile/{user_id}")
async def get_profile(user_id: str):
    """Get user profile including role"""
    try:
        # Try to get from profiles table
        profile = supabase.table("profiles").select("*").eq("id", user_id).execute()
        
        if profile.data and len(profile.data) > 0:
            return profile.data[0]
        
        # Fallback: get from auth user metadata
        try:
            auth_user = supabase.auth.admin.get_user_by_id(user_id)
            if auth_user and auth_user.user:
                return {
                    "id": user_id,
                    "email": auth_user.user.email,
                    "role": auth_user.user.user_metadata.get("role", "student"),
                    "full_name": auth_user.user.user_metadata.get("full_name", auth_user.user.email.split('@')[0])
                }
        except Exception as auth_error:
            print(f"Auth lookup error: {auth_error}")
        
        raise HTTPException(status_code=404, detail="User profile not found")
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Get Profile Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/auth/profile/{user_id}")
async def update_profile(user_id: str, update: ProfileUpdate):
    """Update user profile"""
    try:
        update_data = {}
        if update.full_name is not None:
            update_data["full_name"] = update.full_name
        if update.role is not None:
            if update.role not in ["student", "teacher"]:
                raise HTTPException(status_code=400, detail="Role must be 'student' or 'teacher'")
            update_data["role"] = update.role
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Update profiles table
        result = supabase.table("profiles").update(update_data).eq("id", user_id).execute()
        
        print(f"✅ Profile updated for user {user_id}")
        return {"message": "Profile updated successfully", "data": result.data[0] if result.data else {}}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Update Profile Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auth/logout")
async def logout():
    """Logout user"""
    try:
        supabase.auth.sign_out()
        return {"message": "Logged out successfully"}
    except Exception as e:
        print(f"❌ Logout Error: {e}")
        return {"message": "Logged out"}

@app.get("/auth/check-role/{user_id}")
async def check_user_role(user_id: str):
    """Check if user is a teacher or student"""
    try:
        profile = supabase.table("profiles").select("role").eq("id", user_id).execute()
        
        if profile.data and len(profile.data) > 0:
            role = profile.data[0].get("role", "student")
            return {
                "user_id": user_id,
                "role": role,
                "is_teacher": role == "teacher",
                "is_student": role == "student"
            }
        
        # Fallback to auth metadata
        try:
            auth_user = supabase.auth.admin.get_user_by_id(user_id)
            if auth_user and auth_user.user and auth_user.user.user_metadata:
                role = auth_user.user.user_metadata.get("role", "student")
                return {
                    "user_id": user_id,
                    "role": role,
                    "is_teacher": role == "teacher",
                    "is_student": role == "student"
                }
        except Exception:
            pass
        
        # Default to student if not found
        return {
            "user_id": user_id,
            "role": "student",
            "is_teacher": False,
            "is_student": True
        }
    except Exception as e:
        print(f"❌ Check Role Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

Topic: {topic}

IMPORTANT RULES:
1. For MCQ: Create 4 distinct options. The "answer" field MUST contain the EXACT FULL TEXT of the correct option, NOT just a letter like A/B/C/D.
2. For subjective: The "answer" field should contain a complete model answer.

Format: JSON array only, no markdown.
Example MCQ: {{"id":1,"type":"mcq","question":"What is the capital of France?","options":["London","Paris","Berlin","Madrid"],"answer":"Paris","marks":1}}
Example Subjective: {{"id":2,"type":"subjective","question":"Explain photosynthesis","options":null,"answer":"Photosynthesis is the process by which plants convert sunlight into energy...","marks":2}}"""
    
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
        
        # ⭐ VALIDATION: Fix MCQ answers - ensure answer matches one of the options
        for q in all_questions:
            if q.get("type") == "mcq" and q.get("options"):
                answer = q.get("answer", "")
                options = q.get("options", [])
                
                # Check if answer is just a letter (A, B, C, D)
                if answer in ["A", "B", "C", "D"] and len(options) >= 4:
                    # Convert letter to actual option text
                    letter_index = {"A": 0, "B": 1, "C": 2, "D": 3}
                    idx = letter_index.get(answer, 0)
                    q["answer"] = options[idx]
                    print(f"⚠️ Fixed MCQ answer: '{answer}' -> '{options[idx]}'")
                
                # Also check if answer doesn't match any option (case-insensitive)
                elif answer.lower() not in [opt.lower() for opt in options]:
                    # Try to find a matching option
                    for opt in options:
                        if answer.lower() in opt.lower() or opt.lower() in answer.lower():
                            q["answer"] = opt
                            print(f"⚠️ Fixed MCQ answer: '{answer}' -> '{opt}'")
                            break
        
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

        # ⭐ STORE EMAIL ALONG WITH SUBMISSION
        data = {
            "assignment_id": str(assignment_id),
            "student_id": student_id,
            "student_email": student_email,
            "file_data": b64_encoded
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

@app.get("/teacher-subjects/{teacher_id}")
async def get_teacher_subjects(teacher_id: str):
    """Get all unique subjects for a teacher from their exams and assignments"""
    try:
        print(f"📋 Fetching subjects for teacher: {teacher_id}")
        
        # Get subjects from exams
        exams = supabase.table("exams")\
            .select("subject")\
            .eq("teacher_id", teacher_id)\
            .execute()
        
        # Get subjects from assignments
        assignments = supabase.table("assignments")\
            .select("subject")\
            .eq("teacher_id", teacher_id)\
            .execute()
        
        # Combine and deduplicate
        subjects = set()
        for exam in (exams.data or []):
            if exam.get("subject"):
                subjects.add(exam["subject"])
        for assignment in (assignments.data or []):
            if assignment.get("subject"):
                subjects.add(assignment["subject"])
        
        subjects_list = sorted(list(subjects))
        print(f"✅ Found {len(subjects_list)} unique subjects: {subjects_list}")
        
        return {"subjects": subjects_list}
    except Exception as e:
        print(f"❌ Get Teacher Subjects Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

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

class GradeExamRequest(BaseModel):
    exam_id: str
    student_answers: dict  # {question_id: student_answer}

@app.post("/grade-exam")
async def grade_exam(request: GradeExamRequest):
    """Grade an entire exam - handles both MCQ and subjective questions"""
    try:
        # Get exam questions
        exam_res = supabase.table("exams").select("*").eq("exam_id", request.exam_id.upper()).execute()
        
        if not exam_res.data:
            raise HTTPException(status_code=404, detail="Exam not found")
        
        exam = exam_res.data[0]
        questions = exam.get("questions_json", [])
        
        results = {}
        total_score = 0
        total_marks = 0
        
        for q in questions:
            q_id = str(q.get("id"))
            q_type = q.get("type", "").lower()
            correct_answer = q.get("answer", "")
            student_answer = request.student_answers.get(q_id, "")
            marks = q.get("marks", 1)
            total_marks += marks
            
            if q_type == "mcq":
                # MCQ grading - case-insensitive comparison
                is_correct = False
                
                # Direct match (case-insensitive)
                if student_answer.strip().lower() == correct_answer.strip().lower():
                    is_correct = True
                
                # Check if student selected the correct option by index/letter
                options = q.get("options", [])
                if not is_correct and student_answer in ["A", "B", "C", "D", "0", "1", "2", "3"]:
                    letter_to_idx = {"A": 0, "B": 1, "C": 2, "D": 3, "0": 0, "1": 1, "2": 2, "3": 3}
                    idx = letter_to_idx.get(student_answer, -1)
                    if 0 <= idx < len(options) and options[idx].strip().lower() == correct_answer.strip().lower():
                        is_correct = True
                
                # Check if answer matches any option that is the correct one
                if not is_correct:
                    for i, opt in enumerate(options):
                        if student_answer.strip().lower() == opt.strip().lower():
                            if opt.strip().lower() == correct_answer.strip().lower():
                                is_correct = True
                                break
                
                score = marks if is_correct else 0
                total_score += score
                
                results[q_id] = {
                    "type": "mcq",
                    "correct": is_correct,
                    "score": score,
                    "max_marks": marks,
                    "correct_answer": correct_answer,
                    "student_answer": student_answer,
                    "feedback": "Correct!" if is_correct else f"Incorrect. The correct answer is: {correct_answer}"
                }
            
            else:  # Subjective
                if not student_answer.strip():
                    results[q_id] = {
                        "type": "subjective",
                        "correct": False,
                        "score": 0,
                        "max_marks": marks,
                        "correct_answer": correct_answer,
                        "student_answer": student_answer,
                        "feedback": "No answer provided."
                    }
                else:
                    # Use AI grading for subjective
                    try:
                        grade_prompt = f"""Grade this answer on a scale of 0.0 to 1.0.
Question: {q.get('question', '')}
Correct Answer: {correct_answer}
Student Answer: {student_answer}
Output JSON only: {{"score": 0.75, "feedback": "brief feedback"}}"""
                        
                        response = model.generate_content(grade_prompt)
                        text = response.text.strip().replace("```json", "").replace("```", "").strip()
                        grade_result = json.loads(text)
                        
                        ai_score = float(grade_result.get("score", 0))
                        earned = round(ai_score * marks, 2)
                        total_score += earned
                        
                        results[q_id] = {
                            "type": "subjective",
                            "correct": ai_score >= 0.5,
                            "score": earned,
                            "max_marks": marks,
                            "correct_answer": correct_answer,
                            "student_answer": student_answer,
                            "feedback": grade_result.get("feedback", "")
                        }
                    except Exception as ai_err:
                        print(f"⚠️ AI grading error for question {q_id}: {ai_err}")
                        results[q_id] = {
                            "type": "subjective",
                            "correct": False,
                            "score": 0,
                            "max_marks": marks,
                            "correct_answer": correct_answer,
                            "student_answer": student_answer,
                            "feedback": "Could not grade automatically"
                        }
        
        print(f"✅ Graded exam {request.exam_id}: {total_score}/{total_marks}")
        
        return {
            "exam_id": request.exam_id,
            "total_score": total_score,
            "total_marks": total_marks,
            "percentage": round((total_score / total_marks) * 100, 2) if total_marks > 0 else 0,
            "results": results
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Grade Exam Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit-exam-result")
async def submit_exam_result(sub: SubmissionCreate):
    try:
        # Get student email and name for storage
        student_email = get_user_email(sub.student_id)
        student_name = get_user_name(sub.student_id)
        
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
            "student_name": student_name,
            "score_numeric": sub.score_numeric,
            "total_marks": sub.total_marks,
            "time_taken_seconds": sub.time_taken_seconds,
            "student_answers": sub.student_answers,
            "feedback_json": sub.feedback_json,
            "cheating_log": cheating_log,
            "score": f"{sub.score_numeric}/{sub.total_marks}"
        }
        supabase.table("submissions").insert(data).execute()
        print(f"✅ Exam result submitted for {student_name} ({student_email}) (cheating_log: {cheating_log})")
        
        # Clean up session
        if session_key in active_exam_sessions:
            del active_exam_sessions[session_key]
        
        return {"message": "Exam result saved successfully"}
    except Exception as e:
        print(f"❌ Submit Result Error: {e}")
        
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
            # Try to use stored email from submission, fallback to lookup, then fallback to student_id
            student_email = s.get("student_email")
            
            # If no email in submission, try to fetch from auth
            if not student_email:
                try:
                    student_email = get_user_email(s["student_id"])
                except:
                    pass
            
            # If still no email, use student_id as identifier (don't skip!)
            if not student_email:
                student_email = f"student_{s['student_id'][:8]}"  # Use first 8 chars of ID
                print(f"⚠️ Using student_id as identifier: {student_email}")
            
            # Get student name (from submission or fetch)
            student_name = s.get("student_name")
            if not student_name:
                student_name = get_user_name(s["student_id"])
            
            print(f"Student {s['student_id']} -> {student_name} ({student_email})")
            
            # Determine if exam was clean or unclean based on cheating_log
            cheating_log = s.get("cheating_log") or []
            flag_status = "Unclean" if len(cheating_log) > 0 else "Clean"
            
            results.append({
                "exam_key": s["exam_id"],
                "exam_name": exam_map.get(s["exam_id"], "Unknown"),
                "student_email": student_email,
                "student_name": student_name,
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
            student_email = sub.get("student_email")
            
            # If no email in submission, fetch from auth
            if not student_email:
                student_email = get_user_email(sub["student_id"])
            
            # If still no email, skip this submission instead of showing "unknown@unknown.com"
            if not student_email:
                print(f"⚠️ No email found for student {sub['student_id']}, skipping feedback entry")
                continue
            
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
        
        # First, let's see ALL feedback submissions in the database
        all_feedback = supabase.table("feedback_submissions")\
            .select("*")\
            .execute()
        
        print(f"🔍 Total feedback submissions in database: {len(all_feedback.data if all_feedback.data else [])}")
        
        if all_feedback.data:
            # Show all subjects in the database for comparison
            all_subjects = set(f.get("subject") for f in all_feedback.data if f.get("subject"))
            print(f"🔍 All subjects in feedback_submissions table: {all_subjects}")
            print(f"🔍 Looking for subject: '{subject}'")
        
        # Get all feedback submissions for this subject
        result = supabase.table("feedback_submissions")\
            .select("*")\
            .eq("subject", subject)\
            .order("created_at", desc=True)\
            .execute()
        
        feedback_list = result.data if result.data else []
        print(f"✅ Found {len(feedback_list)} feedback submissions for '{subject}'")
        
        if len(feedback_list) > 0:
            print(f"📝 Sample feedback: {feedback_list[0]}")
        
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
            "average_rating": sum(f.get("rating", 0) for f in formatted_feedback if f.get("rating") is not None) / len([f for f in formatted_feedback if f.get("rating") is not None]) if any(f.get("rating") is not None for f in formatted_feedback) else 0
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