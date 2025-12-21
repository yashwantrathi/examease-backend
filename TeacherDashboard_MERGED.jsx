import { useState, useEffect } from "react";
import axios from "axios";
import { supabase } from "./supabaseClient";
import "./Student.css";

const API_BASE_URL = "http://localhost:8000";
const MAX_FILE_SIZE = 10 * 1024 * 1024;

function TeacherDashboard() {
  const [view, setView] = useState("menu");
  const [loading, setLoading] = useState(false);
  const [user, setUser] = useState(null);
  const [error, setError] = useState("");

  // Stats
  const [stats, setStats] = useState([]);

  // Student Feedback (NEW - Course Feedback)
  const [studentFeedback, setStudentFeedback] = useState({});
  const [expandedSubject, setExpandedSubject] = useState(null);

  // Exam Performance Feedback (OLD)
  const [feedback, setFeedback] = useState(null);

  // Assignments
  const [assignments, setAssignments] = useState([]);
  const [results, setResults] = useState([]);

  // Exam Creation
  const [topic, setTopic] = useState("");
  const [subject, setSubject] = useState("");
  const [numQuestions, setNumQuestions] = useState(5);
  const [duration, setDuration] = useState(30);
  const [questions, setQuestions] = useState([]);
  const [demoQuestions, setDemoQuestions] = useState([]);
  const [savedExamId, setSavedExamId] = useState("");
  const [savedDemoId, setSavedDemoId] = useState("");

  // Assignment Management
  const [assignTitle, setAssignTitle] = useState("");
  const [assignSubject, setAssignSubject] = useState("");
  const [assignDeadline, setAssignDeadline] = useState("");
  const [teacherAssignments, setTeacherAssignments] = useState([]);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      if (data?.user) {
        setUser(data.user);
      }
    });
  }, []);

  const validateFileSize = (file) => {
    if (file.size > MAX_FILE_SIZE) {
      alert(`File size exceeds maximum allowed size of ${MAX_FILE_SIZE / (1024*1024)}MB`);
      return false;
    }
    return true;
  };

  // Fetch student feedback by subject (NEW)
  const fetchStudentFeedback = async () => {
    try {
      const subjects = new Set([
        ...assignments.map(a => a.subject),
        ...results.map(r => r.subject)
      ]);

      const feedbackData = {};
      
      for (const subject of subjects) {
        try {
          const response = await fetch(`${API_BASE_URL}/student-feedback/${subject}`);
          const data = await response.json();
          feedbackData[subject] = data.feedback_list || [];
        } catch (err) {
          console.log(`No feedback for subject: ${subject}`);
        }
      }
      
      setStudentFeedback(feedbackData);
    } catch (error) {
      console.error("Error fetching student feedback:", error);
    }
  };

  const fetchStats = async () => {
    if (!user) return;
    
    setLoading(true);
    setError("");
    
    try {
      const res = await axios.get(`${API_BASE_URL}/teacher-stats/${user.id}`);
      setStats(res.data.results);
      setView("stats");
    } catch (err) {
      setError("Failed to load statistics: " + (err.response?.data?.detail || err.message));
      setStats([]);
      setView("stats");
    }
    
    setLoading(false);
  };

  const fetchFeedback = async () => {
    if (!user) return;
    
    setLoading(true);
    setError("");
    
    try {
      const res = await axios.get(`${API_BASE_URL}/teacher-feedback/${user.id}`);
      setFeedback(res.data);
      setView("feedback");
    } catch (err) {
      setError("Failed to load feedback: " + (err.response?.data?.detail || err.message));
      setFeedback(null);
      setView("feedback");
    }
    
    setLoading(false);
  };

  const fetchStudentCourseFeedback = async () => {
    if (!user) return;
    
    setLoading(true);
    setError("");
    
    try {
      // Fetch assignments and results to get subjects
      let assignments = [];
      let results = [];
      
      try {
        const assignRes = await axios.get(`${API_BASE_URL}/teacher-assignments/${user.id}`);
        assignments = assignRes.data || [];
        setAssignments(assignments);
      } catch (err) {
        console.log("No assignments found or error fetching assignments:", err.message);
      }
      
      try {
        const resultsRes = await axios.get(`${API_BASE_URL}/teacher-stats/${user.id}`);
        results = resultsRes.data.results || [];
        setResults(results);
      } catch (err) {
        console.log("No results found or error fetching results:", err.message);
      }
      
      // Fetch feedback for each subject
      const subjects = new Set([
        ...assignments.map(a => a.subject),
        ...results.map(r => r.subject)
      ]);

      const feedbackData = {};
      
      for (const subject of subjects) {
        try {
          const response = await fetch(`${API_BASE_URL}/student-feedback/${subject}`);
          if (response.ok) {
            const data = await response.json();
            feedbackData[subject] = data.feedback_list || [];
          }
        } catch (err) {
          console.log(`No feedback for subject: ${subject}`);
        }
      }
      
      setStudentFeedback(feedbackData);
      setView("student-feedback");
    } catch (err) {
      setError("Failed to load student feedback: " + err.message);
      setView("student-feedback");
    }
    
    setLoading(false);
  };

  const fetchTeacherAssignments = async () => {
    if (!user) return;
    
    setLoading(true);
    setError("");
    
    try {
      const res = await axios.get(`${API_BASE_URL}/teacher-assignments/${user.id}`);
      setTeacherAssignments(res.data);
      setView("view-assignments");
    } catch (err) {
      setError("Failed to load assignments: " + (err.response?.data?.detail || err.message));
      setTeacherAssignments([]);
      setView("view-assignments");
    }
    
    setLoading(false);
  };

  const handleAIGenerate = async (e) => {
    const file = e.target.files[0];
    if (!file || !validateFileSize(file)) {
      e.target.value = '';
      return;
    }

    if (!topic.trim()) {
      alert("Please enter an exam title first");
      e.target.value = '';
      return;
    }

    setLoading(true);
    setError("");
    
    const fd = new FormData();
    fd.append("file", file);
    fd.append("topic", topic);
    fd.append("num_questions", numQuestions);
    
    try {
      const res = await axios.post(`${API_BASE_URL}/generate-quiz`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setQuestions(res.data.questions);
      setDemoQuestions(res.data.demo_questions || []);
      
      alert(`✅ Generated ${res.data.questions.length} main questions + ${res.data.demo_questions?.length || 0} demo questions!`);
    } catch (err) {
      setError(err.response?.data?.detail || "AI generation failed. Check console.");
      console.error("AI Error:", err);
      alert(err.response?.data?.detail || "Failed to generate questions.");
    }
    
    e.target.value = '';
    setLoading(false);
  };

  const handleSaveExam = async () => {
    if (!user) {
      alert("User not logged in");
      return;
    }

    if (questions.length === 0) {
      alert("No questions to save. Generate questions first.");
      return;
    }

    if (!subject.trim()) {
      alert("Please enter a subject");
      return;
    }

    setLoading(true);
    setError("");
    
    try {
      const mainRes = await axios.post(`${API_BASE_URL}/save-exam`, {
        title: topic,
        subject: subject,
        teacher_id: user.id,
        questions: questions,
        duration: duration,
      });

      const mainExamId = mainRes.data.exam_id;
      setSavedExamId(mainExamId);

      let demoExamId = "";
      
      if (demoQuestions.length > 0) {
        const demoRes = await axios.post(`${API_BASE_URL}/save-exam`, {
          title: "DEMO: " + topic,
          subject: subject,
          teacher_id: user.id,
          questions: demoQuestions,
          duration: Math.ceil(duration / 2),
        });
        demoExamId = demoRes.data.exam_id;
        setSavedDemoId(demoExamId);
      }

      alert(
        `✅ Exam saved!\n\nMain Exam Code: ${mainExamId}${
          demoExamId ? '\nDemo Exam Code: ' + demoExamId : ''
        }\n\nShare these codes with students!`
      );
    } catch (err) {
      setError("Failed to save exam");
      console.error(err);
      alert("Failed to save exam.");
    }
    
    setLoading(false);
  };

  const createAssignment = async () => {
    if (!assignTitle.trim() || !assignSubject.trim() || !assignDeadline) {
      alert("Please fill all assignment fields");
      return;
    }

    setLoading(true);
    
    try {
      await axios.post(`${API_BASE_URL}/create-assignment`, {
        title: assignTitle,
        subject: assignSubject,
        deadline: assignDeadline,
        teacher_id: user.id
      });
      
      alert("✅ Assignment created successfully!");
      
      setAssignTitle("");
      setAssignSubject("");
      setAssignDeadline("");
      setView("menu");
    } catch (err) {
      alert("Failed to create assignment");
      console.error(err);
    }
    
    setLoading(false);
  };

  const downloadSubmission = (fileName, base64Data) => {
    try {
      const byteCharacters = atob(base64Data);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Download error:", err);
      alert("Failed to download file");
    }
  };

  const updateQuestionMarks = (index, value) => {
    const val = parseInt(value) || 0;
    const newQuestions = [...questions];
    newQuestions[index].marks = Math.max(1, val);
    setQuestions(newQuestions);
  };

  const deleteQuestion = (index) => {
    if (window.confirm("Delete this question?")) {
      setQuestions(questions.filter((_, i) => i !== index));
    }
  };

  const exportStatsCSV = () => {
    if (stats.length === 0) {
      alert("No data to export");
      return;
    }

    const headers = ["Exam", "Student Email", "Score", "Max Marks", "Time (mins)", "Date", "Cheating Flags"];
    const rows = stats.map(s => [
      s.exam_name,
      s.student_email,
      s.score,
      s.max_marks,
      s.time_taken,
      s.date,
      s.cheating_flags
    ]);

    const csv = [
      headers.join(","),
      ...rows.map(r => r.join(","))
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `exam_results_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const resetExamForm = () => {
    setQuestions([]);
    setDemoQuestions([]);
    setTopic("");
    setSubject("");
    setSavedExamId("");
    setSavedDemoId("");
  };

  // RENDER FUNCTIONS
  const renderMenu = () => (
    <div className="section-card">
      <div className="section-header">
        <div>
          <h2>Teacher Dashboard</h2>
          <p className="section-subtitle">Manage exams, assignments, and analyze student performance</p>
        </div>
      </div>

      <div className="menu-grid">
        <div 
          className="menu-tile" 
          onClick={() => setView("create")}
          style={{cursor: 'pointer', background: 'linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%)'}}
        >
          <h3>Create Exam</h3>
          <p className="muted">Use AI to automatically generate exam questions from PDF materials</p>
        </div>

        <div 
          className="menu-tile" 
          onClick={() => setView("assignment")}
          style={{cursor: 'pointer', background: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)'}}
        >
          <h3>Create Assignment</h3>
          <p className="muted">Set up new assignments with customizable deadlines</p>
        </div>

        <div 
          className="menu-tile" 
          onClick={fetchStats}
          style={{cursor: 'pointer', background: 'linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%)'}}
        >
          <h3>View Results</h3>
          <p className="muted">Analyze comprehensive student exam performance data</p>
        </div>

        <div 
          className="menu-tile" 
          onClick={fetchStudentCourseFeedback}
          style={{cursor: 'pointer', background: 'linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%)'}}
        >
          <h3>Student Feedback Forms</h3>
          <p className="muted">Review student feedback about courses organized by subject</p>
        </div>

        <div 
          className="menu-tile" 
          onClick={fetchFeedback}
          style={{cursor: 'pointer', background: 'linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%)'}}
        >
          <h3>Exam Performance Feedback</h3>
          <p className="muted">Review AI-generated feedback on how students performed on exams</p>
        </div>

        <div 
          className="menu-tile" 
          onClick={fetchTeacherAssignments}
          style={{cursor: 'pointer', background: 'linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%)'}}
        >
          <h3>Assignment Submissions</h3>
          <p className="muted">Review and download all student assignment submissions</p>
        </div>
      </div>
    </div>
  );

  const renderCreate = () => (
    <div className="section-card">
      <div className="section-header">
        <h2>Create Exam with AI</h2>
        <button className="btn-ghost" onClick={() => setView("menu")}>
          Back
        </button>
      </div>

      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 30}}>
        <div>
          <h3>Exam Details</h3>
          
          <input 
            className="input-pill"
            placeholder="Exam Title (e.g., Physics Midterm)"
            value={topic}
            onChange={e => setTopic(e.target.value)}
          />

          <input 
            className="input-pill"
            placeholder="Subject (e.g., Physics)"
            value={subject}
            onChange={e => setSubject(e.target.value)}
            style={{marginTop: 10}}
          />

          <div style={{display: 'flex', gap: 10, marginTop: 10}}>
            <div style={{flex: 1}}>
              <label style={{fontSize: '0.9rem', color: '#6b7280'}}>Questions</label>
              <input 
                type="number"
                className="input-pill"
                value={numQuestions}
                onChange={e => {
                  const val = parseInt(e.target.value) || 0;
                  setNumQuestions(Math.max(1, Math.min(50, val)));
                }}
                min="1"
                max="50"
              />
            </div>
            <div style={{flex: 1}}>
              <label style={{fontSize: '0.9rem', color: '#6b7280'}}>Duration (mins)</label>
              <input 
                type="number"
                className="input-pill"
                value={duration}
                onChange={e => {
                  const val = parseInt(e.target.value) || 0;
                  setDuration(Math.max(1, val));
                }}
                min="1"
              />
            </div>
          </div>

          <label className="upload-pill" style={{marginTop: 20, width: '100%'}}>
            Upload PDF and Generate (Max 10MB)
            <input 
              type="file" 
              accept=".pdf"
              onChange={handleAIGenerate}
              hidden
            />
          </label>

          {savedExamId && (
            <div style={{
              marginTop: 20,
              padding: 15,
              background: '#f0fdf4',
              borderRadius: 12,
              border: '1px solid #bbf7d0'
            }}>
              <strong style={{color: '#166534'}}>✅ Exams Saved Successfully!</strong>
              
              <div style={{marginTop: 15}}>
                <p style={{fontSize: '0.9rem', color: '#166534', marginBottom: 5}}>
                  Main Exam Code:
                </p>
                <p style={{fontSize: '1.5rem', fontWeight: 800, margin: '5px 0', color: '#166534'}}>
                  {savedExamId}
                </p>
              </div>
              
              {savedDemoId && (
                <div style={{marginTop: 15}}>
                  <p style={{fontSize: '0.9rem', color: '#166534', marginBottom: 5}}>
                    Demo Exam Code:
                  </p>
                  <p style={{fontSize: '1.5rem', fontWeight: 800, margin: '5px 0', color: '#166534'}}>
                    {savedDemoId}
                  </p>
                </div>
              )}
              
              <p style={{fontSize: '0.9rem', color: '#166534', marginTop: 15}}>
                📋 Share these codes with your students
              </p>
              
              <button 
                className="btn-ghost btn-small"
                onClick={resetExamForm}
                style={{marginTop: 15, width: '100%'}}
              >
                Create Another Exam
              </button>
            </div>
          )}
        </div>

        <div>
          <h3>Generated Questions ({questions.length})</h3>
          
          {questions.length === 0 ? (
            <div style={{textAlign: 'center', padding: 40, color: '#6b7280'}}>
              <p>Upload a PDF to generate questions</p>
            </div>
          ) : (
            <div style={{maxHeight: 500, overflowY: 'auto'}}>
              {questions.map((q, i) => (
                <div key={i} className="question-card" style={{marginBottom: 15}}>
                  <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'start'}}>
                    <div style={{flex: 1}}>
                      <strong>Q{i + 1}:</strong> {q.question}
                      <div style={{marginTop: 10}}>
                        <span className={`pill-tag ${q.type === 'mcq' ? 'pill-tag-blue' : 'pill-tag-orange'}`}>
                          {q.type.toUpperCase()}
                        </span>
                      </div>
                    </div>
                    <button 
                      className="tiny-link"
                      onClick={() => deleteQuestion(i)}
                      style={{marginLeft: 10}}
                    >
                      Delete
                    </button>
                  </div>
                  
                  <div style={{marginTop: 10, display: 'flex', alignItems: 'center', gap: 10}}>
                    <label style={{fontSize: '0.9rem'}}>Marks:</label>
                    <input 
                      type="number"
                      value={q.marks}
                      onChange={e => updateQuestionMarks(i, e.target.value)}
                      style={{width: 60, padding: 5, borderRadius: 6, border: '1px solid #d1d5db'}}
                      min="1"
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {questions.length > 0 && !savedExamId && (
            <button 
              className="btn-primary" 
              onClick={handleSaveExam}
              style={{marginTop: 15, width: '100%'}}
            >
              Save Exam
            </button>
          )}
        </div>
      </div>
    </div>
  );

  const renderAssignment = () => (
    <div className="section-card">
      <div className="section-header">
        <h2>Create Assignment</h2>
        <button className="btn-ghost" onClick={() => setView("menu")}>
          Back
        </button>
      </div>

      <div style={{maxWidth: 600, margin: '0 auto'}}>
        <input 
          className="input-pill"
          placeholder="Assignment Title"
          value={assignTitle}
          onChange={e => setAssignTitle(e.target.value)}
        />

        <input 
          className="input-pill"
          placeholder="Subject"
          value={assignSubject}
          onChange={e => setAssignSubject(e.target.value)}
          style={{marginTop: 10}}
        />

        <div style={{marginTop: 10}}>
          <label style={{fontSize: '0.9rem', color: '#6b7280'}}>Deadline</label>
          <input 
            type="date"
            className="input-pill"
            value={assignDeadline}
            onChange={e => setAssignDeadline(e.target.value)}
          />
        </div>

        <button 
          className="btn-primary" 
          onClick={createAssignment}
          style={{marginTop: 20, width: '100%'}}
        >
          Publish Assignment
        </button>
      </div>
    </div>
  );

  const renderStats = () => (
    <div className="section-card">
      <div className="section-header">
        <div>
          <h2>Class Analytics</h2>
          <p className="section-subtitle">{stats.length} submissions</p>
        </div>
        <div className="section-actions">
          <button className="btn-ghost btn-small" onClick={exportStatsCSV}>
            Export CSV
          </button>
          <button className="btn-ghost" onClick={() => setView("menu")}>
            Back
          </button>
        </div>
      </div>

      {stats.length === 0 ? (
        <div style={{textAlign: 'center', padding: 40}}>
          <p className="muted">No submissions yet. Students will appear here after taking exams.</p>
        </div>
      ) : (
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>Exam</th>
                <th>Student Email</th>
                <th>Score</th>
                <th>Time</th>
                <th>Date</th>
                <th>Flags</th>
              </tr>
            </thead>
            <tbody>
              {stats.map((s, idx) => (
                <tr key={idx}>
                  <td>{s.exam_name}</td>
                  <td>{s.student_email}</td>
                  <td>
                    <strong>{s.score}/{s.max_marks}</strong>
                    <span style={{marginLeft: 8, fontSize: '0.85rem', color: '#6b7280'}}>
                      ({((s.score / s.max_marks) * 100).toFixed(0)}%)
                    </span>
                  </td>
                  <td>{s.time_taken} mins</td>
                  <td>{s.date}</td>
                  <td>
                    {s.cheating_flags > 0 ? (
                      <span className="pill-tag pill-tag-red">
                        {s.cheating_flags}
                      </span>
                    ) : (
                      <span className="pill-tag pill-tag-green">Clean</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  // NEW: Student Course Feedback
  const renderStudentFeedback = () => (
    <div className="section-card">
      <div className="section-header">
        <div>
          <h2>💬 Student Feedback Forms</h2>
          <p className="section-subtitle">Student opinions about your courses</p>
        </div>
        <button className="btn-ghost" onClick={() => setView("menu")}>
          Back
        </button>
      </div>

      {Object.entries(studentFeedback).length === 0 ? (
        <div style={{textAlign: 'center', padding: 40}}>
          <p className="muted">No student feedback yet. Students submit feedback through the Feedback Survey section.</p>
        </div>
      ) : (
        <div style={{display: 'flex', flexDirection: 'column', gap: 20}}>
          {Object.entries(studentFeedback).map(([subject, feedbacks]) => (
            <div key={subject} style={{
              padding: 20,
              border: '1px solid #e5e7eb',
              borderRadius: 12,
              background: '#fafafa'
            }}>
              <div 
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: 15,
                  cursor: 'pointer',
                  padding: 12,
                  background: '#f0f7ff',
                  borderRadius: 8,
                  userSelect: 'none'
                }}
                onClick={() => setExpandedSubject(expandedSubject === subject ? null : subject)}
              >
                <div style={{display: 'flex', alignItems: 'center', gap: 12}}>
                  <h3 style={{margin: 0}}>{subject}</h3>
                  <span className="pill-tag pill-tag-blue">
                    {feedbacks.length} {feedbacks.length === 1 ? 'feedback' : 'feedbacks'}
                  </span>
                </div>
                <span style={{fontSize: '14px', color: '#1e40af'}}>
                  {expandedSubject === subject ? '▼' : '▶'}
                </span>
              </div>

              {expandedSubject === subject && (
                <div style={{display: 'flex', flexDirection: 'column', gap: 12}}>
                  {feedbacks.map((fb, i) => (
                    <div key={i} style={{
                      padding: 12,
                      background: 'white',
                      border: '1px solid #e5e7eb',
                      borderRadius: 8,
                      marginBottom: 8
                    }}>
                      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'start'}}>
                        <div style={{flex: 1}}>
                          <p style={{margin: '0 0 5px 0', fontWeight: 600}}>
                            {fb.student_name || "Anonymous"}
                          </p>
                          <p style={{margin: '0', fontSize: '0.9rem', color: '#6b7280'}}>
                            {fb.submitted_at?.substring(0, 10) || "N/A"}
                          </p>
                        </div>
                        {fb.rating && (
                          <span style={{
                            padding: '4px 8px',
                            borderRadius: '4px',
                            fontWeight: 600,
                            fontSize: '12px',
                            background: fb.rating >= 4 ? '#d4edda' : fb.rating === 3 ? '#fff3cd' : '#f8d7da',
                            color: fb.rating >= 4 ? '#155724' : fb.rating === 3 ? '#856404' : '#721c24'
                          }}>
                            ⭐ {fb.rating}/5
                          </span>
                        )}
                      </div>

                      {fb.feedback_text && (
                        <div style={{marginTop: 10, fontSize: '13px', color: '#555', lineHeight: '1.5', fontStyle: 'italic'}}>
                          "{fb.feedback_text}"
                        </div>
                      )}

                      {fb.answers && Object.keys(fb.answers).length > 0 && (
                        <div style={{marginTop: 10, fontSize: '12px'}}>
                          <div style={{fontWeight: 600, color: '#666', marginBottom: '6px'}}>
                            Survey Answers:
                          </div>
                          {Object.entries(fb.answers).map(([q, a]) => (
                            <div key={q} style={{color: '#666', marginBottom: '4px'}}>
                              • <strong>{q}:</strong> {String(a)}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );

  // OLD: Exam Performance Feedback
  const renderFeedback = () => (
    <div className="section-card">
      <div className="section-header">
        <div>
          <h2>📋 Exam Performance Feedback</h2>
          <p className="section-subtitle">{feedback?.feedback_count || 0} submissions</p>
        </div>
        <button className="btn-ghost" onClick={() => setView("menu")}>
          Back
        </button>
      </div>

      {!feedback || feedback.feedback_count === 0 ? (
        <div style={{textAlign: 'center', padding: 40}}>
          <p className="muted">No exam submissions yet.</p>
        </div>
      ) : (
        <div style={{display: 'flex', flexDirection: 'column', gap: 20}}>
          {Object.entries(feedback.by_subject || {}).map(([subject, feedbacks]) => (
            <div key={subject} style={{
              padding: 20,
              border: '1px solid #e5e7eb',
              borderRadius: 12,
              background: '#fafafa'
            }}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 15}}>
                <h3 style={{margin: 0}}>{subject}</h3>
                <span className="pill-tag pill-tag-blue">
                  {feedbacks.length} {feedbacks.length === 1 ? 'submission' : 'submissions'}
                </span>
              </div>

              <div style={{display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 500, overflowY: 'auto'}}>
                {feedbacks.map((fb, i) => (
                  <div key={i} style={{
                    padding: 12,
                    background: 'white',
                    border: '1px solid #e5e7eb',
                    borderRadius: 8,
                    marginBottom: 8
                  }}>
                    <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'start'}}>
                      <div style={{flex: 1}}>
                        <p style={{margin: '0 0 5px 0', fontWeight: 600}}>
                          {fb.student_name}
                        </p>
                        <p style={{margin: '0 0 5px 0', fontSize: '0.9rem', color: '#6b7280'}}>
                          {fb.student_email}
                        </p>
                        <p style={{margin: '0 0 5px 0', fontSize: '0.9rem', color: '#6b7280'}}>
                          Exam: <strong>{fb.exam_name}</strong>
                        </p>
                        <p style={{margin: '0', fontSize: '0.9rem', color: '#6b7280'}}>
                          Score: <strong>{fb.score}</strong> | Time: <strong>{fb.time_taken_minutes}</strong> min
                        </p>
                      </div>
                      <span style={{fontSize: '0.8rem', color: '#9ca3af'}}>
                        {new Date(fb.submitted_at).toLocaleDateString()}
                      </span>
                    </div>

                    <details style={{marginTop: 12, fontSize: '0.9rem', cursor: 'pointer'}}>
                      <summary style={{color: '#1e40af', fontWeight: 500, userSelect: 'none'}}>
                        📋 View Student Answers & Feedback
                      </summary>
                      <div style={{marginTop: 12, padding: 12, background: '#f9fafb', borderRadius: 6, fontSize: '0.85rem'}}>
                        <div style={{marginBottom: 12}}>
                          <strong style={{color: '#1f2937'}}>Student Answers:</strong>
                          <pre style={{
                            background: '#fff',
                            padding: 8,
                            borderRadius: 4,
                            overflow: 'auto',
                            fontSize: '0.8rem',
                            border: '1px solid #e5e7eb',
                            maxHeight: 200
                          }}>
                            {JSON.stringify(fb.student_answers, null, 2)}
                          </pre>
                        </div>
                        <div>
                          <strong style={{color: '#1f2937'}}>Feedback:</strong>
                          <pre style={{
                            background: '#fff',
                            padding: 8,
                            borderRadius: 4,
                            overflow: 'auto',
                            fontSize: '0.8rem',
                            border: '1px solid #e5e7eb',
                            maxHeight: 200
                          }}>
                            {JSON.stringify(fb.feedback_json, null, 2)}
                          </pre>
                        </div>
                      </div>
                    </details>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderViewAssignments = () => (
    <div className="section-card">
      <div className="section-header">
        <h2>Assignment Submissions</h2>
        <button className="btn-ghost" onClick={() => setView("menu")}>
          Back
        </button>
      </div>

      {teacherAssignments.length === 0 ? (
        <div style={{textAlign: 'center', padding: 40}}>
          <p className="muted">No assignments created yet.</p>
        </div>
      ) : (
        <div style={{display: 'flex', flexDirection: 'column', gap: 20}}>
          {teacherAssignments.map(assign => (
            <div key={assign.id} className="question-card">
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: 15}}>
                <div>
                  <h3 style={{margin: 0}}>{assign.title}</h3>
                  <p className="muted" style={{margin: '5px 0'}}>Subject: {assign.subject}</p>
                  <p className="muted" style={{margin: '5px 0'}}>Deadline: {new Date(assign.deadline).toLocaleDateString()}</p>
                  <p className="muted" style={{margin: '5px 0'}}>Created: {new Date(assign.created_at).toLocaleDateString()}</p>
                </div>
                <span className="pill-tag pill-tag-blue">
                  {assign.submission_count} {assign.submission_count === 1 ? 'submission' : 'submissions'}
                </span>
              </div>

              {assign.submissions.length === 0 ? (
                <div style={{padding: 20, textAlign: 'center', background: '#f9fafb', borderRadius: 8, marginTop: 15}}>
                  <p className="muted" style={{margin: 0}}>No submissions yet.</p>
                </div>
              ) : (
                <div className="table-shell" style={{marginTop: 15}}>
                  <table>
                    <thead>
                      <tr>
                        <th>Student</th>
                        <th>Submitted On</th>
                        <th>Status</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {assign.submissions.map(sub => {
                        const submittedDate = new Date(sub.submitted_at);
                        const deadlineDate = new Date(assign.deadline);
                        const wasOnTime = submittedDate <= deadlineDate;
                        
                        return (
                          <tr key={sub.id}>
                            <td>
                              <strong>{sub.student_name}</strong>
                              <br />
                              <span style={{fontSize: '0.85rem', color: '#6b7280'}}>{sub.student_email}</span>
                            </td>
                            <td>{submittedDate.toLocaleString()}</td>
                            <td>
                              <span className={`pill-tag ${wasOnTime ? 'pill-tag-green' : 'pill-tag-orange'}`}>
                                {wasOnTime ? 'On Time' : 'Late'}
                              </span>
                            </td>
                            <td>
                              <button 
                                className="btn-ghost btn-small"
                                onClick={() => downloadSubmission(
                                  `${sub.student_name}_${assign.title}.pdf`,
                                  sub.file_data
                                )}
                              >
                                Download PDF
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );

  // MAIN RENDER
  return (
    <div className="teacher-page">
      {loading && (
        <div style={{textAlign: 'center', padding: 40}}>
          <div className="loader-orbit"><div /><div /><div /></div>
          <p>Loading...</p>
        </div>
      )}

      {error && (
        <div style={{
          padding: 15,
          background: '#fef2f2',
          borderRadius: 12,
          marginBottom: 20,
          border: '1px solid #fecaca'
        }}>
          <strong style={{color: '#991b1b'}}>Error:</strong> {error}
        </div>
      )}

      {!loading && (
        <>
          {view === "menu" && renderMenu()}
          {view === "create" && renderCreate()}
          {view === "assignment" && renderAssignment()}
          {view === "stats" && renderStats()}
          {view === "student-feedback" && renderStudentFeedback()}
          {view === "feedback" && renderFeedback()}
          {view === "view-assignments" && renderViewAssignments()}
        </>
      )}
    </div>
  );
}

export default TeacherDashboard;
