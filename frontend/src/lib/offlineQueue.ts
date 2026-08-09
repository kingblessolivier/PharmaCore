/** The counter keeps trading when the network does not.
 *
 * `docs/19-platform-architecture-decisions.md` §2 calls for an offline-first
 * till and nothing implemented it, so a dropped connection stopped the pharmacy
 * selling. In a Kigali pharmacy that is not hypothetical.
 *
 * The shape:
 *
 * 1. A completed sale is written to IndexedDB **first**, then sent. If the send
 *    fails the sale is already safe on disk — the opposite order loses sales.
 * 2. Each queued sale carries a client-generated `client_reference`. The server
 *    treats a repeat of that key as a no-op returning the original sale, so a
 *    flaky connection that retries five times still sells the goods once.
 * 3. The queue drains on reconnect and on an interval, because `online` fires
 *    when the interface comes up, not when the server is actually reachable.
 *
 * IndexedDB rather than localStorage: sales are structured, can be numerous over
 * a long outage, and localStorage is synchronous — blocking the till's main
 * thread while a queue flushes is the one thing a counter cannot tolerate.
 */

const DB_NAME = "pharmacore-counter";
const DB_VERSION = 1;
const STORE = "queued-sales";

export interface QueuedSaleLine {
  product: number;
  quantity: number;
  /** Which packaging level the quantity counts — a box, a strip, a tablet.
   *  Absent means the product's default sale unit, which is how every line
   *  behaved before units existed. */
  unit?: string;
  unit_price: string;
  tax_rate?: string;
  label?: string;
}

export interface QueuedSale {
  client_reference: string;
  organization: number;
  items: QueuedSaleLine[];
  payments: { method: string; amount: string }[];
  dispensing?: Record<string, unknown>;
  /** The card the cover was quoted against, so the sale and the claim the
   *  scheme settles can be reconciled rather than matched up by hand later. */
  member_number?: string;
  total: string;
  queued_at: string;
  /** Attempts so far — surfaced so a stuck sale is visible, not silently retried. */
  attempts: number;
  last_error?: string;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "client_reference" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function withStore<T>(
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const db = await openDb();
  return new Promise<T>((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    const request = fn(tx.objectStore(STORE));
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    tx.oncomplete = () => db.close();
  });
}

/** A key the till owns, so a replay is recognisable as one. */
export function newClientReference(): string {
  const cryptoObj = globalThis.crypto;
  if (cryptoObj && "randomUUID" in cryptoObj) return cryptoObj.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

export async function enqueue(sale: QueuedSale): Promise<void> {
  await withStore("readwrite", (s) => s.put(sale));
}

export async function queued(): Promise<QueuedSale[]> {
  const rows = await withStore<QueuedSale[]>(
    "readonly",
    (s) => s.getAll() as IDBRequest<QueuedSale[]>,
  );
  return rows.sort((a, b) => a.queued_at.localeCompare(b.queued_at));
}

export async function dequeue(reference: string): Promise<void> {
  await withStore("readwrite", (s) => s.delete(reference));
}

export async function queueSize(): Promise<number> {
  try {
    return (await queued()).length;
  } catch {
    return 0;
  }
}

export interface FlushResult {
  synced: number;
  failed: number;
  remaining: number;
}

/**
 * Push every queued sale at the server.
 *
 * Sales are sent oldest-first and one at a time: the till's own sequence is the
 * order the shop actually traded in, and a later sale is not more important than
 * an earlier one that is stuck.
 */
export async function flush(post: (sale: QueuedSale) => Promise<unknown>): Promise<FlushResult> {
  let synced = 0;
  let failed = 0;

  for (const sale of await queued()) {
    try {
      await post(sale);
      await dequeue(sale.client_reference);
      synced += 1;
    } catch (error) {
      failed += 1;
      // Keep it queued and record why. A sale that cannot be replayed is money
      // that left the shelf, so it needs a person — not a silent drop.
      await enqueue({
        ...sale,
        attempts: sale.attempts + 1,
        last_error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  return { synced, failed, remaining: await queueSize() };
}

/** Wire the queue to the browser's connectivity signals. Returns a teardown. */
export function watchConnectivity(onChange: (online: boolean) => void): () => void {
  const up = () => onChange(true);
  const down = () => onChange(false);
  window.addEventListener("online", up);
  window.addEventListener("offline", down);
  return () => {
    window.removeEventListener("online", up);
    window.removeEventListener("offline", down);
  };
}
