import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { Point } from "@/lib/roomShape";

export type Tool = "select" | "mic" | "speaker" | "room";

interface ToolState {
  activeTool: Tool;
  // Corners of the room outline being drawn, in meters.
  draft: Point[];
  gridSnap: boolean;
  unlocking: boolean;
  showBeams: boolean;
}

const initialState: ToolState = {
  activeTool: "select",
  draft: [],
  gridSnap: false,
  unlocking: false,
  showBeams: true,
}

export const toolSlice = createSlice({
  name: "tool",
  initialState,
  reducers: {
    setTool: (state, action: PayloadAction<Tool>) => {
      state.activeTool = action.payload;
      state.draft = [];
    },
    addDraftPoint: (state, action: PayloadAction<Point>) => {
      state.draft.push(action.payload);
    },
    popDraftPoint: (state) => {
      state.draft.pop();
    },
    setGridSnap: (state, action: PayloadAction<boolean>) => {
      state.gridSnap = action.payload;
    },
    setUnlocking: (state, action: PayloadAction<boolean>) => {
      state.unlocking = action.payload;
    },
    setShowBeams: (state, action: PayloadAction<boolean>) => {
      state.showBeams = action.payload;
    },
  }
})

export const { setTool, addDraftPoint, popDraftPoint, setGridSnap, setUnlocking, setShowBeams } = toolSlice.actions;
export default toolSlice.reducer;
