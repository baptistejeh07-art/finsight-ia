import { NextResponse } from "next/server";

export const runtime = "nodejs";

const SYSTEM_PROMPT = `Tu es l'assistant officiel de FinSight IA. Tu réponds en français, de manière claire, structurée et professionnelle.

À PROPOS DE FINSIGHT
FinSight est une plateforme d'analyse financière institutionnelle propulsée par l'IA. Elle produit, à partir d'un ticker boursier, d'un secteur ou d'un indice, trois livrables : un rapport PDF (≈ 20 pages), un pitchbook PowerPoint (20 slides exactement) et un modèle Excel complet (DCF, ratios, comparables, scénarios). Le tout en quelques minutes.

PIPELINE TECHNIQUE
Sept agents orchestrés via LangGraph :
1. AgentData — multi-sources (yfinance principal, Finnhub pour les news, FMP en fallback) avec normalisation Pydantic.
2. AgentQuant — calculs déterministes en Python : WACC, DCF, ratios. Aucun chiffre généré par LLM.
3. AgentSynthese — commentaire éditorial via Groq llama-3.3-70b (fallback Anthropic Haiku 4.5).
4. AgentQA Python + Haiku — vérifications croisées des sorties.
5. AgentDevil — thèse inverse systématique, ajuste la conviction.
6. Quatre agents de gouvernance — constitution stricte, ChromaDB pour la mémoire vectorielle.
7. Output writers — ReportLab (PDF), python-pptx (PPTX), openpyxl (Excel).

DONNÉES
yfinance gratuit (5 ans d'historique max), Finnhub pour les news (10 articles), FMP en fallback US, FinBERT local pour le sentiment. Aucune donnée client n'est utilisée pour entraîner les modèles.

TARIFS
- Découverte : gratuit, 3 analyses/mois.
- Essentiel : 34,99 €/mois, 20 analyses, comparatif, secteurs et indices.
- Pro : 44,99 €/mois, ajoute le portrait d'entreprise (Pappers), accès anticipé, score FinSight, white-label.
- Équipe : à partir de 199 €/siège/mois, sur devis.
- Enterprise : 299–499 €/siège/mois négocié, on-premise possible, white-label complet.
- API pay-per-use : 0,05 € (data), 0,50 € (analyse complète), 2 € (livrables PDF/PPTX/XLSX).

ROADMAP
Q2 2026 : portrait d'entreprise via Pappers V2 (sociétés non cotées). Courant 2026 : comptes utilisateurs persistants, watchlists, partage. Fin 2026 : Score FinSight propriétaire (note composite qualité/valorisation/momentum/gouvernance).

UNIVERS COUVERT
≈ 50 000 tickers cotés (NYSE, Nasdaq, Euronext, LSE, XETRA, etc.), indices majeurs (CAC 40, S&P 500, Euro Stoxx 50, etc.), analyses sectorielles. Sociétés non cotées via Pappers à partir du Q2 2026.

LE CRÉATEUR
Baptiste Jeh, étudiant en BTS Comptabilité & Gestion en alternance, en préparation du FMVA (Financial Modeling & Valuation Analyst, CFI), candidat en L2 Gestion à la Sorbonne. Ambition : devenir analyste financier en banque d'investissement.

RÈGLES DE RÉPONSE
- Reste factuel et précis. Ne jamais inventer de chiffres ou de fonctionnalités.
- Quand tu ne sais pas, dis-le et oriente vers /contact.
- Réponses courtes (3-6 phrases sauf si la question demande du détail).
- Toujours en français, avec accents complets.`;

export async function POST(req: Request) {
  try {
    const { messages } = await req.json();
    if (!Array.isArray(messages) || messages.length === 0) {
      return NextResponse.json({ error: "Aucun message" }, { status: 400 });
    }

    // Groq d'abord (gratuit, rapide), Anthropic en fallback
    const groqKey = process.env.GROQ_API_KEY || process.env.GROQ_API_KEY_1;
    const anthropicKey = process.env.ANTHROPIC_API_KEY;

    if (!groqKey && !anthropicKey) {
      return NextResponse.json({
        reply:
          "L'assistant FinSight n'est pas encore configuré sur cet environnement. Contactez-nous via /contact pour toute question.",
      });
    }

    let reply: string | null = null;

    // 1. Groq llama-3.3-70b (principal)
    if (groqKey) {
      try {
        const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
          method: "POST",
          headers: {
            "content-type": "application/json",
            authorization: `Bearer ${groqKey}`,
          },
          body: JSON.stringify({
            model: "llama-3.3-70b-versatile",
            max_tokens: 600,
            temperature: 0.3,
            messages: [
              { role: "system", content: SYSTEM_PROMPT },
              ...messages.map((m: { role: string; content: string }) => ({
                role: m.role === "assistant" ? "assistant" : "user",
                content: m.content,
              })),
            ],
          }),
        });
        if (res.ok) {
          const data = await res.json();
          reply = data?.choices?.[0]?.message?.content || null;
        }
      } catch {
        /* fallback Anthropic */
      }
    }

    // 2. Anthropic fallback si Groq KO ou absent
    if (!reply && anthropicKey) {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-api-key": anthropicKey,
          "anthropic-version": "2023-06-01",
        },
        body: JSON.stringify({
          model: "claude-haiku-4-5-20251001",
          max_tokens: 600,
          system: SYSTEM_PROMPT,
          messages: messages.map((m: { role: string; content: string }) => ({
            role: m.role === "assistant" ? "assistant" : "user",
            content: m.content,
          })),
        }),
      });
      if (res.ok) {
        const data = await res.json();
        reply = data?.content?.[0]?.text || null;
      }
    }

    return NextResponse.json({
      reply: reply || "Je n'ai pas pu formuler de réponse, désolé.",
    });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Erreur inconnue" },
      { status: 500 }
    );
  }
}
