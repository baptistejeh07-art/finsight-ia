// FinSight IA — Content script : détecte le ticker de la page et injecte un bouton
// "📊 Analyser avec FinSight". Au clic → ouvre finsight-ia.com/app avec le ticker pré-rempli.

(() => {
  const BUTTON_ID = "finsight-analyze-btn";
  const FINSIGHT_URL = "https://finsight-ia.com/app";

  // --- Extraction du ticker selon la plateforme ---
  function extractTicker() {
    const url = location.href;
    const host = location.hostname;

    // Yahoo Finance : /quote/AAPL
    let m = url.match(/finance\.yahoo\.com\/quote\/([A-Z0-9.\-^]+)/i);
    if (m) return { ticker: m[1].toUpperCase(), source: "yahoo" };

    // TradingView : /symbols/NASDAQ-AAPL ou /symbols/EURONEXT-MC
    m = url.match(/tradingview\.com\/symbols\/[A-Z0-9\-]+?-([A-Z0-9]+)\//i);
    if (m) {
      // Pour TradingView, l'exchange est avant le tiret → on ajoute le suffix approprié
      const exchange = url.match(/\/symbols\/([A-Z0-9]+)-/i)?.[1]?.toUpperCase();
      const ticker = m[1].toUpperCase();
      const suffix = {
        EURONEXT: ".PA", LSE: ".L", XETR: ".DE", SIX: ".SW",
        BME: ".MC", MIL: ".MI", AMS: ".AS", BRU: ".BR",
        TSE: ".T", HKEX: ".HK", TSX: ".TO",
      }[exchange];
      return { ticker: suffix && !ticker.includes(".") ? ticker + suffix : ticker, source: "tradingview" };
    }

    // Boursorama : /cours/RMS (français, ajouter .PA)
    m = url.match(/boursorama\.com\/cours\/(?:1rP)?([A-Z0-9]+)/i);
    if (m) {
      let t = m[1].toUpperCase();
      if (!t.includes(".") && !/^[A-Z]{3,4}$/.test(t)) t += ".PA";
      return { ticker: t, source: "boursorama" };
    }

    // Google Finance : /finance/quote/AAPL:NASDAQ
    m = url.match(/google\.com\/finance\/quote\/([A-Z0-9.\-]+)(?::([A-Z]+))?/i);
    if (m) {
      const ticker = m[1].toUpperCase();
      const exchange = m[2]?.toUpperCase();
      const suffix = { EPA: ".PA", LON: ".L", ETR: ".DE", BIT: ".MI", BME: ".MC", SWX: ".SW", TYO: ".T" }[exchange];
      return { ticker: suffix && !ticker.includes(".") ? ticker + suffix : ticker, source: "google" };
    }

    // Morningstar US : /stocks/xnas/aapl/quote
    m = url.match(/morningstar\.com\/stocks\/[a-z]+\/([a-z0-9.]+)\/quote/i);
    if (m) return { ticker: m[1].toUpperCase(), source: "morningstar" };

    // Investing : /equities/apple-computer-inc → pas de ticker direct, on lit le DOM
    if (host.includes("investing.com")) {
      const el = document.querySelector('[data-test="symbol-header"]')
        || document.querySelector(".instrumentHeader h1");
      const text = el?.innerText || "";
      const match = text.match(/\(([A-Z0-9.\-]+)\)/);
      if (match) return { ticker: match[1].toUpperCase(), source: "investing" };
    }

    // Zonebourse : /cours/action/HERMES-INTERNATIONAL-4735/
    if (host.includes("zonebourse.com")) {
      const h1 = document.querySelector("h1")?.innerText || "";
      // Pas de ticker dans l'URL — on retourne le nom pour que FinSight résolve
      return { ticker: h1.split("-")[0]?.trim() || "", source: "zonebourse", useName: true };
    }

    return null;
  }

  // --- Injection du bouton ---
  function injectButton() {
    if (document.getElementById(BUTTON_ID)) return;
    const data = extractTicker();
    if (!data || !data.ticker) return;

    const btn = document.createElement("button");
    btn.id = BUTTON_ID;
    btn.className = "finsight-btn";
    btn.innerHTML = `
      <span class="fs-icon">📊</span>
      <span class="fs-text">Analyser avec FinSight</span>
      <span class="fs-ticker">${data.ticker}</span>
    `;
    btn.title = `Lancer une analyse fondamentale FinSight sur ${data.ticker}`;
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const url = new URL(FINSIGHT_URL);
      url.searchParams.set(data.useName ? "q" : "ticker", data.ticker);
      url.searchParams.set("utm_source", "chrome_extension");
      url.searchParams.set("utm_medium", data.source);
      window.open(url.toString(), "_blank", "noopener,noreferrer");
    });

    // Position : top-right flottant (évite de casser chaque DOM différent)
    document.body.appendChild(btn);
  }

  // Premier essai
  injectButton();

  // Re-inject si la page change (SPA navigation — Yahoo, TradingView, Google)
  let lastUrl = location.href;
  const observer = new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      const old = document.getElementById(BUTTON_ID);
      if (old) old.remove();
      setTimeout(injectButton, 500);
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
