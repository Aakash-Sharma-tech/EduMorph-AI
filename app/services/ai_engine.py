import os
import json
import requests
import google.generativeai as genai

# Try to configure with api key if available in env
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

generation_config = {
    "temperature": 0.95,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 100000,
}

system_instruction = """You are a helpful, Socratic AI tutor named EduMorph. 
Guide the student to the answer by asking questions rather than giving direct answers. Encourage critical thinking.
If you notice the student is severely struggling with a fundamental concept, generate a JSON object INSTEAD of a normal response:
{"action": "search_book", "query": "core concept they are struggling with"}
Otherwise, respond normally as the tutor."""

def fetch_open_library_books(query):
    """Fetches books from Open Library API."""
    try:
        url = f"https://openlibrary.org/search.json?q={query}&limit=3"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            books = []
            for doc in data.get('docs', []):
                title = doc.get('title', 'Unknown Title')
                author = doc.get('author_name', ['Unknown Author'])[0]
                books.append(f"{title} by {author}")
            return books
    except Exception as e:
        print(f"Open Library API error: {e}")
    return []

def get_ai_response(user_message, chat_history=None):
    if not api_key:
         return "Mock AI response: Gemini API key not configured. I am the Socratic Tutor! (Please set the GEMINI_API_KEY environment variable to enable full AI features)."
         
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=generation_config,
            system_instruction=system_instruction
        )
        
        history = []
        if chat_history:
            for msg in chat_history:
                role = "user" if msg['role'] == 'user' else "model"
                history.append({"role": role, "parts": [msg['content']]})
                
        chat_session = model.start_chat(history=history)
        response = chat_session.send_message(user_message)
        
        # Check if Gemini decided a book search is needed
        response_text = response.text
        if '{"action": "search_book"' in response_text:
            try:
                # Basic parsing to extract query
                import json
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                json_str = response_text[start_idx:end_idx]
                command = json.loads(json_str)
                
                query = command.get("query", "")
                if query:
                    books = fetch_open_library_books(query)
                    if books:
                        books_str = ", ".join(books)
                        follow_up = f"I silently searched the library for '{query}' and found these free resources: {books_str}. Now, frame a response recommending one of these books to the student to help them understand the concept better, maintaining your Socratic persona."
                        second_response = chat_session.send_message(follow_up)
                        return second_response.text
            except Exception as e:
                print(f"Error parsing JSON action: {e}")
        
        return response.text
    except Exception as e:
        return f"Error communicating with AI: {str(e)}"

def get_code_review(code, language, output, had_error):
    if not api_key:
        return f"[Mock Review] Gemini API Key not configured. If live, I'd suggest reviewing this {language} code for basic algorithmic efficiencies!"
        
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=generation_config
        )
        
        prompt = f"""
        Act as a Senior Software Engineer. The student has written the following {language} code and ran it in a local sandbox.
        Code:
        ```{language.lower()}
        {code}
        ```
        Output/Error:
        ```text
        {output}
        ```
        Did it error? {had_error}
        
        Please provide a concise, constructive code review. Focus primarily on time/space complexity and any clear architectural anti-patterns. Use formatting to make it readable.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error reviewing code: {str(e)}"


def _generate_structured_quiz(prompt: str):
    """
    Helper to call Gemini and parse a strict JSON quiz structure.
    Returns a Python list of question dicts.
    """
    if not api_key:
        # Fallback mock quiz for environments without a real key
        return [
            {
                "question": "Mock Question: What is 2 + 2?",
                "options": ["1", "2", "3", "4"],
                "correct_index": 3,
                "type": "mcq",
                "difficulty": "easy",
                "topic": "arithmetic"
            }
        ]

    def _extract_json_array(text: str):
        cleaned = (text or "").replace("```json", "").replace("```", "").strip()
        # Try direct parse first
        try:
            return json.loads(cleaned)
        except Exception:
            pass
        # Try extracting the outermost JSON array
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        # Fall back to raising the original-ish parse error context
        return json.loads(cleaned)

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=generation_config
        )
        response = model.generate_content(prompt)
        return _extract_json_array(response.text)
    except Exception:
        # Let caller decide fallback behaviour
        raise


def generate_quiz_from_notes(notes_text: str, num_questions: int = 5,
                             difficulty: str = "medium", question_types=None):
    """
    Generate quiz questions from extracted notes text.
    Returns a list[dict] with question objects suitable for storage in Quiz.questions_json.
    """
    if not notes_text:
        raise ValueError("Notes text is empty.")

    question_types = question_types or ["mcq"]
    types_str = ", ".join(question_types)

    prompt = f"""
    You are an expert educator designing an assessment.
    The following text contains teacher notes / study material.

    TASK:
    - Generate exactly {num_questions} quiz questions.
    - Overall difficulty: {difficulty}.
    - Supported question types: {types_str}.
    - For EVERY question, you MUST provide:
        - "question": the question text
        - "type": one of "mcq", "true_false", "short_answer"
        - "options": an array of 2–5 answer choices (for ALL types, including true/false and short_answer)
        - "correct_index": integer index into the options array indicating the best correct answer
        - "topic": short topic label (e.g. "OS Deadlocks basics")
        - "difficulty": easy / medium / hard
        - "explanation": 1–3 sentence explanation of why the correct option is right

    CRITICAL JSON INSTRUCTIONS:
    - Output ONLY valid JSON.
    - The root MUST be an array of question objects.
    - Do NOT include any markdown, backticks, or explanations.

    STUDY NOTES:
    {notes_text[:40000]}
    """

    fallback = []
    for i in range(num_questions):
        fallback.append({
            "question": f"Mock Question {i+1}: Based on the notes, which option best fits the key idea?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_index": 0,
            "type": (question_types[0] if question_types else "mcq"),
            "difficulty": difficulty,
            "topic": "Notes-based quiz"
        })

    try:
        parsed = _generate_structured_quiz(prompt)
    except Exception:
        return fallback

    # Basic validation + normalization
    if not isinstance(parsed, list) or len(parsed) == 0:
        return fallback

    normalized = []
    for q in parsed[:num_questions]:
        if not isinstance(q, dict):
            continue
        options = q.get("options") or []
        if not isinstance(options, list) or len(options) < 2:
            options = ["True", "False"]
        correct_index = q.get("correct_index", 0)
        try:
            correct_index = int(correct_index)
        except Exception:
            correct_index = 0
        if correct_index < 0 or correct_index >= len(options):
            correct_index = 0

        normalized.append({
            "question": q.get("question") or "Untitled question",
            "options": options,
            "correct_index": correct_index,
            "type": q.get("type") or (question_types[0] if question_types else "mcq"),
            "difficulty": (q.get("difficulty") or difficulty),
            "topic": q.get("topic") or "Notes-based quiz",
            "explanation": q.get("explanation") or ""
        })

    return normalized if normalized else fallback


def generate_quiz_from_topic(topic: str, num_questions: int = 5,
                             difficulty: str = "medium", question_types=None):
    """
    Generate quiz questions purely from a topic description.
    """
    if not topic:
        raise ValueError("Topic is required to generate a quiz.")

    question_types = question_types or ["mcq"]
    types_str = ", ".join(question_types)

    prompt = f"""
    You are an expert educator designing a focused quiz.

    TOPIC TO ASSESS:
    "{topic}"

    TASK:
    - Generate exactly {num_questions} quiz questions on this topic.
    - Overall difficulty: {difficulty}.
    - Supported question types: {types_str}.
    - For EVERY question, you MUST provide:
        - "question": the question text
        - "type": one of "mcq", "true_false", "short_answer"
        - "options": an array of 2–5 answer choices (for ALL types, including true/false and short_answer)
        - "correct_index": integer index into the options array indicating the best correct answer
        - "topic": short topic label (e.g. "Deadlock detection")
        - "difficulty": easy / medium / hard
        - "explanation": 1–3 sentence explanation of why the correct option is right

    CRITICAL JSON INSTRUCTIONS:
    - Output ONLY valid JSON.
    - The root MUST be an array of question objects.
    - Do NOT include any markdown, backticks, or explanations.
    """

    fallback = []
    for i in range(num_questions):
        fallback.append({
            "question": f"Mock Question {i+1}: Which statement about '{topic}' is most accurate?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_index": 0,
            "type": (question_types[0] if question_types else "mcq"),
            "difficulty": difficulty,
            "topic": topic
        })

    try:
        parsed = _generate_structured_quiz(prompt)
    except Exception:
        return fallback

    if not isinstance(parsed, list) or len(parsed) == 0:
        return fallback

    normalized = []
    for q in parsed[:num_questions]:
        if not isinstance(q, dict):
            continue
        options = q.get("options") or []
        if not isinstance(options, list) or len(options) < 2:
            options = ["True", "False"]
        correct_index = q.get("correct_index", 0)
        try:
            correct_index = int(correct_index)
        except Exception:
            correct_index = 0
        if correct_index < 0 or correct_index >= len(options):
            correct_index = 0

        normalized.append({
            "question": q.get("question") or "Untitled question",
            "options": options,
            "correct_index": correct_index,
            "type": q.get("type") or (question_types[0] if question_types else "mcq"),
            "difficulty": (q.get("difficulty") or difficulty),
            "topic": q.get("topic") or topic,
            "explanation": q.get("explanation") or ""
        })

    return normalized if normalized else fallback


def generate_study_plan(quiz, result, question_breakdown, teacher_feedback: str = ""):
    """
    Use Gemini to propose a personalized study plan based on:
    - quiz metadata
    - student's score and per-question correctness
    - optional teacher feedback string

    Returns a Python list of recommendation dicts.
    """
    # If no real key, return a minimal mock suggestion
    if not api_key:
        return [
            {
                "topic": "Foundations review",
                "weak_reason": "Using mock engine, cannot inspect real answers.",
                "study_topics": ["Revisit your weakest recent topic", "Review lecture notes slowly"],
                "resources": ["Any introductory textbook or course notes"],
                "practice_questions": ["Try 3–5 textbook end-of-chapter questions."]
            }
        ]

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config=generation_config
    )

    percentage = 0.0
    if result.total_questions:
        percentage = (result.score / result.total_questions) * 100.0

    breakdown_str_lines = []
    for idx, qb in enumerate(question_breakdown):
        status = "CORRECT" if qb.get("was_correct") else "WRONG"
        q_topic = qb.get("topic") or ""
        q_type = qb.get("type") or "mcq"
        chosen = qb.get("chosen_option") or ""
        correct = qb.get("correct_option") or ""
        breakdown_str_lines.append(
            f"Q{idx+1} [{status}] (type={q_type}, topic={q_topic})\n"
            f"Question: {qb.get('question')}\n"
            f"Student answer: {chosen}\n"
            f"Correct answer: {correct}\n"
        )

    breakdown_block = "\n\n".join(breakdown_str_lines)

    prompt = f"""
    You are an AI learning coach creating a personalized study plan.

    QUIZ METADATA:
    - Title: {quiz.title}
    - Topic label: {quiz.topic or "N/A"}
    - Difficulty: {quiz.difficulty or "unspecified"}
    - Total questions: {result.total_questions}
    - Score: {result.score} / {result.total_questions}  (approx. {percentage:.1f}%)

    PER-QUESTION BREAKDOWN:
    {breakdown_block}

    TEACHER FEEDBACK (may be empty):
    {teacher_feedback or "No explicit teacher feedback yet."}

    TASK:
    - Identify the student's weakest concepts or patterns of mistakes.
    - Propose a small number of very concrete, actionable study recommendations.

    OUTPUT FORMAT (JSON ONLY):
    - Return a JSON array.
    - Each element MUST be an object with:
        - "topic": short human-readable topic/skill label
        - "weak_reason": 1–2 sentence explanation of why this is weak
        - "study_topics": array of 2–5 short bullet strings of what to study
        - "resources": array of 0–5 recommended resource descriptions (generic is fine, e.g. "Any OS textbook, deadlocks chapter")
        - "practice_questions": array of 1–5 example practice prompts

    CRITICAL:
    - Output ONLY valid JSON.
    - Do NOT include any markdown, commentary, or backticks.
    """

    response = model.generate_content(prompt)
    raw = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def recommend_youtube_videos_for_topics(weak_topics):
    """
    Use Gemini to recommend YouTube videos for a list of weak topics.
    Input: weak_topics: [{ "topic": "...", "accuracy_pct": 42.1, ... }]
    Output: dict mapping topic -> list of { title, channel, url }.
    """
    if not api_key:
        return {}

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config=generation_config
    )

    topics_list = [wt.get("topic") for wt in weak_topics or [] if wt.get("topic")]
    if not topics_list:
        return {}

    topics_block = "\n".join(f"- {t}" for t in topics_list)

    prompt = f"""
    You are a study coach recommending YouTube learning resources.

    STUDENT WEAK TOPICS:
    {topics_block}

    TASK:
    - For EACH topic above, propose 1–3 high-quality YouTube videos that would help a university student improve.
    - Prefer concise, educational videos (lectures, explainers, not random entertainment).

    OUTPUT FORMAT (JSON ONLY):
    {{
      "topics": [
        {{
          "topic": "Exact topic string from the list",
          "videos": [
            {{
              "title": "Video title",
              "channel": "Channel name",
              "url": "https://www.youtube.com/watch?v=VIDEO_ID"
            }}
          ]
        }}
      ]
    }}

    CRITICAL:
    - Output ONLY valid JSON.
    - Do NOT include any markdown, commentary, or backticks.
    """

    try:
        response = model.generate_content(prompt)
        raw = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        by_topic = {}
        for entry in (data.get("topics") or []):
            t = entry.get("topic")
            vids = entry.get("videos") or []
            if t and isinstance(vids, list):
                cleaned = []
                for v in vids:
                    if not isinstance(v, dict):
                        continue
                    cleaned.append({
                        "title": v.get("title") or "Untitled video",
                        "channel": v.get("channel") or "Unknown channel",
                        "url": v.get("url") or "",
                        "topic": t
                    })
                by_topic[t] = cleaned
        return by_topic
    except Exception:
        return {}
