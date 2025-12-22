# Tab Switching Detection & Exam Security Guide

## Backend Implementation (✅ COMPLETE)

The backend now provides session management endpoints:

### Endpoints Added:

1. **`POST /session/start-exam`** - Start tracking an exam session
   ```json
   Request: {
     "student_id": "uuid",
     "exam_id": "EXAM123",
     "session_id": "unique-session-id",
     "action": "start_exam"
   }
   Response: {
     "status": "session_started",
     "message": "Exam session created"
   }
   ```

2. **`POST /session/check-exam`** - Check if session is still valid
   ```json
   Request: {
     "student_id": "uuid",
     "exam_id": "EXAM123",
     "session_id": "unique-session-id",
     "action": "still_active"
   }
   Response: {
     "valid": true|false,
     "message": "...",
     "tab_switched": true|false
   }
   ```

3. **`POST /session/tab-switch`** - Log tab switch violation
   ```json
   Request: {
     "student_id": "uuid",
     "exam_id": "EXAM123",
     "session_id": "unique-session-id",
     "action": "tab_switched"
   }
   Response: {
     "status": "tab_switch_recorded",
     "message": "Tab switch recorded. If you continue, exam will be terminated."
   }
   ```

4. **`POST /session/end-exam`** - Properly end the exam session
   ```json
   Request: {
     "student_id": "uuid",
     "exam_id": "EXAM123",
     "session_id": "unique-session-id",
     "action": "end_exam"
   }
   Response: {
     "status": "session_ended",
     "tab_switched": true|false
   }
   ```

## Frontend Implementation (NEEDED)

### Step 1: Start Session When Exam Begins
In your exam component (StudentPage.jsx or similar), add:

```javascript
import { useState, useEffect } from 'react';

function ExamComponent() {
  const [sessionId] = useState(crypto.randomUUID());
  const API_URL = "http://localhost:8000";
  
  // Start exam session
  useEffect(() => {
    const startSession = async () => {
      try {
        await fetch(`${API_URL}/session/start-exam`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            student_id: studentId,
            exam_id: examId,
            session_id: sessionId,
            action: 'start_exam'
          })
        });
        console.log('✅ Exam session started');
      } catch (err) {
        console.error('Failed to start session:', err);
      }
    };
    
    startSession();
  }, [examId, studentId, sessionId]);
  
  return <div>Exam content...</div>;
}
```

### Step 2: Detect Tab Switches
Add this to your exam component:

```javascript
useEffect(() => {
  const handleVisibilityChange = () => {
    if (document.hidden) {
      // Student switched away from tab
      console.warn('⚠️ Tab switch detected!');
      
      fetch(`${API_URL}/session/tab-switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: studentId,
          exam_id: examId,
          session_id: sessionId,
          action: 'tab_switched'
        })
      });
      
      // Show warning to student
      alert('⚠️ WARNING: You switched tabs during the exam!\n\nMultiple tab switches may result in exam termination.');
      
    } else {
      // Student came back to tab - check if exam is still valid
      checkSessionValidity();
    }
  };
  
  document.addEventListener('visibilitychange', handleVisibilityChange);
  
  return () => {
    document.removeEventListener('visibilitychange', handleVisibilityChange);
  };
}, [examId, studentId, sessionId]);

const checkSessionValidity = async () => {
  try {
    const response = await fetch(`${API_URL}/session/check-exam`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        student_id: studentId,
        exam_id: examId,
        session_id: sessionId,
        action: 'still_active'
      })
    });
    
    const data = await response.json();
    
    if (!data.valid) {
      // Exam session is invalid - terminate
      alert('❌ ' + data.message);
      window.location.href = '/student'; // Redirect away
      return false;
    }
    
    return true;
  } catch (err) {
    console.error('Failed to check session:', err);
    return true; // Allow to continue on error
  }
};
```

### Step 3: End Session When Exam Finishes
When submitting the exam:

```javascript
const handleSubmitExam = async () => {
  // Submit exam results first
  const submitResponse = await fetch(`${API_URL}/submit-exam-result`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      exam_id: examId,
      student_id: studentId,
      score_numeric: score,
      total_marks: totalMarks,
      time_taken_seconds: timeTaken,
      student_answers: answers,
      feedback_json: feedback,
      cheating_log: tabSwitchCount > 0 ? ['tab_switch'] : []
    })
  });
  
  // Then end the session
  await fetch(`${API_URL}/session/end-exam`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      student_id: studentId,
      exam_id: examId,
      session_id: sessionId,
      action: 'end_exam'
    })
  });
  
  // Show results
  window.location.href = '/student/results';
};
```

## Key Features

✅ **Tab Switch Detection**: Uses Page Visibility API
✅ **Session Tracking**: Backend remembers exam state
✅ **Violation Logging**: Tracks how many times student switched tabs
✅ **Automatic Termination**: Exam can be terminated if too many switches
✅ **Warning System**: Student gets warnings before termination

## Browser Support

The `visibilitychange` event is supported in:
- Chrome 13+
- Firefox 10+
- Safari 7+
- Edge 12+
- Internet Explorer 10+

## Notes

- Session data is stored in memory and will be lost if backend restarts
- For production, consider persisting to database
- Tab switches are logged in the cheating_log field
- Teachers can see tab switch violations in exam results

## Example Implementation in StudentPage.jsx

See the tab-switch implementation guide in the frontend repo for a complete example.
