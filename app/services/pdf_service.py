from PIL import Image
import pytesseract
import PyPDF2
import io
import google.generativeai as genai
import os
from app.services.ai_engine import generation_config

def extract_text_from_pdfs(files):
    """Extract and concatenate text from uploaded PDF files."""
    full_text = ""
    for file in files:
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
            for page in pdf_reader.pages:
                extracted = page.extract_text()
                if extracted:
                    full_text += extracted + "\n"
        except Exception as e:
            print(f"Error reading PDF {file.filename}: {e}")
    return full_text


def extract_text_from_files(files):
    """
    Extract text from supported uploads:
    - .pdf via PyPDF2
    - .txt via utf-8 decode (with fallback)
    """
    full_text = ""
    for file in files:
        filename = (file.filename or "").lower()
        if filename.endswith(".pdf"):
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
                for page in pdf_reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        full_text += extracted + "\n"
            except Exception as e:
                print(f"Error reading PDF {file.filename}: {e}")
        elif filename.endswith(".txt"):
            try:
                raw = file.read()
                try:
                    full_text += raw.decode("utf-8") + "\n"
                except Exception:
                    full_text += raw.decode("latin-1", errors="ignore") + "\n"
            except Exception as e:
                print(f"Error reading TXT {file.filename}: {e}")
        else:
            print(f"Unsupported file type: {file.filename}")
    return full_text.strip()

def analyze_exam_papers(files):
    """Sends extracted exam text to Gemini for pattern analysis."""
    text = extract_text_from_pdfs(files)
    if not text:
        return {"success": False, "message": "Failed to extract text from PDFs or files are empty."}
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"success": False, "message": "[Mock Analysis] Gemini API Key not found. If this were live, I would have identified repeating questions on Deadlocks (15% weightage), Normalization (20% weightage), and generated 5 high-probability mock questions for your upcoming exam!"}
        
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=generation_config
        )
        prompt = f"""
        Analyze the following past technical exam papers. 
        Identify repeating question patterns, group them by topic weightage, and generate high-probability mock questions for upcoming exams.
        Format your response in neat Markdown.
        
        Raw Exam Text:
        {text[:50000]} # Limiting context size slightly for safety if huge
        """
        response = model.generate_content(prompt)
        return {"success": True, "analysis": response.text}
    except Exception as e:
        return {"success": False, "message": f"Error analyzing exams: {e}"}

def optimize_syllabi(files):
    """Sends extracted syllabi to Gemini for overlap analysis."""
    text = extract_text_from_pdfs(files)
    if not text:
        return {"success": False, "message": "Failed to extract text from PDFs or files are empty."}
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
         return {"success": False, "message": "[Mock Output] Gemini API Key missing. If live, I would have compared your Dual Degrees. Result: 'Database Systems' overlaps by 80%. Marking 'Entity-Relationship Models' as mastered in Track B!"}
         
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=generation_config
        )
        prompt = f"""
        The following text contains syllabi from multiple academic tracks a student is undertaking concurrently.
        Compare the tracks, identify overlapping concepts, and create a unified timeline. 
        Clearly indicate which prerequisites or topics can be marked as 'mastered' in one track because they are covered in another, to save redundant effort.
        Format your response in neat Markdown.
        
        Syllabus Text:
        {text[:50000]}
        """
        response = model.generate_content(prompt)
        return {"success": True, "analysis": response.text}
    except Exception as e:
        return {"success": False, "message": f"Error analyzing syllabi: {e}"}

def generate_quiz(files):
    """Sends extracted notes to Gemini to generate a multiple-choice quiz."""
    text = extract_text_from_pdfs(files)
    if not text:
        return {"success": False, "message": "Failed to extract text from PDFs or files are empty."}
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
         return {"success": False, "message": "[Mock Output] Gemini API Key missing. If live, I would have read your notes and generated a 5-question multiple choice quiz testing key concepts."}
         
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=generation_config
        )
        prompt = f"""
        Act as an expert educator. The following text contains a student's study notes.
        Generate a comprehensive, engaging multiple-choice quiz (at least 5 questions) to test their understanding of the core concepts in the notes.
        Provide the questions with 4 options each (A, B, C, D). 
        At the very bottom, in a clearly separated section, provide the Answer Key with brief explanations.
        Format your response in neat Markdown.
        
        Study Notes:
        {text[:50000]}
        """
        response = model.generate_content(prompt)
        return {"success": True, "analysis": response.text} # using "analysis" key to match frontend expectation
    except Exception as e:
        return {"success": False, "message": f"Error generating quiz: {e}"}

def extract_text_from_pyq_files(files):
    """
    Extract text from PYQ uploads:
    - .pdf via PyPDF2
    - Image files (jpg, png, etc.) via pytesseract
    """
    full_text = ""
    for file in files:
        filename = (file.filename or "").lower()
        if filename.endswith(".pdf"):
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
                for page in pdf_reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        full_text += extracted + "\n"
            except Exception as e:
                print(f"Error reading PDF {file.filename}: {e}")
        elif filename.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):
            try:
                img = Image.open(io.BytesIO(file.read()))
                extracted = pytesseract.image_to_string(img)
                if extracted:
                    full_text += extracted + "\n"
            except Exception as e:
                print(f"Error reading Image {file.filename}: {e}")
        else:
            print(f"Unsupported pyq file type: {file.filename}")
    return full_text.strip()

def analyze_pyq_schedule(files, duration_days):
    """Sends extracted PYQ text to Gemini for creating a study schedule."""
    text = extract_text_from_pyq_files(files)
    if not text:
        return {"success": False, "message": "Failed to extract text from PYQs or files are empty."}
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
         return {"success": False, "message": f"[Mock Output] Gemini API Key missing. If live, I would have analyzed your PYQs and generated a personalized {duration_days}-day study and revision schedule focusing on key repeated topics."}
         
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=generation_config
        )
        prompt = f"""
        Act as an expert academic planner and tutor.
        The following text contains previous year questions (PYQs) extracted via OCR from images/PDFs.
        The student has an exam coming up in {duration_days} days.

        TASK:
        1. Identify the most frequently repeating and important topics from these PYQs.
        2. Create a detailed, day-by-day study schedule spreading out these topics over {max(1, int(duration_days) - 2)} days.
        3. Allocate the final 2 days for comprehensive revision of these most important topics.
        4. Format the output in well-structured Markdown (use headings, lists, bold text for emphasis).

        Raw PYQ Text:
        {text[:50000]}
        """
        response = model.generate_content(prompt)
        return {"success": True, "analysis": response.text}
    except Exception as e:
        return {"success": False, "message": f"Error generating PYQ schedule: {e}"}
