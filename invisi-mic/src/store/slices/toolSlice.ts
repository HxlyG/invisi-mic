import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export type Tool = "select" | "mic" | "speaker";

interface ToolState {
  activeTool: Tool;
}

const initialState: ToolState = {
  activeTool: "select",
}

export const toolSlice = createSlice({
  name: "tool",
  initialState,
  reducers: {
    setTool: (state, action: PayloadAction<Tool>) => {
      state.activeTool = action.payload;
    },
  }
})

export const { setTool } = toolSlice.actions;
export default toolSlice.reducer;
