import type { DocsContent } from '../types'

const fr: DocsContent = [
  // ─── 1. Pour commencer ────────────────────────────────────────────
  {
    id: 'getting-started',
    title: 'Pour commencer',
    icon: '\u{1F680}',
    subsections: [
      {
        id: 'overview',
        title: 'Qu\u2019est-ce que RoboScope\u00A0?',
        content: `
<p>
  <strong>RoboScope</strong> est un outil de gestion de tests bas\u00E9 sur le web, con\u00E7u
  sp\u00E9cifiquement pour <em>Robot Framework</em>. Il fournit un environnement int\u00E9gr\u00E9
  pour g\u00E9rer les d\u00E9p\u00F4ts de tests, ex\u00E9cuter des campagnes, analyser les rapports
  et suivre les statistiques &mdash; le tout depuis une interface web moderne et unifi\u00E9e.
</p>
<h4>Fonctionnalit\u00E9s principales</h4>
<ul>
  <li><strong>Gestion des d\u00E9p\u00F4ts</strong> &mdash; Connectez des d\u00E9p\u00F4ts Git ou des dossiers locaux pour organiser vos suites de tests.</li>
  <li><strong>Explorateur int\u00E9gr\u00E9</strong> &mdash; Parcourez, \u00E9ditez et cr\u00E9ez des fichiers <code>.robot</code> directement dans le navigateur avec coloration syntaxique.</li>
  <li><strong>Ex\u00E9cution de tests</strong> &mdash; Lancez des ex\u00E9cutions avec des d\u00E9lais configurables, surveillez la progression en temps r\u00E9el via WebSocket et consultez les journaux de sortie.</li>
  <li><strong>Analyse de rapports</strong> &mdash; Visualisez les rapports HTML int\u00E9gr\u00E9s de Robot Framework, inspectez la sortie XML et t\u00E9l\u00E9chargez les archives ZIP.</li>
  <li><strong>Statistiques et tendances</strong> &mdash; Suivez les taux de r\u00E9ussite, les tendances pass\u00E9/\u00E9chou\u00E9 et d\u00E9tectez les tests instables sur des p\u00E9riodes configurables.</li>
  <li><strong>Gestion des environnements</strong> &mdash; Cr\u00E9ez des environnements virtuels Python isol\u00E9s, installez des paquets et d\u00E9finissez des variables d\u2019environnement.</li>
  <li><strong>Acc\u00E8s bas\u00E9 sur les r\u00F4les</strong> &mdash; Quatre niveaux de permissions (Viewer, Runner, Editor, Admin) contr\u00F4lent qui peut voir, ex\u00E9cuter, \u00E9diter ou administrer.</li>
</ul>`,
        tip: 'RoboScope fonctionne de mani\u00E8re optimale avec les navigateurs bas\u00E9s sur Chromium (Chrome, Edge) ou Firefox pour une exp\u00E9rience compl\u00E8te avec l\u2019\u00E9diteur CodeMirror.'
      },
      {
        id: 'login',
        title: 'Connexion',
        content: `
<p>
  Lorsque vous ouvrez RoboScope pour la premi\u00E8re fois, l\u2019\u00E9cran de
  <strong>Connexion</strong> s\u2019affiche. Saisissez votre adresse e-mail et
  votre mot de passe pour vous authentifier.
</p>
<h4>Compte administrateur par d\u00E9faut</h4>
<table>
  <thead>
    <tr><th>Champ</th><th>Valeur</th></tr>
  </thead>
  <tbody>
    <tr><td>E-mail</td><td><code>admin@roboscope.local</code></td></tr>
    <tr><td>Mot de passe</td><td><code>admin123</code></td></tr>
  </tbody>
</table>
<p>
  Apr\u00E8s vous \u00EAtre connect\u00E9 avec le compte par d\u00E9faut, il est
  <strong>fortement recommand\u00E9</strong> de changer le mot de passe imm\u00E9diatement
  ou de cr\u00E9er un utilisateur administrateur d\u00E9di\u00E9 et de d\u00E9sactiver
  le compte par d\u00E9faut.
</p>
<h4>Gestion des sessions</h4>
<p>
  RoboScope utilise une authentification bas\u00E9e sur JWT. Votre jeton de session est
  automatiquement renouvel\u00E9 tant que l\u2019application est ouverte. Si le jeton expire
  (par exemple apr\u00E8s une longue p\u00E9riode d\u2019inactivit\u00E9), vous serez redirig\u00E9
  vers la page de connexion.
</p>`,
        tip: 'Si vous oubliez votre mot de passe, un administrateur peut le r\u00E9initialiser depuis la page Param\u00E8tres.'
      },
      {
        id: 'ui-layout',
        title: 'Disposition de l\u2019interface',
        content: `
<p>L\u2019interface de RoboScope se compose de trois zones principales\u00A0:</p>
<ol>
  <li>
    <strong>Barre lat\u00E9rale</strong> (gauche) &mdash; Le panneau de navigation principal. Il contient
    des liens vers toutes les sections majeures\u00A0: Tableau de bord, D\u00E9p\u00F4ts, Explorateur,
    Ex\u00E9cution, Rapports, Statistiques, Environnements et Param\u00E8tres. La barre lat\u00E9rale
    peut \u00EAtre r\u00E9duite \u00E0 une vue d\u2019ic\u00F4nes (60\u00A0px) pour maximiser l\u2019espace de contenu.
  </li>
  <li>
    <strong>En-t\u00EAte</strong> (haut) &mdash; Affiche le titre de la page actuelle, le nom et le
    r\u00F4le de l\u2019utilisateur connect\u00E9, un s\u00E9lecteur de langue (DE/EN/FR/ES) et le bouton
    de d\u00E9connexion.
  </li>
  <li>
    <strong>Zone de contenu</strong> (centre) &mdash; L\u2019espace de travail principal o\u00F9 la vue
    s\u00E9lectionn\u00E9e est affich\u00E9e. Chaque vue utilise des cartes, des tableaux et des boutons
    d\u2019action conformes au syst\u00E8me de design RoboScope.
  </li>
</ol>
<p>
  La barre lat\u00E9rale mesure <code>250px</code> en mode \u00E9tendu et <code>60px</code> en mode r\u00E9duit.
  L\u2019en-t\u00EAte a une hauteur fixe de <code>56px</code>.
</p>`,
        tip: 'Cliquez sur l\u2019ic\u00F4ne hamburger en haut de la barre lat\u00E9rale pour basculer entre les modes \u00E9tendu et r\u00E9duit.'
      },
      {
        id: 'roles-permissions',
        title: 'R\u00F4les et permissions',
        content: `
<p>
  RoboScope impl\u00E9mente un syst\u00E8me de contr\u00F4le d\u2019acc\u00E8s bas\u00E9 sur les r\u00F4les (RBAC)
  hi\u00E9rarchique. Chaque r\u00F4le sup\u00E9rieur h\u00E9rite de toutes les permissions des r\u00F4les inf\u00E9rieurs.
</p>
<table>
  <thead>
    <tr>
      <th>R\u00F4le</th>
      <th>Niveau</th>
      <th>Permissions</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Viewer</strong></td>
      <td>0</td>
      <td>Voir les tableaux de bord, d\u00E9p\u00F4ts, rapports, statistiques. Acc\u00E8s en lecture seule.</td>
    </tr>
    <tr>
      <td><strong>Runner</strong></td>
      <td>1</td>
      <td>Toutes les permissions Viewer <strong>+</strong> lancer des ex\u00E9cutions, annuler des ex\u00E9cutions, annuler toutes les ex\u00E9cutions.</td>
    </tr>
    <tr>
      <td><strong>Editor</strong></td>
      <td>2</td>
      <td>Toutes les permissions Runner <strong>+</strong> ajouter/modifier/supprimer des d\u00E9p\u00F4ts, \u00E9diter des fichiers dans l\u2019Explorateur, g\u00E9rer les environnements.</td>
    </tr>
    <tr>
      <td><strong>Admin</strong></td>
      <td>3</td>
      <td>Toutes les permissions Editor <strong>+</strong> g\u00E9rer les utilisateurs, changer les r\u00F4les, modifier les param\u00E8tres, supprimer tous les rapports.</td>
    </tr>
  </tbody>
</table>
<p>
  La hi\u00E9rarchie des r\u00F4les est strictement ordonn\u00E9e\u00A0:
  <code>Viewer &lt; Runner &lt; Editor &lt; Admin</code>. Les gardes d\u2019endpoints
  garantissent que les utilisateurs ne peuvent pas effectuer d\u2019actions au-dessus de leur niveau attribu\u00E9.
</p>`,
        tip: 'En cas de doute sur vos droits, v\u00E9rifiez votre badge de r\u00F4le dans l\u2019en-t\u00EAte. Si un bouton est absent, vous avez peut-\u00EAtre besoin d\u2019un r\u00F4le sup\u00E9rieur.'
      }
    ]
  },

  // ─── 2. Tableau de bord ──────────────────────────────────────────
  {
    id: 'dashboard',
    title: 'Tableau de bord',
    icon: '\u{1F4CA}',
    subsections: [
      {
        id: 'dashboard-overview',
        title: 'Aper\u00E7u du tableau de bord',
        content: `
<p>
  Le <strong>Tableau de bord</strong> est la page d\u2019accueil par d\u00E9faut apr\u00E8s la connexion.
  Il fournit une vue d\u2019ensemble de votre activit\u00E9 de test et de la sant\u00E9 de vos d\u00E9p\u00F4ts,
  vous aidant \u00E0 \u00E9valuer rapidement l\u2019\u00E9tat actuel de votre projet.
</p>
<p>
  Le tableau de bord est divis\u00E9 en trois sections\u00A0: les <strong>cartes KPI</strong> en haut,
  un tableau des <strong>ex\u00E9cutions r\u00E9centes</strong> au milieu, et un
  <strong>r\u00E9sum\u00E9 des d\u00E9p\u00F4ts</strong> en bas.
</p>`
      },
      {
        id: 'kpi-cards',
        title: 'Cartes KPI',
        content: `
<p>
  Quatre cartes d\u2019indicateurs cl\u00E9s de performance sont affich\u00E9es en haut du tableau de bord\u00A0:
</p>
<table>
  <thead>
    <tr><th>Carte</th><th>Description</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Ex\u00E9cutions (30j)</strong></td>
      <td>Nombre total d\u2019ex\u00E9cutions de tests au cours des 30 derniers jours.</td>
    </tr>
    <tr>
      <td><strong>Taux de r\u00E9ussite</strong></td>
      <td>Pourcentage d\u2019ex\u00E9cutions dont tous les tests ont r\u00E9ussi (30 derniers jours).</td>
    </tr>
    <tr>
      <td><strong>Dur\u00E9e moyenne</strong></td>
      <td>Dur\u00E9e moyenne des ex\u00E9cutions termin\u00E9es au cours des 30 derniers jours.</td>
    </tr>
    <tr>
      <td><strong>D\u00E9p\u00F4ts actifs</strong></td>
      <td>Nombre de d\u00E9p\u00F4ts ayant eu au moins une ex\u00E9cution dans les 30 derniers jours.</td>
    </tr>
  </tbody>
</table>
<p>
  Chaque carte utilise le syst\u00E8me de design RoboScope\u00A0: fond blanc, accent bleu pour les
  tendances positives et ambre pour les avertissements. Les valeurs se mettent \u00E0 jour
  automatiquement lors de la navigation vers le tableau de bord.
</p>`,
        tip: 'Les cartes KPI refl\u00E8tent les 30 derniers jours d\u2019activit\u00E9. Pour des p\u00E9riodes plus longues, utilisez la page Statistiques.'
      },
      {
        id: 'recent-runs',
        title: 'Tableau des ex\u00E9cutions r\u00E9centes',
        content: `
<p>
  Sous les cartes KPI, un tableau liste les ex\u00E9cutions de tests les plus r\u00E9centes
  de tous les d\u00E9p\u00F4ts. Chaque ligne affiche\u00A0:
</p>
<ul>
  <li><strong>ID d\u2019ex\u00E9cution</strong> &mdash; Un identifiant unique pour l\u2019ex\u00E9cution.</li>
  <li><strong>D\u00E9p\u00F4t</strong> &mdash; Le nom du d\u00E9p\u00F4t concern\u00E9.</li>
  <li><strong>Statut</strong> &mdash; Un badge color\u00E9 indiquant l\u2019\u00E9tat\u00A0: <code>passed</code>, <code>failed</code>, <code>running</code>, <code>pending</code>, <code>error</code>, <code>cancelled</code> ou <code>timeout</code>.</li>
  <li><strong>Dur\u00E9e</strong> &mdash; Le temps d\u2019ex\u00E9cution (ou le temps \u00E9coul\u00E9 si en cours).</li>
  <li><strong>D\u00E9clench\u00E9 par</strong> &mdash; L\u2019utilisateur qui a lanc\u00E9 l\u2019ex\u00E9cution.</li>
  <li><strong>Date</strong> &mdash; Horodatage du lancement de l\u2019ex\u00E9cution.</li>
</ul>
<p>
  Cliquer sur une ligne ouvre la page de <strong>D\u00E9tails de l\u2019ex\u00E9cution</strong> o\u00F9 vous
  pouvez inspecter les journaux de sortie, relancer ou annuler l\u2019ex\u00E9cution.
</p>`
      },
      {
        id: 'repo-summary',
        title: 'Aper\u00E7u des d\u00E9p\u00F4ts',
        content: `
<p>
  La section inf\u00E9rieure du tableau de bord affiche un r\u00E9sum\u00E9 de tous les d\u00E9p\u00F4ts
  enregistr\u00E9s. Pour chaque d\u00E9p\u00F4t, vous pouvez voir\u00A0:
</p>
<ul>
  <li>Nom et type du d\u00E9p\u00F4t (Git ou Local).</li>
  <li>Nombre de fichiers de test d\u00E9tect\u00E9s.</li>
  <li>Horodatage de la derni\u00E8re synchronisation.</li>
  <li>Badge de statut de la derni\u00E8re ex\u00E9cution.</li>
</ul>
<p>
  Cela permet d\u2019identifier rapidement les d\u00E9p\u00F4ts en bonne sant\u00E9 et ceux n\u00E9cessitant
  une attention particuli\u00E8re. Cliquer sur le nom d\u2019un d\u00E9p\u00F4t ouvre la vue
  <strong>Explorateur</strong> pour ce d\u00E9p\u00F4t.
</p>`,
        tip: 'Si un d\u00E9p\u00F4t affiche un horodatage de synchronisation obsol\u00E8te, acc\u00E9dez aux D\u00E9p\u00F4ts et lancez une synchronisation manuelle.'
      }
    ]
  },

  // ─── 3. D\u00E9p\u00F4ts ──────────────────────────────────────────────────
  {
    id: 'repositories',
    title: 'D\u00E9p\u00F4ts',
    icon: '\u{1F4C1}',
    subsections: [
      {
        id: 'repos-overview',
        title: 'Gestion des d\u00E9p\u00F4ts',
        content: `
<p>
  La page <strong>D\u00E9p\u00F4ts</strong> permet d\u2019enregistrer et de g\u00E9rer vos d\u00E9p\u00F4ts de
  tests Robot Framework. RoboScope prend en charge deux types de d\u00E9p\u00F4ts\u00A0:
</p>
<ul>
  <li><strong>D\u00E9p\u00F4ts Git</strong> &mdash; Clon\u00E9s depuis une URL distante, avec s\u00E9lection de branche et fonctionnalit\u00E9s de synchronisation.</li>
  <li><strong>Dossiers locaux</strong> &mdash; Pointant vers un r\u00E9pertoire sur le syst\u00E8me de fichiers du serveur.</li>
</ul>
<p>
  Toutes les donn\u00E9es des d\u00E9p\u00F4ts sont stock\u00E9es dans le r\u00E9pertoire <code>WORKSPACE_DIR</code>
  (par d\u00E9faut\u00A0: <code>~/.roboscope/workspace</code>). Seuls les utilisateurs avec le r\u00F4le
  <strong>Editor</strong> ou sup\u00E9rieur peuvent ajouter, modifier ou supprimer des d\u00E9p\u00F4ts.
</p>`
      },
      {
        id: 'add-git-repo',
        title: 'Ajouter un d\u00E9p\u00F4t Git',
        content: `
<p>Pour ajouter un d\u00E9p\u00F4t Git, cliquez sur le bouton <strong>Ajouter un d\u00E9p\u00F4t</strong> et remplissez le formulaire\u00A0:</p>
<ol>
  <li>S\u00E9lectionnez <strong>Git</strong> comme type de d\u00E9p\u00F4t.</li>
  <li>Saisissez l\u2019<strong>URL du d\u00E9p\u00F4t</strong> (HTTPS ou SSH). Exemple\u00A0: <code>https://github.com/org/tests.git</code></li>
  <li>Sp\u00E9cifiez la <strong>branche</strong> \u00E0 cloner (par d\u00E9faut\u00A0: <code>main</code>).</li>
  <li>Fournissez \u00E9ventuellement un <strong>nom d\u2019affichage</strong>. S\u2019il est laiss\u00E9 vide, le nom est d\u00E9duit de l\u2019URL.</li>
  <li>Cliquez sur <strong>Cr\u00E9er</strong>.</li>
</ol>
<p>
  RoboScope utilise <em>GitPython</em> pour cloner le d\u00E9p\u00F4t dans le r\u00E9pertoire de travail.
  L\u2019op\u00E9ration de clonage s\u2019ex\u00E9cute en t\u00E2che de fond, vous verrez donc un statut
  <code>pending</code> jusqu\u2019\u00E0 son ach\u00E8vement. Une fois le clonage termin\u00E9, le d\u00E9p\u00F4t
  devient disponible dans les vues Explorateur et Ex\u00E9cution.
</p>`,
        tip: 'Pour les d\u00E9p\u00F4ts priv\u00E9s via HTTPS, incluez les identifiants dans l\u2019URL ou configurez les cl\u00E9s SSH sur le serveur.'
      },
      {
        id: 'add-local-repo',
        title: 'Ajouter un dossier local',
        content: `
<p>
  Si vos suites de tests se trouvent d\u00E9j\u00E0 sur le syst\u00E8me de fichiers du serveur,
  vous pouvez les enregistrer en tant que d\u00E9p\u00F4t <strong>Local</strong>\u00A0:
</p>
<ol>
  <li>S\u00E9lectionnez <strong>Local</strong> comme type de d\u00E9p\u00F4t.</li>
  <li>Saisissez le <strong>chemin</strong> absolu vers le r\u00E9pertoire contenant vos fichiers <code>.robot</code>.</li>
  <li>Fournissez un <strong>nom d\u2019affichage</strong>.</li>
  <li>Cliquez sur <strong>Cr\u00E9er</strong>.</li>
</ol>
<p>
  Les d\u00E9p\u00F4ts locaux ne prennent pas en charge les fonctions de synchronisation ou de
  synchronisation automatique car ils r\u00E9f\u00E9rencent un r\u00E9pertoire en direct. Toute modification
  apport\u00E9e aux fichiers sur le disque est imm\u00E9diatement refl\u00E9t\u00E9e dans l\u2019Explorateur.
</p>`
      },
      {
        id: 'sync-autosync',
        title: 'Synchronisation et synchronisation automatique',
        content: `
<p>
  Les d\u00E9p\u00F4ts Git peuvent \u00EAtre synchronis\u00E9s pour r\u00E9cup\u00E9rer les derni\u00E8res modifications depuis le serveur distant\u00A0:
</p>
<ul>
  <li><strong>Synchronisation manuelle</strong> &mdash; Cliquez sur le bouton <strong>Sync</strong> sur une ligne de d\u00E9p\u00F4t. Cela effectue un <code>git pull</code> sur la branche configur\u00E9e.</li>
  <li><strong>Synchronisation automatique</strong> &mdash; Activez le commutateur de synchronisation automatique pour un d\u00E9p\u00F4t. Lorsqu\u2019il est activ\u00E9, RoboScope r\u00E9cup\u00E8re automatiquement les modifications \u00E0 un intervalle configurable avant chaque ex\u00E9cution de test.</li>
</ul>
<p>
  Le statut de synchronisation est indiqu\u00E9 par un horodatage montrant la derni\u00E8re
  synchronisation r\u00E9ussie. Si une synchronisation \u00E9choue (par exemple en cas de conflit
  de fusion), un badge d\u2019erreur appara\u00EEt \u00E0 c\u00F4t\u00E9 du nom du d\u00E9p\u00F4t.
</p>`,
        tip: 'La synchronisation automatique garantit que vous testez toujours le code le plus r\u00E9cent. Activez-la pour les flux CI/CD.'
      },
      {
        id: 'library-check',
        title: 'V\u00E9rification des biblioth\u00E8ques (Gestionnaire de paquets)',
        content: `
<p>
  La fonctionnalit\u00E9 <strong>V\u00E9rification des biblioth\u00E8ques</strong> analyse les fichiers
  <code>.robot</code> et <code>.resource</code> d\u2019un d\u00E9p\u00F4t pour rep\u00E9rer les imports
  <code>Library</code> et v\u00E9rifie si les paquets Python correspondants sont install\u00E9s
  dans un environnement s\u00E9lectionn\u00E9.
</p>
<h4>Comment l\u2019utiliser</h4>
<ol>
  <li>Sur la page <strong>D\u00E9p\u00F4ts</strong>, cliquez sur le bouton <strong>V\u00E9rification des biblioth\u00E8ques</strong> sur une carte de d\u00E9p\u00F4t.</li>
  <li>S\u00E9lectionnez un <strong>Environnement</strong> dans la liste d\u00E9roulante (pr\u00E9-rempli avec l\u2019environnement par d\u00E9faut du d\u00E9p\u00F4t si d\u00E9fini).</li>
  <li>Cliquez sur <strong>Analyser</strong> pour lancer l\u2019analyse du d\u00E9p\u00F4t.</li>
</ol>
<h4>R\u00E9sultats</h4>
<p>Les r\u00E9sultats de l\u2019analyse affichent un tableau avec chaque biblioth\u00E8que et son statut\u00A0:</p>
<ul>
  <li><strong>Install\u00E9e</strong> (vert) &mdash; Le paquet PyPI de la biblioth\u00E8que est install\u00E9 dans l\u2019environnement, avec la version affich\u00E9e.</li>
  <li><strong>Manquante</strong> (rouge) &mdash; La biblioth\u00E8que est utilis\u00E9e dans les fichiers de test mais n\u2019est pas install\u00E9e. Un bouton <strong>Installer</strong> appara\u00EEt pour une installation en un clic.</li>
  <li><strong>Int\u00E9gr\u00E9e</strong> (gris) &mdash; La biblioth\u00E8que fait partie de la biblioth\u00E8que standard de Robot Framework (par ex. Collections, String, BuiltIn) et ne n\u00E9cessite pas d\u2019installation.</li>
</ul>
<h4>Installer les biblioth\u00E8ques manquantes</h4>
<p>
  Cliquez sur <strong>Installer</strong> \u00E0 c\u00F4t\u00E9 d\u2019une biblioth\u00E8que manquante pour l\u2019installer
  dans l\u2019environnement s\u00E9lectionn\u00E9. Utilisez <strong>Installer toutes les manquantes</strong>
  pour installer toutes les biblioth\u00E8ques manquantes en une fois. L\u2019installation utilise la
  gestion de paquets existante (pip install) et s\u2019ex\u00E9cute en arri\u00E8re-plan.
</p>
<h4>Environnement par d\u00E9faut</h4>
<p>
  Chaque d\u00E9p\u00F4t peut avoir un <strong>environnement par d\u00E9faut</strong> assign\u00E9. D\u00E9finissez-le
  lors de l\u2019ajout d\u2019un d\u00E9p\u00F4t ou ult\u00E9rieurement via les param\u00E8tres du d\u00E9p\u00F4t. L\u2019environnement
  par d\u00E9faut est pr\u00E9-s\u00E9lectionn\u00E9 lors de l\u2019ouverture du dialogue de v\u00E9rification des biblioth\u00E8ques.
</p>`,
        tip: 'Lancez une v\u00E9rification des biblioth\u00E8ques apr\u00E8s avoir clon\u00E9 un nouveau d\u00E9p\u00F4t pour identifier et installer rapidement toutes les d\u00E9pendances requises.'
      },
      {
        id: 'project-environment',
        title: 'Environnement du projet',
        content: `
<p>
  Chaque projet peut avoir un <strong>environnement par d\u00E9faut</strong> assign\u00E9. Cet
  environnement est utilis\u00E9 automatiquement lors du lancement des ex\u00E9cutions de tests
  depuis le projet et est pr\u00E9-s\u00E9lectionn\u00E9 dans le dialogue de v\u00E9rification des biblioth\u00E8ques.
</p>
<h4>S\u00E9lectionner un environnement</h4>
<p>
  Sur la page <strong>Projets</strong>, chaque carte de projet affiche une liste d\u00E9roulante
  d\u2019environnements. S\u00E9lectionnez un environnement dans la liste pour l\u2019assigner au projet.
  La modification est enregistr\u00E9e imm\u00E9diatement.
</p>
<p>
  Si un environnement par d\u00E9faut syst\u00E8me a \u00E9t\u00E9 configur\u00E9, il est automatiquement
  pr\u00E9-s\u00E9lectionn\u00E9 lors de l\u2019ajout de nouveaux projets.
</p>`,
        tip: 'Assignez le bon environnement \u00E0 chaque projet pour \u00E9viter les erreurs \u00AB\u00A0biblioth\u00E8que manquante\u00A0\u00BB lors de l\u2019ex\u00E9cution des tests.'
      },
      {
        id: 'bulk-operations',
        title: 'S\u00E9lection et suppression en masse',
        content: `
<p>
  La page D\u00E9p\u00F4ts prend en charge les op\u00E9rations en masse pour une gestion efficace\u00A0:
</p>
<ul>
  <li>Utilisez les <strong>cases \u00E0 cocher</strong> sur chaque ligne pour s\u00E9lectionner plusieurs d\u00E9p\u00F4ts.</li>
  <li>Une case <strong>Tout s\u00E9lectionner</strong> dans l\u2019en-t\u00EAte du tableau permet de basculer tous les \u00E9l\u00E9ments.</li>
  <li>Une fois s\u00E9lectionn\u00E9s, cliquez sur le bouton <strong>Supprimer la s\u00E9lection</strong> (r\u00F4le <strong>Editor+</strong> requis).</li>
  <li>Un dialogue de confirmation affichera la liste des d\u00E9p\u00F4ts \u00E0 supprimer.</li>
</ul>
<p>
  <strong>Attention\u00A0:</strong> La suppression d\u2019un d\u00E9p\u00F4t le retire de RoboScope et supprime
  les donn\u00E9es de l\u2019espace de travail clon\u00E9. Les rapports et l\u2019historique d\u2019ex\u00E9cution
  associ\u00E9s au d\u00E9p\u00F4t ne sont <em>pas</em> automatiquement supprim\u00E9s. Utilisez la page
  Rapports pour nettoyer les anciens rapports si n\u00E9cessaire.
</p>`
      }
    ]
  },

  // ─── 4. Explorateur ───────────────────────────────────────────────
  {
    id: 'explorer',
    title: 'Explorateur',
    icon: '\u{1F50D}',
    subsections: [
      {
        id: 'file-tree',
        title: 'Navigation dans l\u2019arborescence de fichiers',
        content: `
<p>
  L\u2019<strong>Explorateur</strong> fournit un navigateur de fichiers pour parcourir le contenu
  de vos d\u00E9p\u00F4ts. Le panneau de gauche affiche une arborescence hi\u00E9rarchique de r\u00E9pertoires
  et de fichiers. Vous pouvez\u00A0:
</p>
<ul>
  <li>D\u00E9plier et replier les r\u00E9pertoires en cliquant sur l\u2019ic\u00F4ne de dossier ou la fl\u00E8che.</li>
  <li>Cliquer sur un fichier pour l\u2019ouvrir dans le panneau d\u2019\u00E9dition \u00E0 droite.</li>
  <li>Les ic\u00F4nes de fichiers indiquent le type\u00A0: les fichiers <code>.robot</code> ont une ic\u00F4ne sp\u00E9ciale Robot Framework, tandis que les fichiers <code>.py</code>, <code>.yaml</code>, <code>.txt</code> et autres utilisent des ic\u00F4nes standard.</li>
  <li>L\u2019en-t\u00EAte de l\u2019arborescence affiche le <strong>nombre total de cas de test</strong> trouv\u00E9s dans tous les fichiers <code>.robot</code> du projet. Les r\u00E9pertoires affichent \u00E9galement un badge avec leur nombre individuel de tests.</li>
</ul>
<p>
  Une <strong>liste d\u00E9roulante de s\u00E9lection de d\u00E9p\u00F4t</strong> en haut permet de basculer
  entre les d\u00E9p\u00F4ts enregistr\u00E9s sans quitter l\u2019Explorateur.
</p>
<h4>Fonctionnalit\u00E9s localhost</h4>
<p>
  Lors de l\u2019acc\u00E8s \u00E0 RoboScope sur <code>localhost</code>, des fonctionnalit\u00E9s suppl\u00E9mentaires sont disponibles\u00A0:
</p>
<ul>
  <li><strong>Ouvrir le dossier du projet</strong> &mdash; Un bouton dossier dans l\u2019en-t\u00EAte de l\u2019arborescence ouvre le r\u00E9pertoire racine du projet dans votre gestionnaire de fichiers syst\u00E8me (Finder, Explorateur Windows ou Nautilus).</li>
  <li><strong>Ouvrir dans le gestionnaire de fichiers</strong> &mdash; Chaque r\u00E9pertoire de l\u2019arborescence dispose d\u2019un bouton dossier pour l\u2019ouvrir directement dans le gestionnaire de fichiers syst\u00E8me.</li>
  <li><strong>Chemin absolu</strong> &mdash; Lorsqu\u2019un fichier est s\u00E9lectionn\u00E9, le chemin complet du syst\u00E8me de fichiers est affich\u00E9 sous le fil d\u2019Ariane.</li>
</ul>`
      },
      {
        id: 'create-rename-delete',
        title: 'Cr\u00E9er, renommer et supprimer des fichiers',
        content: `
<p>
  Les utilisateurs avec le r\u00F4le <strong>Editor</strong> ou sup\u00E9rieur peuvent g\u00E9rer les fichiers directement dans l\u2019Explorateur\u00A0:
</p>
<h4>Cr\u00E9ation de fichiers</h4>
<p>
  Faites un clic droit sur un r\u00E9pertoire dans l\u2019arborescence et s\u00E9lectionnez <strong>Nouveau fichier</strong>
  ou <strong>Nouveau dossier</strong>. Saisissez le nom et appuyez sur Entr\u00E9e. Les nouveaux fichiers
  <code>.robot</code> sont pr\u00E9-remplis avec un mod\u00E8le de base incluant les sections
  <code>*** Settings ***</code> et <code>*** Test Cases ***</code>.
</p>
<h4>Renommage</h4>
<p>
  Faites un clic droit sur un fichier ou dossier et s\u00E9lectionnez <strong>Renommer</strong>.
  Tapez le nouveau nom et appuyez sur Entr\u00E9e pour confirmer, ou \u00C9chap pour annuler.
</p>
<h4>Suppression</h4>
<p>
  Faites un clic droit et s\u00E9lectionnez <strong>Supprimer</strong>. Un dialogue de
  confirmation appara\u00EEtra. La suppression d\u2019un dossier supprime tout son contenu de mani\u00E8re r\u00E9cursive.
</p>`,
        tip: 'Utilisez l\u2019extension .resource pour les fichiers de ressources Robot Framework et .robot pour les suites de tests afin de garder votre projet organis\u00E9.'
      },
      {
        id: 'codemirror-editor',
        title: '\u00C9diteur CodeMirror',
        content: `
<p>
  Lorsqu\u2019un fichier est s\u00E9lectionn\u00E9, il s\u2019ouvre dans l\u2019\u00E9diteur int\u00E9gr\u00E9
  <strong>CodeMirror</strong>. Fonctionnalit\u00E9s\u00A0:
</p>
<ul>
  <li><strong>Coloration syntaxique</strong> pour Robot Framework (<code>.robot</code>), Python (<code>.py</code>), YAML, JSON et fichiers XML.</li>
  <li><strong>Num\u00E9ros de ligne</strong> affich\u00E9s dans la gouti\u00E8re.</li>
  <li><strong>Indentation automatique</strong> et correspondance des parenth\u00E8ses.</li>
  <li><strong>Rechercher et remplacer</strong> via <code>Ctrl+F</code> / <code>Cmd+F</code>.</li>
  <li><strong>Annuler/R\u00E9tablir</strong> avec historique complet pendant la session d\u2019\u00E9dition.</li>
</ul>
<p>
  Les modifications sont enregistr\u00E9es en cliquant sur le bouton <strong>Enregistrer</strong>
  ou en utilisant le raccourci <code>Ctrl+S</code> / <code>Cmd+S</code>. Un indicateur de
  modifications non enregistr\u00E9es appara\u00EEt dans l\u2019onglet de l\u2019\u00E9diteur lorsque des
  modifications ont \u00E9t\u00E9 apport\u00E9es.
</p>`,
        tip: 'Utilisez Ctrl+G (Cmd+G sur Mac) pour aller \u00E0 un num\u00E9ro de ligne sp\u00E9cifique dans l\u2019\u00E9diteur.'
      },
      {
        id: 'explorer-search',
        title: 'Recherche',
        content: `
<p>
  L\u2019Explorateur comprend une fonctionnalit\u00E9 de <strong>recherche</strong> qui vous permet
  de trouver des fichiers et du contenu dans le d\u00E9p\u00F4t s\u00E9lectionn\u00E9\u00A0:
</p>
<ul>
  <li><strong>Recherche par nom de fichier</strong> &mdash; Tapez un nom de fichier ou un motif dans
      la barre de recherche en haut de l\u2019arborescence pour filtrer la vue.</li>
  <li><strong>Recherche de contenu</strong> &mdash; Utilisez le panneau de recherche pour trouver
      des cha\u00EEnes de texte dans le contenu des fichiers. Les r\u00E9sultats affichent les lignes
      correspondantes avec le chemin du fichier et le num\u00E9ro de ligne.</li>
</ul>
<p>
  Cliquer sur un r\u00E9sultat de recherche ouvre le fichier correspondant dans l\u2019\u00E9diteur
  et fait d\u00E9filer jusqu\u2019\u00E0 la ligne correspondante.
</p>`
      },
      {
        id: 'run-from-explorer',
        title: 'Lancer des tests depuis l\u2019Explorateur',
        content: `
<p>
  Les utilisateurs avec le r\u00F4le <strong>Runner</strong> ou sup\u00E9rieur peuvent lancer des
  ex\u00E9cutions de tests directement depuis l\u2019Explorateur. Lorsque vous visualisez un fichier
  <code>.robot</code> ou un r\u00E9pertoire contenant des fichiers de test\u00A0:
</p>
<ol>
  <li>Cliquez sur le bouton <strong>Ex\u00E9cuter</strong> dans la barre d\u2019outils de l\u2019\u00E9diteur ou faites un clic droit sur un fichier/dossier dans l\u2019arborescence.</li>
  <li>Le chemin cible est automatiquement rempli, pointant vers le fichier ou le r\u00E9pertoire s\u00E9lectionn\u00E9.</li>
  <li>Configurez \u00E9ventuellement un <strong>d\u00E9lai d\u2019expiration</strong>.</li>
  <li>Cliquez sur <strong>D\u00E9marrer l\u2019ex\u00E9cution</strong> pour lancer l\u2019ex\u00E9cution.</li>
</ol>
<p>
  Le statut de l\u2019ex\u00E9cution appara\u00EEt en temps r\u00E9el via WebSocket. Vous pouvez basculer
  vers la page <strong>Ex\u00E9cution</strong> pour suivre la progression ou continuer \u00E0 \u00E9diter
  pendant que les tests s\u2019ex\u00E9cutent en arri\u00E8re-plan.
</p>`,
        tip: 'Ex\u00E9cuter un seul fichier .robot est utile pour une validation rapide, tandis qu\u2019ex\u00E9cuter un r\u00E9pertoire lance la suite compl\u00E8te.'
      }
    ]
  },

  // ─── 5. Ex\u00E9cution ─────────────────────────────────────────────────
  {
    id: 'execution',
    title: 'Ex\u00E9cution',
    icon: '\u25B6\uFE0F',
    subsections: [
      {
        id: 'start-run',
        title: 'D\u00E9marrer une nouvelle ex\u00E9cution',
        content: `
<p>
  Pour d\u00E9marrer une nouvelle ex\u00E9cution de tests depuis la page <strong>Ex\u00E9cution</strong>\u00A0:
</p>
<ol>
  <li>Cliquez sur le bouton <strong>Nouvelle ex\u00E9cution</strong> en haut de la page.</li>
  <li>S\u00E9lectionnez un <strong>D\u00E9p\u00F4t</strong> dans la liste d\u00E9roulante.</li>
  <li>Sp\u00E9cifiez \u00E9ventuellement un <strong>Chemin cible</strong> &mdash; un chemin relatif dans le d\u00E9p\u00F4t pour restreindre l\u2019ex\u00E9cution \u00E0 un fichier ou r\u00E9pertoire sp\u00E9cifique. Laissez vide pour ex\u00E9cuter tous les tests.</li>
  <li>D\u00E9finissez un <strong>D\u00E9lai d\u2019expiration</strong> en secondes (par d\u00E9faut\u00A0: <code>3600</code> secondes / 1 heure). Les ex\u00E9cutions d\u00E9passant cette dur\u00E9e seront automatiquement termin\u00E9es.</li>
  <li>Cliquez sur <strong>D\u00E9marrer</strong> pour mettre l\u2019ex\u00E9cution en file d\u2019attente.</li>
</ol>
<p>
  L\u2019ex\u00E9cution passe au statut <code>pending</code> et est prise en charge par l\u2019ex\u00E9cuteur
  de t\u00E2ches. RoboScope utilisant un ex\u00E9cuteur mono-worker, les ex\u00E9cutions sont trait\u00E9es
  une par une dans l\u2019ordre FIFO (premier arriv\u00E9, premier servi).
</p>`,
        tip: 'Si vous devez ex\u00E9cuter des tests de plusieurs d\u00E9p\u00F4ts, mettez-les en file d\u2019attente s\u00E9quentiellement. Ils s\u2019ex\u00E9cuteront dans l\u2019ordre.'
      },
      {
        id: 'run-status-table',
        title: 'Tableau des statuts d\u2019ex\u00E9cution',
        content: `
<p>
  La vue principale d\u2019ex\u00E9cution affiche un tableau de toutes les ex\u00E9cutions de tests,
  tri\u00E9es par date de cr\u00E9ation (les plus r\u00E9centes en premier). Chaque ligne affiche\u00A0:
</p>
<table>
  <thead>
    <tr><th>Colonne</th><th>Description</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>ID</strong></td><td>Identifiant unique de l\u2019ex\u00E9cution.</td></tr>
    <tr><td><strong>D\u00E9p\u00F4t</strong></td><td>Le d\u00E9p\u00F4t auquel l\u2019ex\u00E9cution appartient.</td></tr>
    <tr><td><strong>Cible</strong></td><td>Le fichier ou r\u00E9pertoire cibl\u00E9 (ou \u00AB\u00A0tout\u00A0\u00BB si le d\u00E9p\u00F4t entier).</td></tr>
    <tr><td><strong>Statut</strong></td><td>Badge color\u00E9\u00A0: <code>pending</code>, <code>running</code>, <code>passed</code>, <code>failed</code>, <code>error</code>, <code>cancelled</code>, <code>timeout</code>.</td></tr>
    <tr><td><strong>Dur\u00E9e</strong></td><td>Temps \u00E9coul\u00E9 du d\u00E9but \u00E0 la fin.</td></tr>
    <tr><td><strong>D\u00E9clench\u00E9 par</strong></td><td>L\u2019utilisateur ayant lanc\u00E9 l\u2019ex\u00E9cution.</td></tr>
    <tr><td><strong>Cr\u00E9\u00E9</strong></td><td>Horodatage de mise en file d\u2019attente de l\u2019ex\u00E9cution.</td></tr>
  </tbody>
</table>
<p>
  Les badges de statut se mettent \u00E0 jour <strong>en temps r\u00E9el</strong> via WebSocket,
  vous n\u2019avez donc jamais besoin de rafra\u00EEchir la page manuellement.
</p>`
      },
      {
        id: 'run-details',
        title: 'D\u00E9tails et sortie de l\u2019ex\u00E9cution',
        content: `
<p>
  Cliquez sur une ligne d\u2019ex\u00E9cution pour ouvrir la vue <strong>D\u00E9tails de l\u2019ex\u00E9cution</strong>, qui fournit\u00A0:
</p>
<ul>
  <li><strong>M\u00E9tadonn\u00E9es de l\u2019ex\u00E9cution</strong> &mdash; D\u00E9p\u00F4t, chemin cible, d\u00E9clencheur, horodatages, d\u00E9lai d\u2019expiration et statut final.</li>
  <li><strong>Sortie standard (stdout)</strong> &mdash; La sortie console de Robot Framework, diffus\u00E9e en direct pendant l\u2019ex\u00E9cution.</li>
  <li><strong>Sortie d\u2019erreur (stderr)</strong> &mdash; Toute sortie d\u2019erreur du processus Python, utile pour diagnostiquer les plantages ou les erreurs d\u2019import.</li>
</ul>
<p>
  Le panneau de sortie d\u00E9file automatiquement vers le bas pendant les ex\u00E9cutions actives.
  Vous pouvez d\u00E9sactiver le d\u00E9filement automatique pour inspecter la sortie ant\u00E9rieure.
  La sortie est affich\u00E9e en police \u00E0 chasse fixe avec les couleurs ANSI supprim\u00E9es
  pour une meilleure lisibilit\u00E9.
</p>`
      },
      {
        id: 'cancel-retry',
        title: 'Annuler et r\u00E9essayer',
        content: `
<p>
  La page Ex\u00E9cution propose plusieurs actions de contr\u00F4le\u00A0:
</p>
<h4>Annuler une ex\u00E9cution</h4>
<p>
  Cliquez sur le bouton <strong>Annuler</strong> d\u2019une ex\u00E9cution <code>running</code> ou
  <code>pending</code> pour la terminer. Le processus sous-jacent re\u00E7oit un signal de
  terminaison et le statut de l\u2019ex\u00E9cution passe \u00E0 <code>cancelled</code>. N\u00E9cessite le
  r\u00F4le <strong>Runner</strong> ou sup\u00E9rieur.
</p>
<h4>R\u00E9essayer une ex\u00E9cution</h4>
<p>
  Pour les ex\u00E9cutions dans un \u00E9tat terminal (<code>failed</code>, <code>error</code>,
  <code>cancelled</code>, <code>timeout</code>), un bouton <strong>R\u00E9essayer</strong> appara\u00EEt.
  Cliquer dessus cr\u00E9e une nouvelle ex\u00E9cution avec la m\u00EAme configuration (d\u00E9p\u00F4t, cible,
  d\u00E9lai) et la met en file d\u2019attente.
</p>
<h4>Annuler toutes les ex\u00E9cutions</h4>
<p>
  Le bouton <strong>Tout annuler</strong> en haut de la page Ex\u00E9cution termine toutes les
  ex\u00E9cutions <code>running</code> et <code>pending</code> en une seule action. Ceci est utile
  lorsque vous devez lib\u00E9rer l\u2019ex\u00E9cuteur imm\u00E9diatement. N\u00E9cessite le r\u00F4le
  <strong>Runner</strong> ou sup\u00E9rieur.
</p>`,
        tip: 'Utilisez \u00AB\u00A0Tout annuler\u00A0\u00BB avec pr\u00E9caution dans les environnements multi-utilisateurs, car cela affecte les ex\u00E9cutions lanc\u00E9es par tous les utilisateurs.'
      }
    ]
  },

  // ─── 6. Rapports ───────────────────────────────────────────────────
  {
    id: 'reports',
    title: 'Rapports',
    icon: '\u{1F4CB}',
    subsections: [
      {
        id: 'report-list',
        title: 'Liste des rapports',
        content: `
<p>
  La page <strong>Rapports</strong> affiche tous les rapports de tests g\u00E9n\u00E9r\u00E9s. Apr\u00E8s
  chaque ex\u00E9cution termin\u00E9e, Robot Framework produit un fichier <code>output.xml</code>
  que RoboScope analyse et stocke pour une analyse ult\u00E9rieure.
</p>
<p>Chaque ligne de rapport affiche\u00A0:</p>
<ul>
  <li><strong>ID du rapport</strong> &mdash; Identifiant unique li\u00E9 \u00E0 l\u2019ex\u00E9cution d\u2019origine.</li>
  <li><strong>D\u00E9p\u00F4t</strong> &mdash; Nom du d\u00E9p\u00F4t source.</li>
  <li><strong>R\u00E9ussis / \u00C9chou\u00E9s</strong> &mdash; Nombre de cas de test r\u00E9ussis et \u00E9chou\u00E9s, affich\u00E9s sous forme de badges color\u00E9s.</li>
  <li><strong>Total des tests</strong> &mdash; Nombre total de cas de test.</li>
  <li><strong>Dur\u00E9e</strong> &mdash; Dur\u00E9e totale de l\u2019ex\u00E9cution.</li>
  <li><strong>Cr\u00E9\u00E9</strong> &mdash; Horodatage de la g\u00E9n\u00E9ration du rapport.</li>
</ul>
<p>
  Cliquez sur une ligne pour ouvrir la vue d\u00E9taill\u00E9e du <strong>Rapport</strong>.
</p>`
      },
      {
        id: 'report-detail',
        title: 'Vue d\u00E9taill\u00E9e du rapport',
        content: `
<p>
  La page de d\u00E9tail du rapport propose trois onglets pour analyser les r\u00E9sultats de tests\u00A0:
</p>
<h4>Onglet R\u00E9sum\u00E9</h4>
<p>
  Affiche les cartes KPI (total des tests, r\u00E9ussis, \u00E9chou\u00E9s, dur\u00E9e), un tableau des tests
  \u00E9chou\u00E9s avec les messages d\u2019erreur, et un tableau de tous les r\u00E9sultats de tests avec
  le statut, la suite, la dur\u00E9e et les tags. Cliquer sur le nom d\u2019un test ouvre la vue
  <strong>Historique du test</strong> pour ce test.
</p>
<h4>Onglet Rapport d\u00E9taill\u00E9</h4>
<p>
  Une vue arborescente riche et interactive de l\u2019ex\u00E9cution compl\u00E8te des tests &mdash; similaire
  au <code>log.html</code> de Robot Framework mais int\u00E9gr\u00E9e directement dans RoboScope.
  Elle analyse le fichier <code>output.xml</code> et affiche les suites, tests et mots-cl\u00E9s
  sous forme d\u2019arborescence extensible.
</p>
<p>Fonctionnalit\u00E9s de l\u2019onglet Rapport d\u00E9taill\u00E9\u00A0:</p>
<ul>
  <li><strong>Barre d\u2019outils</strong> &mdash; Boutons <em>Tout d\u00E9plier</em> / <em>Tout replier</em>
      pour ouvrir ou fermer rapidement tous les n\u0153uds de l\u2019arborescence, et un menu d\u00E9roulant
      <em>Filtre de statut</em> pour afficher Tous, R\u00E9ussis uniquement ou \u00C9chou\u00E9s uniquement.</li>
  <li><strong>Statistiques de suite</strong> &mdash; Chaque en-t\u00EAte de suite affiche les compteurs
      de r\u00E9ussite/\u00E9chec (par ex. &#10003; 5 &#10007; 2) \u00E0 c\u00F4t\u00E9 de la dur\u00E9e.</li>
  <li><strong>Horodatages des mots-cl\u00E9s</strong> &mdash; Les mots-cl\u00E9s affichent leur heure de
      d\u00E9but au format <code>HH:MM:SS.sss</code> pour une analyse temporelle pr\u00E9cise.</li>
  <li><strong>Journal des messages</strong> &mdash; Les messages de chaque mot-cl\u00E9 sont affich\u00E9s
      avec horodatage, niveau de log (INFO, WARN, FAIL, DEBUG) et texte du message. Les messages
      sont color\u00E9s selon le niveau.</li>
  <li><strong>Captures d\u2019\u00E9cran int\u00E9gr\u00E9es</strong> &mdash; Les captures d\u2019\u00E9cran Robot Framework
      int\u00E9gr\u00E9es dans les messages (par ex. de SeleniumLibrary) sont affich\u00E9es en ligne avec un
      rendu d\u2019image correct. Les sources d\u2019images sont automatiquement r\u00E9solues vers le point
      d\u2019acc\u00E8s des ressources du rapport.</li>
  <li><strong>Tags et arguments</strong> &mdash; Les tags de test sont affich\u00E9s sous forme de puces
      color\u00E9es, et les arguments des mots-cl\u00E9s sont affich\u00E9s lorsqu\u2019un n\u0153ud de mot-cl\u00E9 est d\u00E9pli\u00E9.</li>
  <li><strong>Mise en \u00E9vidence des erreurs</strong> &mdash; Les tests \u00E9chou\u00E9s affichent leur message
      d\u2019erreur dans un encadr\u00E9 rouge pour une identification rapide.</li>
</ul>
<h4>Onglet Rapport HTML</h4>
<p>
  Int\u00E8gre le rapport HTML original de Robot Framework (<code>report.html</code>) dans une iframe
  avec une barre d\u2019outils pour la navigation (retour au R\u00E9sum\u00E9) et le rechargement. C\u2019est le
  m\u00EAme rapport que vous obtiendriez en ex\u00E9cutant <code>robot</code> en ligne de commande,
  complet avec des graphiques interactifs, des d\u00E9tails de mots-cl\u00E9s et des liens vers les journaux.
</p>`,
        tip: 'Utilisez l\u2019onglet Rapport d\u00E9taill\u00E9 pour un d\u00E9bogage approfondi avec le chronom\u00E9trage au niveau des mots-cl\u00E9s et les captures d\u2019\u00E9cran. Le filtre de statut aide \u00E0 se concentrer rapidement sur les \u00E9checs.'
      },
      {
        id: 'report-download',
        title: 'T\u00E9l\u00E9chargement ZIP',
        content: `
<p>
  Chaque rapport peut \u00EAtre t\u00E9l\u00E9charg\u00E9 sous forme d\u2019<strong>archive ZIP</strong> contenant
  tous les fichiers de sortie g\u00E9n\u00E9r\u00E9s par Robot Framework\u00A0:
</p>
<ul>
  <li><code>output.xml</code> &mdash; Sortie XML lisible par machine.</li>
  <li><code>report.html</code> &mdash; Rapport HTML interactif.</li>
  <li><code>log.html</code> &mdash; Journal d\u2019ex\u00E9cution d\u00E9taill\u00E9.</li>
  <li>Tout artefact suppl\u00E9mentaire (captures d\u2019\u00E9cran, etc.) captur\u00E9 pendant l\u2019ex\u00E9cution.</li>
</ul>
<p>
  Cliquez sur le bouton <strong>T\u00E9l\u00E9charger ZIP</strong> sur la page de d\u00E9tail du rapport.
  L\u2019archive est g\u00E9n\u00E9r\u00E9e c\u00F4t\u00E9 serveur et envoy\u00E9e en streaming \u00E0 votre navigateur.
</p>`
      },
      {
        id: 'report-bulk-delete',
        title: 'Suppression en masse des rapports',
        content: `
<p>
  Au fil du temps, les rapports accumul\u00E9s peuvent occuper un espace disque important.
  La page Rapports propose deux m\u00E9canismes de suppression\u00A0:
</p>
<ul>
  <li><strong>Suppression individuelle</strong> &mdash; Cliquez sur l\u2019ic\u00F4ne de suppression d\u2019une
      ligne de rapport pour supprimer un seul rapport (r\u00F4le <strong>Editor+</strong> requis).</li>
  <li><strong>Supprimer tous les rapports</strong> &mdash; Cliquez sur le bouton <strong>Tout supprimer</strong>
      pour effacer tous les rapports du syst\u00E8me. Un dialogue de confirmation vous \u00E9vite de
      supprimer accidentellement des donn\u00E9es. Cette action n\u00E9cessite le r\u00F4le <strong>Admin</strong>.</li>
</ul>
<p>
  <strong>Remarque\u00A0:</strong> La suppression de rapports est d\u00E9finitive. Les fichiers
  de rapport associ\u00E9s sont supprim\u00E9s du r\u00E9pertoire <code>REPORTS_DIR</code> sur le serveur.
</p>`,
        tip: 'Pensez \u00E0 t\u00E9l\u00E9charger les rapports importants en ZIP avant d\u2019effectuer une suppression en masse.'
      },
      {
        id: 'ai-failure-analysis',
        title: 'Analyse IA des erreurs',
        content: `
<p>
  Lorsqu\u2019un rapport contient des tests \u00E9chou\u00E9s, l\u2019onglet R\u00E9sum\u00E9 affiche une
  carte <strong>Analyse IA des erreurs</strong> en bas de page. Cette fonctionnalit\u00E9
  utilise un fournisseur LLM configur\u00E9 pour analyser automatiquement les \u00E9checs
  de tests et sugg\u00E9rer des causes et des correctifs.
</p>
<h4>Pr\u00E9requis</h4>
<ul>
  <li>Au moins un <strong>fournisseur IA</strong> doit \u00EAtre configur\u00E9 dans
      <strong>Param\u00E8tres &gt; Fournisseurs IA</strong> (r\u00F4le Admin requis).</li>
  <li>Le rapport doit contenir au moins un test \u00E9chou\u00E9.</li>
</ul>
<h4>Utilisation</h4>
<ol>
  <li>Acc\u00E9dez \u00E0 un rapport contenant des tests \u00E9chou\u00E9s (Rapports &gt; cliquez sur un rapport).</li>
  <li>Faites d\u00E9filer vers le bas jusqu\u2019\u00E0 la carte <strong>Analyse IA des erreurs</strong>
      dans l\u2019onglet R\u00E9sum\u00E9.</li>
  <li>Cliquez sur <strong>Analyser les erreurs</strong>. L\u2019analyse prend g\u00E9n\u00E9ralement
      10 \u00E0 30 secondes selon le nombre d\u2019\u00E9checs et la vitesse du fournisseur LLM.</li>
  <li>Une fois termin\u00E9e, l\u2019analyse est affich\u00E9e en markdown format\u00E9 incluant\u00A0:
      <ul>
        <li><strong>Analyse des causes</strong> &mdash; diagnostic par \u00E9chec</li>
        <li><strong>D\u00E9tection de motifs</strong> &mdash; th\u00E8mes communs entre les \u00E9checs</li>
        <li><strong>Correctifs sugg\u00E9r\u00E9s</strong> &mdash; modifications de code ou de configuration</li>
        <li><strong>Classement par priorit\u00E9</strong> &mdash; CRITICAL / HIGH / MEDIUM / LOW</li>
      </ul>
  </li>
</ol>
<h4>\u00C9tats</h4>
<ul>
  <li><strong>Aucun fournisseur</strong> &mdash; Si aucun fournisseur IA n\u2019est configur\u00E9,
      un message vous dirige vers la page Param\u00E8tres.</li>
  <li><strong>Chargement</strong> &mdash; Un indicateur de progression est affich\u00E9 pendant le traitement.</li>
  <li><strong>Erreur</strong> &mdash; Si l\u2019analyse \u00E9choue (ex. : limite de d\u00E9bit API), le message
      d\u2019erreur est affich\u00E9 avec un bouton R\u00E9essayer.</li>
  <li><strong>Termin\u00E9e</strong> &mdash; Le r\u00E9sultat est affich\u00E9 avec un compteur de tokens
      et un bouton pour relancer l\u2019analyse.</li>
</ul>
<p>
  L\u2019analyse s\u2019ex\u00E9cute en t\u00E2che de fond et ne bloque pas les autres op\u00E9rations.
  Chaque analyse est un appel LLM ind\u00E9pendant &mdash; une r\u00E9analyse peut produire
  des r\u00E9sultats diff\u00E9rents.
</p>`,
        tip: 'L\u2019analyse IA fonctionne mieux avec des messages d\u2019erreur descriptifs. Si vos tests utilisent des messages d\u2019\u00E9chec personnalis\u00E9s, le LLM peut fournir des suggestions plus sp\u00E9cifiques.'
      }
    ]
  },

  // ─── 7. Statistiques ─────────────────────────────────────────────
  {
    id: 'statistics',
    title: 'Statistiques',
    icon: '\u{1F4C8}',
    subsections: [
      {
        id: 'stats-overview',
        title: 'Aper\u00E7u des statistiques',
        content: `
<p>
  La page <strong>Statistiques</strong> offre des informations bas\u00E9es sur les donn\u00E9es
  concernant votre activit\u00E9 de test au fil du temps. Elle combine des cartes KPI,
  des graphiques de tendances et la d\u00E9tection de tests instables pour vous aider
  \u00E0 comprendre les tendances de qualit\u00E9 et \u00E0 identifier les zones probl\u00E9matiques.
</p>
<p>
  Toutes les donn\u00E9es sont accessibles \u00E0 tout utilisateur authentifi\u00E9 (Viewer et sup\u00E9rieur).
  La page r\u00E9cup\u00E8re automatiquement les donn\u00E9es fra\u00EEches lorsque les filtres sont modifi\u00E9s.
</p>`
      },
      {
        id: 'stats-filters',
        title: 'Filtres de p\u00E9riode et de d\u00E9p\u00F4t',
        content: `
<p>
  Deux contr\u00F4les de filtrage apparaissent en haut de la page Statistiques\u00A0:
</p>
<h4>P\u00E9riode</h4>
<p>
  S\u00E9lectionnez une fen\u00EAtre temporelle pr\u00E9d\u00E9finie pour toutes les statistiques\u00A0:
</p>
<ul>
  <li><strong>7 jours</strong> &mdash; Activit\u00E9 de la derni\u00E8re semaine.</li>
  <li><strong>14 jours</strong> &mdash; Deux derni\u00E8res semaines.</li>
  <li><strong>30 jours</strong> &mdash; Dernier mois (par d\u00E9faut).</li>
  <li><strong>90 jours</strong> &mdash; Dernier trimestre.</li>
  <li><strong>1 an</strong> &mdash; 365 derniers jours.</li>
</ul>
<h4>Filtre de d\u00E9p\u00F4t</h4>
<p>
  S\u00E9lectionnez \u00E9ventuellement un d\u00E9p\u00F4t sp\u00E9cifique pour affiner les statistiques.
  Lorsque le filtre est sur <strong>Tous les d\u00E9p\u00F4ts</strong>, les donn\u00E9es agr\u00E9g\u00E9es
  de tous les d\u00E9p\u00F4ts sont affich\u00E9es.
</p>
<p>
  La modification de l\u2019un ou l\u2019autre filtre rafra\u00EEchit imm\u00E9diatement toutes les cartes KPI,
  graphiques et tableaux de la page.
</p>`
      },
      {
        id: 'stats-kpi',
        title: 'Cartes KPI et graphique du taux de r\u00E9ussite',
        content: `
<p>
  Les cartes KPI des Statistiques offrent une vue plus d\u00E9taill\u00E9e que le Tableau de bord\u00A0:
</p>
<ul>
  <li><strong>Total des ex\u00E9cutions</strong> &mdash; Nombre d\u2019ex\u00E9cutions termin\u00E9es dans la p\u00E9riode s\u00E9lectionn\u00E9e.</li>
  <li><strong>Taux de r\u00E9ussite</strong> &mdash; Pourcentage d\u2019ex\u00E9cutions enti\u00E8rement r\u00E9ussies.</li>
  <li><strong>Dur\u00E9e moyenne</strong> &mdash; Temps moyen d\u2019ex\u00E9cution.</li>
  <li><strong>Tests instables</strong> &mdash; Nombre de tests alternant entre r\u00E9ussite et \u00E9chec.</li>
</ul>
<h4>Taux de r\u00E9ussite dans le temps</h4>
<p>
  Un graphique en ligne montre le taux de r\u00E9ussite quotidien pour la p\u00E9riode s\u00E9lectionn\u00E9e.
  L\u2019axe X repr\u00E9sente les dates et l\u2019axe Y le pourcentage (0&ndash;100\u00A0%). Ce graphique
  permet de rep\u00E9rer facilement les r\u00E9gressions ou les am\u00E9liorations au fil du temps.
  Le graphique est aliment\u00E9 par <strong>Chart.js</strong> et prend en charge les infobulles
  au survol pour les valeurs exactes.
</p>`,
        tip: 'Une tendance \u00E0 la baisse du taux de r\u00E9ussite indique souvent des modifications de code introduisant des \u00E9checs. Examinez les dates sp\u00E9cifiques des baisses.'
      },
      {
        id: 'pass-fail-trend',
        title: 'Tendance r\u00E9ussite/\u00E9chec',
        content: `
<p>
  Un <strong>graphique en barres empil\u00E9es</strong> visualise le nombre de cas de test
  r\u00E9ussis vs. \u00E9chou\u00E9s par jour (ou par semaine pour les p\u00E9riodes plus longues).
  Cela compl\u00E8te le graphique du taux de r\u00E9ussite en montrant les volumes absolus\u00A0:
</p>
<ul>
  <li><strong>Barres vertes</strong> repr\u00E9sentent les cas de test r\u00E9ussis.</li>
  <li><strong>Barres rouges</strong> repr\u00E9sentent les cas de test \u00E9chou\u00E9s.</li>
</ul>
<p>
  Un volume \u00E9lev\u00E9 de vert avec des pics rouges occasionnels indique une suite de tests
  g\u00E9n\u00E9ralement saine avec des probl\u00E8mes ponctuels. Des barres rouges constantes sugg\u00E8rent
  des probl\u00E8mes syst\u00E9miques n\u00E9cessitant une attention particuli\u00E8re.
</p>`
      },
      {
        id: 'flaky-detection',
        title: 'D\u00E9tection des tests instables',
        content: `
<p>
  Un <strong>test instable</strong> (flaky) est un test qui alterne entre r\u00E9ussite et \u00E9chec
  sans aucun changement de code. RoboScope d\u00E9tecte les tests instables en analysant
  l\u2019historique de r\u00E9ussite/\u00E9chec des cas de test individuels sur la p\u00E9riode s\u00E9lectionn\u00E9e.
</p>
<p>
  Le tableau des tests instables affiche\u00A0:
</p>
<table>
  <thead>
    <tr><th>Colonne</th><th>Description</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>Nom du test</strong></td><td>Nom complet qualifi\u00E9 du cas de test instable.</td></tr>
    <tr><td><strong>Nombre de basculements</strong></td><td>Nombre de fois o\u00F9 le r\u00E9sultat a chang\u00E9 (r\u00E9ussite&rarr;\u00E9chec ou \u00E9chec&rarr;r\u00E9ussite).</td></tr>
    <tr><td><strong>Taux de r\u00E9ussite</strong></td><td>Pourcentage d\u2019ex\u00E9cutions o\u00F9 le test a r\u00E9ussi.</td></tr>
    <tr><td><strong>Dernier r\u00E9sultat</strong></td><td>R\u00E9sultat le plus r\u00E9cent (badge r\u00E9ussi ou \u00E9chou\u00E9).</td></tr>
  </tbody>
</table>
<p>
  Les tests sont class\u00E9s par nombre de basculements d\u00E9croissant. Un nombre \u00E9lev\u00E9 de
  basculements indique des tests peu fiables qui doivent \u00EAtre examin\u00E9s pour des
  probl\u00E8mes de timing, de d\u00E9pendances d\u2019environnement ou de comportement non d\u00E9terministe.
</p>`,
        tip: 'Les tests instables \u00E9rodent la confiance dans votre suite de tests. Donnez la priorit\u00E9 \u00E0 la correction des tests ayant le plus grand nombre de basculements.'
      },
      {
        id: 'stats-refresh',
        title: 'Rafra\u00EEchissement et obsolescence des donn\u00E9es',
        content: `
<p>
  Les donn\u00E9es statistiques peuvent devenir obsol\u00E8tes \u00E0 mesure que de nouvelles ex\u00E9cutions
  se terminent. Une banni\u00E8re d\u2019obsolescence appara\u00EEt en haut de la page Statistiques
  lorsque les donn\u00E9es n\u2019ont pas \u00E9t\u00E9 rafra\u00EEchies r\u00E9cemment.
</p>
<h4>Rafra\u00EEchissement manuel</h4>
<p>
  Cliquez sur le bouton <strong>Rafra\u00EEchir</strong> pour recharger toutes les cartes KPI,
  graphiques et tableaux avec les derni\u00E8res donn\u00E9es. Cela r\u00E9-agr\u00E8ge les statistiques
  depuis la base de donn\u00E9es pour les filtres actuellement s\u00E9lectionn\u00E9s.
</p>
<h4>Onglets Vue d\u2019ensemble et Analyse approfondie</h4>
<p>
  La page Statistiques est divis\u00E9e en deux onglets\u00A0:
</p>
<ul>
  <li><strong>Vue d\u2019ensemble</strong> &mdash; Cartes KPI, graphique du taux de r\u00E9ussite, tendance r\u00E9ussite/\u00E9chec et d\u00E9tection des tests instables.</li>
  <li><strong>Analyse approfondie</strong> &mdash; Analyse \u00E0 la demande des analyses de mots-cl\u00E9s, m\u00E9triques de qualit\u00E9 des tests, indicateurs de maintenance et analyse du code source. S\u00E9lectionnez des KPIs sp\u00E9cifiques et lancez une analyse pour explorer des informations plus d\u00E9taill\u00E9es.</li>
</ul>
<h4>Analyse du code source (Nouveau)</h4>
<p>
  Lorsqu\u2019un projet est s\u00E9lectionn\u00E9, deux KPIs suppl\u00E9mentaires deviennent disponibles dans la cat\u00E9gorie <em>Analyse du code source</em>\u00A0:
</p>
<ul>
  <li><strong>Analyse des tests sources</strong> &mdash; Analyse vos fichiers <code>.robot</code> directement\u00A0: nombre de cas de test par fichier, lignes moyennes et \u00E9tapes de mots-cl\u00E9s par test, mots-cl\u00E9s les plus utilis\u00E9s et d\u00E9composition par fichier.</li>
  <li><strong>Imports de biblioth\u00E8ques sources</strong> &mdash; Montre quelles biblioth\u00E8ques Robot Framework sont import\u00E9es dans vos fichiers <code>.robot</code> et <code>.resource</code>, combien de fichiers utilisent chaque biblioth\u00E8que et leur distribution relative.</li>
</ul>
<p>
  Ces KPIs fonctionnent ind\u00E9pendamment des rapports d\u2019ex\u00E9cution &mdash; ils analysent les fichiers sources sur le disque, vous obtenez donc des informations m\u00EAme avant d\u2019ex\u00E9cuter des tests.
</p>
<h4>Correction de la distribution des biblioth\u00E8ques</h4>
<p>
  Le KPI <em>Distribution des biblioth\u00E8ques</em> (dans la cat\u00E9gorie Analyse des mots-cl\u00E9s) r\u00E9sout d\u00E9sormais correctement les noms de biblioth\u00E8ques pour les mots-cl\u00E9s Robot Framework bien connus. Auparavant, de nombreux mots-cl\u00E9s \u00E9taient affich\u00E9s comme \u00AB\u00A0Inconnu\u00A0\u00BB car le <code>output.xml</code> n\u2019incluait pas toujours l\u2019attribut de biblioth\u00E8que. Le syst\u00E8me utilise d\u00E9sormais un mapping int\u00E9gr\u00E9 de plus de 500 mots-cl\u00E9s vers leurs biblioth\u00E8ques (BuiltIn, Collections, SeleniumLibrary, Browser, RequestsLibrary, etc.).
</p>`,
        tip: 'Utilisez l\u2019onglet Analyse approfondie pour \u00E9tudier les dur\u00E9es des mots-cl\u00E9s, la densit\u00E9 des assertions et les mod\u00E8les d\u2019erreurs dans vos suites de tests. S\u00E9lectionnez un projet pour activer les KPIs d\u2019analyse du code source.'
      }
    ]
  },

  // ─── 8. Environnements ──────────────────────────────────────────────
  {
    id: 'environments',
    title: 'Environnements',
    icon: '\u2699\uFE0F',
    subsections: [
      {
        id: 'env-overview',
        title: 'Gestion des environnements',
        content: `
<p>
  La page <strong>Environnements</strong> permet de cr\u00E9er et g\u00E9rer des environnements
  virtuels Python isol\u00E9s pour l\u2019ex\u00E9cution des tests. Chaque environnement peut avoir
  son propre ensemble de paquets install\u00E9s et de variables d\u2019environnement, vous
  permettant d\u2019ex\u00E9cuter des tests avec diff\u00E9rentes configurations sans conflits.
</p>
<p>
  Les environnements sont stock\u00E9s dans le r\u00E9pertoire <code>VENVS_DIR</code>
  (par d\u00E9faut\u00A0: <code>~/.roboscope/venvs</code>). La gestion des environnements
  n\u00E9cessite le r\u00F4le <strong>Editor</strong> ou sup\u00E9rieur.
</p>`
      },
      {
        id: 'create-venv',
        title: 'Cr\u00E9er un environnement virtuel',
        content: `
<p>
  Pour cr\u00E9er un nouvel environnement virtuel Python\u00A0:
</p>
<ol>
  <li>Cliquez sur <strong>Nouvel environnement</strong> sur la page Environnements.</li>
  <li>Saisissez un <strong>Nom</strong> pour l\u2019environnement (par ex. <code>rf7-selenium</code>).</li>
  <li>Fournissez \u00E9ventuellement une <strong>Description</strong> de l\u2019usage pr\u00E9vu.</li>
  <li>Cliquez sur <strong>Cr\u00E9er</strong>.</li>
</ol>
<p>
  RoboScope cr\u00E9e un <code>venv</code> Python en arri\u00E8re-plan en utilisant le Python syst\u00E8me.
  Le processus de cr\u00E9ation prend g\u00E9n\u00E9ralement quelques secondes. Une fois pr\u00EAt, le statut
  de l\u2019environnement passe de <code>creating</code> \u00E0 <code>ready</code>.
</p>
<p>
  Chaque environnement inclut automatiquement <code>pip</code> et <code>setuptools</code>.
  Vous devrez ensuite installer Robot Framework et les biblioth\u00E8ques n\u00E9cessaires.
</p>`,
        tip: 'Nommez les environnements de mani\u00E8re descriptive, par ex. \u00AB\u00A0rf7-browser\u00A0\u00BB ou \u00AB\u00A0rf6-selenium\u00A0\u00BB, pour que les membres de l\u2019\u00E9quipe sachent quelles biblioth\u00E8ques sont incluses.'
      },
      {
        id: 'install-packages',
        title: 'Installer des paquets',
        content: `
<p>
  Apr\u00E8s avoir cr\u00E9\u00E9 un environnement, vous pouvez installer des paquets Python de deux mani\u00E8res\u00A0:
</p>
<h4>Biblioth\u00E8ques Robot Framework populaires</h4>
<p>
  Une liste curatrice de paquets couramment utilis\u00E9s est disponible pour une installation en un clic\u00A0:
</p>
<ul>
  <li><code>robotframework</code> &mdash; Le c\u0153ur de Robot Framework.</li>
  <li><code>robotframework-seleniumlibrary</code> &mdash; Tests navigateur bas\u00E9s sur Selenium.</li>
  <li><code>robotframework-browser</code> &mdash; Tests navigateur bas\u00E9s sur Playwright.</li>
  <li><code>robotframework-requests</code> &mdash; Tests d\u2019API HTTP.</li>
  <li><code>robotframework-databaselibrary</code> &mdash; Tests de base de donn\u00E9es.</li>
  <li><code>robotframework-sshlibrary</code> &mdash; Connexions SSH.</li>
  <li><code>robotframework-excellibrary</code> &mdash; Manipulation de fichiers Excel.</li>
</ul>
<h4>Recherche PyPI</h4>
<p>
  Pour tout autre paquet, utilisez le <strong>champ de recherche</strong> pour trouver des
  paquets sur PyPI. Saisissez un nom de paquet, s\u00E9lectionnez la version souhait\u00E9e et
  cliquez sur <strong>Installer</strong>. L\u2019installation s\u2019ex\u00E9cute en t\u00E2che de fond et
  la liste des paquets se met \u00E0 jour une fois termin\u00E9e.
</p>
<p>
  Les paquets install\u00E9s sont affich\u00E9s dans un tableau avec leur nom, version et un
  bouton <strong>D\u00E9sinstaller</strong>.
</p>`,
        tip: 'Installez toujours robotframework en premier avant d\u2019ajouter les paquets de biblioth\u00E8ques pour \u00E9viter les probl\u00E8mes de d\u00E9pendances.'
      },
      {
        id: 'env-variables',
        title: 'Variables d\u2019environnement',
        content: `
<p>
  Chaque environnement peut d\u00E9finir des <strong>variables d\u2019environnement</strong> qui sont
  inject\u00E9es dans le processus lors de l\u2019ex\u00E9cution des tests. C\u2019est utile pour\u00A0:
</p>
<ul>
  <li>D\u00E9finir <code>BROWSER</code> pour contr\u00F4ler quel navigateur Selenium utilise.</li>
  <li>Fournir <code>BASE_URL</code> pour la configuration de l\u2019application test\u00E9e.</li>
  <li>Stocker <code>API_KEY</code> ou d\u2019autres identifiants sans les coder en dur dans les fichiers de test.</li>
</ul>
<p>
  Pour g\u00E9rer les variables, acc\u00E9dez \u00E0 la page de d\u00E9tail d\u2019un environnement et utilisez
  l\u2019onglet <strong>Variables</strong>. Chaque variable a une <strong>Cl\u00E9</strong> et une
  <strong>Valeur</strong>. Cliquez sur <strong>Ajouter une variable</strong> pour cr\u00E9er une
  nouvelle entr\u00E9e, ou utilisez les ic\u00F4nes d\u2019\u00E9dition/suppression pour modifier les entr\u00E9es existantes.
</p>`,
        tip: '\u00C9vitez de stocker des identifiants hautement sensibles comme variables d\u2019environnement. Envisagez d\u2019utiliser un gestionnaire de secrets pour les d\u00E9ploiements en production.'
      },
      {
        id: 'clone-delete-env',
        title: 'Cloner et supprimer des environnements',
        content: `
<p>
  Pour gagner du temps lors de la cr\u00E9ation d\u2019environnements similaires\u00A0:
</p>
<h4>Cloner</h4>
<p>
  Cliquez sur le bouton <strong>Cloner</strong> d\u2019un environnement existant. Cela cr\u00E9e
  un nouvel environnement avec les m\u00EAmes paquets install\u00E9s et variables d\u2019environnement.
  Vous serez invit\u00E9 \u00E0 fournir un nouveau nom. Le clonage est utile lorsque vous avez
  besoin d\u2019une l\u00E9g\u00E8re variation d\u2019une configuration existante (par ex. tester avec
  une version diff\u00E9rente de Robot Framework).
</p>
<h4>Supprimer</h4>
<p>
  Cliquez sur le bouton <strong>Supprimer</strong> et confirmez le dialogue pour
  supprimer d\u00E9finitivement un environnement. Cela supprime le r\u00E9pertoire de
  l\u2019environnement virtuel et toute la configuration associ\u00E9e. Les ex\u00E9cutions
  configur\u00E9es pour utiliser un environnement supprim\u00E9 devront \u00EAtre mises \u00E0 jour
  pour utiliser un autre environnement.
</p>`
      }
    ]
  },

  // ─── 9. Param\u00E8tres ──────────────────────────────────────────────────
  {
    id: 'settings',
    title: 'Param\u00E8tres',
    icon: '\u{1F527}',
    subsections: [
      {
        id: 'settings-overview',
        title: 'Aper\u00E7u des param\u00E8tres',
        content: `
<p>
  La page <strong>Param\u00E8tres</strong> est accessible uniquement aux utilisateurs ayant le
  r\u00F4le <strong>Admin</strong>. Elle fournit des fonctionnalit\u00E9s de gestion des utilisateurs
  et des options de configuration \u00E0 l\u2019\u00E9chelle de l\u2019application.
</p>
<p>
  Les utilisateurs non-admin ne verront pas l\u2019entr\u00E9e Param\u00E8tres dans la barre lat\u00E9rale.
  Tenter d\u2019acc\u00E9der directement \u00E0 l\u2019URL des param\u00E8tres avec des permissions insuffisantes
  entra\u00EEne une redirection vers le Tableau de bord.
</p>`
      },
      {
        id: 'user-management',
        title: 'Gestion des utilisateurs',
        content: `
<p>
  La section de gestion des utilisateurs affiche un tableau de tous les utilisateurs
  enregistr\u00E9s avec les colonnes suivantes\u00A0:
</p>
<ul>
  <li><strong>E-mail</strong> &mdash; L\u2019adresse e-mail de connexion de l\u2019utilisateur.</li>
  <li><strong>Nom</strong> &mdash; Le nom d\u2019affichage montr\u00E9 dans l\u2019en-t\u00EAte et l\u2019historique des ex\u00E9cutions.</li>
  <li><strong>R\u00F4le</strong> &mdash; L\u2019attribution de r\u00F4le actuelle (Viewer, Runner, Editor, Admin).</li>
  <li><strong>Statut</strong> &mdash; Badge actif ou inactif.</li>
  <li><strong>Cr\u00E9\u00E9</strong> &mdash; Date de cr\u00E9ation du compte.</li>
  <li><strong>Actions</strong> &mdash; Boutons de modification et de suppression.</li>
</ul>
<h4>Cr\u00E9er un utilisateur</h4>
<p>
  Cliquez sur <strong>Ajouter un utilisateur</strong> et remplissez le formulaire\u00A0:
</p>
<ol>
  <li>Saisissez l\u2019<strong>E-mail</strong> (doit \u00EAtre unique).</li>
  <li>Saisissez un <strong>Nom d\u2019affichage</strong>.</li>
  <li>D\u00E9finissez le <strong>Mot de passe</strong> initial (minimum 6 caract\u00E8res).</li>
  <li>Attribuez un <strong>R\u00F4le</strong>.</li>
  <li>Cliquez sur <strong>Cr\u00E9er</strong>.</li>
</ol>
<p>
  Le nouvel utilisateur peut imm\u00E9diatement se connecter avec les identifiants fournis.
</p>`
      },
      {
        id: 'role-assignment',
        title: 'Attribution des r\u00F4les',
        content: `
<p>
  Pour changer le r\u00F4le d\u2019un utilisateur, cliquez sur le bouton <strong>Modifier</strong>
  sur sa ligne. Dans le dialogue de modification, s\u00E9lectionnez le nouveau r\u00F4le dans
  la liste d\u00E9roulante et enregistrez.
</p>
<p>
  Les changements de r\u00F4le prennent effet lors de la prochaine requ\u00EAte API de l\u2019utilisateur.
  Si l\u2019utilisateur est actuellement connect\u00E9, son jeton JWT contient encore l\u2019ancien r\u00F4le
  jusqu\u2019\u00E0 son renouvellement. Pour un effet imm\u00E9diat, l\u2019utilisateur doit se d\u00E9connecter
  puis se reconnecter.
</p>
<h4>Directives d\u2019attribution des r\u00F4les</h4>
<table>
  <thead>
    <tr><th>R\u00F4le</th><th>Id\u00E9al pour</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>Viewer</strong></td><td>Parties prenantes, managers et membres d\u2019\u00E9quipe n\u2019ayant besoin que de consulter les r\u00E9sultats.</td></tr>
    <tr><td><strong>Runner</strong></td><td>Ing\u00E9nieurs QA devant lancer des ex\u00E9cutions sans modifier le code de test.</td></tr>
    <tr><td><strong>Editor</strong></td><td>D\u00E9veloppeurs de tests qui \u00E9crivent et maintiennent les tests Robot Framework.</td></tr>
    <tr><td><strong>Admin</strong></td><td>Administrateurs syst\u00E8me responsables de la gestion des utilisateurs et de la configuration.</td></tr>
  </tbody>
</table>`,
        tip: 'Suivez le principe du moindre privil\u00E8ge\u00A0: attribuez le r\u00F4le minimum n\u00E9cessaire pour les responsabilit\u00E9s de chaque utilisateur.'
      },
      {
        id: 'activate-deactivate',
        title: 'Activer et d\u00E9sactiver des utilisateurs',
        content: `
<p>
  Au lieu de supprimer un utilisateur, vous pouvez <strong>d\u00E9sactiver</strong> son compte\u00A0:
</p>
<ul>
  <li>Cliquez sur le bouton <strong>Modifier</strong> sur la ligne de l\u2019utilisateur.</li>
  <li>Basculez le commutateur <strong>Actif</strong> sur d\u00E9sactiv\u00E9.</li>
  <li>Enregistrez les modifications.</li>
</ul>
<p>
  Les utilisateurs d\u00E9sactiv\u00E9s ne peuvent pas se connecter et leurs jetons JWT existants
  sont rejet\u00E9s. Cependant, leur historique d\u2019ex\u00E9cution et les donn\u00E9es associ\u00E9es sont
  conserv\u00E9s. Pour r\u00E9tablir l\u2019acc\u00E8s, basculez simplement le commutateur Actif \u00E0 nouveau.
</p>
<p>
  La <strong>suppression</strong> d\u2019un utilisateur retire d\u00E9finitivement son compte. Utilisez
  le bouton <strong>Supprimer</strong> et confirmez le dialogue. Cette action est irr\u00E9versible.
</p>`,
        tip: 'Pr\u00E9f\u00E9rez la d\u00E9sactivation \u00E0 la suppression pour les utilisateurs susceptibles de revenir. Cela pr\u00E9serve leurs donn\u00E9es d\u2019activit\u00E9 historique.'
      },
      {
        id: 'password-reset',
        title: 'R\u00E9initialisation du mot de passe',
        content: `
<p>
  Les administrateurs peuvent r\u00E9initialiser le mot de passe de n\u2019importe quel utilisateur
  directement depuis l\u2019onglet Utilisateurs\u00A0:
</p>
<ol>
  <li>Acc\u00E9dez \u00E0 <strong>Param\u00E8tres &gt; Utilisateurs</strong>.</li>
  <li>Cliquez sur le bouton <strong>R\u00E9initialiser le mot de passe</strong> sur la ligne de l\u2019utilisateur.</li>
  <li>Saisissez le nouveau mot de passe (minimum 6 caract\u00E8res) dans le dialogue.</li>
  <li>Cliquez sur <strong>D\u00E9finir le mot de passe</strong>.</li>
</ol>
<p>
  Le changement de mot de passe prend effet imm\u00E9diatement. Les sessions existantes de
  l\u2019utilisateur restent valides, mais il aura besoin du nouveau mot de passe pour
  sa prochaine connexion.
</p>`,
        tip: 'Communiquez le nouveau mot de passe \u00E0 l\u2019utilisateur par un canal s\u00E9curis\u00E9. Envisagez de lui demander de le changer \u00E0 la premi\u00E8re connexion.'
      }
    ]
  },

  // ─── 10. Avanc\u00E9 ─────────────────────────────────────────────────────
  {
    id: 'advanced',
    title: 'Avanc\u00E9',
    icon: '\u{1F4A1}',
    subsections: [
      {
        id: 'websocket-updates',
        title: 'Mises \u00E0 jour en temps r\u00E9el via WebSocket',
        content: `
<p>
  RoboScope utilise des connexions <strong>WebSocket</strong> pour fournir des mises \u00E0 jour
  en temps r\u00E9el sans rechargement de page. Le frontend \u00E9tablit une connexion WebSocket
  lors de la connexion via le composable <code>useWebSocket</code>.
</p>
<h4>Ce qui est mis \u00E0 jour en direct</h4>
<ul>
  <li><strong>Changements de statut d\u2019ex\u00E9cution</strong> &mdash; Lorsqu\u2019une ex\u00E9cution change
      d\u2019\u00E9tat (pending &rarr; running &rarr; passed/failed), le badge de statut se met \u00E0 jour
      instantan\u00E9ment sur la page Ex\u00E9cution, le Tableau de bord et toute vue de d\u00E9tails ouverte.</li>
  <li><strong>Diffusion de la sortie</strong> &mdash; La sortie standard et les erreurs des tests
      en cours sont diffus\u00E9es en quasi temps r\u00E9el vers la vue D\u00E9tails de l\u2019ex\u00E9cution.</li>
  <li><strong>Progression de la synchronisation</strong> &mdash; Les op\u00E9rations de synchronisation
      de d\u00E9p\u00F4t mettent \u00E0 jour leur statut via WebSocket une fois termin\u00E9es.</li>
</ul>
<p>
  Si la connexion WebSocket est perdue (par ex. suite \u00E0 une interruption r\u00E9seau), le client
  tente automatiquement de se reconnecter. Une br\u00E8ve notification appara\u00EEt dans la zone
  d\u2019en-t\u00EAte lorsque la connexion est interrompue.
</p>`,
        tip: 'Si les mises \u00E0 jour en direct semblent bloqu\u00E9es, v\u00E9rifiez la console du navigateur pour les erreurs WebSocket. Un rafra\u00EEchissement de page r\u00E9tablit la connexion.'
      },
      {
        id: 'keyboard-shortcuts',
        title: 'Raccourcis clavier',
        content: `
<p>
  RoboScope prend en charge plusieurs raccourcis clavier pour une navigation et une \u00E9dition plus rapides\u00A0:
</p>
<table>
  <thead>
    <tr><th>Raccourci</th><th>Action</th><th>Contexte</th></tr>
  </thead>
  <tbody>
    <tr><td><code>Ctrl+S</code> / <code>Cmd+S</code></td><td>Enregistrer le fichier</td><td>\u00C9diteur Explorer</td></tr>
    <tr><td><code>Ctrl+F</code> / <code>Cmd+F</code></td><td>Rechercher dans le fichier</td><td>\u00C9diteur Explorer</td></tr>
    <tr><td><code>Ctrl+H</code> / <code>Cmd+H</code></td><td>Rechercher et remplacer</td><td>\u00C9diteur Explorer</td></tr>
    <tr><td><code>Ctrl+G</code> / <code>Cmd+G</code></td><td>Aller \u00E0 la ligne</td><td>\u00C9diteur Explorer</td></tr>
    <tr><td><code>Ctrl+Z</code> / <code>Cmd+Z</code></td><td>Annuler</td><td>\u00C9diteur Explorer</td></tr>
    <tr><td><code>Ctrl+Shift+Z</code> / <code>Cmd+Shift+Z</code></td><td>R\u00E9tablir</td><td>\u00C9diteur Explorer</td></tr>
    <tr><td><code>\u00C9chap</code></td><td>Fermer la fen\u00EAtre modale</td><td>Global</td></tr>
  </tbody>
</table>
<p>
  Tous les raccourcis clavier suivent les conventions de la plateforme\u00A0: <code>Ctrl</code>
  sous Windows/Linux, <code>Cmd</code> sous macOS.
</p>`
      },
      {
        id: 'workflow-tips',
        title: 'Conseils pour des flux de travail efficaces',
        content: `
<p>
  Tirez le meilleur parti de RoboScope avec ces conseils pratiques\u00A0:
</p>
<h4>Organisez vos d\u00E9p\u00F4ts avec soin</h4>
<ul>
  <li>Utilisez un d\u00E9p\u00F4t par projet ou domaine de test (par ex. <code>web-tests</code>, <code>api-tests</code>).</li>
  <li>Activez la synchronisation automatique sur les d\u00E9p\u00F4ts Git utilis\u00E9s dans les flux CI/CD.</li>
  <li>Utilisez des noms de d\u00E9p\u00F4t descriptifs pour que les membres de l\u2019\u00E9quipe puissent rapidement identifier le bon.</li>
</ul>
<h4>Exploitez les environnements</h4>
<ul>
  <li>Cr\u00E9ez des environnements s\u00E9par\u00E9s pour diff\u00E9rents contextes de test (par ex. Selenium vs. Browser Library).</li>
  <li>Clonez les environnements lorsque vous n\u2019avez qu\u2019un ou deux paquets \u00E0 changer.</li>
  <li>Utilisez les variables d\u2019environnement pour externaliser la configuration comme les URLs et les identifiants.</li>
</ul>
<h4>Surveillez les tendances de qualit\u00E9</h4>
<ul>
  <li>Consultez la page Statistiques chaque semaine pour rep\u00E9rer les r\u00E9gressions du taux de r\u00E9ussite rapidement.</li>
  <li>Traitez les tests instables rapidement &mdash; ils sapent la confiance dans la suite de tests.</li>
  <li>Utilisez le filtre de d\u00E9p\u00F4t pour isoler les probl\u00E8mes \u00E0 des suites de tests sp\u00E9cifiques.</li>
</ul>
<h4>Collaboration en \u00E9quipe</h4>
<ul>
  <li>Attribuez les r\u00F4les appropri\u00E9s aux membres de l\u2019\u00E9quipe en suivant le principe du moindre privil\u00E8ge.</li>
  <li>Utilisez le Tableau de bord comme tableau d\u2019\u00E9tat partag\u00E9 de l\u2019\u00E9quipe pour suivre la progression des tests.</li>
  <li>T\u00E9l\u00E9chargez les rapports en archives ZIP lorsque vous devez partager des r\u00E9sultats en dehors de RoboScope.</li>
</ul>`
      },
      {
        id: 'troubleshooting',
        title: 'D\u00E9pannage des probl\u00E8mes courants',
        content: `
<p>
  Si vous rencontrez des probl\u00E8mes, consultez les probl\u00E8mes courants et leurs solutions\u00A0:
</p>
<h4>L\u2019ex\u00E9cution reste en statut \u00AB\u00A0Pending\u00A0\u00BB</h4>
<p>
  L\u2019ex\u00E9cuteur de t\u00E2ches traite une ex\u00E9cution \u00E0 la fois. Si une autre ex\u00E9cution est en
  cours, votre ex\u00E9cution attend dans la file d\u2019attente. V\u00E9rifiez la page Ex\u00E9cution
  pour toute ex\u00E9cution longue ou bloqu\u00E9e et annulez-la si n\u00E9cessaire.
</p>
<h4>Le clonage ou la synchronisation Git \u00E9choue</h4>
<ul>
  <li>V\u00E9rifiez que l\u2019URL du d\u00E9p\u00F4t est correcte et accessible depuis le serveur.</li>
  <li>Pour les d\u00E9p\u00F4ts priv\u00E9s, assurez-vous que les identifiants ou cl\u00E9s SSH sont configur\u00E9s.</li>
  <li>V\u00E9rifiez que la branche sp\u00E9cifi\u00E9e existe sur le serveur distant.</li>
  <li>Consultez les journaux du serveur pour les messages d\u2019erreur d\u00E9taill\u00E9s.</li>
</ul>
<h4>L\u2019ex\u00E9cution \u00E9choue avec le statut \u00AB\u00A0Error\u00A0\u00BB</h4>
<p>
  Un statut <code>error</code> (diff\u00E9rent de <code>failed</code>) signifie que l\u2019ex\u00E9cution
  n\u2019a pas pu \u00EAtre d\u00E9marr\u00E9e ou a plant\u00E9 de mani\u00E8re inattendue. Causes courantes\u00A0:
</p>
<ul>
  <li>Robot Framework n\u2019est pas install\u00E9 dans l\u2019environnement s\u00E9lectionn\u00E9.</li>
  <li>Des biblioth\u00E8ques Python requises sont manquantes.</li>
  <li>Le chemin cible n\u2019existe pas dans le d\u00E9p\u00F4t.</li>
  <li>Probl\u00E8mes de permissions sur le r\u00E9pertoire de travail ou de rapports.</li>
</ul>
<h4>Probl\u00E8mes de connexion WebSocket</h4>
<p>
  Si les mises \u00E0 jour en direct ne fonctionnent pas\u00A0:
</p>
<ul>
  <li>Assurez-vous que votre navigateur prend en charge les WebSockets (tous les navigateurs modernes le font).</li>
  <li>V\u00E9rifiez si un proxy inverse ou un pare-feu bloque les connexions WebSocket.</li>
  <li>Cherchez les erreurs de connexion dans la console d\u00E9veloppeur du navigateur (<code>F12</code>).</li>
  <li>Rafra\u00EEchissez la page pour r\u00E9tablir la connexion.</li>
</ul>
<h4>Rapports non g\u00E9n\u00E9r\u00E9s</h4>
<p>
  Si une ex\u00E9cution se termine mais qu\u2019aucun rapport n\u2019appara\u00EEt\u00A0:
</p>
<ul>
  <li>L\u2019ex\u00E9cution a peut-\u00EAtre \u00E9chou\u00E9 avant que Robot Framework ne produise <code>output.xml</code>.</li>
  <li>V\u00E9rifiez la sortie stderr de l\u2019ex\u00E9cution pour les erreurs Python ou Robot Framework.</li>
  <li>V\u00E9rifiez que le r\u00E9pertoire <code>REPORTS_DIR</code> est accessible en \u00E9criture par l\u2019application.</li>
</ul>`,
        tip: 'Pour les probl\u00E8mes persistants, v\u00E9rifiez les journaux du backend avec \u00AB\u00A0make docker-logs\u00A0\u00BB ou consultez la sortie console uvicorn en mode d\u00E9veloppement.'
      },
      {
        id: 'i18n',
        title: 'Support linguistique',
        content: `
<p>
  RoboScope prend en charge plusieurs langues d\u2019interface\u00A0:
</p>
<table>
  <thead>
    <tr><th>Code</th><th>Langue</th></tr>
  </thead>
  <tbody>
    <tr><td><code>en</code></td><td>English</td></tr>
    <tr><td><code>de</code></td><td>Deutsch (Allemand)</td></tr>
    <tr><td><code>fr</code></td><td>Fran\u00E7ais</td></tr>
    <tr><td><code>es</code></td><td>Espa\u00F1ol (Espagnol)</td></tr>
  </tbody>
</table>
<p>
  Pour changer de langue, utilisez le <strong>s\u00E9lecteur de langue</strong> dans l\u2019en-t\u00EAte
  de l\u2019application. La langue s\u00E9lectionn\u00E9e est enregistr\u00E9e dans le stockage local de
  votre navigateur et persiste entre les sessions. Tous les libell\u00E9s, boutons, messages
  de l\u2019interface ainsi que cette documentation s\u2019adaptent \u00E0 la langue s\u00E9lectionn\u00E9e.
</p>`
      }
    ]
  },

  // ─── 11. Mentions l\u00E9gales ──────────────────────────────────────────
  {
    id: 'legal',
    title: 'Mentions l\u00E9gales',
    icon: 'info',
    subsections: [
      {
        id: 'footer',
        title: 'Pied de page',
        content: `
<p>
  Un pied de page est affich\u00E9 en bas de chaque page, contenant\u00A0:
</p>
<ul>
  <li>L\u2019<strong>avis de copyright</strong> de viadee Unternehmensberatung AG.</li>
  <li>Un lien vers le site <strong>mateo-automation.com</strong>.</li>
  <li>Un lien vers la page de <strong>Mentions l\u00E9gales</strong>.</li>
</ul>`
      },
      {
        id: 'imprint',
        title: 'Mentions l\u00E9gales',
        content: `
<p>
  La page de <strong>Mentions l\u00E9gales</strong> fournit l\u2019avis l\u00E9gal requis par la loi
  allemande (Impressum). Elle contient les coordonn\u00E9es de la soci\u00E9t\u00E9
  <em>viadee Unternehmensberatung AG</em>, incluant l\u2019adresse, les informations de contact,
  le conseil d\u2019administration, l\u2019inscription au registre du commerce et le num\u00E9ro
  d\u2019identification TVA.
</p>
<p>
  Acc\u00E9dez \u00E0 la page Mentions l\u00E9gales via le lien dans le pied de page ou en naviguant
  vers <code>/imprint</code>.
</p>`
      }
    ]
  }
]

export default fr
