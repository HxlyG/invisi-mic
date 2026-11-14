import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export type ViewMode = "2d" | "3d";
export type Unit = "m" | "ft";

interface DimensionState {
  viewMode: ViewMode;
  currentUnit: Unit;
}

const initialState: DimensionState = {
  viewMode: "2d",
  currentUnit: "m",
}

export const dimensionSlice = createSlice({
  name: "dimension",
  initialState,
  reducers: {
    setViewMode: (state, action: PayloadAction<ViewMode>) => {
      state.viewMode = action.payload;
    },
    setUnit: (state, action: PayloadAction<Unit>) => {
      state.currentUnit = action.payload;
    },
  }
})

export const { setViewMode, setUnit } = dimensionSlice.actions;
export default dimensionSlice.reducer;