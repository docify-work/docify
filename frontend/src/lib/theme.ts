/**
 * Theme: public pages (landing, auth, privacy) are always light; app pages follow the user's choice.
 * The choice lives in localStorage and is applied as `<html data-theme="light|dark">` (see tokens.css).
 * public/theme-init.js applies it before first paint; `useThemeSync` keeps it right while navigating.
 */
import { useCallback, useEffect, useSyncExternalStore } from "react";

export type ThemePref = "light" | "dark" | "system";
const KEY = "docify-theme";
const EVENT = "docify-theme-change";
const APP_PATH = /^\/(app|new|account|w|dev)(\/|$)/;

export function isAppPath(pathname: string): boolean {
  return APP_PATH.test(pathname);
}

function readPref(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "dark" || v === "system" ? v : "light";
  } catch {
    return "light";
  }
}

function systemDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

export function resolveTheme(pref: ThemePref, pathname: string): "light" | "dark" {
  if (!isAppPath(pathname)) return "light";
  return pref === "dark" || (pref === "system" && systemDark()) ? "dark" : "light";
}

export function applyTheme(pathname: string): void {
  document.documentElement.dataset.theme = resolveTheme(readPref(), pathname);
}

function subscribe(cb: () => void): () => void {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb); // other tabs
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

/** Current preference + setter (shared across components, synced across tabs). */
export function useThemePref(): [ThemePref, (p: ThemePref) => void] {
  const pref = useSyncExternalStore(subscribe, readPref, () => "light" as ThemePref);
  const set = useCallback((p: ThemePref) => {
    try {
      localStorage.setItem(KEY, p);
    } catch {
      /* private mode: still apply for this page */
    }
    window.dispatchEvent(new Event(EVENT));
  }, []);
  return [pref, set];
}

/** Re-applies the theme on navigation, preference change and OS theme change. */
export function useThemeSync(pathname: string): void {
  const [pref] = useThemePref();
  useEffect(() => {
    // Smooth colour cross-fade when switching (not on first paint).
    const root = document.documentElement;
    root.classList.add("theme-transition");
    applyTheme(pathname);
    const t = window.setTimeout(() => root.classList.remove("theme-transition"), 300);
    return () => window.clearTimeout(t);
  }, [pathname, pref]);
  useEffect(() => {
    if (pref !== "system" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme(pathname);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [pref, pathname]);
}
