import React, { useState, useRef, useEffect } from 'react';
import { useEmotion } from '../../context/EmotionContext';
import { checkCrisisKeywords, checkSadWords } from '../../utils/safety';
import { ChatMessage, CBTExercise } from '../../types';
import { CrisisModal } from '../../components/common/CrisisModal';
import { useSpeechRecognition } from '../../hooks/useSpeechRecognition';
import { CrisisAlertModal } from '../../components/modals/CrisisAlertModal';
import { useFaceEmotionDetection } from '../../hooks/useFaceEmotionDetection';

// New Components
import { ChatHeader } from './components/Chat/ChatHeader';
import { MessageList } from './components/Chat/MessageList';
import { ChatInput } from './components/Chat/ChatInput';
import { CommandMenu } from './components/Chat/CommandMenu';
import { VoiceSettingsModal } from './components/Chat/VoiceSettingsModal';
import { GuidedExerciseOverlay } from './components/Chat/GuidedExerciseOverlay';
import { suggestCBTExercise } from '../../utils/cbtLibrary';
import { EmergencySOSModal } from './components/Chat/EmergencySOSModal';
import { API_BASE_URL } from '../../utils/api_config';
import styled from 'styled-components';

export const ChatbotPage: React.FC = () => {
   const { messages, addMessage, setMessages, updateMessage, updateEmotions, sessionId, setSessionId, resetChat, setIsSOSOpen, isTamilMode, setIsTamilMode, setWellnessScore } = useEmotion();
   const [input, setInput] = useState('');
   const [isLoading, setIsLoading] = useState(false);
   const [suggestedExercise, setSuggestedExercise] = useState<CBTExercise | null>(null);
   const [activeExercise, setActiveExercise] = useState<CBTExercise | null>(null);
   const [crisisOpen, setCrisisOpen] = useState(false);
   const [commandMenuOpen, setCommandMenuOpen] = useState(false);
   const [voiceSettingsOpen, setVoiceSettingsOpen] = useState(false);
   const [isVoiceMode, setIsVoiceMode] = useState(false);
   const [isSpeaking, setIsSpeaking] = useState(false);
   const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);
   const [selectedVoiceURI, setSelectedVoiceURI] = useState<string>(localStorage.getItem('preferredVoice') || '');
   const [preferredVoiceEN, setPreferredVoiceEN] = useState<string>(localStorage.getItem('preferredVoice_en') || '');
   const [preferredVoiceTA, setPreferredVoiceTA] = useState<string>(localStorage.getItem('preferredVoice_ta') || '');
   const [speechRate, setSpeechRate] = useState<number>(parseFloat(localStorage.getItem('speechRate') || '1.0'));
   const [speechPitch, setSpeechPitch] = useState<number>(parseFloat(localStorage.getItem('speechPitch') || '1.0'));
   const [crisisData, setCrisisData] = useState<any>(null);
   const [showCrisisModal, setShowCrisisModal] = useState(false);
   const [enableFaceDetection, setEnableFaceDetection] = useState(false);
   const user = JSON.parse(localStorage.getItem('user') || '{}');

   const { isListening, transcript, startListening, stopListening, resetTranscript, hasRecognition } = useSpeechRecognition();
   const { videoRef, isLoading: faceLoading, currentEmotion, shouldTriggerCrisis } = useFaceEmotionDetection(enableFaceDetection);

   // Debug: Log when face detection is enabled
   useEffect(() => {
      console.log('🔄 Face detection enabled state changed:', enableFaceDetection);
   }, [enableFaceDetection]);

   useEffect(() => {
      // Logic: Start with an empty chat as requested (previous chats should not show)
      setMessages([]);
      setSessionId(null);
   }, []);

   useEffect(() => {
      if (transcript) {
         setInput(transcript);
      }
   }, [transcript]);

   useEffect(() => {
      const updateVoices = () => {
         const voices = window.speechSynthesis.getVoices();
         setAvailableVoices(voices);
      };
      updateVoices();
      window.speechSynthesis.onvoiceschanged = updateVoices;
      return () => {
         window.speechSynthesis.onvoiceschanged = null;
      };
   }, []);

   useEffect(() => {
      const handleKeyDown = (e: KeyboardEvent) => {
         if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            setCommandMenuOpen(prev => !prev);
         }
         if ((e.ctrlKey || e.metaKey) && e.key === 'j') {
            e.preventDefault();
            setIsVoiceMode(prev => !prev);
         }
      };
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
   }, []);

   // Monitor face emotions and trigger automatic emergency call after 1 minute
   useEffect(() => {
      if (shouldTriggerCrisis && currentEmotion) {
         // Fetch primary emergency contact and call automatically
         const callEmergencyContact = async () => {
            try {
               const userId = user.user_id || 'guest';
               const response = await fetch(`${API_BASE_URL}/emergency/list/${userId}`);
               const data = await response.json();

               // Find primary contact
               const primaryContact = data.contacts?.find((c: any) => c.is_primary);

               if (primaryContact) {
                  // Show alert before calling
                  const confirmCall = window.confirm(
                     `நீங்க 1 நிமிஷமா வருத்தமா இருக்கீங்க. ${primaryContact.name}-க்கு call பண்ணலாமா?\n\n` +
                     `You've been showing distress for 1 minute. Should I call ${primaryContact.name}?`
                  );

                  if (confirmCall) {
                     // Initiate call
                     window.location.href = `tel:${primaryContact.phone}`;
                  } else {
                     // Show crisis modal instead
                     setCrisisData({
                        severity: 'high',
                        confidence: currentEmotion.confidence,
                        triggers: [currentEmotion.emotion],
                        recommended_actions: ['breathing_exercise', 'helpline_call_suggested'],
                        helpline_numbers: [
                           { name: 'AASRA', number: '+91-9820466726', available: '24/7', languages: ['English', 'Hindi'] },
                           { name: 'Vandrevala Foundation', number: '1860-2662-345', available: '24/7', languages: ['English', 'Tamil', 'Hindi'] },
                           { name: 'iCall', number: '+91-9152987821', available: 'Mon-Sat 8AM-10PM', languages: ['English', 'Hindi'] },
                           { name: 'Sneha India', number: '+91-44-24640050', available: '24/7', languages: ['English', 'Tamil'] }
                        ],
                        message: 'நான் உங்களுக்காக இங்கே இருக்கேன். / I\'m here for you.'
                     });
                     setShowCrisisModal(true);
                  }
               } else {
                  // No primary contact, show crisis modal
                  setCrisisData({
                     severity: 'high',
                     confidence: currentEmotion.confidence,
                     triggers: [currentEmotion.emotion],
                     recommended_actions: ['breathing_exercise', 'helpline_call_suggested'],
                     helpline_numbers: [
                        { name: 'AASRA', number: '+91-9820466726', available: '24/7', languages: ['English', 'Hindi'] },
                        { name: 'Vandrevala Foundation', number: '1860-2662-345', available: '24/7', languages: ['English', 'Tamil', 'Hindi'] },
                        { name: 'iCall', number: '+91-9152987821', available: 'Mon-Sat 8AM-10PM', languages: ['English', 'Hindi'] },
                        { name: 'Sneha India', number: '+91-44-24640050', available: '24/7', languages: ['English', 'Tamil'] }
                     ],
                     message: 'நான் உங்களுக்காக இங்கே இருக்கேன். / I\'m here for you.'
                  });
                  setShowCrisisModal(true);
               }
            } catch (error) {
               console.error('Error fetching emergency contacts:', error);
               // Fallback to crisis modal
               setShowCrisisModal(true);
            }
         };

         callEmergencyContact();
      }
   }, [shouldTriggerCrisis, currentEmotion]);

   useEffect(() => {
      const params = new URLSearchParams(window.location.search);

      if (params.get('voice') === 'true') {
         setIsVoiceMode(true);
         // Clear the param to avoid re-triggering
         const newUrl = window.location.pathname;
         window.history.replaceState({}, '', newUrl);
      }

      if (params.get('checkin') === 'true') {
         // Clear the param to avoid re-triggering on refresh
         window.history.replaceState({}, '', window.location.pathname);

         const firstName = (user.full_name || 'there').split(' ')[0];
         const greetings = [
            `Hi ${firstName}! I just wanted to check in and see how your morning is going. How are you feeling?`,
            `Hello ${firstName}, it's time for our scheduled mindfulness check-in. What's on your mind?`,
            `Hey ${firstName}, I'm here for our daily check-in. How has your day been so far?`
         ];
         const randomGreeting = greetings[Math.floor(Math.random() * greetings.length)];

         const checkinMsg: ChatMessage = {
            id: 'checkin-' + Date.now(),
            role: 'assistant',
            content: randomGreeting,
            timestamp: Date.now()
         };

         setMessages(prev => [...prev, checkinMsg]);
         speak(randomGreeting);
      }
   }, [user.full_name]);

   // Voice Mode Logic
   const speak = (text: string) => {
      if (!window.speechSynthesis) return;
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.onstart = () => setIsSpeaking(true);
      utterance.onend = () => {
         setIsSpeaking(false);
         // Small delay before listening again to avoid hearing own echo
         setTimeout(() => {
            if (isVoiceMode && !isLoading) {
               startListening(isTamilMode ? 'ta-IN' : 'en-US');
            }
         }, 500);
      };
      utterance.onerror = () => setIsSpeaking(false);

      // Voice selection logic
      const voices = window.speechSynthesis.getVoices();
      const preferredURI = isTamilMode ? preferredVoiceTA : preferredVoiceEN;
      let voice = voices.find(v => v.voiceURI === preferredURI);

      if (!voice) {
         // Fallback prioritized selection
         if (isTamilMode) {
            voice = voices.find(v => v.lang.includes('ta') && v.name.includes('Google'))
               || voices.find(v => v.lang.includes('ta'));
         } else {
            // General prioritization: Google/Online first
            const langCode = isTamilMode ? 'ta' : 'en'; // Simple default
            voice = voices.find(v => v.lang.includes(langCode) && (v.name.includes('Google') || v.name.includes('Online')))
               || voices.find(v => v.lang.includes(langCode));
         }
      }

      if (voice) utterance.voice = voice;
      utterance.lang = isTamilMode ? 'ta-IN' : 'en-US';
      utterance.rate = speechRate;
      utterance.pitch = speechPitch;

      window.speechSynthesis.speak(utterance);
   };

   const handleVoiceChange = (uri: string) => {
      setSelectedVoiceURI(uri);
      localStorage.setItem('preferredVoice', uri);

      if (isTamilMode) {
         setPreferredVoiceTA(uri);
         localStorage.setItem('preferredVoice_ta', uri);
      } else {
         setPreferredVoiceEN(uri);
         localStorage.setItem('preferredVoice_en', uri);
      }
   };

   const handleRateChange = (rate: number) => {
      setSpeechRate(rate);
      localStorage.setItem('speechRate', rate.toString());
   };

   const handlePitchChange = (pitch: number) => {
      setSpeechPitch(pitch);
      localStorage.setItem('speechPitch', pitch.toString());
   };

   useEffect(() => {
      if (!isVoiceMode) {
         if (isListening) stopListening();
         window.speechSynthesis?.cancel();
         setIsSpeaking(false);
         return;
      }

      // Only start listening if we're truly idle
      const shouldStartListening = !isSpeaking && !isLoading && !isListening;
      if (shouldStartListening) {
         const timer = setTimeout(() => {
            startListening(isTamilMode ? 'ta-IN' : 'en-US');
         }, 300); // Small delay to prevent race conditions
         return () => clearTimeout(timer);
      }
   }, [isVoiceMode, isTamilMode]);

   // Auto-restart listening if it stops unexpectedly in voice mode
   useEffect(() => {
      if (isVoiceMode && !isListening && !isSpeaking && !isLoading) {
         const timer = setTimeout(() => {
            startListening(isTamilMode ? 'ta-IN' : 'en-US');
         }, 500); // Small delay before restarting
         return () => clearTimeout(timer);
      }
   }, [isListening, isVoiceMode, isSpeaking, isLoading, isTamilMode]);

   // Silence Detection for faster Voice Mode responses
   const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);

   useEffect(() => {
      if (!isVoiceMode || !transcript || isLoading || isSpeaking) {
         if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
         return;
      }

      // Reset timer on every transcript change
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);

      silenceTimerRef.current = setTimeout(() => {
         if (isVoiceMode && transcript && !isLoading && !isSpeaking) {
            console.log("Silence detected, sending message...");
            handleSend(transcript).then(() => {
               resetTranscript();
            });
         }
      }, 1500); // 1.5s silence trigger

      return () => {
         if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      };
   }, [transcript, isVoiceMode, isLoading, isSpeaking]);

   // Auto-send in Voice Mode when transcript is final (as a backup)
   useEffect(() => {
      if (isVoiceMode && transcript && !isListening && !isLoading && !isSpeaking) {
         handleSend(transcript).then(() => {
            resetTranscript();
         });
      }
   }, [isListening, transcript]);

   const handleSend = async (textOverride?: string) => {
      const textToSend = textOverride || input;
      if (!textToSend.trim() || isLoading) return;

      if (isListening) stopListening();

      const userMsg: ChatMessage = {
         id: Date.now().toString(),
         role: 'user',
         content: textToSend,
         timestamp: Date.now(),
         isAudio: isVoiceMode
      };

      addMessage(userMsg);
      setInput('');
      resetTranscript();
      setIsLoading(true);

      // Check for sad words and enable camera for face emotion monitoring
      if (checkSadWords(userMsg.content)) {
         console.log('📹 Camera activated due to sad words detected in message');
         setEnableFaceDetection(true);
      }

      if (checkCrisisKeywords(userMsg.content)) setCrisisOpen(true);

      try {
         const MAX_RETRIES = 2;
         let attempts = 0;
         let response: Response | null = null;
         let lastError: any = null;

         while (attempts <= MAX_RETRIES) {
         try {
            response = await fetch(`${API_BASE_URL}/chat/`, {
               method: 'POST',
               headers: { 'Content-Type': 'application/json' },
               body: JSON.stringify({
                  message: userMsg.content,
                  user_id: user.user_id || 'anonymous',
                  session_id: sessionId,
                  language: isTamilMode ? 'ta' : 'en'
               })
            });
            if (response.ok) break;
            throw new Error(`Server returned ${response.status}`);
         } catch (error) {
            attempts++;
            lastError = error;
            if (attempts <= MAX_RETRIES) {
               console.warn(`Attempt ${attempts} failed. Retrying...`);
               await new Promise(r => setTimeout(r, 1000));
            }
         }
      }

      if (!response || !response.ok) {
         throw lastError || new Error('Failed to get response from backend');
      }

         const data = await response.json();
         const finalResponse = typeof data.response === 'string' ? data.response : data.response?.message || "I'm here for you.";

         // Check for crisis detection
         if (data.crisis_detected && data.crisis_data) {
            setCrisisData(data.crisis_data);
            if (data.crisis_data.severity === 'critical' || data.crisis_data.severity === 'high') {
               // FIRST: Enable camera for face emotion monitoring
               setEnableFaceDetection(true);

               // THEN: Show modal after brief delay to allow camera initialization
               setTimeout(() => {
                  setShowCrisisModal(true);
               }, 1500); // 1.5 second delay for camera to start
            }
         }

         addMessage({
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: finalResponse,
            timestamp: Date.now(),
            isAudio: isVoiceMode
         });

         if (data.session_id) setSessionId(data.session_id);

         if (data.risk_level === 'HIGH' || data.type === 'intervention') {
            setIsSOSOpen(true);
         }

         if (isVoiceMode) {
            speak(finalResponse);
         }

         if (data.metadata?.emotion) {
            updateEmotions(data.metadata.emotion);
            
         }

         if (data.metadata?.wellness_score !== undefined) {
            setWellnessScore(data.metadata.wellness_score);
            localStorage.setItem('wellness_score', data.metadata.wellness_score.toString());
         }

      } catch (error: any) {
         console.error(error);
         addMessage({
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: `I'm having trouble connecting to Healix AI: ${error.message || 'Unknown error'}.`,
            timestamp: Date.now()
         });
      } finally {
         setIsLoading(false);
      }
   };

   const handleNewChat = () => {
      resetChat();
      setSuggestedExercise(null);
   };

   const toggleListening = () => {
      if (isListening) stopListening();
      else startListening(isTamilMode ? 'ta-IN' : 'en-US');
   };

   return (
      <MainContent>
         <CrisisModal isOpen={crisisOpen} onClose={() => setCrisisOpen(false)} />

         {showCrisisModal && crisisData && (
            <CrisisAlertModal
               isOpen={showCrisisModal}
               onClose={() => setShowCrisisModal(false)}
               crisisData={crisisData}
               onStartBreathing={() => {
                  setShowCrisisModal(false);
                  // Start breathing exercise
                  const breathingExercise = suggestCBTExercise({
                     Joy: 0, Trust: 0, Fear: 0.3, Surprise: 0,
                     Sadness: 0.8, Disgust: 0, Anger: 0.2, Anticipation: 0
                  });
                  if (breathingExercise) setActiveExercise(breathingExercise);
               }}
            />
         )}

         <ChatHeader />
         <MessageList messages={messages} isLoading={isLoading} />
         <ChatInput
            input={input}
            setInput={setInput}
            onSend={() => handleSend()}
            isLoading={isLoading}
            isListening={isListening}
            toggleListening={toggleListening}
            isTamilMode={isTamilMode}
            toggleLanguage={() => setIsTamilMode(!isTamilMode)}
            hasRecognition={hasRecognition}
            toggleCommandMenu={() => setCommandMenuOpen(prev => !prev)}
            isVoiceMode={isVoiceMode}
            toggleVoiceMode={() => setIsVoiceMode(!isVoiceMode)}
            isSpeaking={isSpeaking}
            transcript={transcript}
            openVoiceSettings={() => setVoiceSettingsOpen(true)}
         />

         <VoiceSettingsModal
            isOpen={voiceSettingsOpen}
            onClose={() => setVoiceSettingsOpen(false)}
            voices={availableVoices}
            selectedVoiceURI={selectedVoiceURI}
            onVoiceChange={handleVoiceChange}
            rate={speechRate}
            onRateChange={handleRateChange}
            pitch={speechPitch}
            onPitchChange={handlePitchChange}
         />

        

         {activeExercise && (
            <GuidedExerciseOverlay
               exercise={activeExercise}
               onClose={() => setActiveExercise(null)}
               onSpeak={speak}
            />
         )}

         <CommandMenu
            isOpen={commandMenuOpen}
            onClose={() => setCommandMenuOpen(false)}
         />

         {/* Hidden video element for face emotion detection */}
         {enableFaceDetection && (
            <video
               ref={videoRef}
               style={{ display: 'none' }}
               autoPlay
               muted
            />
         )}
      </MainContent>
   );
};

const MainContent = styled.main`
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
  background: #ffffff;
`;

const SuggestionOverlay = styled.div`
  position: absolute;
  bottom: 120px;
  left: 0; right: 0;
  display: flex;
  justify-content: center;
  pointer-events: none;
`;

const SuggestionCard = styled.div`
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 20px;
  padding: 20px 24px;
  width: 90%;
  max-width: 500px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
  pointer-events: auto;
  animation: slideInUp 0.4s cubic-bezier(0.16, 1, 0.3, 1);

  @keyframes slideInUp {
    from { transform: translateY(20px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
  }
`;

const SuggestionText = styled.div`
  strong { color: #818cf8; display: block; margin-bottom: 4px; }
  p { margin: 0; color: #aaa; font-size: 0.9rem; line-height: 1.4; }
`;

const SuggestionActions = styled.div`
  display: flex;
  gap: 12px;
`;

const SuggestionButton = styled.button<{ $primary?: boolean }>`
  flex: 1;
  background: ${props => props.$primary ? '#4f46e5' : '#2a2a2a'};
  color: #111827;
  border: none;
  padding: 10px;
  border-radius: 12px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  &:hover { background: ${props => props.$primary ? '#6366f1' : '#333'}; }
`;
