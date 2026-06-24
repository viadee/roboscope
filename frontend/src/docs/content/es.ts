import type { DocsContent } from '../types'

const es: DocsContent = [
  // ─── 1. Primeros pasos ────────────────────────────────────────────
  {
    id: 'getting-started',
    title: 'Primeros pasos',
    icon: '\u{1F680}',
    subsections: [
      {
        id: 'overview',
        title: '\u00BFQu\u00E9 es RoboScope?',
        content: `
<p>
  <strong>RoboScope</strong> es una herramienta de gesti\u00F3n de pruebas basada en web,
  dise\u00F1ada espec\u00EDficamente para <em>Robot Framework</em>. Proporciona un entorno
  integrado para gestionar repositorios de pruebas, ejecutar ejecuciones, analizar
  informes y realizar seguimiento de estad\u00EDsticas &mdash; todo desde una interfaz
  web moderna y unificada.
</p>
<h4>Capacidades principales</h4>
<ul>
  <li><strong>Gesti\u00F3n de repositorios</strong> &mdash; Conecte repositorios Git o carpetas locales para organizar sus suites de pruebas.</li>
  <li><strong>Explorador integrado</strong> &mdash; Navegue, edite y cree archivos <code>.robot</code> directamente en el navegador con resaltado de sintaxis.</li>
  <li><strong>Ejecuci\u00F3n de pruebas</strong> &mdash; Lance ejecuciones con tiempos de espera configurables, supervise el progreso en tiempo real mediante WebSocket y revise los registros de salida.</li>
  <li><strong>An\u00E1lisis de informes</strong> &mdash; Visualice informes HTML integrados de Robot Framework, inspeccione la salida XML y descargue archivos ZIP.</li>
  <li><strong>Estad\u00EDsticas y tendencias</strong> &mdash; Realice seguimiento de tasas de \u00E9xito, tendencias de aprobados/fallidos y detecte pruebas inestables en per\u00EDodos configurables.</li>
  <li><strong>Gesti\u00F3n de entornos</strong> &mdash; Cree entornos virtuales Python aislados, instale paquetes y defina variables de entorno.</li>
  <li><strong>Acceso basado en roles</strong> &mdash; Cuatro niveles de permisos (Viewer, Runner, Editor, Admin) controlan qui\u00E9n puede ver, ejecutar, editar o administrar.</li>
</ul>`,
        tip: 'RoboScope funciona mejor con navegadores basados en Chromium (Chrome, Edge) o Firefox para la experiencia completa de edici\u00F3n con CodeMirror.'
      },
      {
        id: 'login',
        title: 'Inicio de sesi\u00F3n',
        content: `
<p>
  Al abrir RoboScope por primera vez, se le presentar\u00E1 la pantalla de
  <strong>Inicio de sesi\u00F3n</strong>. Introduzca su direcci\u00F3n de correo
  electr\u00F3nico y contrase\u00F1a para autenticarse.
</p>
<h4>Cuenta de administrador predeterminada</h4>
<table>
  <thead>
    <tr><th>Campo</th><th>Valor</th></tr>
  </thead>
  <tbody>
    <tr><td>Correo electr\u00F3nico</td><td><code>admin@roboscope.local</code></td></tr>
    <tr><td>Contrase\u00F1a</td><td><code>admin123</code></td></tr>
  </tbody>
</table>
<p>
  Despu\u00E9s de iniciar sesi\u00F3n con la cuenta predeterminada, se
  <strong>recomienda encarecidamente</strong> cambiar la contrase\u00F1a
  inmediatamente o crear un usuario administrador dedicado y desactivar
  el predeterminado.
</p>
<h4>Gesti\u00F3n de sesiones</h4>
<p>
  RoboScope utiliza autenticaci\u00F3n basada en JWT. Su token de sesi\u00F3n se
  actualiza autom\u00E1ticamente mientras la aplicaci\u00F3n est\u00E9 abierta. Si el
  token expira (por ejemplo, tras un largo per\u00EDodo de inactividad), ser\u00E1
  redirigido a la p\u00E1gina de inicio de sesi\u00F3n.
</p>`,
        tip: 'Si olvida su contrase\u00F1a, un usuario administrador puede restablecerla desde la p\u00E1gina de Ajustes.'
      },
      {
        id: 'ui-layout',
        title: 'Disposici\u00F3n de la interfaz',
        content: `
<p>La interfaz de RoboScope consta de tres \u00E1reas principales:</p>
<ol>
  <li>
    <strong>Barra lateral</strong> (izquierda) &mdash; El panel de navegaci\u00F3n principal.
    Contiene enlaces a todas las secciones principales: Panel de control, Repositorios,
    Explorador, Ejecuci\u00F3n, Informes, Estad\u00EDsticas, Entornos y Ajustes. La barra
    lateral se puede contraer a una vista reducida de solo iconos (60 px) para maximizar
    el espacio de contenido.
  </li>
  <li>
    <strong>Encabezado</strong> (superior) &mdash; Muestra el t\u00EDtulo de la p\u00E1gina
    actual, el nombre y rol del usuario conectado, un selector de idioma (DE/EN/FR/ES)
    y el bot\u00F3n de cierre de sesi\u00F3n.
  </li>
  <li>
    <strong>\u00C1rea de contenido</strong> (centro) &mdash; El espacio de trabajo principal
    donde se renderiza la vista seleccionada. Cada vista utiliza tarjetas, tablas y
    botones de acci\u00F3n siguiendo el sistema de dise\u00F1o de RoboScope.
  </li>
</ol>
<p>
  El ancho de la barra lateral es de <code>250px</code> cuando est\u00E1 expandida y
  <code>60px</code> cuando est\u00E1 contra\u00EDda. El encabezado tiene una altura fija
  de <code>56px</code>.
</p>`,
        tip: 'Haga clic en el icono de hamburguesa en la parte superior de la barra lateral para alternar entre los modos expandido y contra\u00EDdo.'
      },
      {
        id: 'roles-permissions',
        title: 'Roles y permisos',
        content: `
<p>
  RoboScope implementa un sistema jer\u00E1rquico de control de acceso basado en
  roles (RBAC). Cada rol superior hereda todos los permisos de los roles inferiores.
</p>
<table>
  <thead>
    <tr>
      <th>Rol</th>
      <th>Nivel</th>
      <th>Permisos</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Viewer</strong></td>
      <td>0</td>
      <td>Ver paneles de control, repositorios, informes, estad\u00EDsticas. Acceso de solo lectura.</td>
    </tr>
    <tr>
      <td><strong>Runner</strong></td>
      <td>1</td>
      <td>Todos los permisos de Viewer <strong>+</strong> iniciar ejecuciones, cancelar ejecuciones, cancelar todas las ejecuciones.</td>
    </tr>
    <tr>
      <td><strong>Editor</strong></td>
      <td>2</td>
      <td>Todos los permisos de Runner <strong>+</strong> a\u00F1adir/editar/eliminar repositorios, editar archivos en el Explorador, gestionar entornos.</td>
    </tr>
    <tr>
      <td><strong>Admin</strong></td>
      <td>3</td>
      <td>Todos los permisos de Editor <strong>+</strong> gestionar usuarios, cambiar roles, modificar ajustes, eliminar todos los informes.</td>
    </tr>
  </tbody>
</table>
<p>
  La jerarqu\u00EDa de roles es estrictamente ordenada:
  <code>Viewer &lt; Runner &lt; Editor &lt; Admin</code>. Los controles de los
  endpoints aseguran que los usuarios no puedan realizar acciones por encima de
  su nivel asignado.
</p>`,
        tip: 'Si tiene dudas sobre lo que puede hacer, compruebe su insignia de rol en el encabezado. Si falta un bot\u00F3n, es posible que necesite un rol superior.'
      }
    ]
  },

  // ─── 2. Panel de control ──────────────────────────────────────────
  {
    id: 'dashboard',
    title: 'Panel de control',
    icon: '\u{1F4CA}',
    subsections: [
      {
        id: 'dashboard-overview',
        title: 'Visi\u00F3n general del panel',
        content: `
<p>
  El <strong>Panel de control</strong> es la p\u00E1gina de inicio predeterminada
  despu\u00E9s de iniciar sesi\u00F3n. Es una cuadr\u00EDcula de tarjetas que apunta a cada
  secci\u00F3n navegable de RoboScope, para que un usuario nuevo pueda llegar a
  Repositorios, Explorador, Ejecuciones, Estad\u00EDsticas, Grabador, Entornos,
  Documentaci\u00F3n y Ajustes sin escanear la barra lateral.
</p>
<p>
  Junto a las tarjetas de navegaci\u00F3n, una tarjeta <strong>Consejo del d\u00EDa</strong>
  rota diariamente entre 30 consejos espec\u00EDficos de RoboScope. Las m\u00E9tricas KPI
  m\u00E1s profundas (recuentos de ejecuciones, tasa de \u00E9xito, tendencias de duraci\u00F3n)
  viven en la p\u00E1gina <strong>Estad\u00EDsticas</strong>; las ejecuciones recientes y
  el historial viven en la p\u00E1gina <strong>Ejecuciones</strong>.
</p>`
      },
      {
        id: 'navigation-cards',
        title: 'Tarjetas de navegaci\u00F3n',
        content: `
<p>
  Cada tarjeta es un atajo cliqueable. Al pasar el cursor aparece un chevron
  animado y la tarjeta se eleva ligeramente para confirmar la affordance.
</p>
<table>
  <thead><tr><th>Tarjeta</th><th>Apunta a</th></tr></thead>
  <tbody>
    <tr><td><strong>Proyectos</strong></td><td>Configurar proyectos Git o locales, programar sincronizaci\u00F3n, gestionar permisos.</td></tr>
    <tr><td><strong>Explorador</strong></td><td>Navegar el \u00E1rbol de archivos, editar tests Robot visualmente o en c\u00F3digo.</td></tr>
    <tr><td><strong>Ejecuci\u00F3n</strong></td><td>Lanzar ejecuciones, seguir el progreso en vivo, programar ejecuciones recurrentes.</td></tr>
    <tr><td><strong>Estad\u00EDsticas</strong></td><td>Tendencias pass/fail, tests \u00ABflaky\u00BB, tasa de auto-reparaci\u00F3n.</td></tr>
    <tr><td><strong>Grabador</strong></td><td>Grabar interacciones en un navegador, generar tests Robot autom\u00E1ticamente. (Rol Editor o superior.)</td></tr>
    <tr><td><strong>Entornos</strong></td><td>Gestionar venvs Python, instalar paquetes pip, construir im\u00E1genes Docker. (Rol Editor o superior.)</td></tr>
    <tr><td><strong>Documentaci\u00F3n</strong></td><td>Esta documentaci\u00F3n, completamente buscable en cuatro idiomas.</td></tr>
    <tr><td><strong>Ajustes</strong></td><td>Proveedores IA, retenci\u00F3n, secretos, registro de auditor\u00EDa, cumplimiento. (Rol Admin.)</td></tr>
  </tbody>
</table>
<p>
  Las tarjetas visibles para un usuario respetan su rol: Grabador + Entornos
  necesitan Editor o superior; Ajustes necesita Admin.
</p>`,
        tip: '\u00BFNuevo en RoboScope? Empiece por la tarjeta Proyectos \u2014 un proyecto Git por defecto \u00ABRobot Framework Examples\u00BB se inicializa al primer arranque, as\u00ED tiene algo con lo que jugar al instante.'
      },
      {
        id: 'tip-of-the-day',
        title: 'Consejo del d\u00EDa',
        content: `
<p>
  Una peque\u00F1a tarjeta <strong>\u{1F4A1} Consejo del d\u00EDa</strong> se sit\u00FAa dentro
  de la cuadr\u00EDcula, mostrando uno de los 30 breves consejos espec\u00EDficos de
  RoboScope. Los consejos rotan en un ciclo de 30 d\u00EDas \u2014 cada d\u00EDa calendario
  elige uno nuevo \u2014 para que los usuarios frecuentes aprendan una caracter\u00EDstica
  nueva cada vez que abren el panel.
</p>
<p>
  Los consejos se enfocan espec\u00EDficamente en las funcionalidades de RoboScope
  (paleta del Editor de Flujo, selector del Grabador, palabras clave de
  auto-reparaci\u00F3n, tasa de reparaci\u00F3n de Stats, auto-sync de repos, panel de
  Detalles de Ejecuci\u00F3n, \u2026) \u2014 no consejos gen\u00E9ricos de Robot Framework. El
  texto de los consejos est\u00E1 disponible en las cinco localizaciones de la interfaz (EN/DE/FR/ES/ZH).
</p>`
      }
    ]
  },

  // ─── 3. Repositorios ──────────────────────────────────────────────
  {
    id: 'repositories',
    title: 'Repositorios',
    icon: '\u{1F4C1}',
    subsections: [
      {
        id: 'repos-overview',
        title: 'Gesti\u00F3n de repositorios',
        content: `
<p>
  La p\u00E1gina de <strong>Repositorios</strong> es donde registra y gestiona sus
  repositorios de pruebas de Robot Framework. RoboScope soporta dos tipos de repositorios:
</p>
<ul>
  <li><strong>Repositorios Git</strong> &mdash; Clonados desde una URL remota, con selecci\u00F3n de rama y capacidades de sincronizaci\u00F3n.</li>
  <li><strong>Carpetas locales</strong> &mdash; Apuntando a un directorio en el sistema de archivos del servidor.</li>
</ul>
<p>
  Todos los datos de repositorios se almacenan en el directorio <code>WORKSPACE_DIR</code>
  (por defecto: <code>~/.roboscope/workspace</code>). Solo los usuarios con el rol
  <strong>Editor</strong> o superior pueden a\u00F1adir, editar o eliminar repositorios.
</p>`
      },
      {
        id: 'add-git-repo',
        title: 'A\u00F1adir un repositorio Git',
        content: `
<p>Para a\u00F1adir un repositorio Git, haga clic en el bot\u00F3n <strong>A\u00F1adir repositorio</strong> y complete el formulario:</p>
<ol>
  <li>Seleccione <strong>Git</strong> como tipo de repositorio.</li>
  <li>Introduzca la <strong>URL del repositorio</strong> (HTTPS o SSH). Ejemplo: <code>https://github.com/org/tests.git</code></li>
  <li>Especifique la <strong>Rama</strong> a clonar (por defecto: <code>main</code>).</li>
  <li>Opcionalmente proporcione un <strong>Nombre para mostrar</strong>. Si se deja en blanco, el nombre del repositorio se infiere de la URL.</li>
  <li>Haga clic en <strong>Crear</strong>.</li>
</ol>
<p>
  RoboScope utiliza <em>GitPython</em> para clonar el repositorio en el directorio
  de trabajo. La operaci\u00F3n de clonaci\u00F3n se ejecuta como tarea en segundo
  plano, por lo que ver\u00E1 un estado <code>pending</code> hasta que se complete.
  Una vez finalizada la clonaci\u00F3n, el repositorio estar\u00E1 disponible en las
  vistas de Explorador y Ejecuci\u00F3n.
</p>`,
        tip: 'Para repositorios privados mediante HTTPS, incluya las credenciales en la URL o configure claves SSH en el servidor.'
      },
      {
        id: 'add-local-repo',
        title: 'A\u00F1adir una carpeta local',
        content: `
<p>
  Si sus suites de pruebas ya residen en el sistema de archivos del servidor,
  puede registrarlas como un repositorio <strong>Local</strong>:
</p>
<ol>
  <li>Seleccione <strong>Local</strong> como tipo de repositorio.</li>
  <li>Introduzca la <strong>ruta</strong> absoluta al directorio que contiene sus archivos <code>.robot</code>.</li>
  <li>Proporcione un <strong>Nombre para mostrar</strong>.</li>
  <li>Haga clic en <strong>Crear</strong>.</li>
</ol>
<p>
  Los repositorios locales no soportan funciones de sincronizaci\u00F3n ni
  auto-sincronizaci\u00F3n ya que referencian un directorio activo. Cualquier
  cambio realizado en los archivos en disco se refleja inmediatamente en
  el Explorador.
</p>`
      },
      {
        id: 'sync-autosync',
        title: 'Sincronizaci\u00F3n y auto-sincronizaci\u00F3n',
        content: `
<p>
  Los repositorios Git se pueden sincronizar para obtener los \u00FAltimos cambios del remoto:
</p>
<ul>
  <li><strong>Sincronizaci\u00F3n manual</strong> &mdash; Haga clic en el bot\u00F3n <strong>Sincronizar</strong> en una fila de repositorio. Esto ejecuta un <code>git pull</code> en la rama configurada.</li>
  <li><strong>Auto-sincronizaci\u00F3n</strong> &mdash; Active el interruptor de auto-sincronizaci\u00F3n para un repositorio. Cuando est\u00E9 habilitado, RoboScope obtendr\u00E1 autom\u00E1ticamente los cambios a un intervalo configurable antes de cada ejecuci\u00F3n de pruebas.</li>
</ul>
<p>
  El estado de sincronizaci\u00F3n se indica mediante una marca de tiempo que
  muestra la \u00FAltima sincronizaci\u00F3n exitosa. Si una sincronizaci\u00F3n falla
  (por ejemplo, conflictos de fusi\u00F3n), aparece una insignia de error junto
  al nombre del repositorio.
</p>`,
        tip: 'Importante: Auto-Sync ahora ejecuta un git pull en segundo plano cada sync_interval_minutes (15 min por defecto). El planificador se activa cada 5 min, los intervalos cortos se redondean a 5 min. Use el bot\u00F3n "Sincronizar" expl\u00EDcito y guarde sus cambios antes con "Guardar N cambios" para evitar sobrescrituras.'
      },
      {
        id: 'branch-switching',
        title: 'Cambio de rama y auto-sincronizaci\u00F3n',
        content: `
<h4>Cambio de rama</h4>
<p>
  Cada tarjeta de proyecto Git muestra un <strong>men\u00FA desplegable de ramas</strong> que
  le permite cambiar entre las ramas disponibles. Seleccione una rama diferente para
  hacer checkout. Esto es \u00FAtil para probar ramas de funcionalidades o comparar
  resultados entre ramas.
</p>
<h4>Casilla de Auto-Sync</h4>
<p>
  La casilla <strong>Auto-Sync</strong> en cada tarjeta de proyecto controla si el
  repositorio se sincroniza en segundo plano cada <code>sync_interval_minutes</code>
  (15 min por defecto). Act\u00EDvela para flujos CI/CD donde siempre quiera probar
  el c\u00F3digo m\u00E1s reciente.
</p>
<h4>Sincronizar antes de ejecutar</h4>
<p>
  Active <strong>Sincronizar antes de ejecutar</strong> en un repositorio cuando
  cada ejecuci\u00F3n de pruebas deba usar el commit m\u00E1s reciente. RoboScope
  ejecuta un <code>git pull</code> s\u00EDncrono justo antes de que arranque el
  runner, con un timeout de 60&nbsp;s. La opci\u00F3n est\u00E1 desactivada por
  defecto y a\u00F1ade unos segundos por ejecuci\u00F3n; se combina con Auto-Sync
  &mdash; puede activar ambos, uno o ninguno.
</p>
<p>
  Si el pull falla (red, conflicto, timeout), la ejecuci\u00F3n arranca igualmente
  con lo que haya en disco. El fallo se registra y el siguiente Auto-Sync lo
  reintentar\u00E1.
</p>`
      },
      {
        id: 'library-check',
        title: 'Verificaci\u00F3n de bibliotecas (Gestor de paquetes)',
        content: `
<p>
  La funci\u00F3n de <strong>Verificaci\u00F3n de bibliotecas</strong> escanea los
  archivos <code>.robot</code> y <code>.resource</code> de un repositorio en busca
  de importaciones de <code>Library</code> y verifica si los paquetes Python
  correspondientes est\u00E1n instalados en un entorno seleccionado.
</p>
<h4>C\u00F3mo usar</h4>
<ol>
  <li>En la p\u00E1gina de <strong>Repositorios</strong>, haga clic en el bot\u00F3n <strong>Verificaci\u00F3n de bibliotecas</strong> en cualquier tarjeta de repositorio.</li>
  <li>Seleccione un <strong>Entorno</strong> del men\u00FA desplegable (pre-rellenado con el entorno predeterminado del repositorio si est\u00E1 configurado).</li>
  <li>Haga clic en <strong>Escanear</strong> para analizar el repositorio.</li>
</ol>
<h4>Resultados</h4>
<p>Los resultados del escaneo muestran una tabla con cada biblioteca y su estado:</p>
<ul>
  <li><strong>Instalada</strong> (verde) &mdash; El paquete PyPI de la biblioteca est\u00E1 instalado en el entorno, con la versi\u00F3n mostrada.</li>
  <li><strong>Faltante</strong> (rojo) &mdash; La biblioteca se usa en archivos de prueba pero no est\u00E1 instalada. Aparece un bot\u00F3n <strong>Instalar</strong> para instalaci\u00F3n con un clic.</li>
  <li><strong>Built-in</strong> (gris) &mdash; La biblioteca forma parte de la biblioteca est\u00E1ndar de Robot Framework (por ejemplo, Collections, String, BuiltIn) y no necesita instalaci\u00F3n.</li>
</ul>
<h4>Instalar bibliotecas faltantes</h4>
<p>
  Haga clic en <strong>Instalar</strong> junto a cualquier biblioteca faltante para
  instalarla en el entorno seleccionado. Use <strong>Instalar todas las faltantes</strong>
  para instalar todas las bibliotecas faltantes a la vez. La instalaci\u00F3n utiliza la
  gesti\u00F3n de paquetes del entorno existente (pip install) y se ejecuta en segundo plano.
</p>
<h4>Entorno predeterminado</h4>
<p>
  Cada repositorio puede tener un <strong>entorno predeterminado</strong> asignado.
  Establ\u00E9zcalo al a\u00F1adir un repositorio o m\u00E1s tarde a trav\u00E9s de la
  configuraci\u00F3n del repositorio. El entorno predeterminado se preselecciona al
  abrir el di\u00E1logo de Verificaci\u00F3n de bibliotecas.
</p>`,
        tip: 'Ejecute una Verificaci\u00F3n de bibliotecas despu\u00E9s de clonar un nuevo repositorio para identificar e instalar r\u00E1pidamente todas las dependencias necesarias.'
      },
      {
        id: 'project-environment',
        title: 'Entorno del proyecto',
        content: `
<p>
  Cada proyecto puede tener un <strong>entorno predeterminado</strong> asignado.
  Este entorno se utiliza autom\u00E1ticamente al iniciar ejecuciones de pruebas
  desde el proyecto y se preselecciona en el di\u00E1logo de Verificaci\u00F3n de
  bibliotecas.
</p>
<h4>Seleccionar un entorno</h4>
<p>
  En la p\u00E1gina de <strong>Proyectos</strong>, cada tarjeta de proyecto muestra
  un men\u00FA desplegable de entorno. Seleccione un entorno de la lista para
  asignarlo al proyecto. El cambio se guarda inmediatamente.
</p>
<p>
  Si se ha configurado un entorno predeterminado a nivel del sistema, se
  preselecciona autom\u00E1ticamente al a\u00F1adir nuevos proyectos.
</p>`,
        tip: 'Asigne el entorno correcto a cada proyecto para evitar errores de "biblioteca faltante" durante la ejecuci\u00F3n de pruebas.'
      },
      {
        id: 'bulk-operations',
        title: 'Selecci\u00F3n m\u00FAltiple y eliminaci\u00F3n',
        content: `
<p>
  La p\u00E1gina de Repositorios soporta operaciones masivas para una gesti\u00F3n eficiente:
</p>
<ul>
  <li>Use las <strong>casillas de verificaci\u00F3n</strong> en cada fila para seleccionar m\u00FAltiples repositorios.</li>
  <li>Una casilla <strong>Seleccionar todo</strong> en el encabezado de la tabla alterna todos los elementos.</li>
  <li>Una vez seleccionados, haga clic en el bot\u00F3n <strong>Eliminar seleccionados</strong> (requiere rol <strong>Editor+</strong>).</li>
  <li>Aparecer\u00E1 un di\u00E1logo de confirmaci\u00F3n listando los repositorios a eliminar.</li>
</ul>
<p>
  <strong>Advertencia:</strong> Eliminar un repositorio lo elimina de RoboScope y
  borra los datos del espacio de trabajo clonado. Los informes y el historial de
  ejecuciones asociados al repositorio <em>no</em> se eliminan autom\u00E1ticamente.
  Use la p\u00E1gina de Informes para limpiar informes antiguos si es necesario.
</p>`
      }
    ]
  },

  // ─── 4. Explorador ────────────────────────────────────────────────
  {
    id: 'explorer',
    title: 'Explorador',
    icon: '\u{1F50D}',
    subsections: [
      {
        id: 'file-tree',
        title: 'Navegaci\u00F3n del \u00E1rbol de archivos',
        content: `
<p>
  El <strong>Explorador</strong> proporciona un navegador de sistema de archivos
  para explorar el contenido de sus repositorios. El panel izquierdo muestra un
  \u00E1rbol jer\u00E1rquico de directorios y archivos. Puede:
</p>
<ul>
  <li>Expandir y contraer directorios haciendo clic en el icono de carpeta o la flecha.</li>
  <li>Hacer clic en un archivo para abrirlo en el panel del editor a la derecha.</li>
  <li>Los iconos de archivo indican el tipo: los archivos <code>.robot</code> tienen un icono especial de Robot Framework,
      mientras que los archivos <code>.py</code>, <code>.yaml</code>, <code>.txt</code> y otros usan iconos est\u00E1ndar.</li>
  <li>El encabezado del \u00E1rbol muestra el <strong>n\u00FAmero total de casos de prueba</strong> encontrados en todos los archivos <code>.robot</code> del proyecto. Los directorios tambi\u00E9n muestran una insignia con su recuento individual de pruebas.</li>
</ul>
<p>
  Un <strong>selector de repositorio</strong> en forma de men\u00FA desplegable en la
  parte superior le permite cambiar entre repositorios registrados sin salir del
  Explorador.
</p>
<h4>Funciones de localhost</h4>
<p>
  Al acceder a RoboScope en <code>localhost</code>, hay funciones adicionales disponibles:
</p>
<ul>
  <li><strong>Abrir carpeta del proyecto</strong> &mdash; Un bot\u00F3n de carpeta en el encabezado del \u00E1rbol abre el directorio ra\u00EDz del proyecto en el explorador de archivos del sistema (Finder, Explorador de Windows o Nautilus).</li>
  <li><strong>Abrir en explorador de archivos</strong> &mdash; Cada directorio en el \u00E1rbol tiene un bot\u00F3n de carpeta para abrirlo directamente en el explorador de archivos del sistema.</li>
  <li><strong>Ruta absoluta</strong> &mdash; Cuando se selecciona un archivo, la ruta completa del sistema de archivos se muestra debajo de la barra de navegaci\u00F3n.</li>
</ul>`
      },
      {
        id: 'create-rename-delete',
        title: 'Crear, renombrar y eliminar archivos',
        content: `
<p>
  Los usuarios con rol <strong>Editor</strong> o superior pueden gestionar archivos
  directamente dentro del Explorador:
</p>
<h4>Crear archivos</h4>
<p>
  Haga clic derecho en un directorio del \u00E1rbol de archivos y seleccione
  <strong>Nuevo archivo</strong> o <strong>Nueva carpeta</strong>. Introduzca el
  nombre y pulse Intro. Los nuevos archivos <code>.robot</code> se pre-rellenan
  con una plantilla b\u00E1sica que incluye las secciones <code>*** Settings ***</code>
  y <code>*** Test Cases ***</code>.
</p>
<h4>Renombrar</h4>
<p>
  Haga clic derecho en cualquier archivo o carpeta y seleccione <strong>Renombrar</strong>.
  Escriba el nuevo nombre y pulse Intro para confirmar, o Escape para cancelar.
</p>
<h4>Eliminar</h4>
<p>
  Haga clic derecho y seleccione <strong>Eliminar</strong>. Aparecer\u00E1 un
  di\u00E1logo de confirmaci\u00F3n. Eliminar una carpeta elimina todo su contenido
  de forma recursiva.
</p>`,
        tip: 'Use la extensi\u00F3n .resource para archivos de recursos de Robot Framework y .robot para suites de pruebas para mantener su proyecto organizado.'
      },
      {
        id: 'codemirror-editor',
        title: 'Editor CodeMirror',
        content: `
<p>
  Cuando se selecciona un archivo, se abre en el editor integrado
  <strong>CodeMirror</strong>. Las caracter\u00EDsticas incluyen:
</p>
<ul>
  <li><strong>Resaltado de sintaxis</strong> para Robot Framework (<code>.robot</code>), Python (<code>.py</code>), YAML, JSON y archivos XML.</li>
  <li><strong>N\u00FAmeros de l\u00EDnea</strong> mostrados en el margen.</li>
  <li><strong>Sangr\u00EDa autom\u00E1tica</strong> y coincidencia de par\u00E9ntesis.</li>
  <li><strong>Buscar y reemplazar</strong> mediante <code>Ctrl+F</code> / <code>Cmd+F</code>.</li>
  <li><strong>Deshacer/Rehacer</strong> con historial completo durante la sesi\u00F3n de edici\u00F3n.</li>
</ul>
<p>
  Los cambios se guardan haciendo clic en el bot\u00F3n <strong>Guardar</strong> o
  usando el atajo de teclado <code>Ctrl+S</code> / <code>Cmd+S</code>. Un indicador
  de cambios sin guardar aparece en la pesta\u00F1a del editor cuando se han
  realizado modificaciones.
</p>`,
        tip: 'Use Ctrl+G (Cmd+G en Mac) para saltar a un n\u00FAmero de l\u00EDnea espec\u00EDfico en el editor.'
      },
      {
        id: 'flow-editor',
        title: 'Editor de flujo visual',
        content: `
<p>
  Para archivos <code>.robot</code>, el editor ofrece una tercera pesta\u00F1a llamada
  <strong>Flow</strong> (junto a \u00ABVisual Editor\u00BB y \u00ABCode\u00BB). Esta pesta\u00F1a muestra
  sus casos de prueba como un <strong>grafo interactivo basado en nodos</strong> utilizando Vue Flow.
</p>
<h4>Tipos de nodos</h4>
<ul>
  <li><strong>Nodos Inicio/Fin</strong> &mdash; Nodos redondeados que marcan el inicio y fin de cada flujo. El nodo Inicio muestra el nombre del caso de prueba / palabra clave; haga clic para abrir un panel de ajustes con botones <strong>+ [&hellip;]</strong> para cada ajuste a\u00FAn no adjunto.</li>
  <li><strong>Nodos de palabra clave</strong> (azul) &mdash; Representan llamadas a palabras clave. Haga clic en un nodo para ver sus argumentos en el panel de detalles a la derecha.</li>
  <li><strong>Nodos de control</strong> (borde punteado) &mdash; Representan estructuras de control como <code>IF</code>, <code>FOR</code>, <code>WHILE</code> y <code>TRY/EXCEPT</code>. Codificados por color seg\u00FAn tipo (\u00E1mbar para IF, violeta para FOR/WHILE, turquesa para TRY, rojo para EXCEPT). Las etiquetas de las aristas muestran condiciones de ramificaci\u00F3n (true/false).</li>
  <li><strong>Nodo RETURN</strong> (verde, glifo &uarr;) &mdash; Marca el punto de retorno de una definici\u00F3n de palabra clave. Cada valor de retorno se renderiza como un chip; haga clic en el nodo y use el panel <strong>Valores de retorno</strong> para a\u00F1adir / quitar celdas.</li>
  <li><strong>Notas laterales</strong> (borde punteado, vista previa en cursiva) &mdash; Ajustes de caso de prueba / palabra clave renderizados a la izquierda del nodo Inicio. Vea la siguiente secci\u00F3n.</li>
</ul>
<h4>Paleta de palabras clave</h4>
<p>
  Una barra lateral plegable a la izquierda del lienzo ofrece una <strong>Paleta de palabras clave</strong>
  con cinco categor\u00EDas: BuiltIn, Collections, String, Browser y Control. Puede:
</p>
<ul>
  <li><strong>Buscar</strong> &mdash; Filtrar palabras clave por nombre usando el cuadro de b\u00FAsqueda.</li>
  <li><strong>Clic para a\u00F1adir</strong> &mdash; Haga clic en una palabra clave para seleccionarla (aparece una barra \u00ABA\u00F1adir\u00BB en la parte superior de la paleta), luego haga clic en <strong>+</strong> para insertarla despu\u00E9s del nodo seleccionado actualmente.</li>
  <li><strong>Arrastrar y soltar</strong> &mdash; Arrastre una palabra clave desde la paleta al lienzo para posicionarla con precisi\u00F3n.</li>
</ul>
<h4>Estructuras de control (IF/ELSE, TRY/EXCEPT, bucles)</h4>
<p>
  La categor\u00EDa <strong>Control</strong> de la paleta le permite construir flujo
  de control de Robot Framework sin escribir c\u00F3digo. A\u00F1ada un elemento de la
  misma forma que una palabra clave (seleccionar &rarr; <strong>+</strong>, o
  arrastrarlo al lienzo):
</p>
<ul>
  <li><strong>IF / ELSE</strong>, <strong>FOR Loop</strong>, <strong>WHILE Loop</strong>
      y <strong>TRY / EXCEPT</strong> insertan cada uno un bloque completo y v\u00E1lido
      con su <code>END</code> correspondiente en un solo paso. Un <code>TRY</code> se
      genera como <code>TRY &rarr; EXCEPT &rarr; END</code> para que sea ejecutable
      de inmediato (un <code>TRY&hellip;END</code> a secas es un error de sintaxis en
      Robot Framework).</li>
  <li>Para extender un bloque, seleccione el nodo desde el que desea ramificar y
      a\u00F1ada <strong>ELSE IF</strong>, <strong>ELSE</strong>, <strong>EXCEPT</strong>
      o <strong>FINALLY</strong> &mdash; la nueva cl\u00E1usula se inserta en su lugar,
      dentro del bloque.</li>
  <li><strong>VAR</strong>, <strong>RETURN</strong>, <strong>BREAK</strong> y
      <strong>CONTINUE</strong> tambi\u00E9n est\u00E1n disponibles.</li>
</ul>
<p>
  Seleccione un nodo <code>EXCEPT</code> para editar su patr\u00F3n de error y su
  variable de captura (<code>AS \${error}</code>) en el panel de detalles. Cambie a
  la pesta\u00F1a Code en cualquier momento para ver el texto <code>.robot</code>
  generado &mdash; la estructura y sus marcadores <code>END</code> sobreviven al
  round-trip fielmente.
</p>
<h4>Sincronizaci\u00F3n</h4>
<p>
  Las tres pesta\u00F1as del editor (Visual Editor, Code, Flow) comparten el mismo modelo de datos
  subyacente. Los cambios realizados en una pesta\u00F1a se reflejan inmediatamente en las dem\u00E1s.
  Por ejemplo, a\u00F1adir un nodo de palabra clave en la pesta\u00F1a Flow actualizar\u00E1 tanto el
  formulario del Visual Editor como el c\u00F3digo bruto <code>.robot</code>.
</p>`,
        tip: 'Use el MiniMap en la esquina inferior derecha del lienzo para navegar por suites de pruebas grandes. El panel de controles permite hacer zoom y ajustar la vista.'
      },
      {
        id: 'flow-editor-settings',
        title: 'Ajustes de caso de prueba &amp; palabra clave (notas laterales)',
        content: `
<p>
  Robot Framework permite adjuntar <strong>ajustes
  <code>[&hellip;]</code></strong> a un caso de prueba
  (<code>[Documentation]</code>, <code>[Tags]</code>, <code>[Setup]</code>,
  <code>[Teardown]</code>, <code>[Template]</code>, <code>[Timeout]</code>) y
  a una definición de palabra clave (los mismos más
  <code>[Arguments]</code>). El editor de flujo muestra cada ajuste
  poblado como su propia <strong>nota lateral</strong> apilada
  verticalmente a la izquierda del nodo Inicio, conectada por una
  arista discontinua.
</p>
<p>
  Cada nota lateral muestra una etiqueta como <code>[Tags]</code> y
  una breve vista previa en cursiva del valor (la documentación
  multilínea se limita a dos líneas para que una
  <code>[Documentation]</code> larga no desborde sobre la siguiente).
  Haga clic en una nota lateral para abrir un panel de detalles
  específico del tipo:
</p>
<ul>
  <li><strong>[Documentation]</strong> &mdash; área de texto multilínea.
  El texto multilínea se conserva como filas de continuación
  <code>...</code> en el archivo <code>.robot</code> guardado.</li>
  <li><strong>[Tags]</strong> / <strong>[Arguments]</strong> &mdash;
  entrada separada por comas. <code>${'${name}'}=default</code> es una
  especificación de argumento válida; <code>${'@{name}'}</code>
  funciona para varargs.</li>
  <li><strong>[Setup]</strong> / <strong>[Teardown]</strong> &mdash;
  nombre de la palabra clave a invocar antes / después del cuerpo.
  Sobrescribe Test Setup / Teardown a nivel de Suite solo para este
  caso de prueba.</li>
  <li><strong>[Template]</strong> (solo casos de prueba) &mdash;
  convierte el cuerpo en un bucle guiado por datos donde cada fila
  es una llamada a la palabra clave template.</li>
  <li><strong>[Timeout]</strong> &mdash; tiempo máximo antes de
  abortar (ej. <code>30s</code>, <code>5 minutes</code>).</li>
</ul>
<h4>Añadir un ajuste</h4>
<p>
  Haga clic en el nodo Inicio para abrir el panel
  <strong>Ajustes del caso de prueba</strong> /
  <strong>Ajustes de la palabra clave</strong>. Para cada tipo aún
  no adjunto aparece un botón <strong>+ [&hellip;]</strong>; haga
  clic en él y la nota lateral aparece con un placeholder atenuado
  «haz clic para editar», listo para entrada. Una vez que cada tipo
  está rellenado, el panel cae a una pista que apunta a las notas
  laterales.
</p>
<h4>Quitar un ajuste</h4>
<p>
  Abra el panel de detalles de la nota lateral y use el botón
  <strong>&times;</strong> en el encabezado. La nota lateral
  desaparece del lienzo en cuanto el valor subyacente se vacía.
</p>
<p>
  Las ediciones se almacenan en buffer localmente y se confirman al
  formulario en el <strong>blur</strong> &mdash; teclear ya no
  dispara un deep-watcher por cada pulsación, el panel sobrevive a
  ediciones multi-carácter intactas.
</p>`,
        tip: 'Una nota lateral es solo una visualización de la línea [Documentation] / [Tags] / etc. subyacente — el serializador round-trip siempre produce la sintaxis .robot canónica, así que un archivo editado en la pestaña Flow y guardado se ve idéntico a uno escrito a mano.'
      },
      {
        id: 'explorer-search',
        title: 'B\u00FAsqueda',
        content: `
<p>
  El Explorador incluye una funci\u00F3n de <strong>b\u00FAsqueda</strong> que le
  permite encontrar archivos y contenido dentro del repositorio seleccionado:
</p>
<ul>
  <li><strong>B\u00FAsqueda por nombre de archivo</strong> &mdash; Escriba un nombre de archivo o
      patr\u00F3n en la barra de b\u00FAsqueda en la parte superior del \u00E1rbol de archivos
      para filtrar la vista del \u00E1rbol.</li>
  <li><strong>B\u00FAsqueda de contenido</strong> &mdash; Use el panel de b\u00FAsqueda para encontrar
      cadenas de texto dentro del contenido de los archivos. Los resultados muestran
      l\u00EDneas coincidentes con su ruta de archivo y n\u00FAmero de l\u00EDnea.</li>
</ul>
<p>
  Al hacer clic en un resultado de b\u00FAsqueda, se abre el archivo correspondiente
  en el editor y se desplaza hasta la l\u00EDnea coincidente.
</p>`
      },
      {
        id: 'run-from-explorer',
        title: 'Ejecutar pruebas desde el Explorador',
        content: `
<p>
  Los usuarios con rol <strong>Runner</strong> o superior pueden lanzar ejecuciones
  de pruebas directamente desde el Explorador. Al visualizar un archivo
  <code>.robot</code> o un directorio que contiene archivos de prueba:
</p>
<ol>
  <li>Haga clic en el bot\u00F3n <strong>Ejecutar</strong> en la barra de herramientas del editor o haga clic derecho en un archivo/carpeta del \u00E1rbol.</li>
  <li>La ruta de destino se rellena autom\u00E1ticamente, apuntando al archivo o directorio seleccionado.</li>
  <li>Opcionalmente configure un valor de <strong>tiempo de espera</strong>.</li>
  <li>Haga clic en <strong>Iniciar ejecuci\u00F3n</strong> para lanzar la ejecuci\u00F3n.</li>
</ol>
<p>
  El estado de la ejecuci\u00F3n aparece en tiempo real mediante WebSocket. Puede
  cambiar a la p\u00E1gina de <strong>Ejecuci\u00F3n</strong> para supervisar el
  progreso o continuar editando mientras las pruebas se ejecutan en segundo plano.
</p>`,
        tip: 'Ejecutar un solo archivo .robot es \u00FAtil para validaci\u00F3n r\u00E1pida, mientras que ejecutar un directorio ejecuta la suite completa.'
      }
    ]
  },

  // ─── 5. Recorder ──────────────────────────────────────────────────
  {
    id: 'recorder',
    title: 'Grabador',
    icon: '\uD83D\uDD34',
    subsections: [
      {
        id: 'recorder-overview',
        title: '\u00BFQu\u00E9 es el Grabador?',
        content: `
<p>
  El <strong>Grabador de RoboScope</strong> permite capturar interacciones del navegador y
  generar autom\u00E1ticamente archivos de prueba <code>.robot</code>. Hay dos m\u00E9todos de grabaci\u00F3n:
</p>
<ul>
  <li><strong>Recorder v2 (recomendado)</strong> &mdash; Abra el lanzador desde la entrada
  <em>Recorder</em> de la barra lateral, o directamente desde la barra de herramientas del
  Explorer mediante el bot\u00F3n <em>Recorder v2</em> (el bot\u00F3n del Explorer preselecciona el
  repositorio actual). El lanzador ofrece un selector de transporte (Web / Desktop&nbsp;Windows),
  un campo opcional <em>Abrir URL</em> para que el navegador controlado navegue directamente
  a su p\u00E1gina de inicio (solo se aceptan URL <code>http://</code> / <code>https://</code>
  &mdash; d\u00E9jelo en blanco para iniciar en <code>about:blank</code>), abre una sesi\u00F3n de
  navegador controlada y transmite cada acci\u00F3n capturada mediante Server-Sent Events a la
  lista de pasos en vivo &mdash; con candidatos de selector por paso.</li>
  <li><strong>Extensi\u00F3n de Chrome</strong> &mdash; Instale la extensi\u00F3n RoboScope Recorder para grabar
  directamente en su propio navegador. Las acciones se env\u00EDan a RoboScope a trav\u00E9s de la API cuando est\u00E1 conectado.
  El bot\u00F3n del grabador integrado legacy que antes aparec\u00EDa en la barra de herramientas del Explorer ha sido eliminado;
  los flujos de la extensi\u00F3n de Chrome no se ven afectados porque se comunican directamente con el backend.</li>
</ul>
<h4>Flujo de grabaci\u00F3n</h4>
<ol>
  <li>Iniciar una grabaci\u00F3n (integrada o mediante la extensi\u00F3n)</li>
  <li>Interactuar con la aplicaci\u00F3n web a probar</li>
  <li>Detener la grabaci\u00F3n &mdash; RoboScope genera un archivo <code>.robot</code></li>
  <li>Revisar, editar y guardar la prueba generada en su proyecto</li>
</ol>`,
        tip: 'El grabador integrado funciona sin extensi\u00F3n del navegador. La extensi\u00F3n de Chrome es \u00FAtil para grabar en un navegador donde ya ha iniciado sesi\u00F3n.'
      },
      {
        id: 'recorder-anatomy',
        title: 'Anatom\u00EDa del archivo .robot generado',
        content: `
<p>
  Las grabaciones web se convierten en un archivo <code>.robot</code> autocontenido con
  un <strong>bloque Variables</strong> para el modo visible/headless y un bootstrap de
  Browser-library calibrado para p\u00E1ginas reales.
</p>
<pre><code>*** Settings ***
Library           Browser

*** Variables ***
\${HEADLESS}       false

*** Test Cases ***
Recording 21
    New Browser    chromium    headless=\${HEADLESS}
    New Context
    New Page    https://example.com    wait_until=domcontentloaded
    Click    text=Iniciar sesi\u00F3n
    ...</code></pre>
<h4>Por qu\u00E9 <code>\${HEADLESS}</code> como variable</h4>
<p>
  Permite alternar entre visible y headless sin tocar el cuerpo del test \u2014 basta con
  sobrescribir al invocar:
  <code>robot --variable HEADLESS:true tests/&lt;archivo&gt;.robot</code>. El valor
  por defecto <code>false</code> (navegador visible) refleja el contexto interactivo
  de grabaci\u00F3n.
</p>
<h4>Por qu\u00E9 <code>wait_until=domcontentloaded</code></h4>
<p>
  El default de Playwright <code>wait_until="load"</code> espera por cada subrecurso
  (anuncios, trackers, etiquetas <code>&lt;script&gt;</code> tard\u00EDas). En p\u00E1ginas
  reales eso a menudo no ocurre dentro del timeout de 10 s \u2014 el test falla aunque
  la p\u00E1gina est\u00E9 visiblemente cargada.
  <code>domcontentloaded</code> es suficiente: el DOM est\u00E1 analizado, cualquier
  Click / Type Text / Scroll To Element posterior encuentra su objetivo.
</p>
<h4>Edici\u00F3n en el editor visual</h4>
<p>
  En el panel de detalles del Flow Editor, un peque\u00F1o bot\u00F3n <code>{}</code> junto a
  cualquier entrada tipada (casilla / n\u00FAmero / lista) cambia el slot a entrada de
  texto libre \u2014 \u00FAtil para introducir una variable como <code>\${HEADLESS}</code>
  en un par\u00E1metro booleano, o valores que el recorder no haya podido inferir.
</p>`
      },
      {
        id: 'recorder-selector-verification',
        title: 'Verificaci\u00F3n de selectores &amp; Shadow DOM',
        content: `
<p>
  Cada acci\u00F3n capturada se env\u00EDa con una lista de selectores candidatos
  &mdash; <code>data-testid</code>, <code>role + name</code>, <code>text</code>,
  <code>css</code> (id, clase, parent-scoped), <code>xpath</code>, y una
  cadena <code>host &gt;&gt; inner</code> aware de Shadow DOM cuando aplica.
  RoboScope los clasifica para que el candidato activo sobreviva al
  contrato de modo estricto de Playwright en el replay.
</p>
<h4>Unicidad consciente de la visibilidad</h4>
<p>
  Al capturar, el verificador resuelve cada candidato contra la p\u00E1gina
  en vivo en un \u00FAnico viaje <code>evaluate_all</code> y devuelve
  <code>{ total, visible, actionable }</code>:
</p>
<ul>
  <li><strong>actionable = 1</strong> &mdash; oro; exactamente una
  coincidencia visible + cliqueable.</li>
  <li><strong>visible = 1</strong> &mdash; verificado, penalizaci\u00F3n
  ligera (-5); el elemento es visible pero est\u00E1 deshabilitado
  (ej. input read-only).</li>
  <li><strong>visible &ge; 2</strong> &mdash; multi-coincidencia;
  reescrito a un <code>:nth-match(1)</code> /
  <code>... &gt;&gt; nth=0</code> seg\u00FAn la estrategia para que el
  replay en modo estricto siga eligiendo un elemento. Penalizaci\u00F3n
  -15 para que una alternativa desambiguada por contexto-padre
  gane cuando exista.</li>
  <li><strong>visible = 0, total &ge; 1</strong> &mdash; elemento
  oculto; mantenido como red de seguridad (-25) para que un futuro
  auto-heal pueda probarlo, pero cualquier alternativa visible
  gana siempre.</li>
  <li><strong>total = 0</strong> &mdash; el selector apunta a nada,
  descartado.</li>
</ul>
<h4>Desambiguaci\u00F3n por contexto padre</h4>
<p>
  Un <code>button.submit-btn</code> desnudo que coincida con todos
  los botones Submit de la p\u00E1gina es la causa m\u00E1s com\u00FAn de fallo
  de modo estricto de Playwright en el replay. La estrategia CSS
  ahora tambi\u00E9n emite una variante con scope de ancestro siempre
  que un ancestro estable tenga id / data-testid &mdash; ej.
  <code>#checkout-form button.submit-btn</code> &mdash; con un
  bonus de calidad +10 sobre la cadena desnuda. El verificador la
  prefiere siempre que desambig\u00FCe.
</p>
<h4>Shadow DOM</h4>
<p>
  El script de captura usa <code>ev.composedPath()[0]</code> en
  cada evento para que un clic dentro de una shadow root abierta
  capture el elemento *real* clicado, no el host en el light DOM.
  La caminata de ancestros cruza fronteras shadow v\u00EDa el nodo
  host; cada ancestro lleva una bandera <code>is_shadow_host</code>.
</p>
<p>
  Cuando el elemento capturado vive dentro de una (o varias)
  shadow roots abiertas, la s\u00EDntesis emite un candidato Playwright
  encadenado <code>&lt;host-selector&gt; &gt;&gt; &lt;inner&gt;</code>
  (ej. <code>my-dialog &gt;&gt; [data-testid=&quot;save-btn&quot;]</code>).
  Esto atraviesa expl\u00EDcitamente la frontera shadow &mdash; depender
  del piercing impl\u00EDcito de Playwright depende del motor y es
  f\u00E1cil de configurar mal en el lado Browser library / runner RF.
  Las shadow roots cerradas siguen siendo opacas para el JS
  userspace, as\u00ED que los elementos en root cerrada caen al
  selector del host capturado.
</p>`,
        tip: 'En la UI del recorder, una \u2713 verde junto a un selector significa que resuelve a un \u00FAnico elemento visible + accionable en la p\u00E1gina en vivo. Varios candidatos aparecen ordenados por rango \u2014 el selector permite cambiar a otro si la elecci\u00F3n autom\u00E1tica no coincide con su intenci\u00F3n.'
      },
      {
        id: 'recorder-extension',
        title: 'Extensi\u00F3n de Chrome',
        content: `
<p>
  La extensi\u00F3n de Chrome <strong>RoboScope Recorder</strong> graba interacciones directamente
  en su navegador &mdash; sin necesidad de una ventana separada. Especialmente \u00FAtil
  para p\u00E1ginas que requieren autenticaci\u00F3n, ya que ya ha iniciado sesi\u00F3n.
</p>
<h4>Instalaci\u00F3n</h4>
<ol>
  <li>En el repositorio de RoboScope, encuentre el directorio <code>extension/</code></li>
  <li>Abra <code>chrome://extensions</code> en Chrome o cualquier navegador basado en Chromium</li>
  <li>Active el <strong>Modo de desarrollador</strong> (interruptor en la esquina superior derecha)</li>
  <li>Haga clic en <strong>Cargar extensi\u00F3n sin empaquetar</strong> y seleccione la carpeta <code>extension/</code></li>
  <li>El icono de RoboScope Recorder aparece en la barra de herramientas del navegador</li>
</ol>
<h4>Conexi\u00F3n con RoboScope</h4>
<ol>
  <li>Haga clic derecho en el icono de la extensi\u00F3n y seleccione <strong>Opciones</strong></li>
  <li>Introduzca la <strong>URL del servidor</strong> (ej. <code>http://localhost:8000</code>)</li>
  <li>Introduzca un <strong>Token API</strong> (cr\u00E9elo en RoboScope en Configuraci\u00F3n &rarr; Tokens API)</li>
  <li>Haga clic en <strong>Probar conexi\u00F3n</strong> para verificar</li>
  <li>Seleccione el <strong>Proyecto</strong> objetivo del men\u00FA desplegable</li>
  <li>Haga clic en <strong>Guardar</strong></li>
</ol>
<p>
  Una vez conectado, un indicador verde aparece en el popup de la extensi\u00F3n.
  Todas las acciones grabadas se env\u00EDan autom\u00E1ticamente a su instancia de RoboScope.
</p>`,
        tip: 'La extensi\u00F3n tambi\u00E9n funciona en modo aut\u00F3nomo sin conexi\u00F3n a RoboScope &mdash; genera archivos .robot localmente para descargar.'
      },
      {
        id: 'recorder-extension-usage',
        title: 'Uso de la extensi\u00F3n',
        content: `
<p>
  Haga clic en el icono de la extensi\u00F3n para abrir el popup:
</p>
<ol>
  <li>Haga clic en <strong>Grabar</strong> para capturar acciones en la p\u00E1gina actual</li>
  <li>Interact\u00FAe con la p\u00E1gina &mdash; clics, entradas de texto y selecciones se capturan</li>
  <li>Haga clic en <strong>Detener</strong> para finalizar y generar el script</li>
  <li>Use <strong>Copiar</strong> o <strong>Descargar</strong> para guardar el archivo <code>.robot</code> generado</li>
</ol>
<h4>Funciones adicionales</h4>
<ul>
  <li><strong>Pausa / Reanudar</strong> &mdash; Interrumpir temporalmente sin perder las acciones capturadas</li>
  <li><strong>Escanear p\u00E1gina</strong> &mdash; Analizar la p\u00E1gina en busca de elementos interactivos y generar locators</li>
  <li><strong>Consola XPath</strong> &mdash; Validar expresiones XPath con resaltado visual en la p\u00E1gina</li>
  <li><strong>Plantillas</strong> &mdash; Insertar plantillas de scripts predefinidas (Login, Formulario, Navegaci\u00F3n)</li>
  <li><strong>Configuraci\u00F3n</strong> &mdash; Elegir biblioteca objetivo, sintaxis e idioma</li>
</ul>
<h4>Biblioteca objetivo</h4>
<table>
  <thead>
    <tr><th>Biblioteca</th><th>Keywords</th><th>Caso de uso</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Browser</strong></td>
      <td><code>Click</code>, <code>Fill Text</code>, <code>Select Options By</code></td>
      <td>Pruebas modernas basadas en Playwright</td>
    </tr>
    <tr>
      <td><strong>SeleniumLibrary</strong></td>
      <td><code>Click Element</code>, <code>Input Text</code>, <code>Select From List By Value</code></td>
      <td>Pruebas legacy basadas en Selenium</td>
    </tr>
  </tbody>
</table>`
      }
    ]
  },

  // ─── 6. Ejecuci\u00F3n ─────────────────────────────────────────────────
  {
    id: 'execution',
    title: 'Ejecuci\u00F3n',
    icon: '\u25B6\uFE0F',
    subsections: [
      {
        id: 'start-run',
        title: 'Iniciar una nueva ejecuci\u00F3n',
        content: `
<p>
  Para iniciar una nueva ejecuci\u00F3n de pruebas desde la p\u00E1gina de
  <strong>Ejecuci\u00F3n</strong>:
</p>
<ol>
  <li>Haga clic en el bot\u00F3n <strong>Nueva ejecuci\u00F3n</strong> en la parte superior de la p\u00E1gina.</li>
  <li>Seleccione un <strong>Repositorio</strong> del men\u00FA desplegable.</li>
  <li>Opcionalmente especifique una <strong>Ruta de destino</strong> &mdash; una ruta relativa dentro del
      repositorio para restringir la ejecuci\u00F3n a un archivo o directorio espec\u00EDfico. D\u00E9jelo
      vac\u00EDo para ejecutar todas las pruebas.</li>
  <li>Establezca un <strong>Tiempo de espera</strong> en segundos (por defecto: <code>3600</code>
      segundos / 1 hora). Las ejecuciones que excedan esta duraci\u00F3n ser\u00E1n terminadas
      autom\u00E1ticamente.</li>
  <li>Haga clic en <strong>Iniciar</strong> para poner en cola la ejecuci\u00F3n.</li>
</ol>
<p>
  La ejecuci\u00F3n entra en estado <code>pending</code> y es recogida por el ejecutor
  de tareas. Dado que RoboScope utiliza un ejecutor de un solo worker, las ejecuciones
  se procesan una a la vez en orden FIFO (primero en entrar, primero en salir).
</p>
<h4>Panel de actividad pendiente</h4>
<p>
  Mientras una ejecuci\u00F3n est\u00E9 en estado <code>pending</code>, el panel de detalle muestra
  un peque\u00F1o recuadro \u00E1mbar de <em>Actividad pendiente</em> que explica <strong>por qu\u00E9</strong>
  a\u00FAn no ha comenzado:
</p>
<ul>
  <li><strong>En espera detr\u00E1s de N run(s)</strong> &mdash; uno o m\u00E1s runs anteriores ocupan todav\u00EDa
  el \u00FAnico slot del ejecutor. La posici\u00F3n en la cola se refresca cada pocos segundos.</li>
  <li><strong>Esperando la construcci\u00F3n de la imagen Docker en &lt;entorno&gt;</strong> &mdash; el entorno
  asignado est\u00E1 construyendo su imagen. La cola del log de build se muestra en el panel; el enlace
  <em>Abrir Entornos</em> lleva al log completo.</li>
  <li><strong>Preparando el run\u2026</strong> &mdash; estado transitorio breve que normalmente pasa a
  <code>running</code> en pocos segundos.</li>
</ul>`,
        tip: 'Si necesita ejecutar pruebas de m\u00FAltiples repositorios, p\u00F3ngalas en cola secuencialmente. Se ejecutar\u00E1n en orden.'
      },
      {
        id: 'advanced-run-config',
        title: 'Configuración de ejecución avanzada',
        content: `
<p>
  Más allá del repositorio y la ruta de destino, el diálogo de ejecución ofrece
  controles opcionales para definir <em>cómo</em> se ejecuta Robot Framework. Algunos
  están disponibles para todos; las palancas más potentes se rigen por indicadores de
  función que un administrador debe habilitar primero.
</p>
<h4>Incluir / excluir etiquetas mediante una lista de selección</h4>
<p>
  Use los campos <strong>Incluir etiquetas</strong> y <strong>Excluir etiquetas</strong>
  para ejecutar solo un subconjunto de pruebas. RoboScope analiza las suites del
  repositorio en busca de cada etiqueta declarada (<code>[Tags]</code>, <code>Test Tags</code>,
  <code>Force Tags</code>, <code>Default Tags</code>, <code>Keyword Tags</code>) y las ofrece
  como lista de selección, para que no tenga que recordar los nombres exactos. Aún puede
  escribir libremente una etiqueta que todavía no se haya detectado.
</p>
<h4>Argumentos &amp; variables avanzados (habilitados por el administrador)</h4>
<p>
  Cuando un administrador habilita el indicador <code>executionAdvancedArgs</code>, aparece
  una sección <strong>Avanzado</strong> para usuarios con rol <strong>Editor</strong> o
  superior. Proporciona un editor de <strong>variables</strong> clave/valor (pasadas como
  <code>--variable KEY:VALUE</code>) y un campo libre de <strong>argumentos de robot</strong>
  para opciones adicionales seguras como <code>--randomize all</code>.
</p>
<p>
  Por seguridad, RoboScope valida cada argumento antes de ejecutarlo. Las opciones que
  controlan las ubicaciones de salida (<code>--outputdir</code>, <code>--log</code>,
  <code>--report</code>, …) y cualquier cosa que pueda cargar o ejecutar código
  (<code>--listener</code>, <code>--pythonpath</code>, <code>--variablefile</code>,
  <code>--argumentfile</code>, <code>--prerunmodifier</code>, …) se rechazan, incluidos sus
  alias cortos y abreviaturas. Los argumentos siempre se pasan como una lista, nunca a través
  de un shell, y cada ejecución avanzada se registra en el registro de auditoría.
</p>
<h4>PreRunModifiers &amp; pruebas basadas en datos (habilitados por el administrador)</h4>
<p>
  Otras dos palancas se encuentran tras sus propios indicadores desactivados por defecto:
  <code>executionPreRunModifierUserCode</code> (solo administrador — aplica código modificador
  personalizado que da forma al modelo de la suite antes de la ejecución) y
  <code>executionDataDriver</code> (genera casos de prueba en tiempo de ejecución a partir de
  una fuente de datos CSV frente a una prueba <code>[Template]</code>). Ambos están
  desactivados por defecto y pensados para usuarios avanzados.
</p>
<h4>Relacionado</h4>
<ul>
  <li><strong>Archivos de inicialización de suite</strong> — puede editar el
  <code>__init__.robot</code> de una suite en el editor; RoboScope avisa si declara una
  sección <code>*** Test Cases ***</code>, que Robot Framework prohíbe en un archivo de
  inicialización. Consulte <em>Explorador</em>.</li>
  <li><strong>Nombre largo &amp; id estructural</strong> — el nombre largo completo
  <code>Suite.Sub.Test</code> y el id estructural (p.&nbsp;ej. <code>s1-t1</code>) de cada
  prueba se muestran de solo lectura en la vista de detalle del informe. Consulte
  <em>Informes</em>.</li>
</ul>`,
        tip: 'La sección «Avanzado» permanece oculta a menos que su indicador de función esté habilitado: RoboScope nunca muestra un control que no puede usar. Un administrador puede activar los indicadores en Ajustes → Funciones.'
      },
      {
        id: 'run-status-table',
        title: 'Tabla de estado de ejecuciones',
        content: `
<p>
  La vista principal de Ejecuci\u00F3n muestra una tabla de todas las ejecuciones
  de pruebas, ordenadas por fecha de creaci\u00F3n (m\u00E1s recientes primero). Cada
  fila muestra:
</p>
<table>
  <thead>
    <tr><th>Columna</th><th>Descripci\u00F3n</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>ID</strong></td><td>Identificador \u00FAnico de la ejecuci\u00F3n.</td></tr>
    <tr><td><strong>Repositorio</strong></td><td>El repositorio al que pertenece la ejecuci\u00F3n.</td></tr>
    <tr><td><strong>Destino</strong></td><td>El archivo o directorio objetivo (o &ldquo;all&rdquo; si es todo el repositorio).</td></tr>
    <tr><td><strong>Estado</strong></td><td>Insignia con c\u00F3digo de color: <code>pending</code>, <code>running</code>, <code>passed</code>, <code>failed</code>, <code>error</code>, <code>cancelled</code>, <code>timeout</code>.</td></tr>
    <tr><td><strong>Duraci\u00F3n</strong></td><td>Tiempo transcurrido desde el inicio hasta la finalizaci\u00F3n.</td></tr>
    <tr><td><strong>Iniciado por</strong></td><td>Usuario que inici\u00F3 la ejecuci\u00F3n.</td></tr>
    <tr><td><strong>Creado</strong></td><td>Marca de tiempo de cu\u00E1ndo se puso en cola la ejecuci\u00F3n.</td></tr>
  </tbody>
</table>
<p>
  Las insignias de estado se actualizan <strong>en tiempo real</strong> mediante
  WebSocket, por lo que nunca necesita actualizar la p\u00E1gina manualmente.
</p>`
      },
      {
        id: 'run-details',
        title: 'Detalles de la ejecuci\u00F3n y salida',
        content: `
<p>
  Haga clic en cualquier fila de ejecuci\u00F3n para abrir la vista de
  <strong>Detalles de la ejecuci\u00F3n</strong>, que proporciona:
</p>
<ul>
  <li><strong>Metadatos de la ejecuci\u00F3n</strong> &mdash; Repositorio, ruta de destino, iniciado por, marcas de tiempo, tiempo de espera y estado final.</li>
  <li><strong>Salida est\u00E1ndar (stdout)</strong> &mdash; La salida de consola de Robot Framework, transmitida en vivo mientras la ejecuci\u00F3n est\u00E1 en progreso.</li>
  <li><strong>Error est\u00E1ndar (stderr)</strong> &mdash; Cualquier salida de error del proceso Python, \u00FAtil para diagnosticar fallos o errores de importaci\u00F3n.</li>
</ul>
<p>
  El panel de salida se desplaza autom\u00E1ticamente hacia abajo durante las
  ejecuciones activas. Puede desactivar el desplazamiento autom\u00E1tico para
  inspeccionar la salida anterior. La salida se muestra en fuente monoespaciada
  con colores ANSI eliminados para facilitar la lectura.
</p>`
      },
      {
        id: 'cancel-retry',
        title: 'Cancelar y reintentar',
        content: `
<p>
  La p\u00E1gina de Ejecuci\u00F3n proporciona varias acciones de control:
</p>
<h4>Cancelar una ejecuci\u00F3n</h4>
<p>
  Haga clic en el bot\u00F3n <strong>Cancelar</strong> en una ejecuci\u00F3n con estado
  <code>running</code> o <code>pending</code> para terminarla. Al proceso subyacente
  el subproceso se termina realmente (no solo se marca), liberando los recursos
  inmediatamente. El estado cambia a <code>cancelled</code>.
  Requiere rol <strong>Runner</strong> o superior.
</p>
<h4>Reintentar una ejecuci\u00F3n</h4>
<p>
  Para ejecuciones en estado terminal (<code>failed</code>, <code>error</code>,
  <code>cancelled</code>, <code>timeout</code>), aparece un bot\u00F3n
  <strong>Reintentar</strong>. Al hacer clic, se crea una nueva ejecuci\u00F3n con
  la misma configuraci\u00F3n (repositorio, destino, tiempo de espera) y se pone
  en cola para su ejecuci\u00F3n.
</p>
<h4>Cancelar todas las ejecuciones</h4>
<p>
  El bot\u00F3n <strong>Cancelar todo</strong> en la parte superior de la p\u00E1gina
  de Ejecuci\u00F3n termina todas las ejecuciones actualmente en estado
  <code>running</code> y <code>pending</code> en una sola acci\u00F3n. Esto es
  \u00FAtil cuando necesita liberar el ejecutor inmediatamente. Requiere rol
  <strong>Runner</strong> o superior.
</p>`,
        tip: 'Use "Cancelar todo" con precauci\u00F3n en entornos multiusuario, ya que afecta a las ejecuciones iniciadas por todos los usuarios.'
      }
    ]
  },

  // ─── 6. Informes ──────────────────────────────────────────────────
  {
    id: 'reports',
    title: 'Informes',
    icon: '\u{1F4CB}',
    subsections: [
      {
        id: 'report-list',
        title: 'Lista de informes',
        content: `
<p>
  La p\u00E1gina de <strong>Informes</strong> muestra todos los informes de pruebas
  generados. Despu\u00E9s de cada ejecuci\u00F3n completada, Robot Framework produce
  un archivo <code>output.xml</code> que RoboScope analiza y almacena para su
  posterior an\u00E1lisis.
</p>
<p>Cada fila de informe muestra:</p>
<ul>
  <li><strong>ID del informe</strong> &mdash; Identificador \u00FAnico vinculado a la ejecuci\u00F3n de origen.</li>
  <li><strong>Repositorio</strong> &mdash; Nombre del repositorio de origen.</li>
  <li><strong>Aprobados / Fallidos</strong> &mdash; N\u00FAmero de casos de prueba aprobados y fallidos, mostrados como insignias de color.</li>
  <li><strong>Total de pruebas</strong> &mdash; Recuento total de casos de prueba.</li>
  <li><strong>Duraci\u00F3n</strong> &mdash; Duraci\u00F3n total de la ejecuci\u00F3n.</li>
  <li><strong>Creado</strong> &mdash; Marca de tiempo de la generaci\u00F3n del informe.</li>
</ul>
<p>
  Haga clic en cualquier fila para abrir la vista detallada del <strong>Informe</strong>.
</p>`
      },
      {
        id: 'report-detail',
        title: 'Vista detallada del informe',
        content: `
<p>
  La p\u00E1gina de detalle del informe proporciona tres pesta\u00F1as para analizar
  los resultados de las pruebas:
</p>
<h4>Pesta\u00F1a de resumen</h4>
<p>
  Muestra tarjetas KPI (total de pruebas, aprobadas, fallidas, duraci\u00F3n), una
  tabla de pruebas fallidas con mensajes de error y una tabla de todos los resultados
  de pruebas con estado, suite, duraci\u00F3n y etiquetas. Al hacer clic en el nombre
  de una prueba, se navega a la vista de <strong>Historial de la prueba</strong>
  para esa prueba.
</p>
<h4>Pesta\u00F1a de informe detallado</h4>
<p>
  Una vista de \u00E1rbol rica e interactiva de la ejecuci\u00F3n completa de pruebas
  &mdash; similar al <code>log.html</code> de Robot Framework pero integrada
  directamente en RoboScope. Analiza el <code>output.xml</code> y renderiza suites,
  pruebas y keywords como una jerarqu\u00EDa de \u00E1rbol expandible.
</p>
<p>Caracter\u00EDsticas de la pesta\u00F1a de informe detallado:</p>
<ul>
  <li><strong>Barra de herramientas</strong> &mdash; Botones <em>Expandir todo</em> / <em>Contraer todo</em>
      para abrir o cerrar r\u00E1pidamente todos los nodos del \u00E1rbol, y un <em>Filtro de estado</em>
      desplegable para mostrar Todos, Solo aprobados o Solo fallidos.</li>
  <li><strong>Estad\u00EDsticas de suite</strong> &mdash; Cada encabezado de suite muestra recuentos de
      aprobados/fallidos (por ejemplo, &#10003; 5 &#10007; 2) junto con la duraci\u00F3n.</li>
  <li><strong>Marcas de tiempo de keywords</strong> &mdash; Los keywords muestran su hora de inicio en
      formato <code>HH:MM:SS.sss</code> para un an\u00E1lisis preciso de tiempos.</li>
  <li><strong>Registro de mensajes</strong> &mdash; Los mensajes de cada keyword se muestran con marca
      de tiempo, nivel de registro (INFO, WARN, FAIL, DEBUG) y texto del mensaje. Los mensajes
      est\u00E1n codificados por color seg\u00FAn su nivel.</li>
  <li><strong>Capturas de pantalla en l\u00EDnea</strong> &mdash; Las capturas de pantalla de Robot Framework
      incrustadas en mensajes (por ejemplo, de SeleniumLibrary) se renderizan en l\u00EDnea con
      visualizaci\u00F3n correcta de im\u00E1genes. Las fuentes de imagen se resuelven autom\u00E1ticamente
      al endpoint de recursos del informe.</li>
  <li><strong>Etiquetas y argumentos</strong> &mdash; Las etiquetas de prueba se muestran como chips
      de color, y los argumentos de keywords se muestran cuando se expande un nodo de keyword.</li>
  <li><strong>Resaltado de errores</strong> &mdash; Las pruebas fallidas muestran su mensaje de error
      en un recuadro resaltado en rojo para una r\u00E1pida identificaci\u00F3n.</li>
</ul>
<h4>Pesta\u00F1a de informe HTML</h4>
<p>
  Incrusta el informe HTML original de Robot Framework (<code>report.html</code>) en un
  iframe con una barra de herramientas para navegaci\u00F3n (volver al Resumen) y recarga.
  Este es el mismo informe que obtendr\u00EDa al ejecutar <code>robot</code> en la l\u00EDnea
  de comandos, completo con gr\u00E1ficos interactivos, detalles de keywords y enlaces
  de registro.
</p>`,
        tip: 'Use la pesta\u00F1a de Informe detallado para depuraci\u00F3n en profundidad con tiempos a nivel de keyword y capturas de pantalla. El Filtro de estado ayuda a centrarse r\u00E1pidamente en los fallos.'
      },
      {
        id: 'report-download',
        title: 'Descarga ZIP',
        content: `
<p>
  Cada informe se puede descargar como un <strong>archivo ZIP</strong> que contiene
  todos los archivos de salida generados por Robot Framework:
</p>
<ul>
  <li><code>output.xml</code> &mdash; Salida XML legible por m\u00E1quina.</li>
  <li><code>report.html</code> &mdash; Informe HTML interactivo.</li>
  <li><code>log.html</code> &mdash; Registro detallado de ejecuci\u00F3n.</li>
  <li>Cualquier artefacto adicional (capturas de pantalla, etc.) capturado durante la ejecuci\u00F3n.</li>
</ul>
<p>
  Haga clic en el bot\u00F3n <strong>Descargar ZIP</strong> en la p\u00E1gina de detalle
  del informe. El archivo se genera en el servidor y se transmite a su navegador.
</p>`
      },
      {
        id: 'report-bulk-delete',
        title: 'Eliminaci\u00F3n masiva de informes',
        content: `
<p>
  Con el tiempo, los informes acumulados pueden consumir un espacio significativo en
  disco. La p\u00E1gina de Informes proporciona dos mecanismos de eliminaci\u00F3n:
</p>
<ul>
  <li><strong>Eliminaci\u00F3n individual</strong> &mdash; Haga clic en el icono de eliminar en una fila
      de informe para eliminar un solo informe (requiere <strong>Editor+</strong>).</li>
  <li><strong>Eliminar todos los informes</strong> &mdash; Haga clic en el bot\u00F3n <strong>Eliminar
      todo</strong> para eliminar todos los informes del sistema. Un di\u00E1logo de confirmaci\u00F3n
      asegura que no borre datos accidentalmente. Esta acci\u00F3n requiere el rol <strong>Admin</strong>.</li>
</ul>
<p>
  <strong>Nota:</strong> La eliminaci\u00F3n de informes es permanente. Los archivos de
  informe asociados se eliminan del directorio <code>REPORTS_DIR</code> en el servidor.
</p>`,
        tip: 'Considere descargar los informes importantes como ZIP antes de realizar una eliminaci\u00F3n masiva.'
      },
      {
        id: 'ai-failure-analysis',
        title: 'An\u00E1lisis IA de fallos',
        content: `
<p>
  Cuando un informe contiene tests fallidos, la pesta\u00F1a Resumen muestra una
  tarjeta de <strong>An\u00E1lisis IA de fallos</strong> en la parte inferior. Esta
  funci\u00F3n utiliza un proveedor LLM configurado para analizar autom\u00E1ticamente
  los fallos de tests y sugerir causas ra\u00EDz y correcciones.
</p>
<h4>Requisitos previos</h4>
<ul>
  <li>Al menos un <strong>proveedor de IA</strong> debe estar configurado en
      <strong>Configuraci\u00F3n &gt; Proveedores de IA</strong> (requiere rol Admin).</li>
  <li>El informe debe contener al menos un test fallido.</li>
</ul>
<h4>C\u00F3mo usar</h4>
<ol>
  <li>Navegue a un informe con tests fallidos. La tarjeta de an\u00E1lisis est\u00E1 disponible en <strong>dos lugares</strong>:
      <ul>
        <li><strong>P\u00E1gina de Informes</strong> &mdash; Haga clic en un informe para abrir la vista detallada.</li>
        <li><strong>P\u00E1gina de Ejecuci\u00F3n</strong> &mdash; Haga clic en un run completado para abrir el panel de detalles.</li>
      </ul>
  </li>
  <li>Despl\u00E1cese hacia abajo hasta la tarjeta <strong>An\u00E1lisis IA de fallos</strong>
      en la pesta\u00F1a Resumen.</li>
  <li>Haga clic en <strong>Analizar fallos</strong>. El an\u00E1lisis suele tardar entre
      10 y 30 segundos seg\u00FAn la cantidad de fallos y la velocidad del proveedor LLM.</li>
  <li>Una vez completado, el an\u00E1lisis se muestra como markdown formateado que incluye:
      <ul>
        <li><strong>An\u00E1lisis de causa ra\u00EDz</strong> &mdash; diagn\u00F3stico por fallo</li>
        <li><strong>Detecci\u00F3n de patrones</strong> &mdash; temas comunes entre fallos</li>
        <li><strong>Correcciones sugeridas</strong> &mdash; cambios de c\u00F3digo o configuraci\u00F3n</li>
        <li><strong>Clasificaci\u00F3n por prioridad</strong> &mdash; CRITICAL / HIGH / MEDIUM / LOW</li>
      </ul>
  </li>
</ol>
<h4>Estados</h4>
<ul>
  <li><strong>Sin proveedor</strong> &mdash; Si no hay ning\u00FAn proveedor de IA configurado,
      se muestra un mensaje que dirige a la p\u00E1gina de Configuraci\u00F3n.</li>
  <li><strong>Cargando</strong> &mdash; Se muestra un indicador de progreso durante el procesamiento.</li>
  <li><strong>Error</strong> &mdash; Si el an\u00E1lisis falla (ej.: l\u00EDmite de tasa de API), se muestra
      el mensaje de error con un bot\u00F3n de Reintentar.</li>
  <li><strong>Completado</strong> &mdash; El resultado se muestra con un contador de tokens
      y un bot\u00F3n para volver a analizar.</li>
</ul>
<h4>Idioma de salida</h4>
<p>
  El an\u00E1lisis se genera en el <strong>idioma actualmente seleccionado en la
  interfaz</strong> (EN/DE/FR/ES/ZH) &mdash; la prosa, los t\u00EDtulos y el resumen
  se localizan, mientras que el c\u00F3digo, las palabras clave de Robot Framework,
  las rutas de archivo y los parches sugeridos se mantienen literales para que
  sigan siendo v\u00E1lidos.
</p>
<h4>Parches sugeridos y correcci\u00F3n con un clic</h4>
<p>
  Cuando una correcci\u00F3n es lo bastante concreta, el an\u00E1lisis la presenta como
  un <strong>parche</strong> en formato unified-diff debajo de la prosa, mostrando
  el archivo afectado. Para cada parche puede:
</p>
<ul>
  <li><strong>Corregir autom\u00E1ticamente</strong> &mdash; aplica el parche
      directamente al archivo en el repositorio. El cambio se aplica
      <em>priorizando el contexto</em> (los n\u00FAmeros de l\u00EDnea del diff son
      orientativos) y se <strong>rechaza</strong> si las l\u00EDneas circundantes
      ya no coinciden con el archivo actual &mdash; de modo que un parche obsoleto
      nunca puede corromper un test de forma silenciosa. Revise el diff primero;
      la aplicaci\u00F3n es una acci\u00F3n expl\u00EDcita, con un solo clic.</li>
  <li><strong>Copiar parche</strong> &mdash; copia el unified diff al portapapeles
      para aplicarlo manualmente en su editor.</li>
</ul>
<p>
  El an\u00E1lisis est\u00E1 acotado a la ejecuci\u00F3n para la que se gener\u00F3: abrir una
  ejecuci\u00F3n diferente muestra el an\u00E1lisis propio de esa ejecuci\u00F3n (o ninguno
  todav\u00EDa), nunca un resultado obsoleto de una ejecuci\u00F3n vista anteriormente.
</p>
<p>
  El an\u00E1lisis se ejecuta como una tarea en segundo plano y no bloquea otras operaciones.
  Cada an\u00E1lisis es una llamada LLM independiente &mdash; un rean\u00E1lisis puede producir
  resultados diferentes.
</p>
<h4>Enriquecimiento rf-mcp</h4>
<p>
  Si el <strong>servidor rf-mcp</strong> est\u00E1 en ejecuci\u00F3n (configurado en Configuraci\u00F3n &gt; Robot Framework Knowledge),
  el an\u00E1lisis se enriquece autom\u00E1ticamente con documentaci\u00F3n de palabras clave de Robot Framework.
  El sistema extrae nombres de palabras clave de los mensajes de error (p. ej., \u00ABNo keyword with name
  \u2018Click Element\u2019 found\u00BB) y busca su documentaci\u00F3n a trav\u00E9s de rf-mcp.
  Esto proporciona al LLM firmas de palabras clave precisas y ejemplos de uso,
  lo que mejora la calidad de las sugerencias de correcci\u00F3n.
</p>`,
        tip: 'El an\u00E1lisis de IA funciona mejor con mensajes de error descriptivos. Si sus tests usan mensajes de fallo personalizados, el LLM puede proporcionar sugerencias m\u00E1s espec\u00EDficas. Active el servidor rf-mcp para obtener mejores resultados.'
      }
    ]
  },

  // ─── 7. Estad\u00EDsticas ──────────────────────────────────────────────
  {
    id: 'statistics',
    title: 'Estad\u00EDsticas',
    icon: '\u{1F4C8}',
    subsections: [
      {
        id: 'stats-overview',
        title: 'Visi\u00F3n general de estad\u00EDsticas',
        content: `
<p>
  La p\u00E1gina de <strong>Estad\u00EDsticas</strong> ofrece informaci\u00F3n basada
  en datos sobre su actividad de pruebas a lo largo del tiempo. Combina tarjetas
  KPI, gr\u00E1ficos de tendencias y detecci\u00F3n de pruebas inestables para
  ayudarle a comprender las tendencias de calidad e identificar \u00E1reas
  problem\u00E1ticas.
</p>
<p>
  Todos los datos son accesibles para cualquier usuario autenticado (Viewer y
  superior). La p\u00E1gina obtiene autom\u00E1ticamente datos actualizados cuando
  se cambian los filtros.
</p>`
      },
      {
        id: 'stats-filters',
        title: 'Filtros de per\u00EDodo y repositorio',
        content: `
<p>
  Dos controles de filtro aparecen en la parte superior de la p\u00E1gina de Estad\u00EDsticas:
</p>
<h4>Per\u00EDodo de tiempo</h4>
<p>
  Seleccione una ventana de tiempo predefinida para todas las estad\u00EDsticas:
</p>
<ul>
  <li><strong>7 d\u00EDas</strong> &mdash; \u00DAltima semana de actividad.</li>
  <li><strong>14 d\u00EDas</strong> &mdash; \u00DAltimas dos semanas.</li>
  <li><strong>30 d\u00EDas</strong> &mdash; \u00DAltimo mes (por defecto).</li>
  <li><strong>90 d\u00EDas</strong> &mdash; \u00DAltimo trimestre.</li>
  <li><strong>1 a\u00F1o</strong> &mdash; \u00DAltimos 365 d\u00EDas.</li>
</ul>
<h4>Filtro de repositorio</h4>
<p>
  Opcionalmente seleccione un repositorio espec\u00EDfico para acotar las estad\u00EDsticas.
  Cuando est\u00E1 establecido en <strong>Todos los repositorios</strong>, se muestran
  datos agregados de todos los repositorios.
</p>
<p>
  Cambiar cualquier filtro actualiza inmediatamente todas las tarjetas KPI, gr\u00E1ficos
  y tablas de la p\u00E1gina.
</p>`
      },
      {
        id: 'stats-kpi',
        title: 'Tarjetas KPI y gr\u00E1fico de tasa de \u00E9xito',
        content: `
<p>
  Las tarjetas KPI de Estad\u00EDsticas proporcionan una vista m\u00E1s profunda
  que el Panel de control:
</p>
<ul>
  <li><strong>Ejecuciones totales</strong> &mdash; N\u00FAmero de ejecuciones completadas en el per\u00EDodo seleccionado.</li>
  <li><strong>Tasa de \u00E9xito</strong> &mdash; Porcentaje de ejecuciones completamente aprobadas.</li>
  <li><strong>Duraci\u00F3n media</strong> &mdash; Tiempo medio de ejecuci\u00F3n.</li>
  <li><strong>Pruebas inestables</strong> &mdash; Recuento de pruebas que alternan entre aprobado y fallido.</li>
</ul>
<h4>Tasa de \u00E9xito a lo largo del tiempo</h4>
<p>
  Un gr\u00E1fico de barras muestra la tasa de \u00E9xito diaria para el per\u00EDodo
  seleccionado. El eje X representa las fechas y el eje Y muestra el porcentaje
  (0&ndash;100%); pase el cursor sobre cualquier barra para ver el valor exacto y
  el n\u00FAmero de ejecuciones. El eje es una l\u00EDnea temporal continua: cada d\u00EDa
  calendario del rango recibe el mismo ancho de espacio, y los d\u00EDas
  <strong>sin ejecuciones</strong> se muestran como un hueco vac\u00EDo (una l\u00EDnea
  base tenue, sin barra) en lugar de colapsarse &mdash; de modo que el espaciado
  entre barras refleja el tiempo real transcurrido y facilita detectar
  regresiones o mejoras.
</p>`,
        tip: 'Una tendencia decreciente en la tasa de \u00E9xito a menudo indica que nuevos cambios de c\u00F3digo est\u00E1n introduciendo fallos. Investigue las fechas espec\u00EDficas de las ca\u00EDdas.'
      },
      {
        id: 'pass-fail-trend',
        title: 'Tendencia de aprobados/fallidos',
        content: `
<p>
  Un <strong>gr\u00E1fico de barras apiladas</strong> visualiza el n\u00FAmero de
  casos de prueba aprobados frente a fallidos por d\u00EDa (o por semana para
  rangos de tiempo m\u00E1s largos). Esto complementa el gr\u00E1fico de tasa de
  \u00E9xito al mostrar vol\u00FAmenes absolutos:
</p>
<ul>
  <li><strong>Barras verdes</strong> representan casos de prueba aprobados.</li>
  <li><strong>Barras rojas</strong> representan casos de prueba fallidos.</li>
</ul>
<p>
  Altos vol\u00FAmenes de verde con picos rojos ocasionales indican una suite de
  pruebas generalmente saludable con problemas peri\u00F3dicos. Barras rojas
  consistentes sugieren problemas sist\u00E9micos que necesitan atenci\u00F3n.
</p>`
      },
      {
        id: 'flaky-detection',
        title: 'Detecci\u00F3n de pruebas inestables',
        content: `
<p>
  Una <strong>prueba inestable</strong> (flaky test) es aquella que alterna entre
  aprobado y fallido sin ning\u00FAn cambio en el c\u00F3digo. RoboScope detecta
  pruebas inestables analizando el historial de aprobados/fallidos de casos de
  prueba individuales durante el per\u00EDodo de tiempo seleccionado.
</p>
<p>
  La tabla de pruebas inestables muestra:
</p>
<table>
  <thead>
    <tr><th>Columna</th><th>Descripci\u00F3n</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>Nombre de la prueba</strong></td><td>Nombre completamente cualificado del caso de prueba inestable.</td></tr>
    <tr><td><strong>Recuento de cambios</strong></td><td>N\u00FAmero de veces que el resultado cambi\u00F3 (aprobado&rarr;fallido o fallido&rarr;aprobado).</td></tr>
    <tr><td><strong>Tasa de aprobaci\u00F3n</strong></td><td>Porcentaje de ejecuciones en las que la prueba fue aprobada.</td></tr>
    <tr><td><strong>\u00DAltimo resultado</strong></td><td>Resultado m\u00E1s reciente (insignia de aprobado o fallido).</td></tr>
  </tbody>
</table>
<p>
  Las pruebas se clasifican por recuento de cambios en orden descendente. Los
  recuentos altos de cambios indican pruebas poco fiables que deben investigarse
  por problemas de temporizaci\u00F3n, dependencias de entorno o comportamiento
  no determinista.
</p>`,
        tip: 'Las pruebas inestables erosionan la confianza en su suite de pruebas. Priorice la correcci\u00F3n de las pruebas con el mayor recuento de cambios.'
      },
      {
        id: 'stats-refresh',
        title: 'Actualizar y frescura de datos',
        content: `
<p>
  Los datos de estad\u00EDsticas pueden quedar obsoletos a medida que se completan
  nuevas ejecuciones de pruebas. Un banner de obsolescencia aparece en la parte
  superior de la p\u00E1gina de Estad\u00EDsticas cuando los datos no se han
  actualizado recientemente.
</p>
<h4>Actualizaci\u00F3n manual</h4>
<p>
  Haga clic en el bot\u00F3n <strong>Actualizar</strong> para recargar todas las
  tarjetas KPI, gr\u00E1ficos y tablas con los datos m\u00E1s recientes. Esto vuelve
  a agregar las estad\u00EDsticas de la base de datos para los filtros seleccionados
  actualmente.
</p>
<h4>Pesta\u00F1as de visi\u00F3n general y an\u00E1lisis profundo</h4>
<p>
  La p\u00E1gina de Estad\u00EDsticas se divide en dos pesta\u00F1as:
</p>
<ul>
  <li><strong>Visi\u00F3n general</strong> &mdash; Tarjetas KPI, gr\u00E1fico de tasa de \u00E9xito, tendencia de aprobados/fallidos y detecci\u00F3n de pruebas inestables.</li>
  <li><strong>An\u00E1lisis profundo</strong> &mdash; An\u00E1lisis bajo demanda de anal\u00EDticas de keywords, m\u00E9tricas de calidad de pruebas, indicadores de mantenimiento y an\u00E1lisis de c\u00F3digo fuente. Seleccione KPIs espec\u00EDficos e inicie un an\u00E1lisis para explorar informaci\u00F3n m\u00E1s detallada.</li>
</ul>
<h4>An\u00E1lisis de c\u00F3digo fuente (Nuevo)</h4>
<p>
  Cuando se selecciona un proyecto, dos KPIs adicionales est\u00E1n disponibles en la categor\u00EDa <em>An\u00E1lisis de c\u00F3digo fuente</em>:
</p>
<ul>
  <li><strong>An\u00E1lisis de pruebas del c\u00F3digo fuente</strong> &mdash; Analiza sus archivos fuente <code>.robot</code> directamente: recuento de casos de prueba por archivo, l\u00EDneas promedio y pasos de keywords por prueba, keywords m\u00E1s utilizados y desglose por archivo.</li>
  <li><strong>Importaciones de bibliotecas del c\u00F3digo fuente</strong> &mdash; Muestra qu\u00E9 bibliotecas de Robot Framework se importan en sus archivos <code>.robot</code> y <code>.resource</code>, cu\u00E1ntos archivos usan cada biblioteca y su distribuci\u00F3n relativa.</li>
</ul>
<p>
  Estos KPIs funcionan independientemente de los informes de ejecuci\u00F3n &mdash; analizan los archivos fuente en disco, por lo que obtiene informaci\u00F3n incluso antes de ejecutar cualquier prueba.
</p>
<h4>Correcci\u00F3n de distribuci\u00F3n de bibliotecas</h4>
<p>
  El KPI <em>Distribuci\u00F3n de bibliotecas</em> (en la categor\u00EDa de Anal\u00EDticas de keywords) ahora resuelve correctamente los nombres de bibliotecas para keywords bien conocidos de Robot Framework. Anteriormente, muchos keywords se mostraban como &ldquo;Unknown&rdquo; porque el <code>output.xml</code> no siempre inclu\u00EDa el atributo de biblioteca. El sistema ahora utiliza un mapeo integrado de m\u00E1s de 500 keywords a sus bibliotecas (BuiltIn, Collections, SeleniumLibrary, Browser, RequestsLibrary, etc.).
</p>`,
        tip: 'Use la pesta\u00F1a de An\u00E1lisis profundo para investigar duraciones de keywords, densidad de aserciones y patrones de error en sus suites de pruebas. Seleccione un proyecto para habilitar los KPIs de An\u00E1lisis de c\u00F3digo fuente.'
      }
    ]
  },

  // ─── 8. Entornos ──────────────────────────────────────────────────
  // ─── 7.5 Auto-sanación y resiliencia ────────────────────────────
  {
    id: 'self-healing',
    title: 'Auto-sanación y resiliencia',
    icon: '🩹',
    subsections: [
      {
        id: 'self-healing-overview',
        title: 'Cómo funciona la auto-sanación',
        content: `
<p>
  Los tests derivan. Un dev renombra <code>id=submit</code> a <code>id=submit-btn</code>,
  o envuelve un botón en un nuevo <code>&lt;form&gt;</code>, y cada test que referenciaba
  el locator antiguo se rompe. La librería de auto-sanación de RoboScope reintenta
  los selectores fallidos en tiempo de ejecución contra el DOM vivo &mdash; el test
  pasa mientras RoboScope registra el cambio para revisión.
</p>
<h4>Opt-in por keyword</h4>
<p>
  La auto-sanación no es automática. Importas la librería y usas la variante sanada
  en lugar del keyword Browser simple:
</p>
<pre><code>*** Settings ***
Library    Browser
Library    RoboScopeHeal

*** Test Cases ***
Login Works
    New Browser    chromium
    New Page       https://app.example.com/login
    Heal Fill Text    id=user      alice
    Heal Fill Text    id=password  secret
    Heal Click        id=submit
    Get Text          .welcome-banner
</code></pre>
<h4>Tres niveles de fallback, en orden</h4>
<ol>
  <li><strong>Búsqueda en el sidecar</strong> &mdash; si el fichero <code>.robot</code> tiene
  un hermano <code>&lt;name&gt;.rbs.json</code> del Recorder v2, RoboScope consulta la
  lista de candidatos clasificados capturada en la grabación.</li>
  <li><strong>Transposición de estrategia</strong> &mdash; <code>id=submit</code> prueba
  <code>[data-testid=submit]</code>, <code>text=submit</code>, <code>css=input#submit</code>,
  <code>role=button[name="submit"]</code>. Cada candidato se verifica contra el DOM
  vivo via <code>Get Element Count</code> antes de probarlo &mdash; los no únicos / cero
  coincidencias se descartan.</li>
  <li><strong>Recorrido DOM por huella</strong> &mdash; último recurso. Si la grabación
  guardó una huella (tag + id + testid + clases + rol + texto + cadena de ancestros),
  RoboScope escanea los elementos interactivos y selecciona la mejor coincidencia
  multi-señal por encima de un umbral.</li>
</ol>`,
        tip: 'La auto-sanación solo se dispara en errores de selector. Los fallos de aserción se propagan intactos — RoboScope se niega a tapar una regresión real con una sustitución silenciosa.'
      },
      {
        id: 'self-healing-safety',
        title: 'Sobre de seguridad',
        content: `
<p>
  Hacer clic en el elemento equivocado en tiempo de ejecución es peor que fallar.
  Cada operación pasa por cuatro barreras:
</p>
<ul>
  <li><strong>Presupuesto por test</strong> &mdash; máximo tres sanaciones por defecto.</li>
  <li><strong>Umbral de confianza</strong> &mdash; mutadores 0.7+; solo lectura 0.5+.</li>
  <li><strong>Presupuesto de reintento por llamada</strong> &mdash; una alternativa.</li>
  <li><strong>Clasificación de sospechosos</strong> &mdash; tras el run, las sanaciones se
  cruzan con el resultado de cada test. Pasó → <em>confirmado</em>;
  falló → <em>sospechoso</em>. Solo las confirmadas ofrecen botón Aplicar parche.</li>
</ul>
<h4>Válvula de escape: la etiqueta <code>no-heal</code></h4>
<p>
  Runs CI estrictos pueden desactivar la sanación por test añadiendo la etiqueta
  <code>no-heal</code>. Los keywords <code>Heal *</code> delegan entonces directamente.
</p>`,
        tip: 'Umbrales, presupuestos y ruta del sidecar son todos configurables como argumentos de Library-import.'
      },
      {
        id: 'self-healing-report',
        title: 'Informe de sanaciones en el detalle del run',
        content: `
<p>
  Cada sanación exitosa se añade a <code>&lt;output_dir&gt;/heal_audit.jsonl</code>.
  El panel de detalle del run parsea este fichero y renderiza una tarjeta compacta
  <strong>Selectores autoreparados</strong>.
</p>
<ul>
  <li><strong>🩹 Confirmado</strong> &mdash; el test pasó. Ofrece <em>Copiar parche</em>
  y <em>Aplicar parche</em> (solo Editor+).</li>
  <li><strong>⚠️ Sospechoso</strong> &mdash; el test falló. <em>No</em> se ofrece botón
  de parche.</li>
</ul>
<h4>Seguridad del Aplicar parche</h4>
<p>
  El endpoint escribe atómicamente (temp + rename), rechaza sospechosos / fuera de
  rango / viewer, se niega si la línea del selector falta o es ambigua, y es
  idempotente.
</p>`,
      },
      {
        id: 'self-healing-diagnosis',
        title: 'Diagnóstico de selectores en runs fallidos',
        content: `
<p>
  Para runs fallidos sin sanación, RoboScope sigue ayudando: escanea la salida buscando
  firmas comunes de fallo de locator y busca cada una en el sidecar. Una tarjeta
  <strong>Diagnóstico de selectores</strong> muestra el selector fallido y alternativas
  clasificadas — un clic para copiar.
</p>`,
      },
      {
        id: 'self-healing-rate-kpi',
        title: 'KPI de tasa de sanación',
        content: `
<p>
  La sanación es un indicador adelantado. Una tasa creciente significa que la suite
  está derivando. La vista general de Estadísticas expone esta señal vía la tarjeta
  <strong>🩹 Selectores autoreparados</strong>: número grande, sub-línea con proporción
  de runs, insignias confirmado/sospechoso, sparkline.
</p>`,
        tip: 'Vigila la columna Sospechosos. Un flujo constante significa que las heurísticas son incorrectas para tu base de código — abre una issue.'
      },
      {
        id: 'flaky-quarantine',
        title: 'Cuarentena de tests inestables',
        content: `
<p>
  RoboScope detecta automáticamente los tests inestables en la tabla <strong>Tests
  inestables</strong> de Estadísticas. La <strong>cuarentena</strong> permite marcarlos
  para que se salten en ejecución.
</p>
<h4>Marcar un test en cuarentena</h4>
<ul>
  <li>Abre <strong>Estadísticas</strong>, localiza la tabla.</li>
  <li>Editor+ ven un botón <strong>Silenciar</strong>. Clic → test registrado.</li>
  <li>La fila recibe una insignia <strong>🔕 En cuarentena</strong>.</li>
</ul>
<h4>Efecto en tiempo de ejecución</h4>
<p>
  RoboScope registra un listener de Robot Framework que llama a
  <code>BuiltIn().skip()</code> en tests coincidentes. Aparecen como <code>SKIP</code>
  en <code>output.xml</code> — no como <code>FAIL</code>.
</p>`,
        tip: 'La cuarentena está siempre activa. Quitar vía el mismo botón.'
      },
      {
        id: 'self-healing-ai-patches',
        title: 'Parches sugeridos por IA',
        content: `
<p>
  Al ejecutar <strong>Analizar fallos</strong>, el LLM emite parches unified-diff junto
  al análisis en prosa cuando el arreglo es concreto. Una sección <strong>Parches
  sugeridos</strong> aparece con vista previa del diff por fichero y botón
  <em>Copiar parche</em>.
</p>
<p>
  Estos parches son <em>sugerencias</em> — nunca se aplican automáticamente. RoboScope
  no modificará tu repositorio sin acción explícita.
</p>`,
        tip: 'Los fallos ambiguos nunca producen un bloque de parche.'
      },
    ],
  },
  {
    id: 'environments',
    title: 'Entornos',
    icon: '\u2699\uFE0F',
    subsections: [
      {
        id: 'env-overview',
        title: 'Gesti\u00F3n de entornos',
        content: `
<p>
  La p\u00E1gina de <strong>Entornos</strong> le permite crear y gestionar entornos
  virtuales Python aislados para la ejecuci\u00F3n de pruebas. Cada entorno puede
  tener su propio conjunto de paquetes instalados y variables de entorno, permiti\u00E9ndole
  ejecutar pruebas contra diferentes configuraciones sin conflictos.
</p>
<p>
  Los entornos se almacenan en el directorio <code>VENVS_DIR</code>
  (por defecto: <code>~/.roboscope/venvs</code>). La gesti\u00F3n de entornos
  requiere el rol <strong>Editor</strong> o superior.
</p>`
      },
      {
        id: 'create-venv',
        title: 'Crear un entorno virtual',
        content: `
<p>
  Para crear un nuevo entorno virtual Python:
</p>
<ol>
  <li>Haga clic en <strong>Nuevo entorno</strong> en la p\u00E1gina de Entornos.</li>
  <li>Introduzca un <strong>Nombre</strong> para el entorno (por ejemplo, <code>rf7-selenium</code>).</li>
  <li>Opcionalmente proporcione una <strong>Descripci\u00F3n</strong> de para qu\u00E9 es este entorno.</li>
  <li>Haga clic en <strong>Crear</strong>.</li>
</ol>
<p>
  RoboScope crea un <code>venv</code> de Python en segundo plano usando el Python
  del sistema. El proceso de creaci\u00F3n normalmente tarda unos segundos. Una vez
  listo, el estado del entorno cambia de <code>creating</code> a <code>ready</code>.
</p>
<p>
  Cada entorno incluye autom\u00E1ticamente <code>pip</code> y <code>setuptools</code>.
  Luego necesitar\u00E1 instalar Robot Framework y cualquier biblioteca requerida.
</p>`,
        tip: 'Nombre los entornos de forma descriptiva, por ejemplo, "rf7-browser" o "rf6-selenium", para que los miembros del equipo sepan qu\u00E9 bibliotecas est\u00E1n incluidas.'
      },
      {
        id: 'install-packages',
        title: 'Instalar paquetes',
        content: `
<p>
  Despu\u00E9s de crear un entorno, puede instalar paquetes Python de dos maneras:
</p>
<h4>Bibliotecas populares de Robot Framework</h4>
<p>
  Una lista curada de paquetes com\u00FAnmente utilizados est\u00E1 disponible para
  instalaci\u00F3n con un clic:
</p>
<ul>
  <li><code>robotframework</code> &mdash; El framework central de Robot Framework.</li>
  <li><code>robotframework-seleniumlibrary</code> &mdash; Pruebas de navegador basadas en Selenium.</li>
  <li><code>robotframework-browser</code> &mdash; Pruebas de navegador Playwright (requiere Node.js + <code>rfbrowser init</code>).</li>
  <li><code>robotframework-browser-batteries</code> &mdash; Pruebas de navegador Playwright, aut\u00F3nomo (sin Node.js, recomendado).</li>
  <li><code>robotframework-requests</code> &mdash; Pruebas de API HTTP.</li>
  <li><code>robotframework-databaselibrary</code> &mdash; Pruebas de base de datos.</li>
  <li><code>robotframework-sshlibrary</code> &mdash; Conexiones SSH.</li>
  <li><code>robotframework-excellibrary</code> &mdash; Manejo de archivos Excel.</li>
</ul>
<h4>B\u00FAsqueda en PyPI</h4>
<p>
  Para cualquier otro paquete, use el <strong>campo de b\u00FAsqueda</strong> para
  encontrar paquetes en PyPI. Introduzca un nombre de paquete, seleccione la versi\u00F3n
  deseada y haga clic en <strong>Instalar</strong>. La instalaci\u00F3n se ejecuta como
  tarea en segundo plano y la lista de paquetes se actualiza cuando se completa.
</p>
<p>
  Los paquetes instalados se muestran en una tabla con su nombre, versi\u00F3n y
  un bot\u00F3n de <strong>Desinstalar</strong>.
</p>`,
        tip: 'Siempre instale robotframework primero antes de a\u00F1adir paquetes de bibliotecas para evitar problemas de dependencias.'
      },
      {
        id: 'env-variables',
        title: 'Variables de entorno',
        content: `
<p>
  Cada entorno puede definir <strong>variables de entorno</strong> que se inyectan
  en el proceso cuando se ejecutan las pruebas. Esto es \u00FAtil para:
</p>
<ul>
  <li>Establecer <code>BROWSER</code> para controlar qu\u00E9 navegador usa Selenium.</li>
  <li>Proporcionar <code>BASE_URL</code> para la configuraci\u00F3n de la aplicaci\u00F3n bajo prueba.</li>
  <li>Almacenar <code>API_KEY</code> u otras credenciales sin codificarlas en los archivos de prueba.</li>
</ul>
<p>
  Para gestionar variables, navegue a la p\u00E1gina de detalle de un entorno y use
  la pesta\u00F1a <strong>Variables</strong>. Cada variable tiene una <strong>Clave</strong>
  y un <strong>Valor</strong>. Haga clic en <strong>A\u00F1adir variable</strong> para
  crear una nueva entrada, o use los iconos de editar/eliminar para modificar las
  existentes.
</p>`,
        tip: 'Evite almacenar credenciales altamente sensibles como variables de entorno. Considere usar un gestor de secretos para despliegues en producci\u00F3n.'
      },
      {
        id: 'docker-build',
        title: 'Build Docker y obsolescencia de imagen',
        content: `
<h4>Terminal de build Docker</h4>
<p>
  Al construir una imagen Docker para un entorno, RoboScope transmite la salida del
  build en vivo a un <strong>componente de terminal</strong> en la interfaz. El terminal
  muestra un punto pulsante durante builds activos, auto-scroll para seguir la salida
  y un bot\u00F3n mostrar/ocultar para minimizarlo.
</p>
<h4>Detecci\u00F3n de obsolescencia de imagen</h4>
<p>
  Despu\u00E9s de instalar o eliminar paquetes, la imagen Docker puede quedar desactualizada.
  RoboScope rastrea cu\u00E1ndo se cambiaron los paquetes (<code>packages_changed_at</code>)
  y cu\u00E1ndo se construy\u00F3 la imagen (<code>docker_image_built_at</code>). Si los paquetes
  han cambiado desde el \u00FAltimo build, aparece un <strong>banner de advertencia \u00E1mbar</strong>
  en las vistas de Ejecuci\u00F3n y Explorador.
</p>
<p>
  Haga clic en <strong>Reconstruir</strong> para iniciar un nuevo build Docker.
</p>
<h4>Inicializaci\u00F3n de la biblioteca Browser</h4>
<p>
  Al usar <code>robotframework-browser</code>, RoboScope verifica autom\u00E1ticamente si los
  <code>node_modules</code> de la biblioteca Browser est\u00E1n correctamente inicializados
  despu\u00E9s de la instalaci\u00F3n. Si se necesita inicializaci\u00F3n, aparece un indicador
  <strong>inicializando</strong> en la interfaz, y una verificaci\u00F3n previa asegura que
  la biblioteca est\u00E9 lista antes de la ejecuci\u00F3n.
</p>`
      },
      {
        id: 'clone-delete-env',
        title: 'Clonar y eliminar entornos',
        content: `
<p>
  Para ahorrar tiempo al configurar entornos similares:
</p>
<h4>Clonar</h4>
<p>
  Haga clic en el bot\u00F3n <strong>Clonar</strong> en un entorno existente. Esto
  crea un nuevo entorno con los mismos paquetes instalados y variables de entorno.
  Se le pedir\u00E1 que proporcione un nuevo nombre. La clonaci\u00F3n es \u00FAtil
  cuando necesita una ligera variaci\u00F3n de una configuraci\u00F3n existente (por
  ejemplo, probar con una versi\u00F3n diferente de Robot Framework).
</p>
<h4>Eliminar</h4>
<p>
  Haga clic en el bot\u00F3n <strong>Eliminar</strong> y confirme el di\u00E1logo
  para eliminar permanentemente un entorno. Esto elimina el directorio del entorno
  virtual y toda la configuraci\u00F3n asociada. Las ejecuciones que estaban configuradas
  para usar un entorno eliminado necesitar\u00E1n actualizarse para usar uno diferente.
</p>`
      }
    ]
  },

  // ─── 9. Ajustes ───────────────────────────────────────────────────
  {
    id: 'settings',
    title: 'Ajustes',
    icon: '\u{1F527}',
    subsections: [
      {
        id: 'settings-overview',
        title: 'Visi\u00F3n general de ajustes',
        content: `
<p>
  La p\u00E1gina de <strong>Ajustes</strong> es accesible solo para usuarios con
  el rol <strong>Admin</strong>. Proporciona capacidades de gesti\u00F3n de usuarios
  y opciones de configuraci\u00F3n a nivel de toda la aplicaci\u00F3n.
</p>
<p>
  Los usuarios sin rol de administrador no ver\u00E1n la entrada de Ajustes en la
  navegaci\u00F3n de la barra lateral. Intentar acceder a la URL de ajustes directamente
  con permisos insuficientes resulta en una redirecci\u00F3n al Panel de control.
</p>`
      },
      {
        id: 'user-management',
        title: 'Gesti\u00F3n de usuarios',
        content: `
<p>
  La secci\u00F3n de gesti\u00F3n de usuarios muestra una tabla de todos los
  usuarios registrados con las siguientes columnas:
</p>
<ul>
  <li><strong>Correo electr\u00F3nico</strong> &mdash; La direcci\u00F3n de correo de inicio de sesi\u00F3n del usuario.</li>
  <li><strong>Nombre</strong> &mdash; Nombre para mostrar en el encabezado y el historial de ejecuciones.</li>
  <li><strong>Rol</strong> &mdash; Asignaci\u00F3n de rol actual (Viewer, Runner, Editor, Admin).</li>
  <li><strong>Estado</strong> &mdash; Insignia de activo o inactivo.</li>
  <li><strong>Creado</strong> &mdash; Fecha de creaci\u00F3n de la cuenta.</li>
  <li><strong>Acciones</strong> &mdash; Botones de editar y eliminar.</li>
</ul>
<h4>Crear un usuario</h4>
<p>
  Haga clic en <strong>A\u00F1adir usuario</strong> y complete el formulario:
</p>
<ol>
  <li>Introduzca el <strong>Correo electr\u00F3nico</strong> (debe ser \u00FAnico).</li>
  <li>Introduzca un <strong>Nombre para mostrar</strong>.</li>
  <li>Establezca la <strong>Contrase\u00F1a</strong> inicial (m\u00EDnimo 6 caracteres).</li>
  <li>Asigne un <strong>Rol</strong>.</li>
  <li>Haga clic en <strong>Crear</strong>.</li>
</ol>
<p>
  El nuevo usuario puede iniciar sesi\u00F3n inmediatamente con las credenciales proporcionadas.
</p>`
      },
      {
        id: 'role-assignment',
        title: 'Asignaci\u00F3n de roles',
        content: `
<p>
  Para cambiar el rol de un usuario, haga clic en el bot\u00F3n <strong>Editar</strong>
  en su fila. En el di\u00E1logo de edici\u00F3n, seleccione el nuevo rol del men\u00FA
  desplegable y guarde.
</p>
<p>
  Los cambios de rol surten efecto en la siguiente solicitud API del usuario.
  Si el usuario est\u00E1 actualmente conectado, su token JWT a\u00FAn contiene el
  rol anterior hasta que se actualice. Para un efecto inmediato, el usuario debe
  cerrar sesi\u00F3n e iniciar sesi\u00F3n de nuevo.
</p>
<h4>Gu\u00EDa de asignaci\u00F3n de roles</h4>
<table>
  <thead>
    <tr><th>Rol</th><th>Mejor para</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>Viewer</strong></td><td>Partes interesadas, gerentes y miembros del equipo que solo necesitan revisar resultados.</td></tr>
    <tr><td><strong>Runner</strong></td><td>Ingenieros QA que necesitan lanzar ejecuciones de pruebas pero no modificar el c\u00F3digo de prueba.</td></tr>
    <tr><td><strong>Editor</strong></td><td>Desarrolladores de pruebas que escriben y mantienen pruebas de Robot Framework.</td></tr>
    <tr><td><strong>Admin</strong></td><td>Administradores de sistemas responsables de la gesti\u00F3n de usuarios y configuraci\u00F3n.</td></tr>
  </tbody>
</table>`,
        tip: 'Siga el principio de m\u00EDnimo privilegio: asigne el rol m\u00EDnimo necesario para las responsabilidades de cada usuario.'
      },
      {
        id: 'activate-deactivate',
        title: 'Activar y desactivar usuarios',
        content: `
<p>
  En lugar de eliminar un usuario, puede <strong>desactivar</strong> su cuenta:
</p>
<ul>
  <li>Haga clic en el bot\u00F3n <strong>Editar</strong> en la fila del usuario.</li>
  <li>Cambie el interruptor <strong>Activo</strong> a desactivado.</li>
  <li>Guarde los cambios.</li>
</ul>
<p>
  Los usuarios desactivados no pueden iniciar sesi\u00F3n y sus tokens JWT existentes
  son rechazados. Sin embargo, su historial de ejecuciones y datos asociados se
  conservan. Para restaurar el acceso, simplemente cambie el interruptor Activo de
  nuevo a activado.
</p>
<p>
  <strong>Eliminar</strong> un usuario elimina permanentemente su cuenta. Use el
  bot\u00F3n <strong>Eliminar</strong> y confirme el di\u00E1logo. Esta acci\u00F3n
  no se puede deshacer.
</p>`,
        tip: 'Prefiera la desactivaci\u00F3n sobre la eliminaci\u00F3n para usuarios que puedan regresar. Esto preserva sus datos de actividad hist\u00F3rica.'
      },
      {
        id: 'password-reset',
        title: 'Restablecimiento de contrase\u00F1a',
        content: `
<p>
  Los administradores pueden restablecer la contrase\u00F1a de cualquier usuario
  directamente desde la pesta\u00F1a de Usuarios:
</p>
<ol>
  <li>Navegue a <strong>Ajustes &gt; Usuarios</strong>.</li>
  <li>Haga clic en el bot\u00F3n <strong>Restablecer contrase\u00F1a</strong> en la fila del usuario.</li>
  <li>Introduzca la nueva contrase\u00F1a (m\u00EDnimo 6 caracteres) en el di\u00E1logo.</li>
  <li>Haga clic en <strong>Establecer contrase\u00F1a</strong>.</li>
</ol>
<p>
  El cambio de contrase\u00F1a surte efecto inmediatamente. Las sesiones existentes
  del usuario permanecen v\u00E1lidas, pero necesitar\u00E1n la nueva contrase\u00F1a
  para su pr\u00F3ximo inicio de sesi\u00F3n.
</p>`,
        tip: 'Comunique la nueva contrase\u00F1a al usuario a trav\u00E9s de un canal seguro. Considere pedirle que la cambie de nuevo en el primer inicio de sesi\u00F3n.'
      },
      {
        id: 'api-tokens',
        title: 'Tokens API',
        content: `
<p>
  La pesta\u00F1a <strong>Tokens API</strong> en Ajustes permite a los administradores crear tokens
  para pipelines CI/CD y cuentas de servicio. Los tokens proporcionan acceso program\u00E1tico a
  la API de RoboScope sin necesidad de inicio de sesi\u00F3n interactivo.
</p>
<h4>Crear un token</h4>
<ol>
  <li>Navegue a <strong>Ajustes &gt; Tokens API</strong>.</li>
  <li>Haga clic en <strong>Crear token</strong>.</li>
  <li>Introduzca un <strong>nombre</strong> (por ej. \u00ABPipeline Jenkins\u00BB).</li>
  <li>Seleccione un <strong>rol</strong> &mdash; ya sea <em>Runner</em> (puede iniciar ejecuciones) o <em>Editor</em> (puede adem\u00E1s modificar archivos y ajustes).</li>
  <li>Opcionalmente, establezca una <strong>fecha de expiraci\u00F3n</strong>. Los tokens sin expiraci\u00F3n permanecen v\u00E1lidos hasta ser revocados.</li>
  <li>Haga clic en <strong>Crear</strong>. El token se muestra una sola vez &mdash; c\u00F3pielo inmediatamente.</li>
</ol>
<h4>Usar un token</h4>
<p>
  Incluya el token en la cabecera <code>Authorization</code> de sus solicitudes HTTP:
</p>
<p><code>Authorization: Bearer rbs_...</code></p>
<p>
  Todos los tokens usan el prefijo <code>rbs_</code> para f\u00E1cil identificaci\u00F3n. El valor del
  token se almacena como un hash SHA-256 en la base de datos &mdash; no se puede recuperar
  despu\u00E9s de la creaci\u00F3n.
</p>
<h4>Revocar un token</h4>
<p>
  Haga clic en el bot\u00F3n <strong>Revocar</strong> junto a cualquier token para invalidarlo
  inmediatamente. Los tokens revocados no se pueden restaurar.
</p>`,
        tip: 'Use tokens de corta duraci\u00F3n con fechas de expiraci\u00F3n para pipelines CI/CD para reducir el riesgo de seguridad. Cree tokens separados para cada pipeline o servicio.'
      },
      {
        id: 'outbound-webhooks',
        title: 'Webhooks salientes',
        content: `
<p>
  La pesta\u00F1a <strong>Webhooks</strong> en Ajustes permite configurar notificaciones HTTP
  salientes que se env\u00EDan cuando ocurren eventos de ejecuci\u00F3n de pruebas. Esto es \u00FAtil para
  integrar RoboScope con herramientas de chat (Slack, Teams), sistemas de monitorizaci\u00F3n o
  paneles personalizados.
</p>
<h4>Crear un webhook</h4>
<ol>
  <li>Navegue a <strong>Ajustes &gt; Webhooks</strong>.</li>
  <li>Haga clic en <strong>A\u00F1adir webhook</strong>.</li>
  <li>Introduzca la <strong>URL de destino</strong> (se recomienda HTTPS para producci\u00F3n).</li>
  <li>Introduzca un <strong>secreto</strong> opcional para la firma HMAC-SHA256 de las cargas \u00FAtiles.</li>
  <li>Seleccione los <strong>eventos</strong> a los que desea suscribirse:
    <code>run.started</code>, <code>run.passed</code>, <code>run.failed</code>,
    <code>run.error</code>, <code>run.cancelled</code>, <code>run.timeout</code>.
  </li>
  <li>Haga clic en <strong>Guardar</strong>.</li>
</ol>
<h4>Firmas de carga \u00FAtil</h4>
<p>
  Si se configura un secreto, cada entrega incluye una cabecera
  <code>X-RoboScope-Signature</code> con una firma HMAC-SHA256 del cuerpo de la solicitud.
  Verifique esta firma en el extremo receptor para asegurar que la carga \u00FAtil fue enviada
  por RoboScope y no ha sido manipulada.
</p>
<h4>Registro de entregas &amp; reintentos</h4>
<p>
  RoboScope mantiene un registro de entregas para cada webhook mostrando c\u00F3digos de estado,
  marcas de tiempo y cuerpos de respuesta. Las entregas fallidas se reintentan hasta 3 veces
  con retroceso exponencial. Use el bot\u00F3n <strong>Ping de prueba</strong> para verificar la
  conectividad antes de depender del webhook.
</p>`,
        tip: 'Use el bot\u00F3n Ping de prueba despu\u00E9s de crear un webhook para verificar que su punto final recibe las cargas \u00FAtiles correctamente.'
      },
      {
        id: 'git-webhook-trigger',
        title: 'Disparador de webhook Git',
        content: `
<p>
  RoboScope puede iniciar autom\u00E1ticamente ejecuciones de pruebas cuando se env\u00EDa c\u00F3digo
  a un repositorio Git. La pesta\u00F1a <strong>Webhooks</strong> en Ajustes muestra una
  <strong>URL de webhook entrante</strong> que puede configurar en los ajustes de su
  repositorio de GitHub o GitLab.
</p>
<h4>Configuraci\u00F3n</h4>
<ol>
  <li>Copie la URL del webhook entrante desde <strong>Ajustes &gt; Webhooks</strong>.</li>
  <li>En su plataforma de alojamiento Git (GitHub o GitLab), vaya a los ajustes de webhook de su repositorio.</li>
  <li>A\u00F1ada la URL de RoboScope como nuevo webhook.</li>
  <li>Seleccione <strong>Eventos Push</strong> como disparador.</li>
  <li>Guarde la configuraci\u00F3n del webhook.</li>
</ol>
<h4>C\u00F3mo funciona</h4>
<p>
  Cuando se recibe un evento push, RoboScope compara la <code>git_url</code> entrante
  con los proyectos configurados (con o sin sufijo <code>.git</code>). Extrae el nombre de
  la rama de la referencia <code>refs/heads/...</code> y crea autom\u00E1ticamente un
  <code>ExecutionRun</code> para el proyecto coincidente en la rama enviada.
</p>`,
        tip: 'Aseg\u00FArese de que su instancia de RoboScope sea accesible desde su plataforma de alojamiento Git. Para GitHub, la URL del webhook debe ser p\u00FAblicamente accesible.'
      },
      {
        id: 'audit-log',
        title: 'Registro de auditor\u00EDa',
        content: `
<p>
  La pesta\u00F1a <strong>Registro de auditor\u00EDa</strong> en Ajustes proporciona un registro
  completo de todas las operaciones de escritura (POST, PUT, PATCH, DELETE) realizadas en
  RoboScope. Esto es esencial para el cumplimiento normativo, la supervisi\u00F3n de seguridad
  y la depuraci\u00F3n.
</p>
<h4>Qu\u00E9 se registra</h4>
<p>
  Cada entrada del registro de auditor\u00EDa captura:
</p>
<ul>
  <li><strong>Marca de tiempo</strong> &mdash; Cu\u00E1ndo ocurri\u00F3 la acci\u00F3n.</li>
  <li><strong>Usuario</strong> &mdash; Qui\u00E9n realiz\u00F3 la acci\u00F3n (nombre de usuario).</li>
  <li><strong>Acci\u00F3n</strong> &mdash; El m\u00E9todo HTTP y el endpoint (por ej. POST /runs).</li>
  <li><strong>Recurso</strong> &mdash; El tipo e ID del recurso afectado.</li>
  <li><strong>Direcci\u00F3n IP</strong> &mdash; La direcci\u00F3n IP del cliente.</li>
  <li><strong>Detalles</strong> &mdash; Contexto adicional almacenado como JSON (por ej. campos modificados).</li>
</ul>
<h4>Filtrado &amp; exportaci\u00F3n</h4>
<p>
  Use los controles de filtro para acotar las entradas por tipo de acci\u00F3n, tipo de recurso
  o usuario. La tabla paginada permite navegar por grandes vol\u00FAmenes de registros.
  Haga clic en <strong>Exportar CSV</strong> para descargar las entradas filtradas para
  an\u00E1lisis externo o archivado.
</p>
<h4>Aplicaci\u00F3n de retenci\u00F3n</h4>
<p>
  Un programador en segundo plano se ejecuta cada 24 horas para aplicar las pol\u00EDticas de
  retenci\u00F3n. Los informes y ejecuciones m\u00E1s antiguos que el ajuste
  <code>report_retention_days</code> configurado se eliminan autom\u00E1ticamente. Los administradores
  tambi\u00E9n pueden activar manualmente la aplicaci\u00F3n de retenci\u00F3n mediante
  <strong>Ajustes &gt; Registro de auditor\u00EDa &gt; Ejecutar retenci\u00F3n</strong>.
</p>`,
        tip: 'Exporte los registros de auditor\u00EDa regularmente para fines de cumplimiento. La exportaci\u00F3n CSV incluye todos los campos y respeta los filtros activos.'
      },
      {
        id: 'secrets-encryption',
        title: 'Cifrado de secretos',
        content: `
<p>
  Las variables de entorno pueden marcarse como <strong>secretas</strong> para proteger valores
  sensibles como claves API, contrase\u00F1as y tokens. Las variables secretas se cifran en reposo
  usando cifrado sim\u00E9trico Fernet, derivado del <code>SECRET_KEY</code> de la aplicaci\u00F3n.
</p>
<h4>Marcar una variable como secreta</h4>
<ol>
  <li>Navegue a <strong>Entornos</strong> y seleccione un entorno.</li>
  <li>En la secci\u00F3n <strong>Variables</strong>, a\u00F1ada o edite una variable.</li>
  <li>Active el interruptor <strong>Secreto</strong> para habilitar el cifrado.</li>
  <li>Guarde la variable. El valor se cifra inmediatamente.</li>
</ol>
<h4>C\u00F3mo funciona</h4>
<ul>
  <li>Los valores secretos se almacenan como texto cifrado en la base de datos.</li>
  <li>La interfaz muestra los valores secretos como <code>********</code> &mdash; no se pueden volver a leer.</li>
  <li>Los valores solo se descifran en el momento de la ejecuci\u00F3n de pruebas, cuando se inyectan en el entorno del ejecutor de pruebas.</li>
  <li>Los secretos en texto plano existentes (creados antes de habilitar el cifrado) siguen funcionando mediante una compatibilidad regresiva elegante.</li>
</ul>`,
        tip: 'Use siempre un SECRET_KEY fuerte y \u00FAnico en producci\u00F3n. Si el SECRET_KEY cambia, los secretos cifrados anteriormente se volver\u00E1n ilegibles.'
      },
      {
        id: 'identity-providers',
        title: 'Proveedores de identidad (SSO)',
        content: `
<p>
  RoboScope admite <strong>inicio de sesión único (SSO)</strong> mediante OpenID Connect (OIDC).
  Una vez configurado y habilitado un proveedor de identidad, aparece un botón
  <strong>Iniciar sesión con &hellip;</strong> en la pantalla de inicio de sesión y sus
  usuarios ya no necesitan una contraseña separada de RoboScope.
</p>
<p>
  Tipos de proveedor admitidos:
</p>
<ul>
  <li><strong>Azure AD / Microsoft Entra ID</strong></li>
  <li><strong>Google Workspace</strong></li>
  <li><strong>GitHub</strong></li>
  <li><strong>OIDC genérico</strong> &mdash; cualquier emisor OIDC compatible con los estándares
      (Okta, Keycloak, Auth0, Authentik, &hellip;)</li>
</ul>

<h4>1. Preparar la aplicación en su IdP</h4>
<p>
  En la consola de administración de su IdP, registre una nueva aplicación web y
  anote el <strong>Client ID</strong> y el <strong>Client Secret</strong>. Configure
  la <strong>URI de redirección</strong> como:
</p>
<p><code>https://&lt;su-host-roboscope&gt;/auth/sso/callback</code></p>
<p>
  RoboScope muestra la URL exacta en el formulario de configuración (con un botón
  para copiar). La aplicación debe poder solicitar como mínimo los scopes
  <code>openid profile email</code>. Si desea asignación de equipos basada en
  grupos, habilite también un claim <strong>groups</strong>
  (Azure AD: <em>Configuración de tokens</em> &rarr; añadir el claim <em>groups</em>;
  Keycloak: añadir un mapeador de <em>group membership</em>).
</p>

<h4>2. Crear el proveedor en RoboScope</h4>
<ol>
  <li>Abra <strong>Admin &gt; Proveedores de identidad</strong> en la barra lateral.</li>
  <li>Haga clic en <strong>Añadir proveedor</strong>.</li>
  <li>Complete el formulario:
    <ul>
      <li><strong>Nombre</strong> &mdash; etiqueta mostrada en el botón de inicio de sesión (p.&nbsp;ej. «SSO de la empresa»).</li>
      <li><strong>Tipo de proveedor</strong> &mdash; uno de los cuatro tipos anteriores.</li>
      <li><strong>URL del emisor</strong> &mdash; la URL base del emisor / descubrimiento OIDC.
          Ejemplos:
        <ul>
          <li>Azure AD: <code>https://login.microsoftonline.com/&lt;tenant-id&gt;/v2.0</code></li>
          <li>Google: <code>https://accounts.google.com</code></li>
          <li>GitHub: <code>https://token.actions.githubusercontent.com</code> o su proxy OIDC</li>
          <li>Genérico: la URL donde se sirve <code>/.well-known/openid-configuration</code></li>
        </ul>
      </li>
      <li><strong>Client ID</strong> &mdash; de la aplicación IdP.</li>
      <li><strong>Client Secret</strong> &mdash; de la aplicación IdP. Almacenado cifrado en reposo (Fernet).</li>
      <li><strong>Scopes</strong> &mdash; por defecto <code>openid profile email</code>; añada otros (p.&nbsp;ej. <code>groups</code>, <code>offline_access</code>) como chips.</li>
      <li><strong>Nombre del claim de grupo</strong> &mdash; el claim JWT que contiene los grupos del usuario (por defecto <code>groups</code>).</li>
    </ul>
  </li>
</ol>

<h4>3. Ejecutar la sonda Dry-Run</h4>
<p>
  Antes de poder guardar el proveedor, haga clic en <strong>Ejecutar Dry-Run</strong>.
  La sonda obtiene el documento de descubrimiento OIDC, valida el endpoint JWKS,
  los scopes configurados y el nombre del claim de grupo. El resultado se muestra en línea:
</p>
<ul>
  <li><strong>Aprobado</strong> &mdash; el botón <strong>Guardar</strong> se desbloquea.</li>
  <li><strong>Fallido</strong> &mdash; expanda la fila para ver qué comprobación falló
      (causas más comunes: URL de emisor incorrecta, tráfico de red saliente bloqueado,
      scope no autorizado en el IdP).</li>
</ul>
<p>
  Editar cualquier campo después de un dry-run exitoso marca la sonda como
  <em>obsoleta</em> &mdash; debe volver a ejecutarla antes de guardar.
</p>

<h4>4. Documento de transferencia</h4>
<p>
  Después del primer guardado, puede descargar un documento de
  <strong>transferencia en PDF o Markdown</strong> desde la página de edición del proveedor.
  El artefacto enumera todo lo que el administrador del IdP necesita (URI de redirección,
  scopes requeridos, claim de grupo) y se genera en el mismo idioma que la interfaz
  &mdash; útil cuando RoboScope y el IdP son gestionados por equipos diferentes.
</p>

<h4>5. Primer inicio de sesión del usuario</h4>
<p>
  Una vez habilitado el proveedor, la página de inicio de sesión muestra un botón
  <strong>Iniciar sesión con <em>&lt;Nombre&gt;</em></strong>. En el primer inicio de sesión SSO,
  se crea automáticamente una cuenta de usuario de RoboScope y se vincula al sujeto IdP.
  Si ya existe una cuenta local con contraseña para el mismo correo electrónico,
  se solicita al usuario que confirme la vinculación (pantalla de consentimiento).
</p>

<h4>Asignación de grupos a equipos</h4>
<p>
  En <strong>Admin &gt; Equipos</strong>, puede asignar nombres de grupos del IdP a
  equipos de RoboScope. En cada inicio de sesión SSO, la pertenencia a equipos del
  usuario se resincroniza desde el claim de grupo configurado. Use
  <strong>Crear equipos en lote a partir de grupos del IdP</strong> en la página Equipos
  para iniciar las asignaciones a partir de los grupos ya observados en inicios de sesión recientes.
</p>

<h4>Caché de descubrimiento</h4>
<p>
  Los documentos de descubrimiento OIDC se almacenan en caché durante 24&nbsp;h para
  mantener los inicios de sesión rápidos y resilientes ante breves interrupciones del IdP.
  La lista de proveedores muestra una <strong>insignia de caché obsoleta</strong> cuando
  la caché tiene más de 24&nbsp;h. Active una actualización manual desde la página de
  la lista de proveedores.
</p>

<h4>Bypass de emergencia</h4>
<p>
  Si su IdP no es accesible, un administrador aún puede iniciar sesión con la cuenta
  local <code>admin@roboscope.local</code> (o cualquier otra cuenta local con
  contraseña) mediante el enlace <strong>Usar contraseña en su lugar</strong> en la
  página de inicio de sesión. Este enlace puede ocultarse en
  <strong>Ajustes &gt; Seguridad &gt; Ocultar formulario de contraseña</strong> una vez
  que el SSO esté completamente desplegado.
</p>`,
        tip: 'Ejecute siempre la sonda Dry-Run antes de guardar y antes de desplegar a los usuarios. Detecta el 90&nbsp;% de los errores de configuración (emisor incorrecto, scope faltante, JWKS inaccesible) sin afectar a los usuarios finales.'
      },
      {
        id: 'feature-governance',
        title: 'Gobernanza de funciones (bloqueo de la gestión de paquetes)',
        content: `
<p>En una instalación compartida o remota donde los entornos de Python se administran de forma centralizada, puede desactivar la <strong>gestión de paquetes</strong> para que los usuarios finales no puedan instalar, desinstalar ni actualizar paquetes, crear imágenes de Docker ni ejecutar <code>rfbrowser init</code> sobre el entorno gestionado.</p>
<h4>Cómo desactivarla</h4>
<ul>
  <li><strong>Desde la interfaz</strong> &mdash; en <strong>Ajustes &gt; General &gt; features</strong>, establezca <code>features.packageManagement</code> en <em>No</em>.</li>
  <li><strong>Desde el despliegue</strong> (bloqueo permanente) &mdash; establezca la variable de entorno <code>ROBOSCOPE_FEATURE_PACKAGE_MANAGEMENT=false</code> en el servidor. Esta tiene prioridad sobre el conmutador de la aplicación y la muestra como 🔒 bloqueada (no editable). Cambiar una variable de entorno surte efecto en el siguiente reinicio.</li>
</ul>
<p>El orden de prioridad de resolución es <strong>variable de entorno &rarr; ajuste de la base de datos &rarr; valor predeterminado (habilitado)</strong>.</p>
<h4>Qué cambia cuando está desactivada</h4>
<ul>
  <li>La página de Entornos oculta los controles de instalar / desinstalar / actualizar / crear y muestra un aviso de solo lectura; la lista de paquetes instalados permanece visible.</li>
  <li>Los endpoints de API correspondientes se rechazan en el servidor (HTTP 403) &mdash; el bloqueo no puede eludirse a través de la API, y el bloqueo queda registrado en el Registro de auditoría.</li>
</ul>
<h4>Rol mínimo</h4>
<p>Cuando la gestión de paquetes se deja <em>activada</em>, todavía puede elevar el rol mínimo requerido para cada operación en los ajustes <code>features.packageManagement.role.*</code> (valor predeterminado <strong>Editor</strong>).</p>`,
        tip: 'Use el bloqueo mediante variable de entorno (no solo el conmutador de la aplicación) en instalaciones donde los usuarios finales nunca deban tocar los entornos &mdash; no puede modificarse desde dentro de la aplicación.'
      }
    ]
  },

  // ─── 10. IA y Generaci\u00F3n ──────────────────────────────────────────
  {
    id: 'ai-generation',
    title: 'IA y Generaci\u00F3n',
    icon: '\u{1F916}',
    subsections: [
      {
        id: 'ai-overview',
        title: 'Descripci\u00F3n general',
        content: `
<p>
  RoboScope integra <strong>modelos de lenguaje (LLMs)</strong> para funciones
  impulsadas por IA en el desarrollo de tests Robot Framework:
</p>
<ul>
  <li><strong>Generaci\u00F3n Spec-a-Robot</strong> &mdash; Escribe una especificaci\u00F3n YAML
      <code>.roboscope</code> y deja que el LLM genere un archivo <code>.robot</code> completo.</li>
  <li><strong>Extracci\u00F3n Robot-a-Spec</strong> &mdash; Ingenier\u00EDa inversa de una especificaci\u00F3n
      <code>.roboscope</code> a partir de un archivo <code>.robot</code> existente.</li>
  <li><strong>An\u00E1lisis de fallos IA</strong> &mdash; An\u00E1lisis autom\u00E1tico de fallos de tests
      con identificaci\u00F3n de causas y sugerencias de correcciones.</li>
  <li><strong>Detecci\u00F3n de deriva</strong> &mdash; Detecci\u00F3n de modificaciones manuales
      en archivos <code>.robot</code> generados.</li>
</ul>
<p>
  Todas las funciones de IA requieren al menos un <strong>proveedor LLM</strong>
  configurado en <strong>Ajustes &gt; IA y Generaci\u00F3n</strong>.
</p>`
      },
      {
        id: 'ai-providers',
        title: 'Configurar proveedores LLM',
        content: `
<p>
  Navega a <strong>Ajustes &gt; IA y Generaci\u00F3n</strong> (rol Admin requerido)
  y haz clic en <strong>A\u00F1adir proveedor</strong>. Se soportan cuatro tipos:
</p>
<table>
  <thead>
    <tr><th>Proveedor</th><th>Clave API</th><th>URL base</th><th>Notas</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>OpenAI</strong></td><td>Requerida</td><td>Auto</td><td>GPT-4.1, GPT-4o, o3, o4-mini</td></tr>
    <tr><td><strong>Anthropic</strong></td><td>Requerida</td><td>Auto</td><td>Claude Sonnet/Opus 4.6, Haiku 4.5</td></tr>
    <tr><td><strong>OpenRouter</strong></td><td>Requerida</td><td>Auto</td><td>100+ modelos de diversos proveedores</td></tr>
    <tr><td><strong>Ollama (Local)</strong></td><td>No necesaria</td><td>Auto (localhost:11434)</td><td>Gratuito, privado, se ejecuta en tu m\u00E1quina</td></tr>
  </tbody>
</table>`
      },
      {
        id: 'ai-ollama-setup',
        title: 'Configurar Ollama (LLM local)',
        content: `
<p>
  <strong>Ollama</strong> permite ejecutar LLMs localmente y gratis &mdash;
  ning\u00FAn dato sale de tu ordenador.
</p>
<ol>
  <li><strong>Instalar Ollama</strong> &mdash; Descarga desde <code>ollama.com</code>.</li>
  <li><strong>Descargar un modelo</strong> &mdash; En la terminal:<br />
      <code>ollama pull mistral</code><br />
      Otros modelos populares: <code>llama3.3</code>, <code>deepseek-r1</code>,
      <code>dolphin-mistral</code>, <code>codellama</code>.</li>
  <li><strong>Verificar que funciona</strong> &mdash; <code>ollama list</code> muestra
      los modelos instalados.</li>
  <li><strong>Configurar en RoboScope</strong> &mdash; Ajustes &gt; IA y Generaci\u00F3n,
      A\u00F1adir proveedor:
      <ul>
        <li><strong>Tipo:</strong> Ollama (Local)</li>
        <li><strong>Modelo:</strong> Nombre exacto del modelo (ej. <code>mistral:latest</code>)</li>
        <li><strong>Clave API:</strong> Dejar vac\u00EDo</li>
        <li><strong>URL base:</strong> Dejar vac\u00EDo para <code>http://localhost:11434</code></li>
      </ul>
  </li>
</ol>
<h4>Soluci\u00F3n de problemas</h4>
<ul>
  <li><strong>\u00ABmodel not found\u00BB</strong> &mdash; El nombre del modelo debe coincidir exactamente
      con <code>ollama list</code>.</li>
  <li><strong>Conexi\u00F3n rechazada</strong> &mdash; Aseg\u00FArate de que Ollama est\u00E9 en ejecuci\u00F3n.</li>
  <li><strong>Generaci\u00F3n lenta</strong> &mdash; Los modelos locales son m\u00E1s lentos que las API en la nube
      (30&ndash;120 segundos).</li>
</ul>`,
        tip: 'Para mejores resultados, usa modelos de al menos 7B par\u00E1metros (ej. mistral, llama3.1).'
      },
      {
        id: 'ai-spec-generation',
        title: 'Generar tests desde especificaciones',
        content: `
<ol>
  <li>En el <strong>Explorador</strong>, crea o abre un archivo <code>.roboscope</code>.</li>
  <li>Haz clic en <strong>Generar</strong> en la barra de herramientas.</li>
  <li>Selecciona un proveedor LLM y haz clic en <strong>Generar</strong>.</li>
  <li>Revisa el c\u00F3digo en la <strong>vista previa de diferencias</strong>.</li>
  <li><strong>Aceptar y escribir archivo</strong> o <strong>Descartar</strong>.</li>
</ol>`
      },
      {
        id: 'ai-reverse-extract',
        title: 'Extraer especificaciones de archivos Robot',
        content: `
<ol>
  <li>Abre un archivo <code>.robot</code> en el Explorador.</li>
  <li>Haz clic en <strong>Extraer Spec</strong>.</li>
  <li>El LLM genera una especificaci\u00F3n <code>.roboscope</code> YAML.</li>
  <li>Revisa y acepta el resultado.</li>
</ol>`
      }
    ]
  },

  // ─── 11. Avanzado ─────────────────────────────────────────────────
  {
    id: 'advanced',
    title: 'Avanzado',
    icon: '\u{1F4A1}',
    subsections: [
      {
        id: 'websocket-updates',
        title: 'Actualizaciones en vivo por WebSocket',
        content: `
<p>
  RoboScope utiliza conexiones <strong>WebSocket</strong> para entregar
  actualizaciones en tiempo real sin recargas de p\u00E1gina. El frontend establece
  una conexi\u00F3n WebSocket al iniciar sesi\u00F3n a trav\u00E9s del composable
  <code>useWebSocket</code>.
</p>
<h4>Qu\u00E9 se actualiza en vivo</h4>
<ul>
  <li><strong>Cambios de estado de ejecuci\u00F3n</strong> &mdash; Cuando una ejecuci\u00F3n transiciona
      entre estados (pending &rarr; running &rarr; passed/failed), la insignia de estado se
      actualiza instant\u00E1neamente en la p\u00E1gina de Ejecuci\u00F3n, el Panel de control
      y cualquier vista abierta de Detalles de ejecuci\u00F3n.</li>
  <li><strong>Transmisi\u00F3n de salida</strong> &mdash; La salida est\u00E1ndar y los errores de las
      pruebas en ejecuci\u00F3n se transmiten a la vista de Detalles de la ejecuci\u00F3n en
      casi tiempo real.</li>
  <li><strong>Progreso de sincronizaci\u00F3n</strong> &mdash; Las operaciones de sincronizaci\u00F3n de
      repositorios actualizan su estado v\u00EDa WebSocket cuando se completan.</li>
</ul>
<p>
  Si la conexi\u00F3n WebSocket se pierde (por ejemplo, debido a una interrupci\u00F3n
  de red), el cliente intenta reconectarse autom\u00E1ticamente. Una breve notificaci\u00F3n
  aparece en el \u00E1rea del encabezado cuando la conexi\u00F3n se interrumpe.
</p>`,
        tip: 'Si las actualizaciones en vivo parecen detenerse, compruebe la consola del navegador en busca de errores de WebSocket. Una recarga de p\u00E1gina restablece la conexi\u00F3n.'
      },
      {
        id: 'keyboard-shortcuts',
        title: 'Atajos de teclado',
        content: `
<p>
  RoboScope soporta varios atajos de teclado para una navegaci\u00F3n y edici\u00F3n
  m\u00E1s r\u00E1pidas:
</p>
<table>
  <thead>
    <tr><th>Atajo</th><th>Acci\u00F3n</th><th>Contexto</th></tr>
  </thead>
  <tbody>
    <tr><td><code>Ctrl+S</code> / <code>Cmd+S</code></td><td>Guardar archivo</td><td>Editor del Explorador</td></tr>
    <tr><td><code>Ctrl+F</code> / <code>Cmd+F</code></td><td>Buscar en archivo</td><td>Editor del Explorador</td></tr>
    <tr><td><code>Ctrl+H</code> / <code>Cmd+H</code></td><td>Buscar y reemplazar</td><td>Editor del Explorador</td></tr>
    <tr><td><code>Ctrl+G</code> / <code>Cmd+G</code></td><td>Ir a l\u00EDnea</td><td>Editor del Explorador</td></tr>
    <tr><td><code>Ctrl+Z</code> / <code>Cmd+Z</code></td><td>Deshacer</td><td>Editor del Explorador</td></tr>
    <tr><td><code>Ctrl+Shift+Z</code> / <code>Cmd+Shift+Z</code></td><td>Rehacer</td><td>Editor del Explorador</td></tr>
    <tr><td><code>Escape</code></td><td>Cerrar modal/di\u00E1logo</td><td>Global</td></tr>
  </tbody>
</table>
<p>
  Todos los atajos de teclado siguen las convenciones de la plataforma:
  <code>Ctrl</code> en Windows/Linux, <code>Cmd</code> en macOS.
</p>`
      },
      {
        id: 'workflow-tips',
        title: 'Consejos para flujos de trabajo eficientes',
        content: `
<p>
  Aproveche al m\u00E1ximo RoboScope con estos consejos pr\u00E1cticos:
</p>
<h4>Organice los repositorios de forma reflexiva</h4>
<ul>
  <li>Use un repositorio por proyecto o dominio de pruebas (por ejemplo, <code>web-tests</code>, <code>api-tests</code>).</li>
  <li>Active la auto-sincronizaci\u00F3n en repositorios Git usados en flujos de trabajo CI/CD.</li>
  <li>Use nombres descriptivos de repositorio para que los miembros del equipo puedan identificar r\u00E1pidamente el correcto.</li>
</ul>
<h4>Aproveche los entornos</h4>
<ul>
  <li>Cree entornos separados para diferentes contextos de pruebas (por ejemplo, Selenium vs. Browser Library).</li>
  <li>Clone entornos cuando solo necesite cambiar uno o dos paquetes.</li>
  <li>Use variables de entorno para externalizar la configuraci\u00F3n como URLs y credenciales.</li>
</ul>
<h4>Supervise las tendencias de calidad</h4>
<ul>
  <li>Consulte la p\u00E1gina de Estad\u00EDsticas semanalmente para detectar regresiones en la tasa de \u00E9xito a tiempo.</li>
  <li>Aborde las pruebas inestables r\u00E1pidamente &mdash; socavan la confianza en la suite de pruebas.</li>
  <li>Use el filtro de repositorio para aislar problemas en suites de pruebas espec\u00EDficas.</li>
</ul>
<h4>Colaboraci\u00F3n en equipo</h4>
<ul>
  <li>Asigne roles apropiados a los miembros del equipo siguiendo el principio de m\u00EDnimo privilegio.</li>
  <li>Use el Panel de control como un tablero de estado compartido del equipo para el progreso de las pruebas.</li>
  <li>Descargue informes como archivos ZIP cuando necesite compartir resultados fuera de RoboScope.</li>
</ul>`
      },
      {
        id: 'troubleshooting',
        title: 'Resoluci\u00F3n de problemas comunes',
        content: `
<p>
  Si encuentra problemas, consulte los siguientes problemas comunes y sus soluciones:
</p>
<h4>La ejecuci\u00F3n se queda en estado "Pending"</h4>
<p>
  El ejecutor de tareas procesa una ejecuci\u00F3n a la vez. Si otra ejecuci\u00F3n
  se est\u00E1 ejecutando actualmente, la suya esperar\u00E1 en la cola. Compruebe
  la p\u00E1gina de Ejecuci\u00F3n en busca de ejecuciones de larga duraci\u00F3n o
  atascadas y canc\u00E9lelas si es necesario.
</p>
<h4>La clonaci\u00F3n o sincronizaci\u00F3n de Git falla</h4>
<ul>
  <li>Verifique que la URL del repositorio sea correcta y accesible desde el servidor.</li>
  <li>Para repositorios privados, aseg\u00FArese de que las credenciales o claves SSH est\u00E9n configuradas.</li>
  <li>Compruebe si la rama especificada existe en el remoto.</li>
  <li>Revise los registros del servidor para mensajes de error detallados.</li>
</ul>
<h4>La ejecuci\u00F3n falla con estado "Error"</h4>
<p>
  Un estado <code>error</code> (diferente de <code>failed</code>) significa que la
  ejecuci\u00F3n no pudo iniciarse o se bloque\u00F3 inesperadamente. Causas comunes:
</p>
<ul>
  <li>Robot Framework no est\u00E1 instalado en el entorno seleccionado.</li>
  <li>Faltan bibliotecas Python requeridas.</li>
  <li>La ruta de destino no existe en el repositorio.</li>
  <li>Problemas de permisos en el directorio de trabajo o de informes.</li>
</ul>
<h4>Problemas de conexi\u00F3n WebSocket</h4>
<p>
  Si las actualizaciones en vivo no funcionan:
</p>
<ul>
  <li>Aseg\u00FArese de que su navegador soporte WebSockets (todos los navegadores modernos lo hacen).</li>
  <li>Compruebe si un proxy inverso o firewall est\u00E1 bloqueando las conexiones WebSocket.</li>
  <li>Busque errores de conexi\u00F3n en la consola de desarrollador del navegador (<code>F12</code>).</li>
  <li>Recargue la p\u00E1gina para restablecer la conexi\u00F3n.</li>
</ul>
<h4>Informes no generados</h4>
<p>
  Si una ejecuci\u00F3n se completa pero no aparece ning\u00FAn informe:
</p>
<ul>
  <li>La ejecuci\u00F3n puede haber fallado antes de que Robot Framework produjera <code>output.xml</code>.</li>
  <li>Compruebe la salida stderr de la ejecuci\u00F3n en busca de errores de Python o Robot Framework.</li>
  <li>Verifique que el directorio <code>REPORTS_DIR</code> sea escribible por la aplicaci\u00F3n.</li>
</ul>`,
        tip: 'Para problemas persistentes, compruebe los registros del backend con "make docker-logs" o revise la salida de la consola uvicorn en modo de desarrollo.'
      },
      {
        id: 'i18n',
        title: 'Soporte de idiomas',
        content: `
<p>
  RoboScope soporta m\u00FAltiples idiomas de interfaz:
</p>
<table>
  <thead>
    <tr><th>C\u00F3digo</th><th>Idioma</th></tr>
  </thead>
  <tbody>
    <tr><td><code>en</code></td><td>English (Ingl\u00E9s)</td></tr>
    <tr><td><code>de</code></td><td>Deutsch (Alem\u00E1n)</td></tr>
    <tr><td><code>fr</code></td><td>Fran\u00E7ais (Franc\u00E9s)</td></tr>
    <tr><td><code>es</code></td><td>Espa\u00F1ol</td></tr>
    <tr><td><code>zh</code></td><td>&#20013;&#25991; (chino simplificado)</td></tr>
  </tbody>
</table>
<p>
  Para cambiar de idioma, use el <strong>selector de idioma</strong> en el
  encabezado de la aplicaci\u00F3n. El idioma seleccionado se guarda en el
  almacenamiento local del navegador y persiste entre sesiones. Todas las
  etiquetas de la interfaz, botones y mensajes se adaptan al idioma
  seleccionado. Esta documentaci\u00F3n est\u00E1 escrita en ingl\u00E9s, alem\u00E1n,
  franc\u00E9s y espa\u00F1ol; cuando la interfaz est\u00E1 en chino, la documentaci\u00F3n
  recurre al ingl\u00E9s.
</p>`
      },
      {
        id: 'api-access',
        title: 'Acceso a la API',
        content: `
<p>RoboScope expone una API REST completa bajo <code>/api/v1/</code>. Todo lo que hace la interfaz est\u00E1 disponible de forma program\u00E1tica.</p>
<h4>Autenticaci\u00F3n</h4>
<p>La API utiliza tokens bearer JWT. Solicite un token desde el endpoint de inicio de sesi\u00F3n:</p>
<p><code>POST /api/v1/auth/login</code> con <code>{"email": "...", "password": "..."}</code></p>
<p>Env\u00EDe el token devuelto como una cabecera <code>Authorization: Bearer &lt;token&gt;</code> en cada solicitud.</p>
<h4>Endpoints principales</h4>
<table>
  <thead><tr><th>Endpoint</th><th>Descripci\u00F3n</th></tr></thead>
  <tbody>
    <tr><td><code>GET /api/v1/repos</code></td><td>Listar todos los repositorios</td></tr>
    <tr><td><code>POST /api/v1/runs</code></td><td>Iniciar una nueva ejecuci\u00F3n</td></tr>
    <tr><td><code>GET /api/v1/reports</code></td><td>Listar informes</td></tr>
    <tr><td><code>GET /api/v1/stats/kpis</code></td><td>Obtener datos de KPI</td></tr>
  </tbody>
</table>
<p>La documentaci\u00F3n completa de la API con todos los endpoints, par\u00E1metros y formatos de respuesta est\u00E1 disponible en la <strong>Swagger UI</strong> interactiva en <code>/api/v1/docs</code>.</p>`,
        tip: 'La Swagger UI en /api/v1/docs es la referencia en vivo: cada endpoint, par\u00E1metro y esquema, generado a partir del servidor en ejecuci\u00F3n.'
      }
    ]
  },

  // ─── 12. Legal e informaci\u00F3n ──────────────────────────────────────
  {
    id: 'legal',
    title: 'Legal e informaci\u00F3n',
    icon: 'info',
    subsections: [
      {
        id: 'footer',
        title: 'Pie de p\u00E1gina',
        content: `
<p>
  Se muestra un pie de p\u00E1gina en la parte inferior de cada p\u00E1gina, que contiene:
</p>
<ul>
  <li>El <strong>aviso de copyright</strong> de viadee Unternehmensberatung AG.</li>
  <li>Un enlace al sitio web de <strong>viadee.de</strong>.</li>
  <li>Un enlace a la p\u00E1gina de <strong>Aviso legal</strong> (Impressum).</li>
</ul>`
      },
      {
        id: 'imprint',
        title: 'Aviso legal',
        content: `
<p>
  La p\u00E1gina de <strong>Aviso legal</strong> proporciona el aviso legal requerido
  por la legislaci\u00F3n alemana (Impressum). Contiene los datos de la empresa
  <em>viadee Unternehmensberatung AG</em>, incluyendo direcci\u00F3n, informaci\u00F3n
  de contacto, junta directiva, entrada en el registro mercantil y n\u00FAmero de
  identificaci\u00F3n fiscal.
</p>
<p>
  Acceda a la p\u00E1gina de Aviso legal a trav\u00E9s del enlace del pie de p\u00E1gina
  o navegando a <code>/imprint</code>.
</p>`
      }
    ]
  }
]

export default es
