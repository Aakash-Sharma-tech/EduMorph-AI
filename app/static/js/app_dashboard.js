const { createApp, ref, onMounted, computed, nextTick } = Vue;

const DashboardApp = {
    compilerOptions: { delimiters: ['[[', ']]'] },
    setup() {
        const loading = ref(true);
        const statsData = ref([]);
        const chartInstance = ref(null);
        
        // Quiz & Message properties
        const savedMessages = ref([]);
        const availableQuizzes = ref([]);
        const quizResults = ref([]);
        const studyPlans = ref([]);
        const performance = ref(null);
        const gamification = ref(null);

        const activeQuiz = ref(null);
        const quizAnswers = ref({});
        const timeRemaining = ref(0);
        let timerInterval = null;
        const submittingQuiz = ref(false);

        const quizCode = ref('');
        const quizLookupError = ref('');
        const lookingUpQuiz = ref(false);
        const pendingQuiz = ref(null);

        // Leaderboard State
        const leaderboardData = ref(null);
        const showLeaderboardModal = ref(false);

        // Proctoring State
        const violationCount = ref(0);
        const proctorWarning = ref('');
        const violationLogs = ref([]);
        let faceDetector = null;
        let webcamStream = null;
        let detectionLoopFn = null;
        let lastVideoTime = -1;

        const formatMessage = (text) => {
            return window.marked ? marked.parse(text) : text;
        };
        
        const formatTime = (seconds) => {
            const m = Math.floor(seconds / 60).toString().padStart(2, '0');
            const s = (seconds % 60).toString().padStart(2, '0');
            return `${m}:${s}`;
        };

        const totalScore = computed(() => {
            return statsData.value.reduce((sum, s) => sum + (s.score || 0), 0);
        });

        const topicsCount = computed(() => statsData.value.length);

        const initCharts = () => {
            // Need a slight delay to ensure canvas elements are in the DOM since Vue v-if removal
            setTimeout(() => {
                // Prefer using performance report topic-wise accuracy for the mastery bar chart.
                // Fallback to raw statsData if performance analytics are not yet available.
                let labels = [];
                let scores = [];
                if (performance.value && performance.value.topic_accuracy && performance.value.topic_accuracy.length) {
                    labels = performance.value.topic_accuracy.map(t => t.topic);
                    scores = performance.value.topic_accuracy.map(t => t.accuracy_pct);
                } else {
                    labels = statsData.value.map(s => s.topic);
                    scores = statsData.value.map(s => s.score);
                }

                // Chart defaults for dark mode
                Chart.defaults.color = 'rgba(255, 255, 255, 0.7)';
                Chart.defaults.scale.grid.color = 'rgba(255, 255, 255, 0.1)';

                // Bar Chart
                const barCtx = document.getElementById('barChart');
                if (barCtx) {
                    new Chart(barCtx, {
                        type: 'bar',
                        data: {
                            labels: labels,
                            datasets: [{
                                label: 'Topic Accuracy (%)',
                                data: scores,
                                backgroundColor: 'rgba(99, 102, 241, 0.7)',
                                borderColor: 'rgba(99, 102, 241, 1)',
                                borderWidth: 1,
                                borderRadius: 4
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: { y: { beginAtZero: true, max: 100 } },
                            plugins: {
                                legend: { display: false }
                            }
                        }
                    });
                }

                // Radar Chart
                const radarCtx = document.getElementById('radarChart');
                if (radarCtx) {
                    new Chart(radarCtx, {
                        type: 'radar',
                        data: {
                            labels: labels,
                            datasets: [{
                                label: 'Strength Mapping',
                                data: scores,
                                backgroundColor: 'rgba(139, 92, 246, 0.4)',
                                borderColor: 'rgba(139, 92, 246, 1)',
                                pointBackgroundColor: 'rgba(139, 92, 246, 1)',
                                pointBorderColor: '#fff',
                                pointHoverBackgroundColor: '#fff',
                                pointHoverBorderColor: 'rgba(139, 92, 246, 1)'
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {
                                r: {
                                    angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
                                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                                    pointLabels: { color: 'rgba(255, 255, 255, 0.7)', font: { size: 12 } },
                                    ticks: { display: false, max: 100, beginAtZero: true }
                                }
                            },
                            plugins: {
                                legend: { display: false }
                            }
                        }
                    });
                }
            }, 100);
        };

        const fetchDashboardData = async () => {
             try {
                 const response = await axios.get('/api/dashboard-data');
                 if(response.data.success) {
                     statsData.value = response.data.stats_data; // Assuming stats_data is now part of dashboard-data
                     savedMessages.value = response.data.saved_messages;
                     availableQuizzes.value = response.data.quizzes;
                     quizResults.value = response.data.results || [];
                     studyPlans.value = response.data.study_plans || [];
                     performance.value = response.data.performance || null;
                     gamification.value = response.data.gamification || null;
                     // Re-render charts when richer performance analytics are available
                     initCharts();
                 }
             } catch (error) {
                 console.error("Error fetching dashboard data", error);
             } finally {
                loading.value = false;
            }
        };

        const fetchLeaderboardData = async () => {
            try {
                const response = await axios.get('/api/leaderboard');
                if (response.data.success) {
                    leaderboardData.value = response.data;
                }
            } catch (error) {
                console.error("Error fetching leaderboard data", error);
            }
        };

        const confirmStartQuiz = () => {
            const quiz = pendingQuiz.value;
            if (!quiz) return;
            pendingQuiz.value = null;

            // 1. Force Fullscreen Synchronously with User Gesture
            try {
                if (document.documentElement.requestFullscreen) {
                    document.documentElement.requestFullscreen().catch(e => console.warn(e));
                }
            } catch(e) {
                console.warn("Fullscreen request failed", e);
            }

            activeQuiz.value = quiz;
            quizAnswers.value = {};
            timeRemaining.value = quiz.timer_minutes * 60;
            
            // 2. Reset Proctoring State
            violationCount.value = 0;
            proctorWarning.value = '';
            violationLogs.value = [];
            
            // 3. Attach Fullscreen & Visibility Listeners
            document.addEventListener("visibilitychange", handleVisibilityChange);
            document.addEventListener("fullscreenchange", handleFullscreenChange);

            nextTick(async () => {
                // 4. Init Face Detector if not available
                if (!faceDetector) {
                    try {
                        const vision = await FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm");
                        faceDetector = await FaceDetector.createFromOptions(vision, {
                            baseOptions: {
                                modelAssetPath: "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
                                delegate: "GPU"
                            },
                            runningMode: "VIDEO",
                            minDetectionConfidence: 0.5
                        });
                    } catch(e) {
                        console.error("Failed to load FaceDetector", e);
                    }
                }

                // 5. Start Webcam & Detection Loop
                startWebcamAndDetection();

                if(timerInterval) clearInterval(timerInterval);
                timerInterval = setInterval(() => {
                    timeRemaining.value--;
                    if(timeRemaining.value <= 0) {
                        clearInterval(timerInterval);
                        submitQuiz();
                    }
                }, 1000);
            });
        };

        const enforceViolation = (reason) => {
            if (!activeQuiz.value || submittingQuiz.value) return;
            const logMsg = `[${formatTime(timeRemaining.value)}] ${reason}`;
            violationLogs.value.push(logMsg);
            violationCount.value++;
            
            if (violationCount.value >= 3) {
                proctorWarning.value = "Quiz Terminated: Too many violations.";
                submitQuiz(); // Auto submit on 3rd strike
            }
        };

        const handleVisibilityChange = () => {
            if (document.visibilityState === "hidden") {
                enforceViolation("Suspicious Activity: Exited browser tab or window.");
                proctorWarning.value = "Warning: Tab switching is strictly prohibited!";
                setTimeout(() => proctorWarning.value = '', 4000);
            }
        };

        const handleFullscreenChange = () => {
            if (!document.fullscreenElement) {
                enforceViolation("Suspicious Activity: Exited fullscreen mode.");
                proctorWarning.value = "Warning: You must remain in Fullscreen mode!";
                setTimeout(() => proctorWarning.value = '', 4000);
            }
        };

        const startWebcamAndDetection = async () => {
             // We need to wait a tick for the Vue DOM `<video id="webcam">` to render
             setTimeout(async () => {
                 const videoElement = document.getElementById("webcam");
                 if (!videoElement) return;

                 try {
                     webcamStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
                     videoElement.srcObject = webcamStream;
                 } catch(err) {
                     enforceViolation("Camera Error: Missing or blocked webcam access.");
                     proctorWarning.value = "Camera disabled. Your test is invalid.";
                     return;
                 }

                 videoElement.addEventListener("loadeddata", () => {
                     detectionLoopFn = async () => {
                         if (!activeQuiz.value || !faceDetector) return;
                         let startTimeMs = performance.now();
                         if (videoElement.currentTime !== lastVideoTime) {
                             lastVideoTime = videoElement.currentTime;
                             try {
                                 const detections = faceDetector.detectForVideo(videoElement, startTimeMs).detections;
                                 if (detections.length === 0) {
                                     proctorWarning.value = "No face detected in frame. Please adjust your camera.";
                                     // (Optional) increment violation here if needed, but let's just warn for 0 faces for now
                                 } else if (detections.length > 1) {
                                     proctorWarning.value = "Multiple faces detected. Ensure you are alone.";
                                     // Increment violation every ~few seconds of multiple faces to prevent spam:
                                     // We'll keep it simple for now, relying on the live visual warning
                                 } else {
                                     proctorWarning.value = ""; // Clear warning if 1 face
                                 }
                             } catch(e) {}
                         }
                         if (activeQuiz.value && !submittingQuiz.value) {
                             window.requestAnimationFrame(detectionLoopFn);
                         }
                     };
                     window.requestAnimationFrame(detectionLoopFn);
                 });
             }, 300);
        };

        const stopProctoring = () => {
             // Detach listeners
             document.removeEventListener("visibilitychange", handleVisibilityChange);
             document.removeEventListener("fullscreenchange", handleFullscreenChange);
             
             // Stop Camera
             if (webcamStream) {
                 webcamStream.getTracks().forEach(track => track.stop());
                 webcamStream = null;
             }

             // Exit Fullscreen
             if (document.fullscreenElement) {
                 document.exitFullscreen().catch(err => console.log(err));
             }
        };

        const submitQuiz = async () => {
            if(!activeQuiz.value) return;
            submittingQuiz.value = true;
            clearInterval(timerInterval);
            
            // Halt proctoring services
            stopProctoring();
            
            try {
                const totalTime = activeQuiz.value.timer_minutes * 60;
                const timeTaken = Math.max(0, totalTime - timeRemaining.value);
                const payload = {
                    quiz_id: activeQuiz.value.id,
                    answers: quizAnswers.value,
                    time_taken_seconds: timeTaken,
                    violation_count: violationCount.value,
                    violation_logs: violationLogs.value
                };
                const res = await axios.post('/api/submit-quiz', payload);
                if(res.data.success) {
                    activeQuiz.value = null; // close modal
                    fetchDashboardData(); // refresh lists
                    alert(`Quiz Submitted! You scored ${res.data.score}/${res.data.total}`);
                }
            } catch (err) {
                 alert("Failed to submit quiz.");
            } finally {
                submittingQuiz.value = false;
            }
        };

        const lookupQuizByCode = async () => {
            quizLookupError.value = '';
            const code = (quizCode.value || '').trim();
            if (!code) {
                quizLookupError.value = "Please enter a quiz code.";
                return;
            }
            lookingUpQuiz.value = true;
            try {
                const res = await axios.post('/api/quiz-by-code', { code });
                if (res.data.success) {
                    pendingQuiz.value = res.data.quiz;
                } else {
                    quizLookupError.value = res.data.message || "Could not find a quiz with that code.";
                }
            } catch (err) {
                console.error("Failed to look up quiz by code", err);
                quizLookupError.value = "Unable to validate quiz code. Please try again.";
            } finally {
                lookingUpQuiz.value = false;
            }
        };

        const unstarSavedMessage = async (msg) => {
            try {
                const res = await axios.post('/api/messages/unstar', { id: msg.id });
                if (res.data.success) {
                    savedMessages.value = savedMessages.value.filter((m) => m.id !== msg.id);
                }
            } catch (err) {
                console.error("Unstar error", err);
            }
        };

        onMounted(() => {
            fetchDashboardData();
            fetchLeaderboardData();
        });

        return {
            loading,
            statsData,
            savedMessages,
            availableQuizzes,
            quizResults,
            studyPlans,
            performance,
            gamification,
            activeQuiz,
            quizAnswers,
            timeRemaining,
            submittingQuiz,
            quizCode,
            quizLookupError,
            lookingUpQuiz,
            pendingQuiz,
            leaderboardData,
            showLeaderboardModal,
            violationCount,
            proctorWarning,
            formatMessage,
            formatTime,
            totalScore,
            topicsCount,
            confirmStartQuiz,
            submitQuiz,
            lookupQuizByCode,
            unstarSavedMessage
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('dashboard-app')) {
        createApp(DashboardApp).mount('#dashboard-app');
    }
});
