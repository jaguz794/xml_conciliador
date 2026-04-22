import type { DashboardMetric, DashboardPayload } from "../types";

interface DashboardViewProps {
  dashboard: DashboardPayload;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("es-CO", {
    minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function MetricCard({
  title,
  metric,
  accent,
}: {
  title: string;
  metric: DashboardMetric;
  accent: "cost" | "units";
}) {
  return (
    <article className={`metric-card metric-card-${accent}`}>
      <header>
        <h3>{title}</h3>
      </header>
      <dl>
        <div>
          <dt>XML</dt>
          <dd>{formatNumber(metric.xml)}</dd>
        </div>
        <div>
          <dt>ERP</dt>
          <dd>{formatNumber(metric.erp)}</dd>
        </div>
        <div>
          <dt>{accent === "cost" ? "Diferencia bruta factura" : "Diferencia unidades"}</dt>
          <dd>{formatNumber(metric.diferencia)}</dd>
        </div>
        {accent === "cost" ? (
          <div>
            <dt>Ajuste costo AC</dt>
            <dd>{formatNumber(metric.ajuste_ac)}</dd>
          </div>
        ) : null}
        {accent === "units" ? (
          <div>
            <dt>Cantidad a devolver NP</dt>
            <dd>{formatNumber(metric.ajuste_np)}</dd>
          </div>
        ) : null}
        {accent === "units" ? (
          <div>
            <dt>Total sugerido unidades</dt>
            <dd>{formatNumber(metric.ajuste_sugerido)}</dd>
          </div>
        ) : null}
        <div>
          <dt>{accent === "cost" ? "Saldo costo por revisar" : "Saldo unidades por revisar"}</dt>
          <dd>{formatNumber(metric.saldo)}</dd>
        </div>
      </dl>
    </article>
  );
}

export function DashboardView({ dashboard }: DashboardViewProps) {
  return (
    <div className="dashboard-grid">
      <section className="hero-card">
        <div>
          <p className="eyebrow">Estado general</p>
          <h2>{dashboard.titulo}</h2>
        </div>
        <div className={`hero-status ${dashboard.requiere_validacion ? "warn" : "ok"}`}>
          {dashboard.requiere_validacion ? "Requiere revision" : "Cuadre limpio"}
        </div>
      </section>

      <section className="summary-strip">
        <article>
          <span>Total items</span>
          <strong>{dashboard.total_items}</strong>
        </article>
        <article>
          <span>Items con diferencia</span>
          <strong>{dashboard.items_con_diferencia}</strong>
        </article>
        <article>
          <span>Alertas de rescate</span>
          <strong>{dashboard.alertas_rescate}</strong>
        </article>
      </section>

      <div className="metric-grid">
        <MetricCard title="Costo" metric={dashboard.costo} accent="cost" />
        <MetricCard title="Unidades" metric={dashboard.unidades} accent="units" />
      </div>

      <section className="panel">
        <div className="panel-header stacked">
          <div>
            <h3>Conteo por estado</h3>
            <p>Resumen del cruce entre XML y ERP.</p>
          </div>
        </div>
        <div className="status-grid">
          {Object.entries(dashboard.conteos_estado).map(([status, total]) => (
            <div className="status-pill" key={status}>
              <span>{status}</span>
              <strong>{total}</strong>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
