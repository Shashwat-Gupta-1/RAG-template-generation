"use client";

import React, { createContext, useContext, useState, ReactNode } from "react";

// TabState represents the generic state container for each tab
type TabStateMap = {
  single: Record<string, any>;
  bulk: Record<string, any>;
  agent: Record<string, any>;
};

interface TabStateContextType {
  tabState: TabStateMap;
  setTabState: (tab: keyof TabStateMap, partialState: Record<string, any>) => void;
  resetTabState: (tab: keyof TabStateMap) => void;
}

const TabStateContext = createContext<TabStateContextType | undefined>(undefined);

export function TabStateProvider({ children }: { children: ReactNode }) {
  const [tabState, setTabStateInternal] = useState<TabStateMap>({
    single: {},
    bulk: {},
    agent: {},
  });

  const setTabState = (tab: keyof TabStateMap, partialState: Record<string, any>) => {
    setTabStateInternal((prev) => {
      const oldTabState = prev[tab] || {};
      const newTabState = { ...oldTabState };
      
      for (const key in partialState) {
        if (typeof partialState[key] === 'function') {
          newTabState[key] = partialState[key](oldTabState[key]);
        } else {
          newTabState[key] = partialState[key];
        }
      }

      return {
        ...prev,
        [tab]: newTabState,
      };
    });
  };

  const resetTabState = (tab: keyof TabStateMap) => {
    setTabStateInternal((prev) => ({
      ...prev,
      [tab]: {},
    }));
  };

  return (
    <TabStateContext.Provider value={{ tabState, setTabState, resetTabState }}>
      {children}
    </TabStateContext.Provider>
  );
}

export function useTabState(tab: keyof TabStateMap) {
  const context = useContext(TabStateContext);
  if (!context) {
    throw new Error("useTabState must be used within a TabStateProvider");
  }

  const { tabState, setTabState, resetTabState } = context;

  const updateState = (partialState: Record<string, any>) => {
    setTabState(tab, partialState);
  };

  const resetState = () => {
    resetTabState(tab);
  };

  return {
    state: tabState[tab],
    updateState,
    resetState,
  };
}
