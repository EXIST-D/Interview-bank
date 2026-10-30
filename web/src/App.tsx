import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BankProvider, useBank } from "@/lib/bank";
import { I18n, toLang, translator } from "@/lib/i18n";
import { useRoute } from "@/lib/router";
import { useTheme } from "@/lib/theme";
import { TabBar, Toast, TopBar } from "@/components/app-shell";
import { HomePage } from "@/pages/home";
import { LearningPage } from "@/pages/learning";
import { PublicPage } from "@/pages/public";
import { BankPage } from "@/pages/bank";
import { KnowledgePage } from "@/pages/knowledge";
import { MinePage } from "@/pages/mine";
import { ImportPage } from "@/pages/import";
import { InterviewPage } from "@/pages/interview";
import { PreparePage } from "@/pages/prepare";
import { FavoritesProvider } from "@/lib/favorites";
import { ToastContext } from "@/lib/hooks";
import { LoginRequired } from "@/components/login-required";

function Shell() {
  const route = useRoute();
  const { library } = useBank();
  const [theme, setTheme] = useTheme();
  const [toast, setToast] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const lang = toLang(library?.language);
  const i18n = useMemo(() => ({ lang, t: translator(lang) }), [lang]);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = library?.guest ? "Interview Bank · 公开资料" : `Interview Bank · ${library?.account || library?.name || ""}`;
  }, [lang, library]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [route.board]);

  const showToast = useCallback((text: string) => {
    setToast(text);
    clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setToast(null), 2500);
  }, []);

  const page =
    route.board === "home" ? (
      <HomePage />
    ) : route.board === "bank" ? (
      <BankPage route={route} />
    ) : route.board === "knowledge" ? (
      <KnowledgePage route={route} />
    ) : route.board === "public" ? (
      <PublicPage route={route} />
    ) : route.board === "mine" ? (
      <MinePage route={route} />
    ) : route.board === "import" ? (
      <ImportPage />
    ) : route.board === "interview" ? (
      <InterviewPage route={route} />
    ) : route.board === "prepare" ? (
      <PreparePage route={route} />
    ) : (
      <LearningPage route={route} />
    );

  return (
    <I18n.Provider value={i18n}>
      <ToastContext.Provider value={showToast}>
        <TopBar board={route.board} theme={theme} onTheme={setTheme} onToast={showToast} />
        <main>{!library ? <HomePage /> : library.guest && (route.board === "bank" || route.board === "mine" || route.board === "import" || route.board === "interview" || route.board === "prepare") ? <LoginRequired /> : page}</main>
        <TabBar board={route.board} />
        <Toast text={toast} />
      </ToastContext.Provider>
    </I18n.Provider>
  );
}

export function App() {
  return (
    <BankProvider>
      <FavoritesProvider>
        <Shell />
      </FavoritesProvider>
    </BankProvider>
  );
}
