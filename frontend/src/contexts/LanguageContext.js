import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import translations from "@/i18n/translations";
import { api } from "@/lib/api";

const LanguageContext = createContext();

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(() => localStorage.getItem("nexus_lang") || "en");
  const isAuthenticated = useRef(false);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  // Expose a way for auth flows to mark authenticated state
  const markAuthenticated = useCallback(() => {
    isAuthenticated.current = true;
  }, []);

  const setLang = useCallback((newLang) => {
    setLangState(newLang);
    localStorage.setItem("nexus_lang", newLang);
    document.documentElement.lang = newLang;
    // Persist to backend (ignore errors silently)
    api.put("/user/language", { language: newLang }).catch(() => {});
  }, []);

  const t = useCallback((key) => {
    const keys = key.split(".");
    let val = translations[lang];
    for (const k of keys) {
      val = val?.[k];
    }
    return val || key;
  }, [lang]);

  return (
    <LanguageContext.Provider value={{ lang, setLang, t, markAuthenticated }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used within LanguageProvider");
  return ctx;
}
