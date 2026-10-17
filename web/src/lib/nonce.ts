import { setNonce } from "get-nonce";

// Dialogs lock page scrolling with a small <style> element; the server allows only <style> carrying this page's nonce.
const nonce = document.querySelector<HTMLMetaElement>('meta[name="csp-nonce"]')?.content;
if (nonce && nonce !== "__CSP_NONCE__") setNonce(nonce);
