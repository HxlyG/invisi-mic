import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

// All lengths are meters. x = across the room, y = depth, z = height above the floor.
export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export interface Room {
  width: number;
  length: number;
  height: number;
}

interface SceneState {
  room: Room;
  speakers: SceneItem[];
  micArrays: SceneItem[];
  selected: ItemRef | null;
  // When on, every mic array shares one focus speaker.
  syncFocus: boolean;
  // Running totals used to generate unique ids and names without randomness.
  counters: Record<ItemKind, number>;
}

export type ItemKind = "speaker" | "micArray";

export interface ItemRef {
  kind: ItemKind;
  id: string;
}

export interface SceneItem {
  id: string;
  name: string;
  position: Vec3;
  // Mic arrays only: speaker to aim at; unset means no focus.
  focusId?: string;
  // Speakers only: preset audio track id; unset means silent.
  trackId?: string;
}

export function focusSpeaker(mic: SceneItem, speakers: SceneItem[]): SceneItem | undefined {
  const selected = mic.focusId ? speakers.find((s) => s.id === mic.focusId) : undefined;
  if (selected) return selected;
  return speakers.reduce<SceneItem | undefined>((closest, speaker) => {
    if (!closest) return speaker;
    const distance = (item: SceneItem) => Math.hypot(
      item.position.x - mic.position.x,
      item.position.y - mic.position.y,
      item.position.z - mic.position.z,
    );
    return distance(speaker) < distance(closest) ? speaker : closest;
  }, undefined);
}

export const DEFAULT_HEIGHT: Record<ItemKind, number> = {
  speaker: 1.6,
  micArray: 2.8,
};

const initialState: SceneState = {
  room: { width: 14, length: 10, height: 4.5 },
  speakers: [{ id: "speaker-1", name: "Speaker 01", position: { x: 7, y: 1.5, z: DEFAULT_HEIGHT.speaker } }],
  micArrays: [{ id: "mic-1", name: "Mic array 01", position: { x: 7, y: 8.5, z: DEFAULT_HEIGHT.micArray }, focusId: "speaker-1" }],
  selected: { kind: "speaker", id: "speaker-1" },
  syncFocus: false,
  counters: { speaker: 1, micArray: 1 },
}

const listFor = (state: SceneState, kind: ItemKind) =>
  kind === "speaker" ? state.speakers : state.micArrays;

export const sceneSlice = createSlice({
  name: "scene",
  initialState,
  reducers: {
    setRoom: (state, action: PayloadAction<Partial<Room>>) => {
      state.room = { ...state.room, ...action.payload };
    },
    addItem: (state, action: PayloadAction<{ kind: ItemKind; x: number; y: number }>) => {
      const { kind, x, y } = action.payload;
      const n = ++state.counters[kind];
      const id = kind === "speaker" ? `speaker-${n}` : `mic-${n}`;
      const label = kind === "speaker" ? "Speaker" : "Mic array";
      listFor(state, kind).push({
        id,
        name: `${label} ${String(n).padStart(2, "0")}`,
        position: { x, y, z: DEFAULT_HEIGHT[kind] },
        ...(kind === "micArray" && state.syncFocus ? { focusId: state.micArrays[0]?.focusId } : {}),
      });
      state.selected = { kind, id };
    },
    updateItem: (state, action: PayloadAction<ItemRef & { patch: Partial<Vec3> }>) => {
      const { kind, id, patch } = action.payload;
      const item = listFor(state, kind).find((i) => i.id === id);
      if (item) item.position = { ...item.position, ...patch };
    },
    setFocus: (state, action: PayloadAction<{ id: string; focusId: string | null }>) => {
      const focusId = action.payload.focusId ?? undefined;
      for (const mic of state.micArrays) {
        if (state.syncFocus || mic.id === action.payload.id) mic.focusId = focusId;
      }
    },
    setTrack: (state, action: PayloadAction<{ id: string; trackId: string | null }>) => {
      const speaker = state.speakers.find((s) => s.id === action.payload.id);
      if (speaker) speaker.trackId = action.payload.trackId ?? undefined;
    },
    setSyncFocus: (state, action: PayloadAction<boolean>) => {
      state.syncFocus = action.payload;
      if (action.payload) {
        const firstMic = state.micArrays[0];
        const shared = firstMic?.focusId ?? (firstMic ? focusSpeaker(firstMic, state.speakers)?.id : undefined);
        for (const mic of state.micArrays) mic.focusId = shared;
      } else {
        for (const mic of state.micArrays) mic.focusId = undefined;
      }
    },
    selectItem: (state, action: PayloadAction<ItemRef | null>) => {
      state.selected = action.payload;
    },
    removeItem: (state, action: PayloadAction<ItemRef>) => {
      const { kind, id } = action.payload;
      const remaining = listFor(state, kind).filter((i) => i.id !== id);
      if (kind === "speaker") state.speakers = remaining;
      else state.micArrays = remaining;
      if (state.selected?.id === id) state.selected = null;
    },
  }
})

export const { setRoom, addItem, updateItem, setFocus, setTrack, setSyncFocus, selectItem, removeItem } = sceneSlice.actions;
export default sceneSlice.reducer;
