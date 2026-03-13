const { createApp, ref, onMounted, nextTick } = Vue;

const ClassroomApp = {
    compilerOptions: { delimiters: ['[[', ']]'] },
    setup() {
        const userInput = ref('');
        const chatHistory = ref([
            { role: 'model', content: "Hello! I am EduMorph, your personal Socratic tutor. What would you like to learn today?" }
        ]);
        const loading = ref(false);
        const listening = ref(false);
        const recognition = ref(null);
        
        const voiceModeActive = ref(false);
        const voiceState = ref('idle');
        const voiceMuted = ref(false);
        let currentUtterance = null;
        
        // Focus Tracking state
        const isDistracted = ref(false);
        let distractionTimer = null;
        let lastDistractionTrigger = 0;
        let faceLandmarker;

        // Auto-scroll chat to bottom
        const scrollToBottom = async () => {
            await nextTick();
            const container = document.getElementById('chat-container');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        };

        const formatMessage = (text) => {
            // Using marked.js to render markdown responses safely
            if (window.marked) {
                return marked.parse(text);
            }
            return text;
        };

        const triggerAIReengagement = async () => {
            // Only trigger once every 60 seconds max to prevent spam
            if (Date.now() - lastDistractionTrigger < 60000) return;
            lastDistractionTrigger = Date.now();
            
            chatHistory.value.push({ role: 'model', content: "*I noticed you looking away. Taking a quick stretch or getting distracted? Let me ask you a quick question to re-focus!*" });
            scrollToBottom();
            
            try {
                const response = await axios.post('/api/chat', {
                    message: "SYSTEM INSTRUCTION: The user seems distracted or looking away from the screen. Ask a very brief, engaging, interactive question related to what we were just discussing to pull their attention back.",
                    history: chatHistory.value.slice(0, -1)
                });
                if (response.data.success) {
                    chatHistory.value.push({ role: 'model', content: response.data.reply, starred: false });
                    scrollToBottom();
                    if (response.data.gamification) {
                        window.processGamificationResponse(response.data.gamification);
                    }
                }
            } catch (err) {
                console.error("Failed to fetch re-engagement message.", err);
            }
        };

        const starMessage = async (content, index) => {
            const msg = chatHistory.value[index];
            // In-classroom star:
            // - Only adds a star + saves to backend (no unstar here).
            if (msg.starred) return;
            try {
                const res = await axios.post('/api/messages/save', { content: content });
                if (res.data.success) {
                    msg.starred = true;
                }
            } catch (err) {
                console.error("Failed to star message", err);
            }
        };

        const syncStarredFromDashboard = async () => {
            // Ensure chat stars reflect the latest saved explanations
            try {
                const res = await axios.get('/api/dashboard-data');
                if (res.data.success) {
                    const saved = res.data.saved_messages || [];
                    chatHistory.value.forEach((msg) => {
                        if (msg.role === 'model') {
                            msg.starred = saved.some((s) => s.content === msg.content);
                        }
                    });
                }
            } catch (err) {
                console.error("Failed to sync starred messages", err);
            }
        };

        const sendMessage = async () => {
            if (!userInput.value.trim() || loading.value) return;
            if (listening.value) {
                stopSpeech();
            }

            const messageText = userInput.value;
            chatHistory.value.push({ role: 'user', content: messageText });
            userInput.value = '';
            loading.value = true;
            scrollToBottom();

            try {
                // Ensure textareas reset height
                const textarea = document.querySelector('textarea');
                if (textarea) textarea.style.height = 'auto';

                // We want to send historical context to the API except the final user string which we send direct
                const historyContext = chatHistory.value.slice(0, -1);

                const response = await axios.post('/api/chat', {
                    message: messageText,
                    history: historyContext
                });

                if (response.data.success) {
                    chatHistory.value.push({ role: 'model', content: response.data.reply, starred: false });
                    
                    if (voiceModeActive.value) {
                        speakText(response.data.reply);
                    }
                    
                    if (response.data.gamification) {
                        window.processGamificationResponse(response.data.gamification);
                    }
                } else {
                    chatHistory.value.push({ role: 'model', content: "Sorry, I had trouble thinking about that.", starred: false });
                }
            } catch (err) {
                console.error(err);
                chatHistory.value.push({ role: 'model', content: "Network error occurred.", starred: false });
            } finally {
                loading.value = false;
                scrollToBottom();
            }
        };

        // Web Speech API Integration
        const initSpeechRecognition = () => {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (SpeechRecognition) {
                recognition.value = new SpeechRecognition();
                recognition.value.continuous = false;
                recognition.value.interimResults = true;

                let finalTranscript = '';

                recognition.value.onstart = () => {
                    listening.value = true;
                    if(voiceModeActive.value) voiceState.value = 'listening';
                    finalTranscript = userInput.value;
                };

                recognition.value.onresult = (event) => {
                    let interimTranscript = '';
                    for (let i = event.resultIndex; i < event.results.length; ++i) {
                        if (event.results[i].isFinal) {
                            finalTranscript += event.results[i][0].transcript;
                        } else {
                            interimTranscript += event.results[i][0].transcript;
                        }
                    }
                    userInput.value = finalTranscript + interimTranscript;
                };

                recognition.value.onerror = (event) => {
                    console.error('Speech recognition error', event.error);
                    if (voiceModeActive.value && voiceState.value === 'listening') {
                         voiceState.value = 'idle';
                    }
                    stopSpeech();
                };

                recognition.value.onend = () => {
                    listening.value = false;
                    if (voiceModeActive.value && voiceState.value === 'listening') {
                        // User stopped speaking in voice mode
                        if (userInput.value.trim().length > 0) {
                            voiceState.value = 'processing';
                            sendMessage();
                        } else {
                            voiceState.value = 'idle';
                        }
                    } else if (userInput.value.trim().length > 0 && !voiceModeActive.value) {
                        // Normal chat mode
                        sendMessage();
                    }
                };
            } else {
                console.warn('Speech Recognition API not supported in this browser.');
            }
        };

        const stopSpeech = () => {
            listening.value = false;
            if (recognition.value) {
                recognition.value.stop();
            }
        };

        const speakText = (text) => {
            if (!('speechSynthesis' in window)) return;
            const plainText = text.replace(/[*_#]/g, '').trim();
            window.speechSynthesis.cancel();
            
            voiceState.value = 'speaking';
            currentUtterance = new SpeechSynthesisUtterance(plainText);
            
            currentUtterance.onend = () => {
                if (voiceModeActive.value) {
                    voiceState.value = 'idle';
                    if (!voiceMuted.value) {
                        tryStartListening();
                    }
                }
            };
            
            currentUtterance.onerror = (e) => {
                console.error("Speech Synthesis Error", e);
                if (voiceModeActive.value) voiceState.value = 'idle';
            };
            
            const voices = window.speechSynthesis.getVoices();
            const enVoice = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Google') || v.name.includes('Female'))) || voices[0];
            if(enVoice) currentUtterance.voice = enVoice;
            
            window.speechSynthesis.speak(currentUtterance);
        };

        const tryStartListening = () => {
             if (voiceMuted.value) return;
             if (recognition.value) {
                 try { recognition.value.start(); } catch(e) {}
             }
        };

        const startVoiceMode = () => {
            voiceModeActive.value = true;
            voiceMuted.value = false;
            voiceState.value = 'idle';
            if ('speechSynthesis' in window) window.speechSynthesis.getVoices();
            tryStartListening();
        };

        const closeVoiceMode = () => {
            voiceModeActive.value = false;
            stopVoiceAction();
        };

        const toggleVoiceMute = () => {
            voiceMuted.value = !voiceMuted.value;
            if (voiceMuted.value) {
                if (voiceState.value === 'listening') {
                    stopSpeech();
                    voiceState.value = 'idle';
                }
            } else {
                if (voiceState.value === 'idle') {
                    tryStartListening();
                }
            }
        };

        const stopVoiceAction = () => {
            if ('speechSynthesis' in window) window.speechSynthesis.cancel();
            stopSpeech();
            voiceState.value = 'idle';
        };
        
        // --- MediaPipe Local Focus Tracking Setup ---
        const initFocusTracker = async () => {
            if (!window.FilesetResolver || !window.FaceLandmarker) {
                console.warn("MediaPipe Vision not loaded yet.");
                return;
            }
            try {
                const vision = await FilesetResolver.forVisionTasks(
                    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm"
                );
                faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
                    baseOptions: {
                        modelAssetPath: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
                        delegate: "GPU"
                    },
                    outputFaceBlendshapes: true,
                    runningMode: "VIDEO"
                });
                
                startCamera();
            } catch (err) {
                console.error("Failed to init MediaPipe:", err);
            }
        };

        const startCamera = async () => {
            const video = document.getElementById('webcam');
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                    video.srcObject = stream;
                    video.addEventListener("loadeddata", predictWebcam);
                } catch (err) {
                    console.warn("Camera access denied or unavailable.");
                }
            }
        };

        let lastVideoTime = -1;
        const predictWebcam = async () => {
            const video = document.getElementById('webcam');
            const indicator = document.getElementById('focus-indicator');
            
            if (video.currentTime !== lastVideoTime && faceLandmarker) {
                lastVideoTime = video.currentTime;
                const results = faceLandmarker.detectForVideo(video, performance.now());
                
                // Extremely simple "Focus" proxy: if no face is detected, or face is heavily angled
                // (In a real scenario, we'd calculate pitch/yaw from facial landmarks)
                if (!results.faceLandmarks || results.faceLandmarks.length === 0) {
                    isDistracted.value = true;
                    if(indicator) indicator.className = "absolute bottom-1 right-1 w-2 h-2 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]";
                    
                    if (!distractionTimer) {
                        distractionTimer = setTimeout(() => {
                            if (isDistracted.value) {
                                triggerAIReengagement();
                            }
                            distractionTimer = null;
                        }, 5000); // 5 seconds of continuous distraction
                    }
                } else {
                    isDistracted.value = false;
                    if(indicator) indicator.className = "absolute bottom-1 right-1 w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.8)]";
                    if (distractionTimer) {
                        clearTimeout(distractionTimer);
                        distractionTimer = null;
                    }
                }
            }
            window.requestAnimationFrame(predictWebcam);
        };

        onMounted(() => {
            initSpeechRecognition();
            initFocusTracker();
            syncStarredFromDashboard();
        });

        return {
            userInput,
            chatHistory,
            loading,
            listening,
            voiceModeActive,
            voiceState,
            voiceMuted,
            formatMessage,
            sendMessage,
            startVoiceMode,
            closeVoiceMode,
            toggleVoiceMute,
            stopVoiceAction,
            starMessage
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('classroom-app')) {
        createApp(ClassroomApp).mount('#classroom-app');
    }
});
