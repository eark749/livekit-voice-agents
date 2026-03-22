https://worksh.app/tutorials/livekit-voice-agent/introduction

# The voice pipeline

1. VAD:- voice activity detection it detects speech
    
    ↓
    
2. STT:- speech to text transcribes audio
    
    ↓
    
3. LLM:- generates reply, prompts, planning, tools live here
    
    ↓
    
4. TTS:- text to speech converts the response from the llm to audio

supporting components like background voice cancellation, noise suppresion and end of turn detectors helps a agent behave like a good conversational partner. 

### **Latency expectations**

Humans expect conversational latency under ~500ms. Every component adds delay:

| **Component** | **Best Case** | **Typical** |
| --- | --- | --- |
| VAD | 15–20ms | 20–30ms |
| STT | 200–300ms | 400–600ms |
| LLM | 100–200ms | 500–1000ms |
| TTS | 100–150ms | 200–300ms |
| **Total** | ~415ms | 1.1s–2s |

**Why WebRTC for voice**

1. we can use http/tcp but it sends packets in order if one packet is lost it will wait till the order is retramitted which will cause delay which is called head-of-inline blocking and which we dont want in live speech. 
2. websocket is also an option it is bidirectional and real-time but they still suffer from tcp head-of-inline blocking.

→ best is WebRTC over UDP (unreliable transport) to avoid retransmission delays. it encodes audio using opus codec and adjusts it bitrate depending on network, it also comes with timestamp becuase packet trasmission is not in order so to know which packet to order when so it comes with a timestamp that “I belong to time = 60ms” so receiver knows which chunk to be played and jitter buffer temporarily stores and reorders packet to smooth out n/w delays. 

## VAD vs Semantic turn detection

here vad only sees when the activity is not there and the agent will start is work whereas semantic turn detection sees what is the meaning of the sentence and it thinks “is this feels like a complete thought”.

## Turn detector

1. reduces unwanted interruptions 
2. improves stt accuracy
3. ~20ms latency

## Best practice is to combine turn detector with vad and noise cancellation, language aware paude handling thats why mutli-lingual, which also works with preemtive generation(llm starts planing even if its not clear of eos)

# Voice + Prompt = Personality

1. match phrasing to voice
2. dialect awareness 
3. emotion control
4. keep replies brief

# Every production grade voice agents comes with fallback.

## Key Metrics Overview

1. TTFA — Time to first audio (<1000ms for most responses)
2. TTFT — Time to first token
3. Token usage and cost
4. Interruption rate
5. Fallback activation

Core metrics to monitor:

1. Preemptive generation
2. EOU metrics
3. STT metrics
4. TTFA
5. LLM metrics
6. TTS metrics
7. Usage metrics

## **Metrics You Should Track**

- Time to first LLM token (TTFT)
- User interruption/barge-in rate
- Tool latency and failure rate; fallback activations
- Time to first audio frame (TTFA)
- STT accuracy proxies (e.g., correction requests, intent reversals)

Agent cycles through several stages during a conversation 

1. listening
2. thinking
3. speaking

the agent state change event fires each time agent transistion between these cycles. 

## Preemptive generation

lets llm to start forming response before the user finishes speaking, the agent waits for clear end of term before actualy speaking, but the thinking has already begun. which can lead to faster response (hence 100’s of milisenconds saved off percieved latency for longer user term)

Tradeoffs (but it trades accuracy for speed):

1. mid sentence direction changes 
2. complex multi-part instructions
3. high accuracy domain

## Data retention

1. 30 days retention 
2. automatic deletion after 30 days
3. data stored in us

## Latency optimization

1. stream everything
2. Paralleliza stt - llm - tts
3. keep prompts tight

# Tools and MCP bestpractices

livekit uses @function_tool decoractor  to expose python function as tool to livekit

1. be specific in description
2. keep tools fast (<2s)
3. handle errors with toolerror
4. return meaningful data

if long running tool add await.context.say(something to keep user engaged) and when we dont want user to interrupt during a tool call we can add context.disallow_interruption 

# Production workflow

- collect recording consent
- escalate to humans
- handoff between specialised agent
- preserve context

# Production Flow

- consent task
- triage agent
- specialised agent
- manager escalation
- human handoff
