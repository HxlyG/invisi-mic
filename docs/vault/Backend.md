# Backend

## Purpose

The backend processes microphone-array audio and determines where a speaker is located.

The backend should remain independent from the frontend as much as possible.

## Directory Structure

```
backend/
├── .venv/
├── src/
│   ├── __init__.py
│   └── main.py
├── tests/
├── simulation/
└── requirements.txt
```

## Responsibilities

The backend will eventually handle:

1. Audio input
    
2. Audio preprocessing
    
3. Speaker detection
    
4. Time Difference of Arrival (TDOA)
    
5. Direction estimation
    
6. Beamforming
    
7. Communication with the frontend
    

## Development Strategy

The system will initially use simulated microphone signals.

Once the algorithm works reliably in simulation, it can be adapted to real microphone hardware.

## Important Principle

The core audio-processing functions should not depend on the frontend or networking layer.

For example:

```
result = process_audio(microphone_signals)
```

should be possible independently of how the frontend receives the result.

## Current Status

- Python environment
    
- Basic project structure
    
- Microphone simulation
    
- Audio preprocessing
    
- TDOA
    
- Direction estimation
    
- Beamforming
    
- Backend/frontend interface
    
- Real-time processing