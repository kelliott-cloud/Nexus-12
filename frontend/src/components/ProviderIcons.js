/**
 * AI Provider brand icons — inline SVGs for each provider.
 * Used in chat avatars, agent cards, and anywhere provider identity is shown.
 */

const PROVIDER_ICONS = {
  claude: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15.5v-2.09c-1.72-.45-3-2-3-3.91 0-2.21 1.79-4 4-4s4 1.79 4 4c0 1.91-1.28 3.46-3 3.91v2.09c2.84-.48 5-2.94 5-5.91 0-3.31-2.69-6-6-6s-6 2.69-6 6c0 2.97 2.16 5.43 5 5.91z"/>
    </svg>
  ),
  chatgpt: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1">
      <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855l-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681z"/>
    </svg>
  ),
  gemini: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.6 0 12 0zm0 3.6c2.2 0 4.2.8 5.8 2.2L12 12 6.2 5.8C7.8 4.4 9.8 3.6 12 3.6zm-8.4 8.4c0-2.2.8-4.2 2.2-5.8L12 12 5.8 17.8c-1.4-1.6-2.2-3.6-2.2-5.8zm8.4 8.4c-2.2 0-4.2-.8-5.8-2.2L12 12l5.8 6.2c-1.6 1.4-3.6 2.2-5.8 2.2zm8.4-8.4c0 2.2-.8 4.2-2.2 5.8L12 12l6.2-5.8c1.4 1.6 2.2 3.6 2.2 5.8z"/>
    </svg>
  ),
  deepseek: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
    </svg>
  ),
  perplexity: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
    </svg>
  ),
  grok: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
    </svg>
  ),
  mistral: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <rect x="2" y="4" width="4" height="4"/><rect x="10" y="4" width="4" height="4"/><rect x="18" y="4" width="4" height="4"/><rect x="2" y="10" width="4" height="4"/><rect x="6" y="10" width="4" height="4"/><rect x="10" y="10" width="4" height="4"/><rect x="14" y="10" width="4" height="4"/><rect x="18" y="10" width="4" height="4"/><rect x="2" y="16" width="4" height="4"/><rect x="10" y="16" width="4" height="4"/><rect x="18" y="16" width="4" height="4"/>
    </svg>
  ),
  cohere: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M12 2a10 10 0 100 20 10 10 0 000-20zm0 4a6 6 0 110 12 6 6 0 010-12zm0 2a4 4 0 100 8 4 4 0 000-8z"/>
    </svg>
  ),
  groq: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M3 3h18v18H3V3zm2 2v14h14V5H5zm3 3h8v2H8V8zm0 3h8v2H8v-2zm0 3h5v2H8v-2z"/>
    </svg>
  ),
  mercury: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/>
    </svg>
  ),
  pi: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M4 6h16v2H4zm2 4h4v8H8v-6H6zm6 0h4v8h-2v-6h-2z"/>
    </svg>
  ),
  manus: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M12 2L2 7v10l10 5 10-5V7L12 2zm0 2.5L19 8l-7 3.5L5 8l7-3.5zM4 9.5l7 3.5v7L4 16.5v-7zm16 0v7l-7 3.5v-7l7-3.5z"/>
    </svg>
  ),
  qwen: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c3.86 0 7 3.14 7 7 0 1.93-.78 3.68-2.05 4.95l-1.41-1.41A5.006 5.006 0 0017 12c0-2.76-2.24-5-5-5s-5 2.24-5 5a5.006 5.006 0 001.46 3.54l-1.41 1.41A6.978 6.978 0 015 12c0-3.86 3.14-7 7-7zm0 4a3 3 0 110 6 3 3 0 010-6z"/>
    </svg>
  ),
  kimi: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M12 2a10 10 0 100 20 10 10 0 000-20zm-2 5h4l-2 4h3l-5 6 1-4H8l2-6z"/>
    </svg>
  ),
  llama: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M12 2C9.5 2 7.5 3.5 7 5.5L5 7v4l-1 1v4h2v2h3v-2h6v2h3v-2h2v-4l-1-1V7l-2-1.5C16.5 3.5 14.5 2 12 2zm-2 5a1 1 0 110 2 1 1 0 010-2zm4 0a1 1 0 110 2 1 1 0 010-2z"/>
    </svg>
  ),
  glm: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M4 4h7v7H4V4zm9 0h7v7h-7V4zM4 13h7v7H4v-7zm9 0h7v7h-7v-7zM6 6v3h3V6H6zm9 0v3h3V6h-3zM6 15v3h3v-3H6zm9 0v3h3v-3h-3z"/>
    </svg>
  ),
  cursor: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M5 3l14 9-6 2 4 7-3 1-4-7-5 4V3z"/>
    </svg>
  ),
  notebooklm: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M4 4h2v16H4V4zm4 0h12v2H8V4zm0 4h12v2H8V8zm0 4h10v2H8v-2zm0 4h12v2H8v-2z"/>
    </svg>
  ),
  copilot: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-full h-full p-1.5">
      <path d="M12 0c6.627 0 12 5.373 12 12s-5.373 12-12 12S0 18.627 0 12 5.373 0 12 0zm-.5 4C8.46 4 6 6.46 6 9.5V14h2V9.5C8 7.57 9.57 6 11.5 6h1C14.43 6 16 7.57 16 9.5V14h2V9.5C18 6.46 15.54 4 12.5 4h-1zM7 15v2a5 5 0 0010 0v-2h-2v2a3 3 0 01-6 0v-2H7z"/>
    </svg>
  ),
};

export function ProviderIcon({ provider, size = 32, color = "#fff", bgColor }) {
  const icon = PROVIDER_ICONS[provider];
  if (!icon) {
    // Fallback to letter initial
    return (
      <div
        className="rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0"
        style={{ width: size, height: size, backgroundColor: bgColor || "#3f3f46", color }}
      >
        {(provider || "?")[0].toUpperCase()}
      </div>
    );
  }
  return (
    <div
      className="rounded-lg flex items-center justify-center flex-shrink-0"
      style={{ width: size, height: size, backgroundColor: bgColor || "#18181b", color }}
      aria-label={`${provider} AI provider`}
    >
      {icon}
    </div>
  );
}

export default PROVIDER_ICONS;
