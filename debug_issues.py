#!/usr/bin/env python3
"""Debug script to investigate submission and email issues"""
import main

print("=" * 70)
print("🔍 DEBUGGING ASSIGNMENT & EMAIL ISSUES")
print("=" * 70)

# Known IDs from the system
TEACHER_ID = '875beb3e-e64a-4029-8b24-a9a2a0dfd31b'
STUDENT_ID = '092d83b1-d1d4-48d1-85f0-4e13969cf12b'

print("\n📋 ISSUE 1: Check Assignment Submissions Data")
print("-" * 70)

try:
    # Get teacher's assignments
    assignments = main.supabase.table('assignments').select('*').eq('teacher_id', TEACHER_ID).execute()
    print(f"✓ Teacher has {len(assignments.data)} assignments:")
    
    for a in assignments.data:
        assignment_id = a['id']
        print(f"\n  Assignment: {a['title']} (ID: {assignment_id})")
        print(f"  ID Type: {type(assignment_id).__name__}")
        
        # Check submissions - try both UUID and string
        subs_uuid = main.supabase.table('assignment_submissions').select('*').eq('assignment_id', assignment_id).execute()
        subs_str = main.supabase.table('assignment_submissions').select('*').eq('assignment_id', str(assignment_id)).execute()
        
        print(f"  Submissions (by UUID): {len(subs_uuid.data)}")
        print(f"  Submissions (by string): {len(subs_str.data)}")
        
        # Use the one that worked
        subs = subs_uuid.data if subs_uuid.data else subs_str.data
        for s in subs:
            print(f"    ✓ Submission from: {s['student_id']}")
            print(f"      Submitted at: {s.get('created_at', 'N/A')}")
            print(f"      Assignment ID in submission: {s.get('assignment_id')} (type: {type(s.get('assignment_id')).__name__})")
            
except Exception as e:
    print(f"✗ Error fetching assignments: {e}")
    import traceback
    traceback.print_exc()

print("\n\n📧 ISSUE 2: Check Student Email Retrieval")
print("-" * 70)

try:
    # Check profiles table
    profile = main.supabase.table('profiles').select('*').eq('id', STUDENT_ID).execute()
    print(f"✓ Profile data for {STUDENT_ID}:")
    if profile.data:
        print(f"  Found: {profile.data[0]}")
        print(f"  Has email? {'email' in profile.data[0]}")
        if 'email' in profile.data[0]:
            print(f"  Email value: {profile.data[0]['email']}")
    else:
        print(f"  ✗ No profile found in profiles table")
    
    # Try auth.admin
    print(f"\n✓ Checking auth.users table:")
    try:
        auth_user = main.supabase.auth.admin.get_user_by_id(STUDENT_ID)
        print(f"  Found user: {auth_user.user.email if auth_user and auth_user.user else 'N/A'}")
    except Exception as e:
        print(f"  ✗ Error accessing auth.users: {e}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n\n📊 ISSUE 3: Check Submissions with Email")
print("-" * 70)

try:
    # Get submissions for viewing in results
    exams = main.supabase.table('exams').select('exam_id').eq('teacher_id', TEACHER_ID).execute()
    if exams.data:
        exam_ids = [e['exam_id'] for e in exams.data]
        print(f"✓ Teacher has {len(exam_ids)} exams")
        
        subs = main.supabase.table('submissions').select('*').in_('exam_id', exam_ids).execute()
        print(f"✓ Submissions: {len(subs.data)}")
        
        for s in subs.data[:3]:  # Show first 3
            email = main.get_user_email(s['student_id'])
            print(f"\n  Exam: {s['exam_id']}")
            print(f"  Student ID: {s['student_id']}")
            print(f"  Retrieved Email: {email}")
            print(f"  Score: {s['score_numeric']}/{s['total_marks']}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("✓ Debug complete. Check output above for issues.")
print("=" * 70)
