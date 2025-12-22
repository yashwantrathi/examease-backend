# Supabase Email Fix - Step by Step

## The Problem
Error: `column profiles.user_metadata does not exist`

The `get_user_email()` function tries to look up emails but Supabase doesn't have the data structure it expects. Result: All students show as "unknown@unknown.com"

## The Solution

### Option A: Add Email Column to Submissions (RECOMMENDED - FASTEST)

✅ **Best option** - Only 2 SQL commands needed

**Step 1: Open Supabase Dashboard → SQL Editor**

**Step 2: Run this command to add email column:**
```sql
ALTER TABLE submissions ADD COLUMN student_email VARCHAR(255) DEFAULT 'unknown@unknown.com';
```

**Step 3: Backfill existing submissions with email from profiles:**
```sql
UPDATE submissions 
SET student_email = profiles.email
FROM profiles
WHERE submissions.student_id = profiles.id
AND submissions.student_email = 'unknown@unknown.com';
```

**Step 4: Test**
- Refresh teacher dashboard
- Students should now show actual emails instead of "unknown@unknown.com"

---

### Option B: Fix Profiles Table (ALTERNATIVE - REQUIRES MIGRATION)

⚠️ **More complex** - Requires multiple steps

**Step 1: Check if profiles table has email column:**
```sql
SELECT column_name FROM information_schema.columns 
WHERE table_name='profiles' AND column_name='email';
```

**Step 2a: If no email column, add it:**
```sql
ALTER TABLE profiles ADD COLUMN email VARCHAR(255);
```

**Step 2b: If auth.users has emails, populate it:**
```sql
UPDATE profiles 
SET email = auth.users.email
FROM auth.users
WHERE profiles.user_id = auth.users.id
AND profiles.email IS NULL;
```

**Step 3: Remove user_metadata references from get_user_email()** (optional optimization)

---

## How to Access Supabase Dashboard

1. Go to https://app.supabase.com
2. Login with your credentials
3. Select your ExamEase project
4. Click "SQL Editor" in left sidebar
5. Click "New Query"
6. Paste one of the commands above
7. Click "Run" button

---

## Expected Results

### Before Fix:
Teacher Dashboard shows:
```
Assignment Submissions
┌─────────────────────────────────────────┐
│ Student: unknown@unknown.com            │
│ Score: 45/100                           │
│ Time: 12 minutes                        │
└─────────────────────────────────────────┘
```

### After Fix:
Teacher Dashboard shows:
```
Assignment Submissions
┌─────────────────────────────────────────┐
│ Student: rajesh.patel@example.com       │
│ Score: 45/100                           │
│ Time: 12 minutes                        │
└─────────────────────────────────────────┘
```

---

## Verification

**To verify the fix worked:**

```sql
-- Check if student_email column was added
SELECT student_id, student_email FROM submissions LIMIT 5;

-- Check how many submissions still have 'unknown@unknown.com'
SELECT COUNT(*) FROM submissions WHERE student_email = 'unknown@unknown.com';

-- View a specific student's emails
SELECT DISTINCT student_email FROM submissions WHERE student_id = 'YOUR_STUDENT_ID';
```

---

## Troubleshooting

### Error: "relation 'profiles' does not exist"
✅ The student_email column is already in submissions table. Just check that backfill worked:
```sql
SELECT COUNT(*) FROM submissions WHERE student_email != 'unknown@unknown.com';
```

### Error: "column 'user_metadata' does not exist"
✅ This is expected - the backend code handles this gracefully. The email will still be stored in `student_email` column.

### Still seeing "unknown@unknown.com" after fix
✅ The backend needs to store email for NEW submissions. Make sure `main.py` has this code:
```python
student_email = get_user_email(sub.student_id)
data["student_email"] = student_email
```
✅ Check that `student_email` is being inserted into database for new submissions

### Old submissions not showing email
✅ Run the backfill command to populate email for existing submissions:
```sql
UPDATE submissions 
SET student_email = profiles.email
FROM profiles
WHERE submissions.student_id = profiles.id
AND submissions.student_email = 'unknown@unknown.com';
```

---

## Time Estimate

- **Adding column & backfill:** 2 minutes
- **Testing in dashboard:** 2 minutes
- **Total:** 5 minutes

---

## After This Fix

✅ Teachers will see actual student emails in:
- Teacher Dashboard → View Results
- Teacher Dashboard → Assignment Submissions
- Teacher Dashboard → Feedback Forms (new feature)

✅ All future submissions will automatically store email

✅ Backend will continue to work even if email lookup fails (graceful fallback still in place)
