// JARVIS-Windows - Main entry point
// Uses the ported orb.ts from original JARVIS + Web Speech API

import { createOrb, OrbState } from './orb';

// Types
interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

// Global state
let ws: WebSocket | null = null;
let recognition: SpeechRecognition | null = null;
let isListening = false;
let orb: ReturnType<typeof createOrb> | null = null;
let audioContext: AudioContext | null = null;
let analyser: AnalyserNode | null = null;
let microphoneStream: MediaStream | null = null;

// DOM elements
const statusDot = document.getElementById('statusDot') as HTMLElement;
const statusText = document.getElementById('statusText') as HTMLElement;
const micButton = document.getElementById('micButton') as HTMLButtonElement;
const transcriptEl = document.getElementById('transcript') as HTMLElement;
const canvas = document.getElementById('orbCanvas') as HTMLCanvasElement;

// Initialize orb
function initOrb() {
  orb = createOrb(canvas);
  // Set initial state
  orb.setState('idle');
}

// WebSocket connection
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.hostname}:8340/ws/voice`;
  
  ws = new WebSocket(wsUrl);
  
  ws.onopen = () => {
    updateStatus(true, 'Connected');
    micButton.disabled = false;
    // Initialize audio after connection
    initAudio();
  };
  
  ws.onclose = () => {
    updateStatus(false, 'Disconnected');
    micButton.disabled = true;
    setTimeout(connectWebSocket, 3000);
  };
  
  ws.onerror = (err) => {
    console.error('WebSocket error:', err);
    updateStatus(false, 'Connection error');
  };
  
  ws.onmessage = (event) => {
    try {
      const msg: WebSocketMessage = JSON.parse(event.data);
      handleWebSocketMessage(msg);
    } catch (e) {
      console.error('Failed to parse message:', e);
    }
  };
}

function updateStatus(connected: boolean, text: string) {
  statusDot.classList.toggle('disconnected', !connected);
  statusText.textContent = text;
}

function handleWebSocketMessage(msg: WebSocketMessage) {
  switch (msg.type) {
    case 'output':
      addTranscript('assistant', msg.text);
      orb?.setState('speaking');
      setTimeout(() => orb?.setState('idle'), 1000);
      break;
    case 'tool_use':
      addTranscript('system', `🔧 Using tool: ${msg.tool}`);
      orb?.setState('thinking');
      break;
    case 'tool_result':
      addTranscript('system', `✓ Tool completed`);
      break;
    case 'run_started':
      addTranscript('system', `▶ Run started: ${msg.run_id}`);
      orb?.setState('thinking');
      break;
    case 'run_finished':
      addTranscript('system', `✓ Run finished: ${msg.status}`);
      orb?.setState('idle');
      break;
    case 'error':
      addTranscript('system', `✗ Error: ${msg.error}`);
      orb?.setState('idle');
      break;
    case 'warning':
      addTranscript('system', `⚠ ${msg.message}`);
      break;
    case 'thinking':
      addTranscript('system', `💭 ${msg.message}`);
      orb?.setState('thinking');
      break;
    case 'pong':
      break;
  }
}

// Audio initialization for orb analyser
async function initAudio() {
  try {
    microphoneStream = await navigator.mediaDevices.getUserMedia({ 
      audio: { 
        echoCancellation: true, 
        noiseSuppression: true, 
        autoGainControl: true 
      } 
    });
    
    audioContext = new AudioContext();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.8;
    
    const source = audioContext.createMediaStreamSource(microphoneStream);
    source.connect(analyser);
    
    orb?.setAnalyser(analyser);
  } catch (e) {
    console.warn('Could not initialize audio for orb:', e);
  }
}

// Speech Recognition
function initSpeechRecognition() {
  const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.error('SpeechRecognition not supported');
    statusText.textContent = 'Speech not supported in this browser';
    micButton.disabled = true;
    return;
  }
  
  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-US';
  
  recognition.onstart = () => {
    isListening = true;
    micButton.classList.add('listening');
    statusText.textContent = 'Listening...';
    orb?.setState('listening');
  };
  
  recognition.onend = () => {
    isListening = false;
    micButton.classList.remove('listening');
    if (ws?.readyState === WebSocket.OPEN) {
      statusText.textContent = 'Connected';
    }
    orb?.setState('idle');
  };
  
  recognition.onresult = (event: SpeechRecognitionEvent) => {
    let finalTranscript = '';
    
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) {
        finalTranscript += event.results[i][0].transcript;
      }
    }
    
    if (finalTranscript.trim()) {
      addTranscript('user', finalTranscript);
      sendSpeech(finalTranscript);
    }
  };
  
  recognition.onerror = (event: any) => {
    console.error('Speech recognition error:', event.error);
    if (event.error === 'not-allowed') {
      statusText.textContent = 'Microphone permission denied';
      micButton.disabled = true;
    }
    orb?.setState('idle');
  };
}

function sendSpeech(text: string) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'speech', text }));
    orb?.setState('thinking');
  }
}

function toggleListening() {
  if (!recognition) return;
  
  if (isListening) {
    recognition.stop();
  } else {
    try {
      recognition.start();
    } catch (e) {
      console.error('Failed to start recognition:', e);
    }
  }
}

// Transcript display
function addTranscript(role: 'user' | 'assistant' | 'system', text: string) {
  const entry = document.createElement('div');
  entry.className = 'transcript-entry';
  
  const roleEl = document.createElement('div');
  roleEl.className = 'transcript-role';
  roleEl.textContent = role === 'user' ? 'You' : role === 'assistant' ? 'JARVIS' : 'System';
  
  const textEl = document.createElement('div');
  textEl.className = 'transcript-text';
  textEl.textContent = text;
  
  entry.appendChild(roleEl);
  entry.appendChild(textEl);
  transcriptEl.appendChild(entry);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

// Event listeners
micButton.addEventListener('click', toggleListening);

// Initialize
initOrb();
initSpeechRecognition();
connectWebSocket();

// Handle page visibility
document.addEventListener('visibilitychange', () => {
  if (document.hidden && isListening) {
    recognition?.stop();
  }
});

// Keyboard shortcut: Space to toggle mic
document.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && e.target === document.body) {
    e.preventDefault();
    toggleListening();
  }
});

console.log('JARVIS-Windows frontend loaded with original orb');