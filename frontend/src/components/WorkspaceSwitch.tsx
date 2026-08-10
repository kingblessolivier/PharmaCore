/* The header control that says which of your two jobs you are doing.
 *
 * Only rendered when somebody genuinely holds both. It changes the home screen
 * and nothing else — see lib/workspace.ts for why this is a view preference
 * rather than a second account. */

import { Briefcase, Check, ChevronDown, Store } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "../lib/auth";
import {
  WORKSPACE_HINT,
  WORKSPACE_LABEL,
  hasBothRoles,
  storeWorkspace,
  storedWorkspace,
  type Workspace,
} from "../lib/workspace";

export function WorkspaceSwitch({ onChange }: { onChange?: (w: Workspace) => void }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState<Workspace>(storedWorkspace);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  if (!hasBothRoles(user)) return null;

  const pick = (workspace: Workspace) => {
    setCurrent(workspace);
    storeWorkspace(workspace);
    setOpen(false);
    onChange?.(workspace);
    // The home screen is chosen at render from this value, and other screens
    // read it too, so a full reload is the honest way to apply it everywhere
    // at once rather than leaving half the app on the old view.
    window.location.reload();
  };

  const Icon = current === "owner" ? Briefcase : Store;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium text-ink-700 hover:bg-surface-100"
        title="Which of your jobs you are doing"
      >
        <Icon className="h-3.5 w-3.5 text-ink-500" aria-hidden />
        <span className="hidden sm:inline">{WORKSPACE_LABEL[current]}</span>
        <ChevronDown className="h-3 w-3 opacity-60" aria-hidden />
      </button>

      {open && (
        <div className="absolute right-0 top-9 z-50 w-64 rounded-lg border border-line bg-surface-0 p-1 shadow-lg">
          <div className="px-2 py-1.5 text-[11px] font-semibold text-ink-500">Working as</div>
          {(["operations", "owner"] as Workspace[]).map((workspace) => (
            <button
              key={workspace}
              onClick={() => pick(workspace)}
              className="flex w-full items-start gap-2 rounded-md px-2 py-2 text-left hover:bg-surface-100"
            >
              <span className="mt-0.5 w-4 shrink-0">
                {current === workspace && (
                  <Check className="h-3.5 w-3.5 text-brand-600" aria-hidden />
                )}
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-medium text-ink-900">
                  {WORKSPACE_LABEL[workspace]}
                </span>
                <span className="mt-0.5 block text-xs text-ink-500">
                  {WORKSPACE_HINT[workspace]}
                </span>
              </span>
            </button>
          ))}
          <p className="border-t border-line px-2 py-2 text-[11px] leading-relaxed text-ink-500">
            One account, one set of permissions. This only changes which screen you land on.
          </p>
        </div>
      )}
    </div>
  );
}
