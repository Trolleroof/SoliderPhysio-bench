const LOGO: Record<string, string> = {
  anthropic: "claude",
  openai: "openai",
  google: "gemini",
  moonshotai: "kimi",
  "x-ai": "grok",
  deepseek: "deepseek",
  meta: "meta",
  tencent: "hunyuan",
};
export const color = (p: string) => `var(--${p})`;

export function Mark({ provider }: { provider: string }) {
  const l = LOGO[provider];
  const style = { "--c": color(provider), "--src": `url(/model-logos/${l}.svg)` } as React.CSSProperties;
  return l ? <i className="logo" style={style} aria-hidden="true" /> : <i className="dot" style={style} aria-hidden="true" />;
}
