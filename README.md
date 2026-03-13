# EduMorph AI 

## Project Overview
EduMorph AI is a visually immersive, functional educational SaaS platform MVP. It provides an interactive 3D learning environment where an advanced Socratic AI tutor adapts to a student's unique pace and curriculum. 

The application is built using a strict MVC architecture with a Python Flask backend and a modern CSS/JS frontend leveraging Vue.js via CDN, delivering a seamless single-page application feel without complex build steps.

## Technical Stack
* **Backend**: Python 3.9+, Flask, SQLAlchemy (ORM)
* **Database**: SQLite
* **AI Engine**: Google Gemini API (gemini-2.5-flash)
* **Frontend Logic**: Vue.js 3 (via CDN), Axios
* **Styling**: TailwindCSS (via CDN), custom glassmorphism CSS
* **Visuals & Animations**: Three.js, Chart.js, Anime.js
* **Native browser features**: Web Speech API for voice-to-text input, MediaPipe/TensorFlow.js for computer vision
* **Other Tools**: Pyodide (WASM Python execution), PyPDF2, Open Library API

## Application Structure (MVC)
The project follows a standard Model-View-Controller framework:
* **Models** (`app/models.py`): Maps Python classes (`User`, `Topic`, `UserProgress`) to SQLite tables using SQLAlchemy.
* **Views** (`app/templates/`): Jinja2 HTML templates acting as the shells for the Vue.js frontend applications.
* **Controllers** (`app/routes/`): Flask blueprints handling routing logic (`auth.py`, `dashboard.py`, `api.py`).
* **Services** (`app/services/`): Core business logic abstracted from controllers, particularly the AI integration (`ai_engine.py`).

## Core Features and Functionalities

### 1. Interactive 3D Landing Experience
* The landing page (`landing.html`) welcomes users with a "Wow" factor. It implements **Three.js** (`visualizer.js`) to render an animated, interactive 3D icosahedron representing "knowledge" that subtlely reacts to mouse movements. 
* Smooth entrance animations powered by **Anime.js** create a polished, futuristic feel.

### 2. User Authentication
* A dedicated login and signup interface (`login.html`) utilizing Vue.js (`app_auth.js`) for immediate form validation and reactive UI toggling between login/signup states.
* Passwords are securely hashed using `werkzeug.security`.
* Session state is managed across the application using `Flask-Login`.

### 3. Analytical Dashboard
* Upon logging in, students are presented with their learning metrics on the Dashboard (`dashboard.html`).
* The data is fetched dynamically via Axios from the Flask API (`/api/stats`) without reloading the page.
* **Chart.js** renders this data into responsive, interactive visualizations:
  * A Bar Chart displaying overall mastery scores across subjects.
  * A Radar Chart mapping the student's relative strengths to emphasize areas needing improvement.

### 4. Socratic AI Classroom
* The core learning environment (`classroom.html`) features a chat interface powered by **Vue.js** (`app_classroom.js`).
* Messages are sent via Axios to the backend `api/chat` route.
* The backend (`ai_engine.py`) securely communicates with the **Google Gemini API**. The system prompt mandates a "Socratic" tutoring style—guiding students to answers through questioning rather than providing direct solutions.
* Chat history context is automatically managed and sent with each request to maintain conversational coherence.
* Responses containing code or formatted text are parsed safely on the frontend using `marked.js`.

### 5. Voice Interaction (Web Speech API)
* The classroom features native voice-to-text integration utilizing the browser's built-in **Web Speech API**.
* Clicking the microphone icon activates listening mode. The spoken audio is converted to text in real-time and populated into the chat input form.
* The system automatically detects when the user finishes speaking and triggers the submission to the AI tutor, providing a hands-free interactive learning experience.

### 6. Advanced Feature 1: Smart Book Recommender
* Instead of relying purely on its internal weights, if the Gemini System prompt detects extreme struggles with a topic, it outputs a JSON command to the backend.
* The Flask server intercepts this, queries the **Open Library Search API** for the topic, and feeds the resulting free book recommendations back to Gemini.
* Gemini seamlessly incorporates these real-world book titles into its conversational flow.

### 7. Advanced Feature 2, 3 & 4: PDF Synthesizer (Analyze Tab)
* A dedicated `Analyze` dashboard allows users to upload local `.pdf` files.
* **Exam Pattern Analyzer**: Extracts text via `PyPDF2` from multiple past papers and pushes to Gemini's large context window, generating repeating patterns, weightages, and mock questions.
* **Dual-Syllabus Optimizer**: Compares multiple uploaded syllabus PDFs. Gemini identifies overlapping subjects across degrees and instructs the user on which modules they can skip/mark as mastered.
* **PDF to Quiz Generator**: Upload direct class/lecture notes as PDFs and have Gemini automatically generate a comprehensive, interactive multiple-choice quiz with an answer key at the bottom.

### 8. Advanced Feature 5: Smart Book & Video Recommendation Hub
* The former `Sandbox` dashboard has been transformed into a **Books** hub for personalized reading and video recommendations.
* **Search-Based Recommendations**: Students can enter any topic (e.g. "DBMS normalization", "recursion", "networking") and the system queries the **Open Library** API to surface curated books including title, author, cover image, and a short description.
* **Performance-Based Recommendations (Books)**: The backend uses stored quiz attempts (teacher quizzes + self-study Analyze quizzes) to identify weak topics. It then fetches targeted **book suggestions** for those topics, highlighting them in a dedicated "Books for Your Weak Topics" panel.
* **Performance-Based Recommendations (YouTube Videos via Gemini)**: For the same weak topics, the backend calls the Gemini API with a strict JSON prompt to suggest relevant YouTube learning videos (title, channel, and URL) without using the YouTube Data API directly. These links are grouped by topic and rendered as clickable hyperlinks in the UI.
* Recommended titles and "viewed" status are persisted in the DB via the `BookRecommendation` model so the system can avoid re-suggesting the same books and builds a personalized reading history for each student.

### 9. Advanced Feature 6: Local Computer Vision Focus Tracker
* The classroom contains a real-time webcam feed analyzed locally via **Google MediaPipe FaceLandmarker**.
* If the user looks away from the screen for more than 5 seconds continuously, it triggers an event.
* A silent API request is sent to Gemini instructing it to engage the user with a quick interactive quiz based on recent chat history to pull their focus back.
* No video data ever leaves the local browser, ensuring privacy.

### 10. Advanced Feature 7: Role-Based Access Control & Teacher Toolkit
* Added Role-Based Access Control (RBAC) allowing individuals to signup as Teachers.
* Teachers get redirected to a proprietary **Educator Dashboard**.
* **3D Student Topology**: Using Plotly.js, teachers can track global student progress mapped dynamically in real-time across a 3D scatter chart.
* **Global Test Deployment**: Teachers can upload source material PDFs. A strict prompt forces Gemini to spit out perfect JSON Quiz layouts containing questions/answers, which is stored in the DB and globally deployed to all linked student dashboards along with a strict timer.
* **Feedback Loops**: Students execute the quiz inside an automated modal UI. Results are streamed back to the Teacher's Dashboard where they can drop quick personalized feedback onto the student's record.

### 11. Advanced Feature 8: Starred Knowledge Retention
* Within the active AI classroom, a user can "Star" any high-value explanation or message generated from the Gemini AI.
* This POSTs to the backend and saves it persistently to their DB record.
* The Student Dashboard queries these messages and surfaces them in a neat scrollable "Saved Messages" window so they never lose track of a great insight.

## UI/UX Design (Glassmorphism & Dark Mode)
* The entire application incorporates a consistent "Futuristic Education" theme.
* It utilizes a dark mode base via Tailwind utilities (e.g., `bg-gray-900`, `text-white`).
* UI elements (cards, navbars, chat bubbles) overlaying the 3D backgrounds use "Glassmorphism"—achieved through semi-transparent backgrounds and backdrop blur (`backdrop-blur-md`, `bg-white/10`).

## Setup and Running
1. Install dependencies: `pip install -r requirements.txt`
2. Obtain a Gemini API key from Google AI Studio.
3. Set the environment variable: 
   * Windows: `set GEMINI_API_KEY="your_api_key_here"`
   * Mac/Linux: `export GEMINI_API_KEY="your_api_key_here"`
   * Alternatively, create a `.env` file containing `GEMINI_API_KEY=your_api_key_here` in the root folder.
4. Run the application: `python run.py`
5. Open a browser and navigate to `http://127.0.0.1:5000/`

*Note: If no API key is set, the application will provide a mock response in the chat interface to demonstrate the UI flow.*
