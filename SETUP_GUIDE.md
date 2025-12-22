# 🔗 Frontend-Backend Connection Guide

## Current Setup Status
✅ **Backend**: Running on `http://localhost:8000`
✅ **Frontend**: Configured to connect to `http://localhost:8000`
✅ **CORS**: Properly configured for `http://localhost:5173` and `http://localhost:5174`

## How to Run Both

### Step 1: Start the Backend (Terminal 1)
```bash
cd C:\Users\surya\OneDrive\Desktop\examease-backend
python main.py
```

Output should show:
```
✅ Services initialized successfully
🚀 Starting ExamEase Backend Server...
🌐 Server will run at: http://localhost:8000
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 2: Start the Frontend (Terminal 2)
```bash
cd C:\Users\surya\OneDrive\Desktop\examease-frontend
npm run dev
```

Output should show:
```
VITE v... ready in ... ms
➜  Local:   http://localhost:5173/
```

### Step 3: Open in Browser
Navigate to: **`http://localhost:5173`**

## Testing Connectivity

Run the connectivity test:
```bash
cd C:\Users\surya\OneDrive\Desktop\examease-backend
python test_connectivity.py
```

You should see:
```
✅ All tests passed! Frontend can connect to backend.
   Backend URL: http://localhost:8000
```

## Common Issues & Fixes

### Issue 1: Port Already in Use
**Error**: `Address already in use`

**Solution**: Kill the process using the port
```bash
# For port 8000 (backend)
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# For port 5173 (frontend)
netstat -ano | findstr :5173
taskkill /PID <PID> /F
```

### Issue 2: CORS Error in Browser Console
**Error**: `Access to XMLHttpRequest has been blocked by CORS policy`

**Solution**: This means backend isn't running or isn't properly configured. Make sure:
1. Backend is running on `http://localhost:8000`
2. The CORS middleware in `main.py` includes your frontend's origin

Current CORS settings allow:
- `http://localhost:5173` (default Vite dev port)
- `http://localhost:5174` (alternate port)
- `http://127.0.0.1:5173` (localhost alias)

### Issue 3: Can't Connect to Supabase
**Error**: Connection fails when creating/reading data

**Solution**: 
1. Check your Supabase credentials in `main.py`
2. Ensure your Supabase project has the required tables
3. Check RLS (Row Level Security) policies if data isn't showing

### Issue 4: Features Not Working (Buttons Not Responding)
**Most Likely Cause**: Backend returning 500 errors

**Debug Steps**:
1. Open browser DevTools (`F12`)
2. Go to `Network` tab
3. Click the button that's not working
4. Look for red requests (errors)
5. Click the failed request and check the `Response` tab
6. Look at backend terminal for error messages

## API Endpoints Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Check backend health |
| `/` | GET | Server status |
| `/generate-quiz` | POST | Generate quiz from PDF |
| `/student-assignments/{student_id}` | GET | Get student's assignments |
| `/teacher-assignments/{teacher_id}` | GET | Get teacher's assignments |
| `/submit-assignment` | POST | Submit assignment file |
| `/create-assignment` | POST | Create new assignment |
| `/student-stats/{student_id}` | GET | Get student exam stats |
| `/teacher-stats/{teacher_id}` | GET | Get teacher exam stats |

## Troubleshooting Checklist

- [ ] Backend running? (`http://localhost:8000/health` returns 200)
- [ ] Frontend running? (Can access `http://localhost:5173`)
- [ ] CORS errors in browser console? (Check DevTools)
- [ ] API returns 500? (Check backend terminal for errors)
- [ ] Files uploading fail? (Check file size < 10MB)
- [ ] Supabase data not appearing? (Check authentication & RLS)

## Contact Debug Info

If you still have issues, provide:
1. Backend console error message (full traceback)
2. Browser DevTools Network tab error response
3. The feature/button that's not working
4. Steps to reproduce
