// Login page of a hosted reader. It is served at the reader's own address, so a successful login reloads into the reader.
import { StrictMode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { ExternalLink, Lock } from "lucide-react";
import "./lib/nonce";
import "./lib/theme";
import "./styles.css";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { publicBrowseHref } from "@/lib/access";

const TEXT = {
  zh: {
    tagline: "每一次积累，都算数。",
    title: "登录你的题库",
    lead: "登录后使用个人面经、笔记、收藏和练习记录。",
    browse: "先浏览公开资料",
    username: "用户名",
    password: "密码",
    show: "显示",
    hide: "隐藏",
    submit: "登录",
    busy: "正在登录…",
    foot: "HTTPS 加密连接 · 连续输错会暂时锁定",
    repo: "开源项目 · 在 GitHub 上查看",
    empty: "请输入用户名和密码。",
    offline: "暂时连不上服务器，请稍后重试。",
  },
  en: {
    tagline: "Every question counts.",
    title: "Sign in to your bank",
    lead: "Sign in for your interviews, notes, favourites and practice history.",
    browse: "Browse public resources first",
    username: "Username",
    password: "Password",
    show: "Show",
    hide: "Hide",
    submit: "Sign in",
    busy: "Signing in…",
    foot: "Encrypted over HTTPS · repeated mistakes lock sign-in for a while",
    repo: "Open source · view on GitHub",
    empty: "Enter your username and password.",
    offline: "The server cannot be reached right now. Try again shortly.",
  },
};
const lang = (navigator.language || "zh").toLowerCase().startsWith("zh") ? "zh" : "en";
const say = (key: keyof (typeof TEXT)["zh"]) => TEXT[lang][key];
document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";

const field =
  "h-11 w-full rounded-xl border border-border bg-card px-3.5 text-body outline-none transition-shadow focus:border-primary focus:shadow-[0_0_0_4px_var(--accent)]";

function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [shake, setShake] = useState(false);
  const user = useRef<HTMLInputElement>(null);

  useEffect(() => user.current?.focus(), []);

  const fail = (text: string) => {
    setError(text);
    setShake(true);
    setTimeout(() => setShake(false), 400);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!username.trim() || !password) return fail(say("empty"));
    setBusy(true);
    setError("");
    try {
      const response = await fetch("api/login", {
        method: "POST",
        cache: "no-store",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const result = await response.json().catch(() => ({}));
      if (response.ok) return location.replace(location.pathname + location.hash);
      setPassword("");
      fail(result.error || say("offline"));
    } catch {
      fail(say("offline"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="grid min-h-dvh place-items-center px-5 py-10">
      <div className="flex w-full max-w-[380px] flex-col items-center gap-6">
        <form noValidate onSubmit={submit} className={cn("w-full surface p-7 transition-transform", shake && "animate-[shake_0.35s]")}>
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-xl bg-primary text-callout font-semibold text-primary-foreground">iB</span>
            <span>
              <span className="block text-headline font-semibold">Interview Bank</span>
              <span className="block text-caption text-muted-foreground">{say("tagline")}</span>
            </span>
          </div>
          <h1 className="mt-6 text-title-2 font-bold">{say("title")}</h1>
          <p className="mt-1.5 text-footnote text-muted-foreground">{say("lead")}</p>
          <label className="mt-6 block">
            <span className="mb-1.5 block text-footnote font-medium">{say("username")}</span>
            <input
              ref={user}
              id="login-username"
              name="username"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className={field}
            />
          </label>
          <label className="mt-4 block">
            <span className="mb-1.5 block text-footnote font-medium">{say("password")}</span>
            <span className="relative block">
              <input
                id="login-password"
                name="password"
                type={visible ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className={cn(field, "pr-16")}
              />
              <button
                type="button"
                aria-pressed={visible}
                onClick={() => setVisible(!visible)}
                className="absolute top-1/2 right-2 -translate-y-1/2 rounded-lg px-2 py-1 text-footnote text-primary hover:bg-accent"
              >
                {say(visible ? "hide" : "show")}
              </button>
            </span>
          </label>
          {error && (
            <p role="alert" className="mt-4 rounded-xl bg-destructive/10 px-3 py-2 text-footnote text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" size="lg" className="mt-6 w-full" disabled={busy}>
            {say(busy ? "busy" : "submit")}
          </Button>
          <p className="mt-5 flex items-center justify-center gap-1.5 text-caption text-muted-foreground">
            <Lock className="size-3" />
            {say("foot")}
          </p>
        </form>
        {document.querySelector('meta[name="public-reading"]') && <a href={publicBrowseHref()} className="text-subhead font-medium text-primary hover:underline">{say("browse")}</a>}
        <a href="https://github.com/EXIST-D/Interview-bank" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-footnote text-muted-foreground hover:text-foreground">
          {say("repo")}
          <ExternalLink className="size-3.5" />
        </a>
      </div>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Login />
  </StrictMode>,
);
