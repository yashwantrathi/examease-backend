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

  // Student Feedback (NEW)
  const [studentFeedback, setStudentFeedback] = useState({});
  const [expandedSubject, setExpandedSubject] = useState(null);

  // Exam Performance Feedback (OLD)
  const [feedback, setFeedback] = useState(null);

  // Assignment
  const [assignments, setAssignments] = useState([]);
  const [results, setResults] = useState([]);

  // Fetch student feedback by subject
  const fetchStudentFeedback = async () => {
    try {
      // Get unique subjects from assignments and exams
      const subjects = new Set([
        ...assignments.map(a => a.subject),
        ...results.map(r => r.subject)
      ]);

      const feedbackData = {};
      
      for (const subject of subjects) {
        const response = await fetch(`http://localhost:8000/student-feedback/${subject}`);
        const data = await response.json();
        feedbackData[subject] = data.feedback_list || [];
      }
      
      setStudentFeedback(feedbackData);
    } catch (error) {
      console.error("Error fetching student feedback:", error);
    }
  };

  // Fetch exam results for this teacher
  const fetchResults = async () => {
    try {
      const response = await fetch(`http://localhost:8000/teacher-exams/${user.id}`);
      const data = await response.json();
      setResults(data.results || []);
    } catch (error) {
      console.error("Error fetching results:", error);
    }
  };

  // Fetch assignments for this teacher
  const fetchAssignments = async () => {
    try {
      const response = await fetch(`http://localhost:8000/get-assignments`);
      const data = await response.json();
      setAssignments(data || []);
    } catch (error) {
      console.error("Error fetching assignments:", error);
    }
  };

  useEffect(() => {
    fetchResults();
    fetchAssignments();
  }, [user.id]);

  useEffect(() => {
    if (assignments.length > 0 || results.length > 0) {
      fetchStudentFeedback();
    }
  }, [assignments, results]);

  const dashboardStyles = `
    .dashboard-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
      padding: 20px;
      max-width: 1400px;
      margin: 0 auto;
    }

    @media (max-width: 1024px) {
      .dashboard-grid {
        grid-template-columns: 1fr;
      }
    }

    .dashboard-card {
      background: white;
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      transition: all 0.3s ease;
    }

    .dashboard-card:hover {
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      transform: translateY(-2px);
    }

    .dashboard-title {
      font-size: 20px;
      font-weight: 600;
      margin-bottom: 16px;
      color: #333;
    }

    .dashboard-content {
      font-size: 16px;
      line-height: 1.6;
      color: #555;
    }

    .dashboard-label {
      font-size: 14px;
      font-weight: 500;
      color: #666;
      margin-bottom: 8px;
    }

    .dashboard-value {
      font-size: 18px;
      font-weight: 600;
      color: #1e40af;
      margin-bottom: 12px;
    }

    .dashboard-scroll-content {
      max-height: 400px;
      overflow-y: auto;
      padding-right: 8px;
    }

    .dashboard-scroll-content::-webkit-scrollbar {
      width: 6px;
    }

    .dashboard-scroll-content::-webkit-scrollbar-track {
      background: #f1f1f1;
      border-radius: 3px;
    }

    .dashboard-scroll-content::-webkit-scrollbar-thumb {
      background: #888;
      border-radius: 3px;
    }

    .dashboard-scroll-content::-webkit-scrollbar-thumb:hover {
      background: #555;
    }

    .feedback-item {
      padding: 12px;
      border: 1px solid #e0e0e0;
      border-radius: 6px;
      margin-bottom: 10px;
      background: #f9f9f9;
    }

    .feedback-item:hover {
      background: #f0f7ff;
      border-color: #1e40af;
    }

    .feedback-rating {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 4px;
      font-weight: 600;
      margin-left: 8px;
      font-size: 12px;
    }

    .rating-5 { background: #d4edda; color: #155724; }
    .rating-4 { background: #d1ecf1; color: #0c5460; }
    .rating-3 { background: #fff3cd; color: #856404; }
    .rating-2 { background: #f8d7da; color: #721c24; }
    .rating-1 { background: #f8d7da; color: #721c24; }

    .subject-section {
      margin-bottom: 16px;
      padding-bottom: 16px;
      border-bottom: 2px solid #e0e0e0;
    }

    .subject-section:last-child {
      border-bottom: none;
    }

    .subject-header {
      cursor: pointer;
      padding: 12px;
      background: #f0f7ff;
      border-radius: 6px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }

    .subject-header:hover {
      background: #e3f2fd;
    }

    .subject-name {
      font-size: 16px;
      font-weight: 600;
      color: #1e40af;
    }

    .feedback-count {
      font-size: 13px;
      color: #666;
      background: white;
      padding: 4px 8px;
      border-radius: 4px;
    }

    .toggle-icon {
      font-size: 14px;
      color: #1e40af;
    }
  `;

  return (
    <div>
      <style>{dashboardStyles}</style>
      
      <div className="dashboard-grid">
        {/* Dashboard 1: Class Overview */}
        <div className="dashboard-card">
          <div className="dashboard-title">👥 Class Overview</div>
          <div className="dashboard-content">
            <div style={{ marginBottom: "16px" }}>
              <div className="dashboard-label">Total Students:</div>
              <div className="dashboard-value">
                {new Set([
                  ...results.map(r => r.student_id),
                  ...assignments.map(a => a.student_id)
                ]).size}
              </div>
            </div>
            <div style={{ marginBottom: "16px" }}>
              <div className="dashboard-label">Total Exams Created:</div>
              <div className="dashboard-value">
                {new Set(results.map(r => r.exam_id)).size}
              </div>
            </div>
            <div>
              <div className="dashboard-label">Assignments Pending:</div>
              <div className="dashboard-value">
                {assignments.filter(a => !a.submitted).length}
              </div>
            </div>
          </div>
        </div>

        {/* Dashboard 2: Exam Results Summary */}
        <div className="dashboard-card">
          <div className="dashboard-title">📊 Exam Results</div>
          <div className="dashboard-scroll-content">
            {results.slice(0, 10).map((result, idx) => (
              <div key={idx} style={{ marginBottom: "12px", paddingBottom: "12px", borderBottom: "1px solid #eee" }}>
                <div className="dashboard-label">
                  {result.student_name || "Student"}
                </div>
                <div className="dashboard-value">
                  {result.score_numeric}/{result.total_marks}
                </div>
                <div style={{ fontSize: "12px", color: "#999" }}>
                  {result.exam_name || "Exam"} • {result.created_at?.substring(0, 10) || "N/A"}
                </div>
              </div>
            ))}
            {results.length === 0 && (
              <div style={{ color: "#999", textAlign: "center", padding: "20px 0" }}>
                No exam submissions yet
              </div>
            )}
          </div>
        </div>

        {/* Dashboard 3: Student Feedback Forms */}
        <div className="dashboard-card" style={{ gridColumn: "1 / -1" }}>
          <div className="dashboard-title">💬 Student Feedback Forms</div>
          <div className="dashboard-scroll-content">
            {Object.entries(studentFeedback).length > 0 ? (
              Object.entries(studentFeedback).map(([subject, feedbacks]) => (
                <div key={subject} className="subject-section">
                  <div
                    className="subject-header"
                    onClick={() =>
                      setExpandedSubject(expandedSubject === subject ? null : subject)
                    }
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <span className="subject-name">{subject}</span>
                      <span className="feedback-count">{feedbacks.length} feedback</span>
                    </div>
                    <span className="toggle-icon">
                      {expandedSubject === subject ? "▼" : "▶"}
                    </span>
                  </div>

                  {expandedSubject === subject && (
                    <div>
                      {feedbacks.map((feedback, idx) => (
                        <div key={idx} className="feedback-item">
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
                            <div>
                              <div style={{ fontWeight: 600, fontSize: "14px", color: "#333" }}>
                                {feedback.student_name || "Anonymous"}
                              </div>
                              <div style={{ fontSize: "12px", color: "#666", marginTop: "4px" }}>
                                {feedback.submitted_at?.substring(0, 10) || "N/A"}
                              </div>
                            </div>
                            {feedback.rating && (
                              <span className={`feedback-rating rating-${feedback.rating}`}>
                                ⭐ {feedback.rating}/5
                              </span>
                            )}
                          </div>

                          {feedback.feedback_text && (
                            <div style={{ marginTop: "10px", fontSize: "13px", color: "#555", lineHeight: "1.5" }}>
                              "{feedback.feedback_text}"
                            </div>
                          )}

                          {feedback.answers && Object.keys(feedback.answers).length > 0 && (
                            <div style={{ marginTop: "10px", fontSize: "12px" }}>
                              <div style={{ fontWeight: 600, color: "#666", marginBottom: "6px" }}>
                                Answers:
                              </div>
                              {Object.entries(feedback.answers).map(([q, a]) => (
                                <div key={q} style={{ color: "#666", marginBottom: "4px" }}>
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
              ))
            ) : (
              <div style={{ color: "#999", textAlign: "center", padding: "20px 0" }}>
                No student feedback yet
              </div>
            )}
          </div>
        </div>

        {/* Dashboard 4: Pending Assignments */}
        <div className="dashboard-card" style={{ gridColumn: "1 / -1" }}>
          <div className="dashboard-title">📋 Assignment Status</div>
          <div className="dashboard-scroll-content">
            {assignments.map((assignment, idx) => (
              <div key={idx} style={{ marginBottom: "12px", paddingBottom: "12px", borderBottom: "1px solid #eee" }}>
                <div className="dashboard-label">
                  {assignment.student_name || "Student"}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="dashboard-value" style={{ fontSize: "16px" }}>
                    {assignment.submitted ? "✓ Submitted" : "⏳ Pending"}
                  </span>
                  <span style={{ fontSize: "12px", color: "#666" }}>
                    {assignment.submitted_date || "Not submitted"}
                  </span>
                </div>
              </div>
            ))}
            {assignments.length === 0 && (
              <div style={{ color: "#999", textAlign: "center", padding: "20px 0" }}>
                No assignments assigned yet
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default TeacherDashboard;
