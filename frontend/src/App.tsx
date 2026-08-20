import { startTransition, useEffect, useState, type FormEvent } from "react";

import {
  ApiError,
  changePassword,
  clearStoredAuthToken,
  createUser,
  fetchCurrentUser,
  fetchDatabaseHealth,
  fetchHealth,
  fetchInvoices,
  fetchReconciliation,
  fetchUserActivity,
  fetchUserDailyConsultations,
  fetchUsers,
  getStoredAuthToken,
  login,
  logout,
  persistAuthToken,
  scanFolder,
  updateUser,
  uploadInvoiceFile,
} from "./api";
import { DashboardView } from "./components/DashboardView";
import { DataTable } from "./components/DataTable";
import type {
  AuthUser,
  ConciliacionResponse,
  DatabaseHealthResponse,
  FacturaDisponible,
  HealthResponse,
  ProcessedBatchResponse,
  UserActivityItem,
  UserDailyConsultationItem,
  UserSummary,
} from "./types";

type TabKey = "dashboard" | "detalle" | "ac" | "np";
type WorkspaceView = "conciliador" | "usuarios";

const TAB_OPTIONS: Array<{ key: TabKey; label: string }> = [
  { key: "dashboard", label: "Dashboard" },
  { key: "detalle", label: "Cruce ERP/XML" },
  { key: "ac", label: "AC | Ajuste costo" },
  { key: "np", label: "NP | Nota proveedor" },
];

const EMPTY_CREATE_USER_FORM = {
  username: "",
  full_name: "",
  password: "",
  is_admin: false,
  is_active: true,
  must_change_password: true,
};

const EMPTY_EDIT_USER_FORM = {
  full_name: "",
  password: "",
  is_admin: false,
  is_active: true,
  must_change_password: false,
};

const EMPTY_PASSWORD_CHANGE_FORM = {
  current_password: "",
  new_password: "",
  confirm_password: "",
};

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

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "medium",
  }).format(new Date(`${value}T00:00:00`));
}

function App() {
  const [authToken, setAuthToken] = useState<string | null>(() => getStoredAuthToken());
  const [sessionReady, setSessionReady] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);

  const [nit, setNit] = useState("");
  const [factura, setFactura] = useState("");
  const [activeTab, setActiveTab] = useState<TabKey>("dashboard");
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>("conciliador");
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

  const [managedUsers, setManagedUsers] = useState<UserSummary[]>([]);
  const [selectedManagedUserId, setSelectedManagedUserId] = useState<number | null>(null);
  const [userActivity, setUserActivity] = useState<UserActivityItem[]>([]);
  const [userDailyConsultations, setUserDailyConsultations] = useState<UserDailyConsultationItem[]>([]);
  const [loadingAdminData, setLoadingAdminData] = useState(false);
  const [userAdminStatus, setUserAdminStatus] = useState("");
  const [creatingUser, setCreatingUser] = useState(false);
  const [savingUserChanges, setSavingUserChanges] = useState(false);
  const [newUserForm, setNewUserForm] = useState(EMPTY_CREATE_USER_FORM);
  const [userEditForm, setUserEditForm] = useState(EMPTY_EDIT_USER_FORM);
  const [passwordChangeForm, setPasswordChangeForm] = useState(EMPTY_PASSWORD_CHANGE_FORM);
  const [passwordChangeStatus, setPasswordChangeStatus] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);

  const selectedManagedUser =
    managedUsers.find((user) => user.id === selectedManagedUserId) ?? null;

  useEffect(() => {
    void bootstrapPublicServices();
  }, []);

  useEffect(() => {
    void restoreStoredSession();
  }, []);

  useEffect(() => {
    if (selectedManagedUser) {
      setUserEditForm({
        full_name: selectedManagedUser.full_name,
        password: "",
        is_admin: selectedManagedUser.is_admin,
        is_active: selectedManagedUser.is_active,
        must_change_password: selectedManagedUser.must_change_password,
      });
      return;
    }

    setUserEditForm(EMPTY_EDIT_USER_FORM);
  }, [selectedManagedUser]);

  async function bootstrapPublicServices() {
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
  }

  async function restoreStoredSession() {
    const storedToken = getStoredAuthToken();
    if (!storedToken) {
      setSessionReady(true);
      return;
    }

    try {
      const user = await fetchCurrentUser(storedToken);
      startTransition(() => {
        setAuthToken(storedToken);
        setCurrentUser(user);
      });
      if (!user.must_change_password) {
        await refreshInvoices(storedToken);
        if (user.is_admin) {
          await refreshAdminData(storedToken);
        }
      }
    } catch {
      clearSessionState();
      setAuthMessage("La sesion guardada ya no es valida. Ingresa nuevamente.");
    } finally {
      setSessionReady(true);
    }
  }

  function clearSessionState() {
    clearStoredAuthToken();
    startTransition(() => {
      setAuthToken(null);
      setCurrentUser(null);
      setAvailableInvoices([]);
      setResult(null);
      setManagedUsers([]);
      setSelectedManagedUserId(null);
      setUserActivity([]);
      setUserDailyConsultations([]);
      setWorkspaceView("conciliador");
      setPasswordChangeForm(EMPTY_PASSWORD_CHANGE_FORM);
    });
  }

  function handleProtectedError(rawError: unknown, fallbackMessage: string): void {
    if (rawError instanceof ApiError && rawError.status === 401) {
      clearSessionState();
      setError("La sesion vencio o fue cerrada. Ingresa nuevamente.");
      return;
    }

    setError(rawError instanceof Error ? rawError.message : fallbackMessage);
  }

  async function refreshInvoices(tokenOverride?: string) {
    const token = tokenOverride ?? authToken;
    if (!token) {
      return;
    }

    try {
      const invoices = await fetchInvoices(token, { limit: 15 });
      startTransition(() => {
        setAvailableInvoices(invoices);
      });
    } catch (invoiceError) {
      handleProtectedError(invoiceError, "No fue posible cargar las facturas recientes.");
    }
  }

  async function refreshAdminData(tokenOverride?: string, focusUserId?: number | null) {
    const token = tokenOverride ?? authToken;
    if (!token) {
      return;
    }

    setLoadingAdminData(true);
    try {
      const users = await fetchUsers(token);
      const targetUserId = focusUserId ?? selectedManagedUserId ?? users[0]?.id ?? null;
      const [activity, dailyConsultations] = targetUserId
        ? await Promise.all([
            fetchUserActivity(token, targetUserId),
            fetchUserDailyConsultations(token, targetUserId),
          ])
        : [[], []];

      startTransition(() => {
        setManagedUsers(users);
        setSelectedManagedUserId(targetUserId);
        setUserActivity(activity);
        setUserDailyConsultations(dailyConsultations);
      });
    } catch (adminError) {
      handleProtectedError(adminError, "No fue posible cargar la auditoria de usuarios.");
    } finally {
      setLoadingAdminData(false);
    }
  }

  async function loadActivityForUser(userId: number) {
    if (!authToken) {
      return;
    }

    setLoadingAdminData(true);
    try {
      const [activity, dailyConsultations] = await Promise.all([
        fetchUserActivity(authToken, userId),
        fetchUserDailyConsultations(authToken, userId),
      ]);
      startTransition(() => {
        setSelectedManagedUserId(userId);
        setUserActivity(activity);
        setUserDailyConsultations(dailyConsultations);
      });
    } catch (activityError) {
      handleProtectedError(activityError, "No fue posible cargar la actividad del usuario.");
    } finally {
      setLoadingAdminData(false);
    }
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!loginUsername.trim() || !loginPassword.trim()) {
      setAuthMessage("Debes ingresar usuario y contrasena.");
      return;
    }

    setAuthLoading(true);
    setAuthMessage("");
    setError("");

    try {
      const loginResult = await login(loginUsername, loginPassword);
      persistAuthToken(loginResult.token);
      startTransition(() => {
        setAuthToken(loginResult.token);
        setCurrentUser(loginResult.user);
        setWorkspaceView("conciliador");
      });
      setAuthMessage("");
      setPasswordChangeStatus("");
      setLoginPassword("");
      setPasswordChangeForm((current) => ({
        ...current,
        current_password: loginPassword,
      }));
      if (!loginResult.user.must_change_password) {
        await refreshInvoices(loginResult.token);
        if (loginResult.user.is_admin) {
          await refreshAdminData(loginResult.token);
        }
      }
    } catch (loginError) {
      setAuthMessage(loginError instanceof Error ? loginError.message : "No fue posible iniciar sesion.");
    } finally {
      setAuthLoading(false);
      setSessionReady(true);
    }
  }

  async function handleLogout() {
    if (authToken) {
      try {
        await logout(authToken);
      } catch {
        // Si la sesion ya vencio igualmente limpiamos el estado local.
      }
    }

    clearSessionState();
    setAuthMessage("Sesion cerrada correctamente.");
  }

  async function runSearch(searchNit = nit, searchFactura = factura, forceRefresh = false) {
    if (!authToken) {
      setError("Debes iniciar sesion antes de consultar.");
      return;
    }

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
      const payload = await fetchReconciliation(authToken, searchNit.trim(), searchFactura.trim(), forceRefresh);
      startTransition(() => {
        setNit(searchNit.trim());
        setFactura(searchFactura.trim());
        setResult(payload);
        setActiveTab("dashboard");
        setWorkspaceView("conciliador");
      });
      if (currentUser?.is_admin) {
        await refreshAdminData(authToken, selectedManagedUserId);
      }
    } catch (searchError) {
      setResult(null);
      handleProtectedError(searchError, "No fue posible consultar la factura.");
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
    if (!authToken) {
      setUploadStatus("Debes iniciar sesion antes de procesar archivos.");
      return;
    }

    if (!selectedFile) {
      setUploadStatus("Selecciona primero un archivo XML o ZIP.");
      return;
    }

    setUploading(true);
    setUploadStatus("");

    try {
      const batch = await uploadInvoiceFile(authToken, selectedFile);
      setUploadStatus(formatBatchMessage(batch));
      setSelectedFile(null);
      await refreshInvoices(authToken);

      if (currentUser?.is_admin) {
        await refreshAdminData(authToken, selectedManagedUserId);
      }

      if (batch.procesadas[0]) {
        await runSearch(batch.procesadas[0].nit, batch.procesadas[0].factura);
      }
    } catch (uploadError) {
      if (uploadError instanceof ApiError && uploadError.status === 401) {
        handleProtectedError(uploadError, "La sesion vencio.");
      } else {
        setUploadStatus(uploadError instanceof Error ? uploadError.message : "No fue posible cargar el archivo.");
      }
    } finally {
      setUploading(false);
    }
  }

  async function handleScanFolder() {
    if (!authToken) {
      setUploadStatus("Debes iniciar sesion antes de escanear la carpeta.");
      return;
    }

    setScanningFolder(true);
    setUploadStatus("");

    try {
      const batch = await scanFolder(authToken, false);
      setUploadStatus(formatBatchMessage(batch));
      await refreshInvoices(authToken);
      if (currentUser?.is_admin) {
        await refreshAdminData(authToken, selectedManagedUserId);
      }
    } catch (scanError) {
      if (scanError instanceof ApiError && scanError.status === 401) {
        handleProtectedError(scanError, "La sesion vencio.");
      } else {
        setUploadStatus(scanError instanceof Error ? scanError.message : "No fue posible escanear la carpeta.");
      }
    } finally {
      setScanningFolder(false);
    }
  }

  async function handleCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!authToken) {
      return;
    }

    setCreatingUser(true);
    setUserAdminStatus("");

    try {
      const createdUser = await createUser(authToken, newUserForm);
      setNewUserForm(EMPTY_CREATE_USER_FORM);
      setUserAdminStatus(`Usuario ${createdUser.username} creado correctamente.`);
      await refreshAdminData(authToken, createdUser.id);
    } catch (userError) {
      if (userError instanceof ApiError && userError.status === 401) {
        handleProtectedError(userError, "La sesion vencio.");
      } else {
        setUserAdminStatus(userError instanceof Error ? userError.message : "No fue posible crear el usuario.");
      }
    } finally {
      setCreatingUser(false);
    }
  }

  async function handleUpdateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!authToken || !selectedManagedUser) {
      return;
    }

    setSavingUserChanges(true);
    setUserAdminStatus("");

    try {
      const updatedUser = await updateUser(authToken, selectedManagedUser.id, {
        full_name: userEditForm.full_name,
        password: userEditForm.password.trim() || undefined,
        is_admin: userEditForm.is_admin,
        is_active: userEditForm.is_active,
        must_change_password: userEditForm.must_change_password,
      });

      if (currentUser && currentUser.id === updatedUser.id) {
        startTransition(() => {
          setCurrentUser(updatedUser);
        });
      }

      setUserAdminStatus(`Usuario ${updatedUser.username} actualizado correctamente.`);
      await refreshAdminData(authToken, updatedUser.id);
    } catch (userError) {
      if (userError instanceof ApiError && userError.status === 401) {
        handleProtectedError(userError, "La sesion vencio.");
      } else {
        setUserAdminStatus(userError instanceof Error ? userError.message : "No fue posible actualizar el usuario.");
      }
    } finally {
      setSavingUserChanges(false);
    }
  }

  async function handleChangePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!authToken || !currentUser) {
      return;
    }

    if (!passwordChangeForm.current_password.trim() || !passwordChangeForm.new_password.trim()) {
      setPasswordChangeStatus("Debes ingresar la contrasena actual y la nueva.");
      return;
    }

    if (passwordChangeForm.new_password !== passwordChangeForm.confirm_password) {
      setPasswordChangeStatus("La confirmacion de la nueva contrasena no coincide.");
      return;
    }

    setChangingPassword(true);
    setPasswordChangeStatus("");

    try {
      const updatedUser = await changePassword(
        authToken,
        passwordChangeForm.current_password,
        passwordChangeForm.new_password,
      );
      startTransition(() => {
        setCurrentUser(updatedUser);
        setPasswordChangeForm(EMPTY_PASSWORD_CHANGE_FORM);
      });
      setPasswordChangeStatus("Contrasena actualizada correctamente.");

      await refreshInvoices(authToken);
      if (updatedUser.is_admin) {
        await refreshAdminData(authToken, updatedUser.id);
      }
    } catch (passwordError) {
      if (passwordError instanceof ApiError && passwordError.status === 401) {
        handleProtectedError(passwordError, "La sesion vencio.");
      } else {
        setPasswordChangeStatus(
          passwordError instanceof Error ? passwordError.message : "No fue posible cambiar la contrasena.",
        );
      }
    } finally {
      setChangingPassword(false);
    }
  }

  const passwordChangeFormPanel = (
    <form className="search-form" onSubmit={handleChangePassword}>
      <label>
        <span>Contrasena actual</span>
        <input
          type="password"
          value={passwordChangeForm.current_password}
          onChange={(event) =>
            setPasswordChangeForm((current) => ({ ...current, current_password: event.target.value }))
          }
          placeholder="Ingresa tu contrasena actual"
        />
      </label>
      <label>
        <span>Nueva contrasena</span>
        <input
          type="password"
          value={passwordChangeForm.new_password}
          onChange={(event) =>
            setPasswordChangeForm((current) => ({ ...current, new_password: event.target.value }))
          }
          placeholder="Minimo 8 caracteres"
        />
      </label>
      <label>
        <span>Confirmar nueva contrasena</span>
        <input
          type="password"
          value={passwordChangeForm.confirm_password}
          onChange={(event) =>
            setPasswordChangeForm((current) => ({ ...current, confirm_password: event.target.value }))
          }
          placeholder="Repite la nueva contrasena"
        />
      </label>
      <button className="primary-button" type="submit" disabled={changingPassword}>
        {changingPassword ? "Guardando..." : "Cambiar contrasena"}
      </button>
    </form>
  );

  const acEmptyMessage = result
    ? result.ac.rows.length === 0 && Math.abs(result.dashboard.costo.saldo) >= 1
      ? `No hay ajustes AC clasificados para esta factura. La diferencia quedo en saldo por revisar (${formatDisplayNumber(result.dashboard.costo.saldo)}). Revisa el Cruce ERP/XML.`
      : "No se encontraron ajustes de costo en esta factura."
    : "No se encontraron ajustes de costo en esta factura.";

  if (!sessionReady) {
    return (
      <div className="auth-shell">
        <section className="brand-card auth-card">
          <p className="eyebrow">Supermercados Popular</p>
          <h1>Conciliador XML y ERP</h1>
          <p>Restaurando sesion y preparando la aplicacion.</p>
        </section>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <div className="auth-shell">
        <section className="brand-card auth-card">
          <div className="brand-copy">
            <p className="eyebrow">Supermercados Popular</p>
            <h1>Conciliador XML y ERP</h1>
            <p>
              Ingresa con tu usuario para consultar facturas, procesar XML y dejar trazabilidad de quien entra y
              cuantas consultas realiza.
            </p>
          </div>

          <form className="search-form auth-form" onSubmit={handleLogin}>
            <label>
              <span>Usuario</span>
              <input
                value={loginUsername}
                onChange={(event) => setLoginUsername(event.target.value)}
                placeholder="Ej. analista.facturas"
              />
            </label>
            <label>
              <span>Contrasena</span>
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
                placeholder="Ingresa tu contrasena"
              />
            </label>
            <button className="primary-button" type="submit" disabled={authLoading}>
              {authLoading ? "Ingresando..." : "Iniciar sesion"}
            </button>
          </form>

          {authMessage ? <p className="helper-text">{authMessage}</p> : null}
          {error ? <div className="error-banner">{error}</div> : null}

          <div className="health-list auth-health">
            <article>
              <span>API</span>
              <strong>{health?.ok ? "Disponible" : "Pendiente"}</strong>
            </article>
            <article>
              <span>Base de datos</span>
              <strong>{databaseHealth?.ok ? "Conectada" : "Pendiente"}</strong>
            </article>
          </div>
        </section>
      </div>
    );
  }

  if (currentUser.must_change_password) {
    return (
      <div className="auth-shell">
        <section className="brand-card auth-card">
          <div className="brand-copy">
            <p className="eyebrow">Cambio obligatorio</p>
            <h1>Actualiza tu contrasena</h1>
            <p>
              Tu usuario fue creado o reiniciado con una contrasena temporal. Debes cambiarla antes de consultar
              facturas o procesar archivos.
            </p>
            <p>
              Usuario actual: <strong>{currentUser.username}</strong>
            </p>
          </div>

          {passwordChangeFormPanel}

          {passwordChangeStatus ? <p className="helper-text">{passwordChangeStatus}</p> : null}

          <button className="secondary-button" type="button" onClick={handleLogout}>
            Cerrar sesion
          </button>
        </section>
      </div>
    );
  }

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

        <section className="panel session-card">
          <div className="panel-header">
            <div>
              <h3>Sesion actual</h3>
              <p>
                {currentUser.full_name} ({currentUser.username})
              </p>
            </div>
            <button className="secondary-button" type="button" onClick={handleLogout}>
              Cerrar sesion
            </button>
          </div>
          <div className="session-meta">
            <article>
              <span>Perfil</span>
              <strong>{currentUser.is_admin ? "Administrador" : "Consulta"}</strong>
            </article>
            <article>
              <span>Clave</span>
              <strong>{currentUser.must_change_password ? "Cambio pendiente" : "Actualizada"}</strong>
            </article>
            <article>
              <span>Ultimo ingreso</span>
              <strong>{formatDateTime(currentUser.last_login_at)}</strong>
            </article>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header stacked">
            <div>
              <h3>Cambiar contrasena</h3>
              <p>Actualiza tu clave personal cuando lo necesites.</p>
            </div>
          </div>
          {passwordChangeFormPanel}
          {passwordChangeStatus ? <p className="helper-text">{passwordChangeStatus}</p> : null}
        </section>

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
        {currentUser.is_admin ? (
          <nav className="workspace-switcher" aria-label="Secciones de trabajo">
            <button
              type="button"
              className={workspaceView === "conciliador" ? "tab-button active" : "tab-button"}
              onClick={() => setWorkspaceView("conciliador")}
            >
              Consulta e ingesta
            </button>
            <button
              type="button"
              className={workspaceView === "usuarios" ? "tab-button active" : "tab-button"}
              onClick={() => setWorkspaceView("usuarios")}
            >
              Usuarios y auditoria
            </button>
          </nav>
        ) : null}

        {error ? <div className="error-banner">{error}</div> : null}

        {workspaceView === "usuarios" && currentUser.is_admin ? (
          <>
            <section className="result-header">
              <div>
                <p className="eyebrow">Administracion</p>
                <h2>Usuarios y trazabilidad</h2>
              </div>
              <div className="result-actions">
                <div className="result-tag">
                  {loadingAdminData ? "Actualizando..." : `${managedUsers.length} usuario(s) registrados`}
                </div>
              </div>
            </section>

            <section className="panel">
              <div className="panel-header stacked">
                <div>
                  <h3>Resumen de usuarios</h3>
                  <p>Consulta el ultimo ingreso, el total acumulado y el detalle diario de consultas por usuario.</p>
                </div>
              </div>
              <div className="user-grid">
                {managedUsers.map((user) => (
                  <button
                    key={user.id}
                    type="button"
                    className={selectedManagedUserId === user.id ? "user-card active" : "user-card"}
                    onClick={() => void loadActivityForUser(user.id)}
                  >
                    <div className="user-card-top">
                      <strong>{user.full_name}</strong>
                      <div className="badge-stack">
                        <span className={user.is_active ? "inline-badge ok" : "inline-badge warn"}>
                          {user.is_active ? "Activo" : "Inactivo"}
                        </span>
                        {user.must_change_password ? (
                          <span className="inline-badge warn">Cambio de clave pendiente</span>
                        ) : null}
                      </div>
                    </div>
                    <span>@{user.username}</span>
                    <small>{user.is_admin ? "Administrador" : "Consulta"}</small>
                    <div className="user-card-stats">
                      <article>
                        <span>Ultimo ingreso</span>
                        <strong>{formatDateTime(user.last_login_at)}</strong>
                      </article>
                      <article>
                        <span>Consultas</span>
                        <strong>{formatDisplayNumber(user.total_consultas)}</strong>
                      </article>
                      <article>
                        <span>Eventos</span>
                        <strong>{formatDisplayNumber(user.total_eventos)}</strong>
                      </article>
                    </div>
                  </button>
                ))}
              </div>
            </section>

            <div className="panel-grid admin-grid">
              <section className="panel">
                <div className="panel-header stacked">
                  <div>
                    <h3>Crear usuario</h3>
                    <p>Agrega accesos individuales para dejar trazabilidad por persona.</p>
                  </div>
                </div>

                <form className="search-form" onSubmit={handleCreateUser}>
                  <label>
                    <span>Usuario</span>
                    <input
                      value={newUserForm.username}
                      onChange={(event) =>
                        setNewUserForm((current) => ({ ...current, username: event.target.value }))
                      }
                      placeholder="Ej. cartera.1"
                    />
                  </label>
                  <label>
                    <span>Nombre completo</span>
                    <input
                      value={newUserForm.full_name}
                      onChange={(event) =>
                        setNewUserForm((current) => ({ ...current, full_name: event.target.value }))
                      }
                      placeholder="Ej. Maria Perez"
                    />
                  </label>
                  <label>
                    <span>Contrasena inicial</span>
                    <input
                      type="password"
                      value={newUserForm.password}
                      onChange={(event) =>
                        setNewUserForm((current) => ({ ...current, password: event.target.value }))
                      }
                      placeholder="Usa 123456 si sera temporal"
                    />
                  </label>
                  <label className="toggle-row">
                    <input
                      type="checkbox"
                      checked={newUserForm.is_admin}
                      onChange={(event) =>
                        setNewUserForm((current) => ({ ...current, is_admin: event.target.checked }))
                      }
                    />
                    <span>Permisos de administrador</span>
                  </label>
                  <label className="toggle-row">
                    <input
                      type="checkbox"
                      checked={newUserForm.is_active}
                      onChange={(event) =>
                        setNewUserForm((current) => ({ ...current, is_active: event.target.checked }))
                      }
                    />
                    <span>Usuario activo</span>
                  </label>
                  <label className="toggle-row">
                    <input
                      type="checkbox"
                      checked={newUserForm.must_change_password}
                      onChange={(event) =>
                        setNewUserForm((current) => ({
                          ...current,
                          must_change_password: event.target.checked,
                        }))
                      }
                    />
                    <span>Debe cambiar contrasena al ingresar</span>
                  </label>
                  <button className="primary-button" type="submit" disabled={creatingUser}>
                    {creatingUser ? "Creando..." : "Crear usuario"}
                  </button>
                </form>
              </section>

              <section className="panel">
                <div className="panel-header stacked">
                  <div>
                    <h3>Editar usuario</h3>
                    <p>Ajusta nombre, estado, rol y contrasena del usuario seleccionado.</p>
                  </div>
                </div>

                {selectedManagedUser ? (
                  <form className="search-form" onSubmit={handleUpdateUser}>
                    <label>
                      <span>Usuario</span>
                      <input value={selectedManagedUser.username} disabled />
                    </label>
                    <label>
                      <span>Nombre completo</span>
                      <input
                        value={userEditForm.full_name}
                        onChange={(event) =>
                          setUserEditForm((current) => ({ ...current, full_name: event.target.value }))
                        }
                      />
                    </label>
                    <label>
                      <span>Nueva contrasena</span>
                      <input
                        type="password"
                        value={userEditForm.password}
                        onChange={(event) =>
                          setUserEditForm((current) => ({ ...current, password: event.target.value }))
                        }
                        placeholder="Deja en blanco para conservar la actual"
                      />
                    </label>
                    <label className="toggle-row">
                      <input
                        type="checkbox"
                        checked={userEditForm.is_admin}
                        onChange={(event) =>
                          setUserEditForm((current) => ({ ...current, is_admin: event.target.checked }))
                        }
                      />
                      <span>Administrador</span>
                    </label>
                    <label className="toggle-row">
                      <input
                        type="checkbox"
                        checked={userEditForm.is_active}
                        onChange={(event) =>
                          setUserEditForm((current) => ({ ...current, is_active: event.target.checked }))
                        }
                      />
                      <span>Activo</span>
                    </label>
                    <label className="toggle-row">
                      <input
                        type="checkbox"
                        checked={userEditForm.must_change_password}
                        onChange={(event) =>
                          setUserEditForm((current) => ({
                            ...current,
                            must_change_password: event.target.checked,
                          }))
                        }
                      />
                      <span>Solicitar cambio de contrasena al ingresar</span>
                    </label>
                    <button className="primary-button" type="submit" disabled={savingUserChanges}>
                      {savingUserChanges ? "Guardando..." : "Guardar cambios"}
                    </button>
                  </form>
                ) : (
                  <div className="empty-state compact">Selecciona un usuario para editarlo.</div>
                )}
              </section>
            </div>

            <section className="panel">
              <div className="panel-header stacked">
                <div>
                  <h3>Consultas por fecha</h3>
                  <p>Conteo diario de consultas exitosas del usuario seleccionado.</p>
                </div>
              </div>

              {selectedManagedUser ? (
                userDailyConsultations.length > 0 ? (
                  <div className="table-wrap">
                    <table className="data-table daily-consultation-table">
                      <thead>
                        <tr>
                          <th>Fecha</th>
                          <th>Consultas</th>
                        </tr>
                      </thead>
                      <tbody>
                        {userDailyConsultations.map((item) => (
                          <tr key={item.date}>
                            <td>{formatDate(item.date)}</td>
                            <td>{formatDisplayNumber(item.total_consultas)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty-state compact">
                    Aun no hay consultas exitosas registradas para este usuario.
                  </div>
                )
              ) : (
                <div className="empty-state compact">Selecciona un usuario para ver sus consultas por fecha.</div>
              )}
            </section>

            <section className="panel">
              <div className="panel-header stacked">
                <div>
                  <h3>Actividad reciente</h3>
                  <p>Log de ingresos, consultas, reprocesos e ingestas del usuario seleccionado.</p>
                </div>
              </div>

              {userAdminStatus ? <p className="helper-text">{userAdminStatus}</p> : null}

              {selectedManagedUser ? (
                userActivity.length > 0 ? (
                  <div className="table-wrap">
                    <table className="data-table activity-table">
                      <thead>
                        <tr>
                          <th>Fecha</th>
                          <th>Accion</th>
                          <th>NIT</th>
                          <th>Factura</th>
                          <th>Detalle</th>
                          <th>IP</th>
                        </tr>
                      </thead>
                      <tbody>
                        {userActivity.map((item) => (
                          <tr key={item.id}>
                            <td>{formatDateTime(item.created_at)}</td>
                            <td>{item.action}</td>
                            <td>{item.target_nit ?? "-"}</td>
                            <td>{item.target_factura ?? "-"}</td>
                            <td>{item.detail ?? "-"}</td>
                            <td>{item.ip_address ?? "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty-state compact">Aun no hay actividad registrada para este usuario.</div>
                )
              ) : (
                <div className="empty-state compact">Selecciona un usuario para ver su actividad.</div>
              )}
            </section>
          </>
        ) : result ? (
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
