import { useDeferredValue, useState } from "react";

import type { TablePayload } from "../types";

interface DataTableProps {
  title: string;
  table: TablePayload;
  emptyMessage: string;
}

function formatHeader(value: string): string {
  return value
    .split("_")
    .join(" ")
    .toLowerCase()
    .replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  if (typeof value === "number") {
    return new Intl.NumberFormat("es-CO", {
      minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
      maximumFractionDigits: 2,
    }).format(value);
  }

  return String(value);
}

function cellClass(column: string, value: unknown): string {
  const normalizedColumn = column.toLowerCase();
  const normalizedValue = String(value ?? "").toUpperCase();

  if (normalizedColumn === "estado") {
    if (normalizedValue === "OK") {
      return "cell-badge cell-badge-ok";
    }
    return "cell-badge cell-badge-warn";
  }

  if (normalizedColumn === "alerta_cruce" && normalizedValue === "RESCATE CEROS") {
    return "cell-badge cell-badge-alert";
  }

  return "";
}

export function DataTable({ title, table, emptyMessage }: DataTableProps) {
  const [filter, setFilter] = useState("");
  const deferredFilter = useDeferredValue(filter);
  const normalizedFilter = deferredFilter.trim().toLowerCase();
  const hasTotals = Object.keys(table.totals ?? {}).length > 0;
  const hasSummary = (table.summary ?? []).length > 0;
  const filteredRows = table.rows.filter((row) => {
    if (!normalizedFilter) {
      return true;
    }
    return JSON.stringify(row).toLowerCase().includes(normalizedFilter);
  });

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h3>{title}</h3>
          <p>{filteredRows.length} fila(s) visibles</p>
        </div>
        <input
          className="table-filter"
          placeholder="Filtrar en la tabla"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        />
      </div>

      {filteredRows.length === 0 ? (
        <div className="empty-state compact">{emptyMessage}</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                {table.columns.map((column) => (
                  <th key={column}>{formatHeader(column)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row, index) => (
                <tr key={`${title}-${index}`}>
                  {table.columns.map((column) => (
                    <td key={`${title}-${index}-${column}`}>
                      <span className={cellClass(column, row[column])}>
                        {formatValue(row[column])}
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
            {hasTotals ? (
              <tfoot>
                <tr className="table-total-row">
                  {table.columns.map((column, index) => {
                    const totalValue = table.totals[column];
                    const fallbackLabel = index === 0 ? "TOTAL" : "";
                    return (
                      <td key={`${title}-total-${column}`}>
                        <strong>{formatValue(totalValue ?? fallbackLabel)}</strong>
                      </td>
                    );
                  })}
                </tr>
              </tfoot>
            ) : null}
          </table>
        </div>
      )}

      {hasSummary ? (
        <div className="table-summary-strip">
          {table.summary.map((item) => (
            <article key={`${title}-${item.label}`} className="table-summary-card">
              <span>{item.label}</span>
              <strong>{formatValue(item.value)}</strong>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
