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
  despu\u00E9s de iniciar sesi\u00F3n. Proporciona una visi\u00F3n general de alto
  nivel de su actividad de pruebas y el estado de los repositorios, ayud\u00E1ndole
  a evaluar r\u00E1pidamente el estado actual de su proyecto.
</p>
<p>
  El Panel de control se divide en tres secciones: <strong>Tarjetas KPI</strong>
  en la parte superior, una tabla de <strong>Ejecuciones recientes</strong> en el
  centro y un <strong>Resumen de repositorios</strong> en la parte inferior.
</p>`
      },
      {
        id: 'kpi-cards',
        title: 'Tarjetas KPI',
        content: `
<p>
  Se muestran cuatro tarjetas de indicadores clave de rendimiento en la parte
  superior del Panel de control:
</p>
<table>
  <thead>
    <tr><th>Tarjeta</th><th>Descripci\u00F3n</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Ejecuciones (30d)</strong></td>
      <td>N\u00FAmero total de ejecuciones de pruebas realizadas en los \u00FAltimos 30 d\u00EDas.</td>
    </tr>
    <tr>
      <td><strong>Tasa de \u00E9xito</strong></td>
      <td>Porcentaje de ejecuciones completadas con todas las pruebas aprobadas (\u00FAltimos 30 d\u00EDas).</td>
    </tr>
    <tr>
      <td><strong>Duraci\u00F3n media</strong></td>
      <td>Tiempo medio de reloj de las ejecuciones de pruebas completadas en los \u00FAltimos 30 d\u00EDas.</td>
    </tr>
    <tr>
      <td><strong>Repos activos</strong></td>
      <td>N\u00FAmero de repositorios que han tenido al menos una ejecuci\u00F3n en los \u00FAltimos 30 d\u00EDas.</td>
    </tr>
  </tbody>
</table>
<p>
  Cada tarjeta utiliza el sistema de dise\u00F1o de RoboScope: fondo blanco, acento
  azul para tendencias positivas y \u00E1mbar para advertencias. Los valores se
  actualizan autom\u00E1ticamente al navegar al Panel de control.
</p>`,
        tip: 'Las tarjetas KPI reflejan los \u00FAltimos 30 d\u00EDas de actividad. Para rangos de tiempo m\u00E1s largos, use la p\u00E1gina de Estad\u00EDsticas.'
      },
      {
        id: 'recent-runs',
        title: 'Tabla de ejecuciones recientes',
        content: `
<p>
  Debajo de las tarjetas KPI, una tabla enumera las ejecuciones de pruebas m\u00E1s
  recientes en todos los repositorios. Cada fila muestra:
</p>
<ul>
  <li><strong>ID de ejecuci\u00F3n</strong> &mdash; Un identificador \u00FAnico para la ejecuci\u00F3n.</li>
  <li><strong>Repositorio</strong> &mdash; El nombre del repositorio contra el que se lanz\u00F3 la ejecuci\u00F3n.</li>
  <li><strong>Estado</strong> &mdash; Una insignia de color que indica el estado de la ejecuci\u00F3n: <code>passed</code>, <code>failed</code>, <code>running</code>, <code>pending</code>, <code>error</code>, <code>cancelled</code> o <code>timeout</code>.</li>
  <li><strong>Duraci\u00F3n</strong> &mdash; Cu\u00E1nto tiempo tard\u00F3 la ejecuci\u00F3n (o cu\u00E1nto tiempo lleva ejecut\u00E1ndose).</li>
  <li><strong>Iniciado por</strong> &mdash; El usuario que inici\u00F3 la ejecuci\u00F3n.</li>
  <li><strong>Fecha</strong> &mdash; Marca de tiempo de cu\u00E1ndo se inici\u00F3 la ejecuci\u00F3n.</li>
</ul>
<p>
  Al hacer clic en una fila, se navega a la p\u00E1gina de <strong>Detalles de
  la ejecuci\u00F3n</strong> donde puede inspeccionar los registros de salida,
  reintentar o cancelar la ejecuci\u00F3n.
</p>`
      },
      {
        id: 'repo-summary',
        title: 'Resumen de repositorios',
        content: `
<p>
  La secci\u00F3n inferior del Panel de control muestra un resumen de todos los
  repositorios registrados. Para cada repositorio, puede ver:
</p>
<ul>
  <li>Nombre del repositorio y tipo (Git o Local).</li>
  <li>N\u00FAmero de archivos de prueba detectados.</li>
  <li>Marca de tiempo de la \u00FAltima sincronizaci\u00F3n.</li>
  <li>Insignia de estado de la \u00FAltima ejecuci\u00F3n.</li>
</ul>
<p>
  Esto proporciona una visi\u00F3n r\u00E1pida de qu\u00E9 repositorios est\u00E1n
  en buen estado y cu\u00E1les pueden necesitar atenci\u00F3n. Al hacer clic en el
  nombre de un repositorio, se accede a la vista del <strong>Explorador</strong>
  de ese repositorio.
</p>`,
        tip: 'Si un repositorio muestra una marca de tiempo de sincronizaci\u00F3n obsoleta, navegue a Repositorios y lance una sincronizaci\u00F3n manual.'
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
        tip: 'La auto-sincronizaci\u00F3n asegura que siempre pruebe contra el c\u00F3digo m\u00E1s reciente. Act\u00EDvela para flujos de trabajo tipo CI/CD.'
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

  // ─── 5. Ejecuci\u00F3n ─────────────────────────────────────────────────
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
</p>`,
        tip: 'Si necesita ejecutar pruebas de m\u00FAltiples repositorios, p\u00F3ngalas en cola secuencialmente. Se ejecutar\u00E1n en orden.'
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
  se le env\u00EDa una se\u00F1al de terminaci\u00F3n y el estado de la ejecuci\u00F3n
  cambia a <code>cancelled</code>. Requiere rol <strong>Runner</strong> o superior.
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
  <li>Navegue a un informe con tests fallidos (Informes &gt; haga clic en un informe).</li>
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
<p>
  El an\u00E1lisis se ejecuta como una tarea en segundo plano y no bloquea otras operaciones.
  Cada an\u00E1lisis es una llamada LLM independiente &mdash; un rean\u00E1lisis puede producir
  resultados diferentes.
</p>`,
        tip: 'El an\u00E1lisis de IA funciona mejor con mensajes de error descriptivos. Si sus tests usan mensajes de fallo personalizados, el LLM puede proporcionar sugerencias m\u00E1s espec\u00EDficas.'
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
  Un gr\u00E1fico de l\u00EDneas muestra la tasa de \u00E9xito diaria para el per\u00EDodo
  seleccionado. El eje X representa las fechas y el eje Y muestra el porcentaje
  (0&ndash;100%). Este gr\u00E1fico facilita la detecci\u00F3n de regresiones o mejoras
  a lo largo del tiempo. El gr\u00E1fico est\u00E1 impulsado por <strong>Chart.js</strong>
  y soporta tooltips al pasar el cursor para valores exactos.
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
  <li><code>robotframework-browser</code> &mdash; Pruebas de navegador basadas en Playwright.</li>
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
      }
    ]
  },

  // ─── 10. Avanzado ─────────────────────────────────────────────────
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
  </tbody>
</table>
<p>
  Para cambiar de idioma, use el <strong>selector de idioma</strong> en el
  encabezado de la aplicaci\u00F3n. El idioma seleccionado se guarda en el
  almacenamiento local del navegador y persiste entre sesiones. Todas las
  etiquetas de la interfaz, botones, mensajes y esta documentaci\u00F3n se
  adaptan al idioma seleccionado.
</p>`
      }
    ]
  },

  // ─── 11. Legal e informaci\u00F3n ──────────────────────────────────────
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
  <li>Un enlace al sitio web de <strong>mateo-automation.com</strong>.</li>
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
