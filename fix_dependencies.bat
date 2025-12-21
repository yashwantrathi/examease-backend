@echo off
echo ========================================
echo ExamEase Dependency Fixer
echo ========================================
echo.
echo Uninstalling conflicting packages...
pip uninstall -y supabase httpx gotrue

echo.
echo Installing compatible versions...
pip install supabase==2.10.0
pip install httpx==0.27.0
pip install gotrue==2.9.1

echo.
echo Installing other dependencies...
pip install fastapi==0.109.0
pip install uvicorn[standard]==0.27.0
pip install python-multipart==0.0.6
pip install google-generativeai==0.3.2
pip install PyPDF2==3.0.1
pip install reportlab==4.0.9
pip install python-dotenv==1.0.0
pip install pydantic==2.5.3

echo.
echo ========================================
echo ✅ Dependencies fixed!
echo ========================================
echo.
echo Now run: python main.py
pause