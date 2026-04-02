import { useEffect, useRef, useState } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { Globe, ChevronDown } from "lucide-react";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
  { code: "zh", label: "中文" },
  { code: "hi", label: "हिन्दी" },
  { code: "ar", label: "العربية" },
  { code: "fr", label: "Français" },
  { code: "pt", label: "Português" },
  { code: "ru", label: "Русский" },
  { code: "ja", label: "日本語" },
  { code: "de", label: "Deutsch" },
];

export function LanguageToggle({ variant = "default" }) {
  const { lang, setLang } = useLanguage();
  const current = LANGUAGES.find(l => l.code === lang) || LANGUAGES[0];
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    const onClick = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const compact = variant === "compact";

  return (
    <div className="relative" data-testid="language-toggle" ref={rootRef}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5"
        data-testid="language-select"
      >
        <Globe className="w-3.5 h-3.5 text-zinc-500" />
        <span className={compact ? "text-xs text-zinc-400 hover:text-zinc-200" : "text-sm text-zinc-300 hover:text-zinc-100"}>{current.label}</span>
        <ChevronDown className="w-3 h-3 text-zinc-500" />
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-2 min-w-[150px] rounded-lg border border-zinc-800 bg-zinc-900 p-1 shadow-xl z-50" data-testid="language-menu">
          {LANGUAGES.map(l => (
            <button
              key={l.code}
              type="button"
              onClick={() => { setLang(l.code); setOpen(false); }}
              className={`w-full rounded-md px-3 py-2 text-left transition-colors ${l.code === lang ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"} ${compact ? "text-xs" : "text-sm"}`}
              data-testid={`language-option-${l.code}`}
            >
              {l.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
