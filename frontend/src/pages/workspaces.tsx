/* -------------------------------------------------------------------------- */
/* Screens that were separate nav entries and are really one job.              */
/*                                                                             */
/* Each of these was two to five top-level menu items. None of them was a       */
/* distinct destination: they were facets of one desk, and splitting them made  */
/* a user pick a screen before they could start work, then leave it to compare  */
/* against its neighbour.                                                       */
/*                                                                             */
/* The page components are unchanged — they are hosted as tabs. Consolidating   */
/* the menu should cost no behaviour, and anything that had to be rewritten to  */
/* be merged probably should not have been merged.                              */
/* -------------------------------------------------------------------------- */

import { Workspace } from "../components/Workspace";
import { AttendancePage } from "./AttendancePage";
import { ColdChainCompliancePage } from "./ColdChainCompliancePage";
import { IngredientsPage } from "./IngredientsPage";
import { InteractionsPage } from "./InteractionsPage";
import { ManufacturersPage } from "./ManufacturersPage";
import { PermissionMatrixPage } from "./PermissionMatrixPage";
import { ShiftRosterPage } from "./ShiftRosterPage";
import { StatutoryFilingsPage } from "./StatutoryFilingsPage";
import { StatutoryRatesPage } from "./StatutoryRatesPage";
import { SubstitutesPage } from "./SubstitutesPage";
import { TaxCodesPage } from "./TaxCodesPage";
import { TaxEbmPage } from "./TaxEbmPage";
import { TaxPaymentsPage } from "./TaxPaymentsPage";
import { TemperatureLogsPage } from "./TemperatureLogsPage";
import { TimesheetsPage } from "./TimesheetsPage";
import { UomPage } from "./UomPage";
import { UsersPage } from "./UsersPage";
import { VatPage } from "./VatPage";

/** VAT, EBM, RRA payments and tax codes are one desk, worked in that order. */
export function TaxWorkspace() {
  return (
    <Workspace
      title="Tax & compliance"
      subtitle="The VAT return, the fiscalisation record behind it, what has been paid to RRA, and the codes it is all derived from."
      tabs={[
        { id: "vat", label: "VAT return", element: <VatPage /> },
        { id: "ebm", label: "EBM audit", element: <TaxEbmPage /> },
        { id: "payments", label: "RRA payments", element: <TaxPaymentsPage /> },
        { id: "codes", label: "Tax codes", element: <TaxCodesPage /> },
      ]}
    />
  );
}

/** Readings and the compliance verdict drawn from them — never separate questions. */
export function ColdChainWorkspace() {
  return (
    <Workspace
      title="Cold chain"
      subtitle="What the sensors recorded, and whether that keeps the cold chain compliant."
      tabs={[
        { id: "logs", label: "Temperature logs", element: <TemperatureLogsPage /> },
        { id: "compliance", label: "Compliance", element: <ColdChainCompliancePage /> },
      ]}
    />
  );
}

/** Product attributes nobody navigates to on purpose — they are looked up. */
export function ReferenceDataWorkspace() {
  return (
    <Workspace
      title="Reference data"
      subtitle="The catalogue's supporting tables: who makes a medicine, what is in it, how it converts, what it interacts with and what may replace it."
      tabs={[
        { id: "manufacturers", label: "Manufacturers", element: <ManufacturersPage /> },
        { id: "ingredients", label: "Active ingredients", element: <IngredientsPage /> },
        { id: "interactions", label: "Drug interactions", element: <InteractionsPage /> },
        { id: "substitutes", label: "Substitutes", element: <SubstitutesPage /> },
        { id: "uom", label: "UoM conversions", element: <UomPage /> },
      ]}
    />
  );
}

/** Attendance, roster and timesheet are one week seen three ways. */
export function TimeWorkspace() {
  return (
    <Workspace
      title="Time & attendance"
      subtitle="Who was rostered, who actually attended, and the approved timesheet payroll is allowed to read."
      tabs={[
        { id: "attendance", label: "Attendance", element: <AttendancePage /> },
        { id: "roster", label: "Shift rosters", element: <ShiftRosterPage /> },
        { id: "timesheets", label: "Timesheets", element: <TimesheetsPage /> },
      ]}
    />
  );
}

/** A filing and the rate it was computed at are read together or not at all. */
export function StatutoryWorkspace() {
  return (
    <Workspace
      title="Statutory filings"
      subtitle="PAYE, RSSB and CBHI returns, and the rates they are calculated from."
      tabs={[
        { id: "filings", label: "Filings", element: <StatutoryFilingsPage /> },
        { id: "rates", label: "Rates", element: <StatutoryRatesPage /> },
      ]}
    />
  );
}

/** Who someone is, and what that lets them do. Two halves of one question. */
export function AccessWorkspace() {
  return (
    <Workspace
      title="Users & access"
      subtitle="The people with accounts, and the permissions each role carries."
      tabs={[
        { id: "users", label: "Users", element: <UsersPage /> },
        { id: "permissions", label: "Role permissions", element: <PermissionMatrixPage /> },
      ]}
    />
  );
}
