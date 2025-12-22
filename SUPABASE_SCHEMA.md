# Supabase Schema Update Instructions

## Check Current Schema

Run these SQL queries in your Supabase SQL editor to see current table structure:

```sql
-- Check assignment_submissions table
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'assignment_submissions'
ORDER BY ordinal_position;

-- Check submissions table
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'submissions'
ORDER BY ordinal_position;
```

## Add Missing Columns (if needed)

### 1. Add student_email to assignment_submissions

```sql
-- Check if column exists first
ALTER TABLE assignment_submissions
ADD COLUMN student_email TEXT;

-- Make it indexed for faster lookups
CREATE INDEX idx_assignment_submissions_email 
ON assignment_submissions(student_email);
```

### 2. Add student_email to submissions (if not exists)

```sql
-- Check if column exists first
ALTER TABLE submissions
ADD COLUMN student_email TEXT;

-- Make it indexed
CREATE INDEX idx_submissions_email 
ON submissions(student_email);
```

### 3. Update existing records (OPTIONAL - for past submissions)

If you want to populate existing records with emails, run this after adding the columns:

```sql
-- For assignment_submissions
UPDATE assignment_submissions
SET student_email = 'unknown@unknown.com'
WHERE student_email IS NULL;

-- For submissions
UPDATE submissions
SET student_email = 'unknown@unknown.com'
WHERE student_email IS NULL;
```

## Enable Timestampz for created_at

Ensure `created_at` is properly set up:

```sql
-- Check current setup
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'assignment_submissions'
AND column_name = 'created_at';

-- If not auto-generated, update existing ones
UPDATE assignment_submissions
SET created_at = NOW()
WHERE created_at IS NULL;

-- Make it auto-generate for future rows (if using PostgreSQL triggers)
-- This should be set at table creation, but can be verified in Supabase UI
```

## Recommended Table Structures

### assignment_submissions
```sql
CREATE TABLE assignment_submissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  assignment_id UUID NOT NULL REFERENCES assignments(id),
  student_id UUID NOT NULL,
  student_email TEXT,
  file_data TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_assignment_submissions_assignment_id ON assignment_submissions(assignment_id);
CREATE INDEX idx_assignment_submissions_student_id ON assignment_submissions(student_id);
CREATE INDEX idx_assignment_submissions_email ON assignment_submissions(student_email);
```

### submissions
```sql
CREATE TABLE submissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_id TEXT NOT NULL,
  student_id UUID NOT NULL,
  student_email TEXT,
  score_numeric FLOAT NOT NULL,
  total_marks FLOAT NOT NULL,
  time_taken_seconds INTEGER,
  student_answers JSONB,
  feedback_json JSONB,
  cheating_log JSONB DEFAULT '[]'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_submissions_exam_id ON submissions(exam_id);
CREATE INDEX idx_submissions_student_id ON submissions(student_id);
CREATE INDEX idx_submissions_email ON submissions(student_email);
CREATE INDEX idx_submissions_created_at ON submissions(created_at);
```

## Update RLS Policies (if needed)

If you want the backend to read auth.users emails, update RLS:

```sql
-- Allow service role to read auth.users (already allowed by default)
-- For profiles table, allow authenticated users to read their own
ALTER POLICY "Enable read access for authenticated users" ON profiles
FOR SELECT
USING (auth.uid() = id);

-- Allow service role to read all profiles
ALTER POLICY "Enable read access for service role" ON profiles
FOR SELECT
USING (true);
```

## Verify Changes

After making changes, run this in SQL editor:

```sql
-- Check assignment_submissions columns
\d assignment_submissions

-- Check submissions columns
\d submissions

-- Check RLS policies
SELECT schemaname, tablename, policyname, permissive, roles, qual, with_check
FROM pg_policies
WHERE tablename IN ('assignment_submissions', 'submissions', 'profiles');
```

## Test Connection

After schema updates, test the API:

```bash
curl http://localhost:8000/health
```

Should return:
```json
{
  "status": "healthy",
  "supabase": "connected",
  "gemini": "configured",
  "max_file_size_mb": 10
}
```

## If Using Supabase UI

Instead of SQL, you can:

1. Go to **Database** → **Tables**
2. Select **assignment_submissions**
3. Click **+ Add Column**
4. Name: `student_email`
5. Type: `Text`
6. Nullable: Yes
7. Save

Repeat for `submissions` table if needed.

## Notes

- These changes are backward compatible
- Old records will have NULL or "unknown@unknown.com" in the new email column
- New submissions will automatically include the student email
- No data loss from these changes
- Indexes improve query performance for large datasets
