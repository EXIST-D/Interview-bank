import { LockKeyhole } from "lucide-react";
import { loginHref } from "@/lib/access";
import { useI18n } from "@/lib/i18n";
import { href } from "@/lib/router";
import { Button } from "./ui/button";

export function LoginRequired() {
  const { t } = useI18n();
  return <section className="mx-auto max-w-lg px-5 py-20 text-center sm:py-28">
    <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-accent text-primary"><LockKeyhole className="size-6" /></span>
    <h1 className="mt-5 text-title-2 font-bold">{t("login_required_title")}</h1>
    <p className="mt-3 text-callout leading-relaxed text-muted-foreground">{t("login_required_hint")}</p>
    <div className="mt-6 flex flex-wrap justify-center gap-3">
      <Button asChild><a href={loginHref()}>{t("login")}</a></Button>
      <Button variant="outline" asChild><a href={href("knowledge")}>{t("browse_public")}</a></Button>
    </div>
  </section>;
}
