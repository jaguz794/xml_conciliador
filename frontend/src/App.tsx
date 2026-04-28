import { startTransition, useEffect, useState, type FormEvent } from "react";

import {
  fetchDatabaseHealth,
  fetchHealth,
  fetchInvoices,
  fetchReconciliation,
  scanFolder,
  uploadInvoiceFile,
} from "./api";
import { DashboardView } from "./components/DashboardView";
import { DataTable } from "./components/DataTable";
import type {
  ConciliacionResponse,
  DatabaseHealthResponse,
  FacturaDisponible,
  HealthResponse,
  ProcessedBatchResponse,
} from "./types";

type TabKey = "dashboard" | "detalle" | "ac" | "np";

const TAB_OPTIONS: Array<{ key: TabKey; label: string }> = [
  { key: "dashboard", label: "Dashboard" },
  { key: "detalle", label: "Cruce ERP/XML" },
  { key: "ac", label: "AC | Ajuste costo" },
  { key: "np", label: "NP | Nota proveedor" },
];

function formatBatchMessage(result: ProcessedBatchResponse): string {
  if (result.total_procesadas === 0) {
    return "No se detectaron XML validos en el archivo o carpeta.";
  }
  return `Se procesaron ${result.total_procesadas} factura(s) correctamente.`;
}

function formatDisplayNumber(value: number): string {
  return new Intl.NumberFormat("es-CO", {
    minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function App() {
  const [nit, setNit] = useState("");
  const [factura, setFactura] = useState("");
  const [activeTab, setActiveTab] = useState<TabKey>("dashboard");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [databaseHealth, setDatabaseHealth] = useState<DatabaseHealthResponse | null>(null);
  const [availableInvoices, setAvailableInvoices] = useState<FacturaDisponible[]>([]);
  const [result, setResult] = useState<ConciliacionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [scanningFolder, setScanningFolder] = useState(false);
  const [refreshingResult, setRefreshingResult] = useState(false);

  useEffect(() => {
    void bootstrap();
  }, []);

  async function bootstrap() {
    try {
      const apiHealth = await fetchHealth();
      startTransition(() => {
        setHealth(apiHealth);
      });
    } catch (bootstrapError) {
      setError(bootstrapError instanceof Error ? bootstrapError.message : "No fue posible iniciar la interfaz.");
      return;
    }

    try {
      const dbHealth = await fetchDatabaseHealth();
      startTransition(() => {
        setDatabaseHealth(dbHealth);
      });
    } catch (databaseError) {
      setError(databaseError instanceof Error ? databaseError.message : "La base de datos no esta disponible.");
    }

    try {
      const invoices = await fetchInvoices({ limit: 15 });
      startTransition(() => {
        setAvailableInvoices(invoices);
      });
    } catch (invoicesError) {
      setError(
        invoicesError instanceof Error
          ? invoicesError.message
          : "No fue posible cargar las facturas recientes.",
      );
    }
  }

  async function refreshInvoices() {
    const invoices = await fetchInvoices({ limit: 15 });
    startTransition(() => {
      setAvailableInvoices(invoices);
    });
  }

  async function runSearch(searchNit = nit, searchFactura = factura, forceRefresh = false) {
    if (!searchNit.trim() || !searchFactura.trim()) {
      setError("Debes ingresar el NIT y el numero de factura.");
      return;
    }

    if (forceRefresh) {
      setRefreshingResult(true);
    } else {
      setLoading(true);
    }
    setError("");

    try {
      const payload = await fetchReconciliation(searchNit.trim(), searchFactura.trim(), forceRefresh);
      startTransition(() => {
        setNit(searchNit.trim());
        setFactura(searchFactura.trim());
        setResult(payload);
        setActiveTab("dashboard");
      });
    } catch (searchError) {
      setResult(null);
      setError(searchError instanceof Error ? searchError.message : "No fue posible consultar la factura.");
    } finally {
      setLoading(false);
      setRefreshingResult(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runSearch();
  }

  async function handleUpload() {
    if (!selectedFile) {
      setUploadStatus("Selecciona primero un archivo XML o ZIP.");
      return;
    }

    setUploading(true);
    setUploadStatus("");

    try {
      const batch = await uploadInvoiceFile(selectedFile);
      setUploadStatus(formatBatchMessage(batch));
      setSelectedFile(null);
      await refreshInvoices();

      if (batch.procesadas[0]) {
        await runSearch(batch.procesadas[0].nit, batch.procesadas[0].factura);
      }
    } catch (uploadError) {
      setUploadStatus(uploadError instanceof Error ? uploadError.message : "No fue posible cargar el archivo.");
    } finally {
      setUploading(false);
    }
  }

  async function handleScanFolder() {
    setScanningFolder(true);
    setUploadStatus("");

    try {
      const batch = await scanFolder(false);
      setUploadStatus(formatBatchMessage(batch));
      await refreshInvoices();
    } catch (scanError) {
      setUploadStatus(scanError instanceof Error ? scanError.message : "No fue posible escanear la carpeta.");
    } finally {
      setScanningFolder(false);
    }
  }

  const acEmptyMessage = result
    ? result.ac.rows.length === 0 && Math.abs(result.dashboard.costo.saldo) >= 1
      ? `No hay ajustes AC clasificados para esta factura. La diferencia quedo en saldo por revisar (${formatDisplayNumber(result.dashboard.costo.saldo)}). Revisa el Cruce ERP/XML.`
      : "No se encontraron ajustes de costo en esta factura."
    : "No se encontraron ajustes de costo en esta factura.";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <header className="brand-card">
          <div className="brand-top">
            <div className="brand-copy">
              <p className="eyebrow">Supermercados Popular</p>
              <h1>Conciliador XML y ERP</h1>
              <p>
                Consulta por factura y NIT, procesa XML o ZIP y revisa dashboard, cruce, ajuste costo y nota
                proveedor desde el navegador.
              </p>
            </div>
            <div className="brand-logo-shell">
              <img className="brand-logo" src="/logo-popular.png" alt="Logo Supermercados Popular" />
            </div>
          </div>
        </header>

        <section className="panel">
          <div className="panel-header stacked">
            <div>
              <h3>Buscar factura</h3>
              <p>El backend responde con Dashboard, Cruce ERP/XML, Ajuste costo y Nota proveedor.</p>
            </div>
          </div>
          <form className="search-form" onSubmit={handleSubmit}>
            <label>
              <span>NIT</span>
              <input value={nit} onChange={(event) => setNit(event.target.value)} placeholder="Ej. 830002366" />
            </label>
            <label>
              <span>Numero de factura</span>
              <input
                value={factura}
                onChange={(event) => setFactura(event.target.value)}
                placeholder="Ej. TD50395942"
              />
            </label>
            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? "Consultando..." : "Consultar"}
            </button>
          </form>
        </section>

        <section className="panel">
          <div className="panel-header stacked">
            <div>
              <h3>Ingesta</h3>
              <p>Sube un XML/ZIP o lee la carpeta configurada del backend.</p>
            </div>
          </div>

          <label className="file-picker">
            <span>{selectedFile ? selectedFile.name : "Seleccionar XML o ZIP"}</span>
            <input
              type="file"
              accept=".xml,.zip"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            />
          </label>

          <div className="button-stack">
            <button className="primary-button" type="button" onClick={handleUpload} disabled={uploading}>
              {uploading ? "Procesando..." : "Subir y procesar"}
            </button>
            <button className="secondary-button" type="button" onClick={handleScanFolder} disabled={scanningFolder}>
              {scanningFolder ? "Escaneando..." : "Escanear carpeta de entrada"}
            </button>
          </div>

          {uploadStatus ? <p className="helper-text">{uploadStatus}</p> : null}
        </section>

        <section className="panel">
          <div className="panel-header stacked">
            <div>
              <h3>Estado de servicios</h3>
            </div>
          </div>
          <div className="health-list">
            <article>
              <span>API</span>
              <strong>{health?.ok ? "Disponible" : "Pendiente"}</strong>
            </article>
            <article>
              <span>Base de datos</span>
              <strong>{databaseHealth?.ok ? "Conectada" : "Pendiente"}</strong>
            </article>
            <article>
              <span>Host BD</span>
              <strong>{databaseHealth?.host ?? "-"}</strong>
            </article>
            <article>
              <span>Base</span>
              <strong>{databaseHealth?.database ?? "-"}</strong>
            </article>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header stacked">
            <div>
              <h3>Facturas almacenadas</h3>
              <p>Atajos rapidos desde `factura_xml_detalle`.</p>
            </div>
          </div>
          <div className="invoice-list">
            {availableInvoices.map((invoice) => (
              <button
                key={`${invoice.nit}-${invoice.factura}`}
                className="invoice-chip"
                type="button"
                onClick={() => void runSearch(invoice.nit, invoice.factura)}
              >
                <span>{invoice.factura}</span>
                <small>{invoice.nit}</small>
              </button>
            ))}
            {availableInvoices.length === 0 ? (
              <div className="empty-state compact">Aun no hay facturas visibles en la tabla XML.</div>
            ) : null}
          </div>
        </section>
      </aside>

      <main className="content-panel">
        {error ? <div className="error-banner">{error}</div> : null}

        {result ? (
          <>
            <section className="result-header">
              <div>
                <p className="eyebrow">Consulta activa</p>
                <h2>
                  Factura {result.factura} | NIT {result.nit}
                </h2>
              </div>
              <div className="result-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => void runSearch(result.nit, result.factura, true)}
                  disabled={refreshingResult}
                >
                  {refreshingResult ? "Reprocesando..." : "Reprocesar"}
                </button>
                <div className="result-tag">
                  {result.dashboard.requiere_validacion ? "Requiere revision manual" : "Cuadre limpio"}
                </div>
              </div>
            </section>

            <nav className="tab-bar" aria-label="Pestanas de conciliacion">
              {TAB_OPTIONS.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  className={activeTab === tab.key ? "tab-button active" : "tab-button"}
                  onClick={() => setActiveTab(tab.key)}
                >
                  {tab.label}
                </button>
              ))}
            </nav>

            {activeTab === "dashboard" ? <DashboardView dashboard={result.dashboard} /> : null}
            {activeTab === "detalle" ? (
              <DataTable
                title="Cruce detallado ERP vs XML"
                table={result.detalle}
                emptyMessage="No hay filas de detalle para esta conciliacion."
              />
            ) : null}
            {activeTab === "ac" ? (
              <DataTable
                title="AC - Ajuste costo"
                table={result.ac}
                emptyMessage={acEmptyMessage}
              />
            ) : null}
            {activeTab === "np" ? (
              <DataTable
                title="NP - Nota proveedor"
                table={result.np}
                emptyMessage="No se encontraron cantidades pendientes por devolver en esta factura."
              />
            ) : null}
          </>
        ) : (
          <section className="empty-state">
            <p className="eyebrow">Listo para consultar</p>
            <h2>Busca una factura o procesa un XML para verla aqui.</h2>
            <p>
              La pantalla principal mostrara el dashboard y las tablas del cruce directamente en el navegador.
            </p>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
