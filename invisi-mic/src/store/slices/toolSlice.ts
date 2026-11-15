import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export type Tool = "select" | "mic" | "speaker";

interface ToolState {
  activeTool: Tool;
  gridSnap: boolean;
  unlocking: boolean;
}

const initialState: ToolState = {
  activeTool: "select",
  gridSnap: false,
  unlocking: false,
}

export const toolSlice = createSlice({
  name: "tool",
  initialState,
  reducers: {
    setTool: (state, action: PayloadAction<Tool>) => {
      state.activeTool = action.payload;
    },
    setGridSnap: (state, action: PayloadAction<boolean>) => {
      state.gridSnap = action.payload;
    },
    setUnlocking: (state, action: PayloadAction<boolean>) => {
      state.unlocking = action.payload;
    },
  }
})

export const { setTool, setGridSnap, setUnlocking } = toolSlice.actions;
export default toolSlice.reducer;
