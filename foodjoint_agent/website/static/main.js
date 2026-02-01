const statusEl = document.getElementById("connectionStatus");
const statusTextEl = document.getElementById("connectionText");
const toggleBtn = document.getElementById("toggleSession");
const micWrapper = document.getElementById("micWrapper");
const transcriptLog = document.getElementById("transcriptLog");
const transcriptIndicator = document.getElementById("transcriptIndicator");
const ICON_IDLE = '<span class="material-symbols-rounded mic-icon">mic</span>';
const ICON_CONNECTING =
  '<span class="material-symbols-rounded mic-icon spinner">progress_activity</span>';
const ICON_ACTIVE = '<span class="material-symbols-rounded mic-icon">equalizer</span>';

let socket = null;
let connecting = false;
let micStream = null;
let inputContext = null;
let inputProcessor = null;
let outputContext = null;
let outputProcessor = null;
const playbackQueue = [];
let playbackOffset = 0;
const INPUT_SAMPLE_RATE = 16000;
const OUTPUT_SAMPLE_RATE = 24000;
let inputSampleRate = INPUT_SAMPLE_RATE;
let outputSampleRate = OUTPUT_SAMPLE_RATE;
const VAD_THRESHOLD = 0.005;
const VAD_SILENCE_MS = 500;
const VAD_MIN_SPEECH_MS = 150;
const VAD_MAX_SPEECH_MS = 12000;
const VAD_NOISE_FLOOR_WINDOW = 8;
const VAD_NOISE_FLOOR_MIN_SAMPLES = 4;
const VAD_NOISE_FLOOR_MULTIPLIER = 2.5;
const VAD_NOISE_FLOOR_OFFSET = 0.0008;
const VAD_START_OFFSET = 0.001;
const VAD_RELEASE_MULTIPLIER = 0.6;
const BARGE_IN_RMS = 0.02;
const BARGE_IN_MIN_MS = 220;
let vadActive = false;
let vadSilenceMs = 0;
let vadSpeechMs = 0;
let vadActivityMs = 0;
let vadSignalSent = false;
let noiseFloor = 0;
let noiseFloorSamples = [];
let bargeInAccumMs = 0;

const liveRows = {
  user: null,
  assistant: null,
};
const transcriptState = {
  user: { text: "", lastFinal: "" },
  assistant: { text: "", lastFinal: "" },
  seenFinalIds: new Set(),
};

const setTranscriptEmpty = () => {
  if (!transcriptLog) return;
  transcriptLog.innerHTML = "";
  const empty = document.createElement("div");
  empty.className = "chat-empty";
  empty.innerHTML = `
  <div class="chat-empty-text">🎤 Start speaking to see the transcript</div>
  <div class="chat-empty-hint">Mic listens automatically</div>
`;
  transcriptLog.appendChild(empty);
  showTranscriptIndicator(false);
};

const ensureTranscriptReady = () => {
  if (!transcriptLog) return;
  const empty = transcriptLog.querySelector(".chat-empty");
  if (empty) {
    empty.remove();
    showTranscriptIndicator(true);
  }
};

const createTranscriptRow = (role) => {
  if (!transcriptLog) return null;
  ensureTranscriptReady();
  const row = document.createElement("div");
  row.className = `message ${role}`;

  const textEl = document.createElement("div");
  textEl.className = "message-text";

  row.appendChild(textEl);
  transcriptLog.appendChild(row);
  return row;
};

const writeTranscript = (role, text, isFinal, mode = "append") => {
  if (!text || !transcriptLog) {
    if (isFinal) liveRows[role] = null;
    return;
  }
  let row = liveRows[role];
  if (!row) {
    row = createTranscriptRow(role);
    if (!row) return;
    liveRows[role] = row;
  }

  const textEl = row.querySelector(".message-text");
  if (!textEl) {
    // Fallback: set text directly on row
    if (mode === "replace") {
      row.textContent = text;
    } else {
      row.textContent = text;
    }
  } else {
    if (mode === "replace") {
      textEl.textContent = text;
    } else if (isFinal && textEl.textContent && text.startsWith(textEl.textContent)) {
      textEl.textContent = text;
    } else {
      textEl.textContent += text;
    }
  }

  if (isFinal) {
    liveRows[role] = null;
  }
  transcriptLog.scrollTop = transcriptLog.scrollHeight;
};

const normalizeText = (text) => text.replace(/\s+/g, " ").trim();

const applyTranscript = (role, text, opts) => {
  if (!text) return;
  const state = transcriptState[role];
  const normalized = normalizeText(text);
  if (!normalized) return;

  if (opts.isFinal) {
    if (opts.id && transcriptState.seenFinalIds.has(opts.id)) return;
    if (normalizeText(state.lastFinal) === normalized) return;
    writeTranscript(role, text, true, "replace");
    state.text = "";
    state.lastFinal = text;
    if (opts.id) transcriptState.seenFinalIds.add(opts.id);
    return;
  }

  if (opts.isDelta) {
    const current = state.text || "";
    if (current.endsWith(text)) return;
    state.text = current + text;
    writeTranscript(role, state.text, false, "replace");
    return;
  }

  if (normalized === normalizeText(state.text)) return;
  state.text = text;
  writeTranscript(role, state.text, false, "replace");
};

const setStatus = (text) => {
  if (statusTextEl) {
    statusTextEl.textContent = text;
  }
};

const setMicActive = (active) => {
  if (toggleBtn) {
    if (active) {
      toggleBtn.classList.add("active");
      if (micWrapper) micWrapper.classList.add("active");
      if (statusEl) statusEl.classList.add("listening");
    } else {
      toggleBtn.classList.remove("active");
      if (micWrapper) micWrapper.classList.remove("active");
      if (statusEl) statusEl.classList.remove("listening");
    }
  }
};

const showTranscriptIndicator = (show) => {
  if (transcriptIndicator) {
    if (show) {
      transcriptIndicator.classList.add("live");
    } else {
      transcriptIndicator.classList.remove("live");
    }
  }
};

const stopAudio = () => {
  if (inputProcessor) {
    inputProcessor.disconnect();
    inputProcessor.onaudioprocess = null;
    inputProcessor = null;
  }
  if (inputContext) {
    inputContext.close();
    inputContext = null;
  }
  if (micStream) {
    micStream.getTracks().forEach((track) => track.stop());
    micStream = null;
  }
  if (outputProcessor) {
    outputProcessor.disconnect();
    outputProcessor.onaudioprocess = null;
    outputProcessor = null;
  }
  if (outputContext) {
    outputContext.close();
    outputContext = null;
  }
  playbackQueue.length = 0;
  playbackOffset = 0;
  vadActive = false;
  vadSilenceMs = 0;
  vadSpeechMs = 0;
  vadActivityMs = 0;
  vadSignalSent = false;
  noiseFloor = 0;
  noiseFloorSamples = [];
};

const floatTo16BitPCM = (input) => {
  const buffer = new ArrayBuffer(input.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < input.length; i += 1) {
    let sample = Math.max(-1, Math.min(1, input[i]));
    sample = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    view.setInt16(i * 2, sample, true);
  }
  return buffer;
};

const floatToInt16 = (input) => {
  const output = new Int16Array(input.length);
  for (let i = 0; i < input.length; i += 1) {
    let sample = Math.max(-1, Math.min(1, input[i]));
    sample = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    output[i] = sample;
  }
  return output;
};

const int16ToFloat32 = (input) => {
  const output = new Float32Array(input.length);
  for (let i = 0; i < input.length; i += 1) {
    output[i] = input[i] / 32768;
  }
  return output;
};

const resampleBuffer = (input, inputRate, outputRate) => {
  if (inputRate === outputRate) return input;
  const ratio = inputRate / outputRate;
  const newLength = Math.max(1, Math.round(input.length / ratio));
  const output = new Float32Array(newLength);
  for (let i = 0; i < newLength; i += 1) {
    const position = i * ratio;
    const left = Math.floor(position);
    const right = Math.min(left + 1, input.length - 1);
    const fraction = position - left;
    output[i] = input[left] + (input[right] - input[left]) * fraction;
  }
  return output;
};

const enqueuePlayback = (buffer) => {
  if (!(buffer instanceof ArrayBuffer)) return;
  let chunk = new Int16Array(buffer);
  if (outputSampleRate !== OUTPUT_SAMPLE_RATE) {
    const floatChunk = int16ToFloat32(chunk);
    const resampled = resampleBuffer(floatChunk, OUTPUT_SAMPLE_RATE, outputSampleRate);
    chunk = floatToInt16(resampled);
  }
  if (chunk.length > 0) {
    playbackQueue.push(chunk);
    if (playbackQueue.length === 1) {
      setStatus("Speaking...");
    }
  }
};

const ensureOutputAudio = async () => {
  if (outputContext) return;
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  outputContext = new AudioCtx({ sampleRate: OUTPUT_SAMPLE_RATE });
  outputSampleRate = outputContext.sampleRate;
  console.log(`[audio] Output audio context created (sample rate: ${outputSampleRate}Hz)`);

  outputProcessor = outputContext.createScriptProcessor(2048, 1, 1);
  let wasPlaying = false;
  outputProcessor.onaudioprocess = (event) => {
    const output = event.outputBuffer.getChannelData(0);
    let outIndex = 0;
    const isPlaying = playbackQueue.length > 0;

    while (outIndex < output.length) {
      if (!playbackQueue.length) {
        output[outIndex] = 0;
        outIndex += 1;
        continue;
      }
      const current = playbackQueue[0];
      while (outIndex < output.length && playbackOffset < current.length) {
        output[outIndex] = current[playbackOffset] / 32768;
        playbackOffset += 1;
        outIndex += 1;
      }
      if (playbackOffset >= current.length) {
        playbackQueue.shift();
        playbackOffset = 0;
      }
    }

    if (wasPlaying && !playbackQueue.length) {
      setStatus("Listening...");
    }
    wasPlaying = isPlaying;
  };
  outputProcessor.connect(outputContext.destination);

  try {
    await outputContext.resume();
    console.log(`[audio] Output audio context resumed`);
  } catch (err) {
    console.error("Failed to resume output audio context:", err);
    throw err;
  }
};

const startMicrophone = async () => {
  micStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true
    }
  });
  console.log("[mic] Microphone access granted");

  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  inputContext = new AudioCtx({ sampleRate: INPUT_SAMPLE_RATE });
  inputSampleRate = inputContext.sampleRate;
  console.log(`[audio] Input audio context created (sample rate: ${inputSampleRate}Hz)`);

  const source = inputContext.createMediaStreamSource(micStream);
  const silentGain = inputContext.createGain();
  silentGain.gain.value = 0;
  inputProcessor = inputContext.createScriptProcessor(2048, 1, 1);

  let audioPacketCount = 0;
  let lastLogTime = Date.now();

  inputProcessor.onaudioprocess = (event) => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }

    const input = event.inputBuffer.getChannelData(0);
    const frameMs = (input.length / inputSampleRate) * 1000;

    let energy = 0;
    for (let i = 0; i < input.length; i += 1) {
      energy += input[i] * input[i];
    }
    const rms = Math.sqrt(energy / input.length);
    if (!vadActive) {
      noiseFloorSamples.push(rms);
      if (noiseFloorSamples.length > VAD_NOISE_FLOOR_WINDOW) {
        noiseFloorSamples.shift();
      }
      if (noiseFloorSamples.length >= VAD_NOISE_FLOOR_MIN_SAMPLES) {
        const sorted = [...noiseFloorSamples].sort((a, b) => a - b);
        const index = Math.floor(sorted.length * 0.2);
        noiseFloor = sorted[index] ?? noiseFloor;
      }
    }

    const adaptiveThreshold = Math.max(
      VAD_THRESHOLD,
      noiseFloor * VAD_NOISE_FLOOR_MULTIPLIER + VAD_NOISE_FLOOR_OFFSET
    );
    const releaseThreshold = Math.max(
      VAD_THRESHOLD * VAD_RELEASE_MULTIPLIER,
      noiseFloor * VAD_NOISE_FLOOR_MULTIPLIER * VAD_RELEASE_MULTIPLIER + VAD_NOISE_FLOOR_OFFSET
    );
    const startThreshold = adaptiveThreshold + VAD_START_OFFSET;

    if (playbackQueue.length) {
      if (rms >= Math.max(BARGE_IN_RMS, startThreshold)) {
        bargeInAccumMs += frameMs;
        if (bargeInAccumMs >= BARGE_IN_MIN_MS) {
          playbackQueue.length = 0;
          playbackOffset = 0;
          bargeInAccumMs = 0;
          setStatus("Listening...");
        }
      } else {
        bargeInAccumMs = 0;
      }
    } else {
      bargeInAccumMs = 0;
    }

    const now = Date.now();
    if (now - lastLogTime > 3000) {
      const vadStatus = vadActive ? (vadSignalSent ? 'ACTIVE' : 'DETECTING') : 'IDLE';
      console.log(`[${vadStatus}] RMS: ${rms.toFixed(6)}, threshold: ${adaptiveThreshold.toFixed(6)}`);
      lastLogTime = now;
      audioPacketCount = 0;
    }

    const aboveThreshold = vadActive ? rms >= adaptiveThreshold : rms >= startThreshold;

    if (aboveThreshold) {
      if (!vadActive) {
        vadActive = true;
        vadSpeechMs = 0;
        vadActivityMs = frameMs;
        vadSignalSent = false;
        console.log("[vad] Detecting voice");
      } else {
        vadActivityMs += frameMs;
      }

      vadSpeechMs += frameMs;

      if (!vadSignalSent && vadSpeechMs >= VAD_MIN_SPEECH_MS) {
        console.log("[vad] Voice confirmed");
        setStatus("Listening...");
        setMicActive(true);
        try {
          socket.send(JSON.stringify({ type: "vad", state: "start" }));
          vadSignalSent = true;
        } catch (err) {
          console.error("Failed to send VAD start:", err);
        }
      }

      vadSilenceMs = 0;
    } else if (vadActive) {
      vadActivityMs += frameMs;
      if (rms < releaseThreshold) {
        vadSilenceMs += frameMs;
      } else {
        vadSilenceMs = 0;
      }
      if (vadSignalSent && vadActivityMs >= VAD_MAX_SPEECH_MS) {
        console.warn("VAD safety stop");
        setStatus("Listening...");
        setMicActive(false);
        try {
          socket.send(JSON.stringify({ type: "vad", state: "end" }));
        } catch (err) {
          console.error("Failed to send VAD end:", err);
        }
        vadActive = false;
        vadSilenceMs = 0;
        vadSpeechMs = 0;
        vadActivityMs = 0;
        vadSignalSent = false;
        return;
      }
      if (vadSilenceMs >= VAD_SILENCE_MS) {
        if (vadSignalSent) {
          console.log("[vad] Voice ended");
          setStatus("Listening...");
          setMicActive(false);
          try {
            socket.send(JSON.stringify({ type: "vad", state: "end" }));
          } catch (err) {
            console.error("Failed to send VAD end:", err);
          }
        }
        vadActive = false;
        vadSilenceMs = 0;
        vadSpeechMs = 0;
        vadActivityMs = 0;
        vadSignalSent = false;
      }
    }

    const resampled =
      inputSampleRate === INPUT_SAMPLE_RATE
        ? input
        : resampleBuffer(input, inputSampleRate, INPUT_SAMPLE_RATE);
    const pcm = floatTo16BitPCM(resampled);

    try {
      socket.send(pcm);
      audioPacketCount++;
    } catch (err) {
      console.error("Failed to send audio:", err);
    }
  };

  source.connect(inputProcessor);
  inputProcessor.connect(silentGain);
  silentGain.connect(inputContext.destination);

  if (inputContext.state === 'suspended') {
    console.log("Resuming suspended audio context...");
  }
  await inputContext.resume();
  console.log(`[audio] Audio context state: ${inputContext.state}`);
};

const handleServerEvent = (payload) => {
  if (!payload || typeof payload !== "object") return;
  if (payload.type === "transcript") {
    applyTranscript(payload.role || "assistant", payload.text || "", {
      isFinal: payload.final !== false,
      isDelta: payload.final === false,
      id: payload.id || null,
    });
    return;
  }
  if (payload.type === "status") {
    if (payload.state === "ready") {
      setStatus("Listening...");
    }
    return;
  }
  if (payload.type === "error") {
    setStatus(payload.message || "Error occurred");
  }
};

const disconnect = () => {
  if (socket) {
    socket.onopen = null;
    socket.onmessage = null;
    socket.onclose = null;
    socket.onerror = null;
    socket.close();
  }
  socket = null;
  connecting = false;
  stopAudio();
  liveRows.user = null;
  liveRows.assistant = null;
  transcriptState.user.text = "";
  transcriptState.user.lastFinal = "";
  transcriptState.assistant.text = "";
  transcriptState.assistant.lastFinal = "";
  transcriptState.seenFinalIds.clear();
  setTranscriptEmpty();
  setStatus("Tap to start ordering");
  setMicActive(false);
  toggleBtn.innerHTML = ICON_IDLE;
  toggleBtn.disabled = false;
};

const connect = async () => {
  if (connecting || socket) return;
  connecting = true;
  setStatus("Connecting...");
  toggleBtn.innerHTML = ICON_CONNECTING;
  toggleBtn.disabled = true;

  try {
    setTranscriptEmpty();
    await ensureOutputAudio();
    await startMicrophone();
  } catch (err) {
    console.error("Failed to start audio", err);
    setStatus("Microphone error. Tap to retry.");
    stopAudio();
    toggleBtn.innerHTML = ICON_IDLE;
    toggleBtn.disabled = false;
    connecting = false;
    return;
  }

  try {
    console.log(`Connecting to WebSocket: ${socketUrl}`);
    socket = new WebSocket(socketUrl);
    socket.binaryType = "arraybuffer";

    socket.onopen = () => {
      console.log("[ws] WebSocket connected");
      setStatus("Listening...");
      showTranscriptIndicator(true);
      toggleBtn.innerHTML = ICON_ACTIVE;
      toggleBtn.classList.add("active");
      if (micWrapper) micWrapper.classList.add("active");
      toggleBtn.disabled = false;
      connecting = false;
    };

    socket.onmessage = async (event) => {
      if (typeof event.data === "string") {
        try {
          const payload = JSON.parse(event.data);
          handleServerEvent(payload);
        } catch (err) {
          console.warn("Unable to parse server event", err);
        }
        return;
      }
      let audioBuffer = event.data;
      if (event.data instanceof Blob) {
        try {
          audioBuffer = await event.data.arrayBuffer();
        } catch (err) {
          console.error("Failed to convert Blob to ArrayBuffer:", err);
          return;
        }
      }
      if (audioBuffer && audioBuffer.byteLength > 0) {
        enqueuePlayback(audioBuffer);
      }
    };

    socket.onerror = (err) => {
      console.error("WebSocket error:", err);
      disconnect();
      setStatus("Connection error. Tap to retry.");
    };

    socket.onclose = (event) => {
      console.log(`WebSocket closed (code: ${event.code})`);
      if (event.reason) {
        console.log(`WebSocket close reason: ${event.reason}`);
      }

      if (event.code === 1006) {
        setStatus("Connection lost. Tap to reconnect.");
      } else if (event.code === 1011) {
        setStatus("Server error. Tap to retry.");
      } else if (event.code === 1013) {
        setStatus("Server busy. Try again later.");
      }

      if (socket) disconnect();
    };
  } catch (err) {
    console.error("Failed to connect", err);
    setStatus("Connection failed. Tap to retry.");
    stopAudio();
    socket = null;
    toggleBtn.innerHTML = ICON_IDLE;
    toggleBtn.disabled = false;
    connecting = false;
  }
};

toggleBtn.addEventListener("click", () => {
  if (socket) {
    disconnect();
  } else {
    connect();
  }
});

window.addEventListener("beforeunload", () => disconnect());

setTranscriptEmpty();
