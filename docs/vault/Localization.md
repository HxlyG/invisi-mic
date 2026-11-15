# Speaker Localization

## Goal

Determine the direction a speaker is coming from using multiple microphones.

The system should eventually provide an estimated direction and confidence value.

## Microphone Array

The initial simulation will use four microphones arranged in a square.

Example:

```
Mic 0 ───────── Mic 1
  │               │
  │               │
  │               │
Mic 3 ───────── Mic 2
```

Initial microphone positions:

```
Mic 0 = (-0.5,  0.5)
Mic 1 = ( 0.5,  0.5)
Mic 2 = ( 0.5, -0.5)
Mic 3 = (-0.5, -0.5)
```

Units are meters.

## Core Approach

The initial localization algorithm will use Time Difference of Arrival (TDOA).

A sound reaches each microphone at a slightly different time.

These differences can be used to determine the direction of the sound source.

## GCC-PHAT

Generalized Cross-Correlation with Phase Transform (GCC-PHAT) will initially be used to estimate the relative delay between microphone signals.

Conceptually:

```
Mic A ──────┐
            │
            ▼
         GCC-PHAT
            │
Mic B ──────┘
            │
            ▼
       Time Delay
```

## Speed of Sound

The initial simulation will assume:

```
speed of sound ≈ 343 m/s
```

This can later be made configurable.

## Output

The localization system should eventually produce something similar to:

```
Direction: 42.3°
Confidence: 0.91
```

## Testing

The simulation should generate a sound source at a known angle.

The localization algorithm should not receive the angle directly.

Example:

```
Known source angle:      45°
Estimated source angle:  44.2°
Error:                    0.8°
```

## Success Criteria

The system should:

- Correctly estimate direction for a single sound source.
    
- Continue working with moderate noise.
    
- Produce stable results over multiple audio frames.
    
- Operate quickly enough for real-time use.
    

## Future Improvements

Potential future approaches:

- Multiple simultaneous speakers
    
- 3D localization
    
- Reverberation handling
    
- Adaptive filtering
    
- Improved confidence estimation
    
- Real microphone hardware