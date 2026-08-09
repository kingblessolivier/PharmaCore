/* -------------------------------------------------------------------------- */
/* Putting a picture on a record.                                             */
/*                                                                            */
/* Five fields in this system hold an image — company logo, organization      */
/* logo, product photo, listing photo, employee badge — and every one of them */
/* was a text box asking for a URL. That is a reasonable thing to ask a       */
/* developer and an impossible thing to ask a pharmacist, who has the picture */
/* on their phone and nowhere to put it. So the fields stayed empty, and the  */
/* documents and storefronts that read them rendered a blank space.           */
/*                                                                            */
/* Pasting a URL still works, because some suppliers do publish product       */
/* images and retyping them into an upload would be silly.                    */
/* -------------------------------------------------------------------------- */

import { useRef, useState, type ChangeEvent } from "react";
import { ImagePlus, Loader2, Trash2, AlertTriangle } from "lucide-react";
import { api, ApiError, assetUrl, uploadImage } from "../lib/api";

type Purpose = "logo" | "product" | "listing" | "photo";

/** Refused here rather than after a round trip, so a 40 MB photo on a slow
 *  connection fails in the moment instead of two minutes later. The server
 *  enforces the same limits; this is only courtesy. */
const MAX_BYTES = 6 * 1024 * 1024;
const ACCEPTED = ["image/png", "image/jpeg", "image/webp"];

export function ImageUpload({
  value,
  onChange,
  purpose,
  label,
  hint,
  shape = "square",
}: {
  value: string;
  onChange: (url: string) => void;
  purpose: Purpose;
  label: string;
  /** What this picture is used for downstream — worth saying when it ends up
   *  somewhere the person uploading it will not immediately see. */
  hint?: string;
  shape?: "square" | "wide" | "round";
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** A picture somebody else hosts. It renders here and not on paper. */
  const isRemote = /^https?:/i.test(value);

  const pick = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    // Let the same file be chosen again after a failure.
    event.target.value = "";
    if (!file) return;

    if (!ACCEPTED.includes(file.type)) {
      setError("Choose a PNG, JPEG or WebP image.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setError(`That image is ${(file.size / 1024 / 1024).toFixed(1)} MB. The limit is 6 MB.`);
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const stored = await uploadImage(file, purpose);
      onChange(stored.url);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That upload did not go through.");
    } finally {
      setBusy(false);
    }
  };

  const frame =
    shape === "round"
      ? "h-20 w-20 rounded-full"
      : shape === "wide"
        ? "h-20 w-40 rounded-lg"
        : "h-20 w-20 rounded-lg";

  return (
    <div>
      <div className="mb-1 text-sm font-medium text-ink-700">{label}</div>
      <div className="flex items-start gap-3">
        <div
          className={`${frame} flex shrink-0 items-center justify-center overflow-hidden border border-line bg-surface-50`}
        >
          {value ? (
            <img
              src={assetUrl(value)}
              alt=""
              className="h-full w-full object-contain"
              /* A stored URL can rot — an external host goes away, a file is
                 deleted. Saying so beats a browser's broken-image glyph. */
              onError={(e) => {
                e.currentTarget.style.display = "none";
                setError("That image could not be loaded from where it is stored.");
              }}
            />
          ) : (
            <ImagePlus className="h-6 w-6 text-ink-400" aria-hidden />
          )}
        </div>

        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap gap-2">
            <input
              ref={input}
              type="file"
              accept={ACCEPTED.join(",")}
              onChange={pick}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => input.current?.click()}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-xs font-medium text-ink-700 hover:bg-surface-50 disabled:opacity-60"
            >
              {busy ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : (
                <ImagePlus className="h-3.5 w-3.5" aria-hidden />
              )}
              {busy ? "Uploading…" : value ? "Replace" : "Upload image"}
            </button>
            {value && !busy && (
              <button
                type="button"
                onClick={() => {
                  onChange("");
                  setError(null);
                }}
                className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-xs font-medium text-danger-700 hover:bg-danger-50"
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden />
                Remove
              </button>
            )}
          </div>

          <input
            type="url"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="…or paste an image address"
            className="w-full rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-xs text-ink-700 placeholder:text-ink-400 focus:border-brand-500 focus:outline-none"
          />

          {/* Said here rather than discovered on a printed document. Generated
              PDFs never fetch from the internet — it is slow, it fails when
              the other end is down, and it would let a pasted address point
              our server at anything. A pasted picture shows on screen and is
              left off the paperwork. */}
          {isRemote && (
            <p className="flex items-start gap-1.5 text-xs text-warning-700">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              Shown on screen, but left off generated documents. Upload the file to have it
              printed on invoices and orders.
            </p>
          )}

          {hint && !error && !isRemote && <p className="text-xs text-ink-500">{hint}</p>}
          {error && (
            <p className="flex items-start gap-1.5 text-xs text-danger-700">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              {error}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Upload straight onto a record that already exists.
 *
 * The plain control above belongs in a form, where the URL is saved with
 * everything else. This one is for a record on screen with no form around it —
 * a product in a table, an organization in a drawer — where the picture is the
 * only thing changing and a save button would be ceremony.
 */
export function InlineImageUpload({
  value,
  purpose,
  patchPath,
  field,
  label,
  hint,
  shape,
  onSaved,
}: {
  value: string;
  purpose: Purpose;
  /** The detail endpoint of the record being patched. */
  patchPath: string;
  /** Which field on that record holds the picture. */
  field: string;
  label: string;
  hint?: string;
  shape?: "square" | "wide" | "round";
  onSaved?: () => void;
}) {
  const [current, setCurrent] = useState(value);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const save = async (url: string) => {
    setCurrent(url);
    setError(null);
    setSaved(false);
    try {
      await api(patchPath, { method: "PATCH", body: JSON.stringify({ [field]: url }) });
      setSaved(true);
      onSaved?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save that image.");
    }
  };

  return (
    <div>
      <ImageUpload
        value={current}
        onChange={save}
        purpose={purpose}
        label={label}
        hint={hint}
        shape={shape}
      />
      {saved && !error && <p className="mt-1 text-xs text-success-700">Saved.</p>}
      {error && <p className="mt-1 text-xs text-danger-700">{error}</p>}
    </div>
  );
}
