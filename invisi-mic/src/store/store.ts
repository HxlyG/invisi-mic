import { configureStore } from "@reduxjs/toolkit";
import dimensionReducer from "./slices/dimensionSlice";
import sceneReducer from "./slices/sceneSlice";
import toolReducer from "./slices/toolSlice";

export const makeStore = () => {
  return configureStore({
    reducer: {
      dimension: dimensionReducer,
      scene: sceneReducer,
      tool: toolReducer,
    },
  });
};

export type AppStore = ReturnType<typeof makeStore>;
export type RootState = ReturnType<AppStore['getState']>;
export type AppDispatch = AppStore['dispatch'];