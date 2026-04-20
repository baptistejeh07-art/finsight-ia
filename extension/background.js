// FinSight IA — Background service worker
// Minimal : aucune action lourde côté background pour cette v1.
// L'extension est essentiellement content-script-based.

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") {
    chrome.tabs.create({ url: "https://finsight-ia.com/app?utm_source=chrome_extension&utm_medium=install" });
  }
});

chrome.action.onClicked.addListener((tab) => {
  // Si popup désactivé, fallback : ouvre FinSight direct
  chrome.tabs.create({ url: "https://finsight-ia.com/app?utm_source=chrome_extension&utm_medium=action" });
});
