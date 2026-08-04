import rwandaData from "../lib/rwanda.json";
import { SelectField } from "./ui";

// data.json shape: Province → District → Sector → Cell → [Village]
type Tree = Record<string, Record<string, Record<string, Record<string, string[]>>>>;
const RWANDA = rwandaData as Tree;

export interface RwandaValue {
  province: string;
  district: string;
  sector: string;
  cell: string;
  village: string;
}

const keysOf = (o: object | undefined): string[] => (o ? Object.keys(o) : []);

/** Cascading Province → District → Sector → Cell → Village selects, driven by the
 * bundled Rwanda administrative dataset. Selecting a level resets the ones below. */
export function RwandaLocation({
  value,
  onChange,
}: {
  value: RwandaValue;
  onChange: (v: RwandaValue) => void;
}) {
  const { province, district, sector, cell, village } = value;

  const districts = keysOf(RWANDA[province]);
  const sectors = keysOf(RWANDA[province]?.[district]);
  const cells = keysOf(RWANDA[province]?.[district]?.[sector]);
  const villages = RWANDA[province]?.[district]?.[sector]?.[cell] ?? [];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <SelectField
        label="Province"
        value={province}
        onChange={(e) =>
          onChange({ province: e.target.value, district: "", sector: "", cell: "", village: "" })
        }
      >
        <option value="">— select —</option>
        {keysOf(RWANDA).map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </SelectField>

      <SelectField
        label="District"
        value={district}
        disabled={!province}
        onChange={(e) =>
          onChange({ ...value, district: e.target.value, sector: "", cell: "", village: "" })
        }
      >
        <option value="">— select —</option>
        {districts.map((d) => (
          <option key={d} value={d}>
            {d}
          </option>
        ))}
      </SelectField>

      <SelectField
        label="Sector"
        value={sector}
        disabled={!district}
        onChange={(e) => onChange({ ...value, sector: e.target.value, cell: "", village: "" })}
      >
        <option value="">— select —</option>
        {sectors.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </SelectField>

      <SelectField
        label="Cell"
        value={cell}
        disabled={!sector}
        onChange={(e) => onChange({ ...value, cell: e.target.value, village: "" })}
      >
        <option value="">— select —</option>
        {cells.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </SelectField>

      <SelectField
        label="Village"
        value={village}
        disabled={!cell}
        onChange={(e) => onChange({ ...value, village: e.target.value })}
      >
        <option value="">— select —</option>
        {villages.map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </SelectField>
    </div>
  );
}
