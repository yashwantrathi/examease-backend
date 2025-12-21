-- Create feedback_submissions table for student feedback survey responses
CREATE TABLE IF NOT EXISTS feedback_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL,
    student_name TEXT,
    subject TEXT NOT NULL,
    feedback_text TEXT,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    answers JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Add indexes for faster queries
CREATE INDEX IF NOT EXISTS feedback_submissions_subject_idx ON feedback_submissions(subject);
CREATE INDEX IF NOT EXISTS feedback_submissions_student_id_idx ON feedback_submissions(student_id);
CREATE INDEX IF NOT EXISTS feedback_submissions_created_at_idx ON feedback_submissions(created_at DESC);

-- Enable RLS (Row Level Security)
ALTER TABLE feedback_submissions ENABLE ROW LEVEL SECURITY;

-- Create RLS policy: students can only see/insert their own feedback
CREATE POLICY "Students can view and insert their own feedback"
ON feedback_submissions
FOR ALL
USING (student_id = auth.uid())
WITH CHECK (student_id = auth.uid());

-- Create RLS policy: service role can access all feedback (for teachers)
CREATE POLICY "Service role can access all feedback"
ON feedback_submissions
USING (true)
WITH CHECK (true)
FOR ROLE service_role;
