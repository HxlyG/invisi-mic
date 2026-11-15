# Speaker Amplification — Architecture

## Overview

This project uses an array of microphones to determine the direction a speaker is coming from and selectively amplify audio from that direction.

The system is being developed as a simulation first because the physical microphone array is not currently available.

## System Pipeline

```text
Microphone Array
       ↓
Audio Input
       ↓
Preprocessing
       ↓
Speaker Detection
       ↓
TDOA / GCC-PHAT
       ↓
Direction Estimation
       ↓
Beamforming
       ↓
Processed Audio
       ↓
Frontend
```

## Components

### Frontend

Responsible for:
- User interface
- Visualizing speaker direction
- Receiving processed audio
- Displaying system status

### Backend

Responsible for:
- Receiving microphone signals
- Processing audio
- Estimating speaker direction
- Beamforming / spatial filtering
- Sending processed audio and localization information to the frontend

### Simulation

The simulation will generate multiple microphone signals from a known virtual sound source.

This allows the localization algorithm to be tested before connecting real microphones.

## Data Flow

The backend should expose a simple interface so the frontend does not need to know how the localization algorithm works.

Conceptually:

```text
Microphone Signals
        ↓
Backend
        ↓
{
    direction,
    confidence,
    processed audio
}
        ↓
Frontend
```

## Current Technology

- Python
- NumPy
- SciPy
- Librosa
- Sounddevice
- Matplotlib
- GitHub
- Obsidian
- OpenRouter / Copilot for AI assistance

## Design Goal

Keep audio processing, localization, beamforming, simulation, and networking separated so each component can be developed and tested independently.