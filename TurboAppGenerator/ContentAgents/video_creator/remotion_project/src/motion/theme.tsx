import React, { createContext, useContext } from "react";
import { defaultTheme, type Theme } from "./tokens";

const ThemeContext = createContext<Theme>(defaultTheme);

export const ThemeProvider: React.FC<{ theme?: Partial<Theme>; children: React.ReactNode }> = ({
  theme,
  children,
}) => <ThemeContext.Provider value={{ ...defaultTheme, ...theme }}>{children}</ThemeContext.Provider>;

export const useTheme = () => useContext(ThemeContext);
