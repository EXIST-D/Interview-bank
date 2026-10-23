// Same-page login preserves the reading route. No third-party return URL is accepted.
import type { MouseEvent } from "react";
export function loginHref(hash = location.hash) {
  return location.pathname + "?login=1" + hash;
}
export function signIn(hash?: string) { location.assign(loginHref(hash)); }
export function onSignIn(event: MouseEvent<HTMLAnchorElement>) {
  if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  signIn();
}

export function notesLoginHref() {
  const [path, query = ""] = location.hash.split("?");
  const params = new URLSearchParams(query);
  params.set("panel", "notes");
  return loginHref(path + "?" + params.toString());
}

export function publicBrowseHref() {
  const hash = /^#\/(?:knowledge|public|learning)(?:[/?]|$)/.test(location.hash) ? location.hash : "#/knowledge";
  return location.pathname + hash;
}
