"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Upload,
  FileText,
  FileSpreadsheet,
  FileCheck2,
  AlertTriangle,
  Trash2,
  Loader2,
  Sparkles,
  CheckCircle2,
  X,
} from "lucide-react";
import {
  uploadDocument,
  extractDocument,
  validateDocument,
  listAnalysisDocuments,
  deleteDocument,
  type UserDocument,
} from "@/lib/api";

interface Props {
  analysisId: string;
}

const TYPE_LABELS: Record<string, string> = {
  compte_resultat: "Compte de résultat",
  bilan: "Bilan",
  contrat: "Contrat",
  autre: "Autre document",
};

const ACCEPTED = ".pdf,.xlsx,.xls,.png,.jpg,.jpeg,.webp,.txt,.csv";
const MAX_SIZE = 20 * 1024 * 1024;

export function DocumentUploadBox({ analysisId }: Props) {
  const [docs, setDocs] = useState<UserDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [validatingDoc, setValidatingDoc] = useState<UserDocument | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listAnalysisDocuments(analysisId);
      setDocs(res.documents || []);
    } catch (e) {
      console.warn("[DocumentUploadBox] list failed", e);
    } finally {
      setLoading(false);
    }
  }, [analysisId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function handleFiles(files: FileList | File[]) {
    setError(null);
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        if (file.size > MAX_SIZE) {
          setError(`${file.name} > 20 Mo, ignoré`);
          continue;
        }
        const up = await uploadDocument(file, analysisId);
        if (up.cached) continue; // déjà en BDD avec extraction
        // Lance extraction en arrière-plan, refresh périodique
        void (async () => {
          try {
            await extractDocument(up.id);
          } catch (e) {
            console.warn("[extract] failed", e);
          } finally {
            void reload();
          }
        })();
      }
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur upload");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteDocument(id);
      await reload();
    } catch (e) {
      console.warn("[delete] failed", e);
    }
  }

  async function handleRetryExtract(id: string) {
    try {
      await extractDocument(id);
    } catch (e) {
      console.warn("[extract retry] failed", e);
    } finally {
      await reload();
    }
  }

  return (
    <div className="bg-white border border-ink-200 rounded-md p-4">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-4 h-4 text-navy-500" />
        <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500">
          Documents complémentaires
        </div>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (e.dataTransfer.files?.length) void handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-md p-4 text-center cursor-pointer transition-colors ${
          dragOver ? "border-navy-500 bg-navy-50" : "border-ink-200 hover:border-navy-400"
        } ${uploading ? "opacity-60 pointer-events-none" : ""}`}
      >
        <Upload className="w-5 h-5 text-ink-400 mx-auto mb-1" />
        <div className="text-xs text-ink-700 font-medium">
          {uploading ? "Upload en cours…" : "Glisse un PDF, XLSX, image ou contrat"}
        </div>
        <div className="text-[10px] text-ink-400 mt-0.5">
          Bilan, compte de résultat, contrat — max 20 Mo
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) void handleFiles(e.target.files);
            if (e.target) e.target.value = "";
          }}
        />
      </div>

      {error && (
        <div className="mt-2 text-[11px] text-signal-sell flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" /> {error}
        </div>
      )}

      <div className="mt-3 space-y-1.5">
        {loading && docs.length === 0 ? (
          <div className="text-xs text-ink-400 italic">Chargement…</div>
        ) : docs.length === 0 ? (
          <div className="text-xs text-ink-400 italic">Aucun document uploadé.</div>
        ) : (
          docs.map((d) => (
            <DocRow
              key={d.id}
              doc={d}
              onDelete={() => handleDelete(d.id)}
              onRetry={() => handleRetryExtract(d.id)}
              onValidate={() => setValidatingDoc(d)}
            />
          ))
        )}
      </div>

      {validatingDoc && (
        <ValidationModal
          doc={validatingDoc}
          onClose={() => setValidatingDoc(null)}
          onSaved={async () => {
            setValidatingDoc(null);
            await reload();
          }}
        />
      )}
    </div>
  );
}

function fileIcon(d: UserDocument) {
  const m = d.mime_type || "";
  if (m.includes("sheet") || m.includes("excel"))
    return <FileSpreadsheet className="w-4 h-4 text-emerald-600" />;
  if (d.validated) return <FileCheck2 className="w-4 h-4 text-signal-buy" />;
  return <FileText className="w-4 h-4 text-navy-500" />;
}

function statusBadge(d: UserDocument) {
  if (d.status === "extracting")
    return (
      <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 inline-flex items-center gap-1">
        <Loader2 className="w-2.5 h-2.5 animate-spin" /> Extraction…
      </span>
    );
  if (d.status === "error")
    return (
      <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-50 text-signal-sell">
        Erreur
      </span>
    );
  if (d.validated)
    return (
      <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-signal-buy inline-flex items-center gap-1">
        <CheckCircle2 className="w-2.5 h-2.5" /> Validé
      </span>
    );
  if (d.status === "extracted")
    return (
      <span className="text-[10px] px-1.5 py-0.5 rounded bg-navy-50 text-navy-600">
        À valider
      </span>
    );
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded bg-ink-50 text-ink-500">
      Uploadé
    </span>
  );
}

function DocRow({
  doc,
  onDelete,
  onRetry,
  onValidate,
}: {
  doc: UserDocument;
  onDelete: () => void;
  onRetry: () => void;
  onValidate: () => void;
}) {
  return (
    <div className="flex items-center gap-2 py-1.5 px-2 border border-ink-100 rounded-md text-xs">
      {fileIcon(doc)}
      <div className="flex-1 min-w-0">
        <div className="font-medium text-ink-900 truncate">{doc.filename}</div>
        <div className="text-[10px] text-ink-500 flex items-center gap-2">
          {doc.type_detected && (
            <span>{TYPE_LABELS[doc.type_detected] || doc.type_detected}</span>
          )}
          {doc.size_bytes != null && <span>· {formatSize(doc.size_bytes)}</span>}
        </div>
      </div>
      {statusBadge(doc)}
      <div className="flex items-center gap-1">
        {doc.status === "extracted" && !doc.validated && (
          <button
            onClick={onValidate}
            className="text-[10px] px-2 py-1 rounded bg-navy-500 text-white hover:bg-navy-600"
          >
            Valider
          </button>
        )}
        {doc.status === "error" && (
          <button
            onClick={onRetry}
            className="text-[10px] px-2 py-1 rounded border border-ink-200 hover:bg-ink-50"
          >
            Relancer
          </button>
        )}
        <button
          onClick={onDelete}
          className="p-1 text-ink-400 hover:text-signal-sell rounded"
          title="Supprimer"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} ko`;
  return `${(bytes / 1024 / 1024).toFixed(1)} Mo`;
}

// ─── Modale de validation : édition du JSON extrait ────────────────────────

function ValidationModal({
  doc,
  onClose,
  onSaved,
}: {
  doc: UserDocument;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [data, setData] = useState<Record<string, unknown>>(doc.extracted_data || {});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const isCompte = doc.type_detected === "compte_resultat" || doc.type_detected === "bilan";

  function setField(k: string, v: string) {
    const num = v === "" ? null : Number(v);
    setData((prev) => ({ ...prev, [k]: Number.isFinite(num as number) ? num : v }));
  }

  async function handleSave(validated: boolean) {
    setSaving(true);
    setErr(null);
    try {
      await validateDocument(doc.id, data, validated);
      onSaved();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Erreur sauvegarde");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 bg-ink-900/50 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-md max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-ink-200">
          <div>
            <div className="text-sm font-semibold text-ink-900">
              Vérifier les données extraites
            </div>
            <div className="text-xs text-ink-500">
              {doc.filename} · {TYPE_LABELS[doc.type_detected || "autre"]}
            </div>
          </div>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-700">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 overflow-auto flex-1">
          {isCompte ? (
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(data)
                .filter(([k]) => !k.startsWith("_") && k !== "type")
                .map(([k, v]) => (
                  <div key={k} className="flex flex-col">
                    <label className="text-[10px] text-ink-500 uppercase tracking-wide">
                      {k.replace(/_/g, " ")}
                    </label>
                    <input
                      value={v == null ? "" : String(v)}
                      onChange={(e) => setField(k, e.target.value)}
                      className="px-2 py-1 border border-ink-200 rounded text-xs font-mono focus:outline-none focus:border-navy-500"
                    />
                  </div>
                ))}
            </div>
          ) : (
            <textarea
              value={JSON.stringify(data, null, 2)}
              onChange={(e) => {
                try {
                  setData(JSON.parse(e.target.value));
                  setErr(null);
                } catch {
                  setErr("JSON invalide");
                }
              }}
              className="w-full h-96 p-2 border border-ink-200 rounded text-[11px] font-mono focus:outline-none focus:border-navy-500"
            />
          )}
          {err && <div className="text-[11px] text-signal-sell mt-2">{err}</div>}
        </div>

        <div className="flex items-center justify-end gap-2 p-3 border-t border-ink-200">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-xs rounded border border-ink-200 hover:bg-ink-50"
          >
            Annuler
          </button>
          <button
            onClick={() => handleSave(false)}
            disabled={saving}
            className="px-3 py-1.5 text-xs rounded border border-ink-200 hover:bg-ink-50 disabled:opacity-50"
          >
            Sauvegarder brouillon
          </button>
          <button
            onClick={() => handleSave(true)}
            disabled={saving}
            className="px-3 py-1.5 text-xs rounded bg-navy-500 text-white hover:bg-navy-600 disabled:opacity-50"
          >
            {saving ? "…" : "Valider"}
          </button>
        </div>
      </div>
    </div>
  );
}
