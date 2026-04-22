# Conciliador XML Web

Este repositorio ahora tiene dos capas:

- `app/`: codigo legacy que hoy procesa XML y genera Excel.
- `backend/`: API `FastAPI` para ingesta y consulta web.
- `frontend/`: interfaz `React + Vite` con pestanas para `Dashboard`, `Cruce ERP/XML`, `AC` y `NP`.

## Que hace esta version

- Procesa `XML` o `ZIP` desde el navegador.
- Puede escanear la carpeta `facturas_entrada`.
- Guarda el detalle XML en `factura_xml_detalle` igual que tu flujo actual.
- Genera y guarda un snapshot de conciliacion por factura para acelerar las consultas posteriores.
- Consulta por `NIT + factura`.
- Muestra el resultado en el navegador sin generar Excel.

## Estructura

```text
xml_conciliador/
├─ app/                     # Legacy
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ core/
│  │  ├─ models/
│  │  ├─ services/
│  │  ├─ db.py
│  │  ├─ main.py
│  │  └─ watch_folder.py
│  └─ requirements.txt
├─ frontend/
│  ├─ src/
│  ├─ package.json
│  └─ vite.config.ts
├─ facturas_entrada/
├─ facturas_procesadas/
└─ .env.example
```

## Requisitos

- Python 3.12+
- Node 20+
- Acceso de red a PostgreSQL

## Paso a paso para probar en localhost

### 1. Verificar conectividad con la base real

Desde PowerShell:

```powershell
Test-NetConnection 192.168.10.9 -Port 5432
```

Debe salir `TcpTestSucceeded : True`.

### 2. Crear archivo `.env`

Desde la raiz del repo:

```powershell
Copy-Item .env.example .env
```

Abre `.env` y ajusta si hace falta:

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

Si vas a correr el frontend en otro puerto o dominio, agrega ese origen en `CORS_ORIGINS`.

### 3. Crear entorno virtual e instalar backend

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
```

### 4. Probar que el backend vea la base

Con el entorno virtual activo:

```powershell
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Abre:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/api/salud`
- `http://127.0.0.1:8000/api/salud/db`

Si `/api/salud/db` responde bien, la API ya esta entrando a la BD real por red.

### 5. Instalar y ejecutar el frontend

En otra terminal, desde la raiz del repo:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Abre:

- `http://127.0.0.1:5173`

## Arranque rapido en Windows

Si no quieres escribir comandos cada vez, desde el explorador de Windows o desde PowerShell puedes usar:

- [start_backend.bat](/C:/Users/POPULAR/Desktop/AUTOMATIZACION%20COSTOS/xml_conciliador/start_backend.bat)
- [start_frontend.bat](/C:/Users/POPULAR/Desktop/AUTOMATIZACION%20COSTOS/xml_conciliador/start_frontend.bat)
- [start_all.bat](/C:/Users/POPULAR/Desktop/AUTOMATIZACION%20COSTOS/xml_conciliador/start_all.bat)

Uso:

1. Doble clic en `start_backend.bat` para la API.
2. Doble clic en `start_frontend.bat` para la interfaz.
3. O doble clic en `start_all.bat` para abrir ambos en ventanas separadas.

Si `start_backend.bat` falla, revisa que exista:

- `.venv\Scripts\python.exe`

Si `start_frontend.bat` falla, revisa que exista:

- `frontend\node_modules`

### 6. Cargar XML o consultar facturas ya guardadas

Tienes tres formas:

- Subir un `XML` o `ZIP` desde la interfaz.
- Usar el boton `Escanear carpeta de entrada` para leer `facturas_entrada`.
- Buscar una factura ya almacenada escribiendo `NIT` y `numero de factura`.

### 7. Activar vigilancia automatica de carpeta

Si quieres que el backend procese automaticamente todo archivo nuevo en `facturas_entrada`, abre una tercera terminal con el entorno virtual activo:

```powershell
.venv\Scripts\Activate.ps1
python -m backend.app.watch_folder
```

Con eso, cada `XML` o `ZIP` que llegue a `facturas_entrada` se procesa y, si todo sale bien, se mueve a `facturas_procesadas`.

## Endpoints principales

- `GET /api/salud`
- `GET /api/salud/db`
- `GET /api/facturas`
- `GET /api/conciliaciones/{nit}/{factura}`
- `POST /api/ingesta/archivo`
- `POST /api/ingesta/escanear-carpeta`

## Flujo recomendado de uso

1. Cargar XML/ZIP o dejar corriendo el watcher.
2. El backend deja precalculado el snapshot de la conciliacion.
3. Buscar la factura por `NIT + numero`.
4. Si necesitas recalcular contra el ERP actual, usa el boton `Reprocesar` del front.
5. Revisar `Dashboard`.
6. Validar `Cruce ERP/XML`.
7. Entrar a `AC` y `NP` para ver ajustes sugeridos.

## Notas importantes

- Esta version ya no genera Excel.
- `AC` y `NP` se calculan en backend a partir del mismo cruce que antes alimentaba el Excel.
- No se hicieron cambios destructivos sobre tu carpeta `app/` legacy.
- La tabla `factura_xml_detalle` sigue siendo la base del almacenamiento XML.
- Los snapshots de consulta se guardan en `cache\conciliaciones`.
- Los `ZIP` movidos a `facturas_procesadas` pueden limpiarse automaticamente despues de `PROCESSED_ZIP_RETENTION_DAYS` dias.

## GitHub y despliegue automatico

La forma recomendada para este proyecto es:

- GitHub para versionar el codigo.
- `GitHub Actions` para disparar el despliegue.
- `self-hosted runner` instalado dentro del Debian.

Esto es mejor que desplegar por SSH desde internet porque tu servidor y tu base estan en red local.

### 1. Crear el repositorio en GitHub

En GitHub:

1. Entra a `New repository`.
2. Crea uno vacio.
3. No agregues `README`, `.gitignore` ni licencia para evitar conflictos en el primer push.

Referencia oficial:

- [Quickstart for repositories](https://docs.github.com/github/getting-started-with-github/create-a-repo)

### 2. Convertir este proyecto en repositorio Git

Desde la raiz del proyecto en tu maquina local:

```powershell
cd "C:\Users\POPULAR\Desktop\AUTOMATIZACION COSTOS\xml_conciliador"
git init
git branch -M main
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

### 3. Instalar un self-hosted runner en Debian

En GitHub:

1. Abre el repositorio.
2. Ve a `Settings > Actions > Runners`.
3. Pulsa `New self-hosted runner`.
4. Elige `Linux`.

GitHub te mostrara los comandos exactos para descargarlo y registrarlo.

Referencia oficial:

- [Managing self-hosted runners](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners?platform=linux)
- [About self-hosted runners](https://docs.github.com/en/actions/concepts/runners/about-self-hosted-runners)

### 4. Instalar el runner como servicio

En Debian, despues de registrar el runner, entra a su carpeta y ejecuta:

```bash
sudo ./svc.sh install
sudo ./svc.sh start
```

Referencia oficial:

- [Configuring the self-hosted runner application as a service](https://docs.github.com/en/actions/how-tos/hosting-your-own-runners/managing-self-hosted-runners/configuring-the-self-hosted-runner-application-as-a-service?learn=hosting_your_own_runners&platform=linux)

### 5. Etiquetas del runner

Cuando registres el runner, agrega estas etiquetas:

- `self-hosted`
- `linux`
- `debian`
- `xml-conciliador`

El workflow del repo ya quedo configurado para usar esas etiquetas en:

- `.github/workflows/deploy.yml`

### 6. Permitir que el runner reinicie servicios

Si el runner no se ejecuta como `root`, crea una regla de `sudoers` para el usuario del runner.

Ejemplo si el usuario se llama `github-runner`:

```bash
sudo visudo -f /etc/sudoers.d/github-runner-xml-conciliador
```

Contenido:

```text
github-runner ALL=(root) NOPASSWD: /bin/systemctl restart xml-conciliador-backend
github-runner ALL=(root) NOPASSWD: /bin/systemctl restart xml-conciliador-watcher
github-runner ALL=(root) NOPASSWD: /bin/systemctl reload nginx
github-runner ALL=(root) NOPASSWD: /bin/systemctl list-unit-files
```

### 7. Instalar `rsync` en Debian

El script de despliegue usa `rsync` para copiar cambios al directorio real de la app:

```bash
sudo apt update
sudo apt install -y rsync
```

### 8. Script de despliegue

El proyecto ya incluye:

- `scripts/deploy_server.sh`

Ese script:

- sincroniza el codigo al directorio `/opt/xml_conciliador`
- conserva `.env`, `.venv` y carpetas operativas
- reinstala dependencias Python
- recompila frontend
- reinicia backend y watcher
- recarga `nginx`

### 9. Workflow automatico

El proyecto ya incluye:

- `.github/workflows/deploy.yml`

Se ejecuta:

- en cada `push` a `main`
- manualmente desde `Actions > Deploy To Debian > Run workflow`

### 10. Flujo normal de trabajo

Cada vez que hagas un cambio:

```powershell
git add .
git commit -m "Describe el cambio"
git push
```

Despues de eso:

1. GitHub detecta el push.
2. Lanza el workflow.
3. El runner en Debian toma el trabajo.
4. El script despliega en `/opt/xml_conciliador`.
5. Se reinician servicios.

### 11. Verificar el despliegue

En Debian:

```bash
sudo systemctl status xml-conciliador-backend --no-pager
sudo systemctl status xml-conciliador-watcher --no-pager
sudo systemctl status nginx --no-pager
journalctl -u xml-conciliador-backend -n 100 --no-pager
```

En GitHub:

1. Entra a `Actions`.
2. Abre la corrida `Deploy To Debian`.
3. Revisa si el job termino en verde.

### 12. Secretos

Para este flujo basico no necesitas secretos extra si usas self-hosted runner en el mismo Debian.

Referencia oficial:

- [Secrets reference](https://docs.github.com/en/actions/reference/security/secrets)

## Limpieza automatica de ZIP

La aplicacion ahora incluye un limpiador de `ZIP` procesados:

- Solo borra archivos `.zip` dentro de `facturas_procesadas`.
- No toca `XML`.
- No borra archivos subidos desde navegador porque esos hoy se procesan en memoria y no se guardan en disco.
- La retencion se controla con `PROCESSED_ZIP_RETENTION_DAYS` en el `.env`.

Ejecucion manual:

```powershell
python -m backend.app.cleanup_processed_archives
```

En Debian, lo recomendado es correrlo una vez al dia con `cron` o `systemd timer`. Ejemplo con `cron`:

```cron
0 2 * * * cd /opt/xml_conciliador && /opt/xml_conciliador/.venv/bin/python -m backend.app.cleanup_processed_archives >> /var/log/xml_conciliador_zip_cleanup.log 2>&1
```
