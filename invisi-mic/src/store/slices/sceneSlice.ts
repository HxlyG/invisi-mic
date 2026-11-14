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
}

export const DEFAULT_HEIGHT: Record<ItemKind, number> = {
  speaker: 1.6,
  micArray: 2.8,
};

const initialState: SceneState = {
  room: { width: 14, length: 10, height: 4.5 },
  speakers: [{ id: "speaker-1", name: "Speaker 01", position: { x: 7, y: 1.5, z: DEFAULT_HEIGHT.speaker } }],
  micArrays: [{ id: "mic-1", name: "Mic array 01", position: { x: 7, y: 8.5, z: DEFAULT_HEIGHT.micArray } }],
  selected: { kind: "speaker", id: "speaker-1" },
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
      });
      state.selected = { kind, id };
    },
    updateItem: (state, action: PayloadAction<ItemRef & { patch: Partial<Vec3> }>) => {
      const { kind, id, patch } = action.payload;
      const item = listFor(state, kind).find((i) => i.id === id);
      if (item) item.position = { ...item.position, ...patch };
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

export const { setRoom, addItem, updateItem, selectItem, removeItem } = sceneSlice.actions;
export default sceneSlice.reducer;
