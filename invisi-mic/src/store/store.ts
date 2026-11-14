import { configureStore } from "@reduxjs/toolkit";
import dimensionReducer from "./slices/dimensionSlice";

export const makeStore = () => {
  return configureStore({
    reducer: {
      dimension: dimensionReducer,
    },
  });
};

export type AppStore = ReturnType<typeof makeStore>;
export type RootState = ReturnType<AppStore['getState']>;
export type AppDispatch = AppStore['dispatch'];