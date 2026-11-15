# Beamforming

## Goal

Use the estimated speaker direction to combine microphone signals in a way that emphasizes audio coming from that direction.

## Concept

Each microphone receives the same sound at a slightly different time.

If the signals are shifted to compensate for those differences, the target speaker's signal can reinforce itself when the signals are combined.

```
Mic 1 ──────┐
            │ delay
Mic 2 ──────┤
            │ delay
Mic 3 ──────┤
            │ delay
Mic 4 ──────┘
            │
            ▼
          SUM
            │
            ▼
     Focused Audio
```

## Initial Approach

Start with delay-and-sum beamforming.

The localization algorithm provides the target direction.

The beamformer calculates the required delay for each microphone and combines the signals.

## Input

The beamformer will receive:

```
Microphone signals
+
Microphone positions
+
Target direction
+
Sample rate
```

## Output

The output should be a single processed audio signal with the target direction emphasized.

## Testing

The simulation should contain:

- A target speaker
    
- Optional background noise
    
- Optional secondary sound sources
    

The effectiveness of beamforming can then be measured by comparing:

```
Original signal
vs.
Beamformed signal
```

## Future Improvements

Potential improvements include:

- Better noise suppression
    
- Adaptive beamforming
    
- Multiple target directions
    
- Reverberation compensation
    
- Automatic speaker tracking