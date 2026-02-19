<script setup lang="ts">
import { onMounted, ref, watch, computed, nextTick, onUnmounted, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useExplorerStore } from '@/stores/explorer.store'
import { useReposStore } from '@/stores/repos.store'
import { useEnvironmentsStore } from '@/stores/environments.store'
import { useToast } from '@/composables/useToast'
import { createRun } from '@/api/execution.api'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import type { TreeNode } from '@/types/domain.types'

// CodeMirror imports
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightSpecialChars } from '@codemirror/view'
import { EditorState } from '@codemirror/state'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { python } from '@codemirror/lang-python'
import { LanguageSupport, StreamLanguage } from '@codemirror/language'
import { syntaxHighlighting, defaultHighlightStyle } from '@codemirror/language'
import { tags } from '@lezer/highlight'

const route = useRoute()
const router = useRouter()
const explorer = useExplorerStore()
const repos = useReposStore()
const envs = useEnvironmentsStore()
const toast = useToast()
const { t } = useI18n()

const searchQuery = ref('')
const selectedRepoId = ref<number | null>(null)
const expandedPaths = ref<Set<string>>(new Set())
const editorContent = ref('')
const isDirty = ref(false)
const saving = ref(false)
const editorContainer = ref<HTMLElement | null>(null)
const editorView = shallowRef<EditorView | null>(null)

// Dialogs
const showCreateDialog = ref(false)
const showRenameDialog = ref(false)
const showDeleteConfirm = ref(false)
const newFilePath = ref('')
const renameNewName = ref('')
const contextTarget = ref<TreeNode | null>(null)
const runningFile = ref<string | null>(null)
const runOverlay = ref<{ show: boolean; fileName: string; runId: number | null; error: string | null }>({
  show: false, fileName: '', runId: null, error: null,
})
const showEnvPrompt = ref(false)
const settingUpDefaultEnv = ref(false)
const pendingRunNode = ref<TreeNode | null>(null)

// Breadcrumb
const breadcrumb = computed(() => {
  if (!explorer.selectedFile) return []
  const parts = explorer.selectedFile.path.split('/')
  return parts.map((p, i) => ({
    name: p,
    path: parts.slice(0, i + 1).join('/'),
    isLast: i === parts.length - 1,
  }))
})

const isEditable = computed(() => {
  if (!explorer.selectedFile) return false
  const ext = explorer.selectedFile.extension?.toLowerCase()
  const editableExtensions = ['.robot', '.resource', '.py', '.txt', '.yaml', '.yml', '.json', '.xml', '.csv', '.tsv', '.cfg', '.ini', '.toml', '.md', '.rst', '.html', '.css', '.js', '.ts', '.sh', '.bat', '.ps1', '.env', '.gitignore']
  return ext ? editableExtensions.includes(ext) : true
})

const isRobot = computed(() => explorer.selectedFile?.extension?.toLowerCase() === '.robot')

const isLocalhost = computed(() =>
  ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname)
)

const currentRepo = computed(() =>
  repos.repos.find(r => r.id === selectedRepoId.value)
)

const absolutePath = computed(() => {
  if (!isLocalhost.value || !currentRepo.value || !explorer.selectedFile) return null
  return currentRepo.value.local_path + '/' + explorer.selectedFile.path
})

onMounted(async () => {
  await Promise.all([repos.fetchRepos(), envs.fetchEnvironments()])
  const repoId = Number(route.params.repoId)
  if (repoId && repos.repos.find(r => r.id === repoId)) {
    selectedRepoId.value = repoId
    await explorer.fetchTree(repoId)
    autoExpandRoot()
  } else if (repos.repos.length) {
    selectedRepoId.value = repos.repos[0].id
    await explorer.fetchTree(repos.repos[0].id)
    autoExpandRoot()
  }
})

onUnmounted(() => {
  editorView.value?.destroy()
})

watch(selectedRepoId, async (newId) => {
  if (newId) {
    router.replace(`/explorer/${newId}`)
    explorer.clearSelection()
    isDirty.value = false
    await explorer.fetchTree(newId)
    autoExpandRoot()
  }
})

const STORAGE_KEY_PREFIX = 'explorer-expanded-'

function getStorageKey(): string {
  return STORAGE_KEY_PREFIX + (selectedRepoId.value || 'default')
}

function saveExpandedPaths() {
  try {
    localStorage.setItem(getStorageKey(), JSON.stringify([...expandedPaths.value]))
  } catch { /* ignore quota errors */ }
}

function loadExpandedPaths() {
  try {
    const stored = localStorage.getItem(getStorageKey())
    if (stored) {
      const paths = JSON.parse(stored) as string[]
      expandedPaths.value = new Set(paths)
      return true
    }
  } catch { /* ignore parse errors */ }
  return false
}

function autoExpandRoot() {
  if (loadExpandedPaths()) return
  if (explorer.tree) {
    expandedPaths.value.add(explorer.tree.path)
  }
}

// --- Tree navigation ---

function toggleExpand(node: TreeNode) {
  const key = node.path
  if (expandedPaths.value.has(key)) {
    expandedPaths.value.delete(key)
  } else {
    expandedPaths.value.add(key)
  }
  saveExpandedPaths()
}

function isExpanded(node: TreeNode): boolean {
  return expandedPaths.value.has(node.path)
}

function collectAllDirPaths(node: TreeNode, paths: string[]) {
  if (node.type === 'directory') {
    paths.push(node.path)
    if (node.children) {
      for (const child of node.children) {
        collectAllDirPaths(child, paths)
      }
    }
  }
}

function expandAll() {
  if (!explorer.tree) return
  const paths: string[] = [explorer.tree.path]
  if (explorer.tree.children) {
    for (const child of explorer.tree.children) {
      collectAllDirPaths(child, paths)
    }
  }
  expandedPaths.value = new Set(paths)
  saveExpandedPaths()
}

function collapseAll() {
  expandedPaths.value.clear()
  saveExpandedPaths()
}

async function onNodeClick(node: TreeNode) {
  if (!selectedRepoId.value) return
  if (node.type === 'directory') {
    toggleExpand(node)
  } else {
    if (isDirty.value && !confirm(t('explorer.discardChanges'))) return
    isDirty.value = false
    await explorer.openFile(selectedRepoId.value, node.path)
    editorContent.value = explorer.selectedFile?.content || ''
    await nextTick()
    initEditor()
  }
}

// --- CodeMirror editor ---

// Comprehensive Robot Framework keyword set (based on npp-robot + RF5/RF7)
const RF_BUILTINS = new Set([
  // BuiltIn library
  'call method', 'catenate', 'comment', 'continue for loop', 'continue for loop if',
  'convert to binary', 'convert to boolean', 'convert to bytes', 'convert to hex',
  'convert to integer', 'convert to number', 'convert to octal', 'convert to string',
  'create dictionary', 'create list', 'evaluate', 'exit for loop', 'exit for loop if',
  'fail', 'fatal error', 'get count', 'get length', 'get library instance',
  'get time', 'get variable value', 'get variables', 'import library', 'import resource',
  'import variables', 'keyword should exist', 'length should be', 'log', 'log many',
  'log to console', 'log variables', 'no operation', 'pass execution', 'pass execution if',
  'regexp escape', 'reload library', 'remove tags', 'repeat keyword', 'replace variables',
  'return from keyword', 'return from keyword if', 'run keyword', 'run keyword and continue on failure',
  'run keyword and expect error', 'run keyword and ignore error', 'run keyword and return',
  'run keyword and return if', 'run keyword and return status', 'run keyword if',
  'run keyword if all critical tests passed', 'run keyword if all tests passed',
  'run keyword if any critical tests failed', 'run keyword if any tests failed',
  'run keyword if test failed', 'run keyword if test passed',
  'run keyword if timeout occurred', 'run keyword unless', 'run keywords',
  'set global variable', 'set library search order', 'set log level',
  'set suite documentation', 'set suite metadata', 'set suite variable',
  'set tags', 'set test documentation', 'set test message', 'set test variable',
  'set variable', 'set variable if', 'should be empty', 'should be equal',
  'should be equal as integers', 'should be equal as numbers', 'should be equal as strings',
  'should be true', 'should contain', 'should contain x times', 'should end with',
  'should match', 'should match regexp', 'should not be empty', 'should not be equal',
  'should not be equal as integers', 'should not be equal as numbers',
  'should not be equal as strings', 'should not be true', 'should not contain',
  'should not end with', 'should not match', 'should not match regexp',
  'should not start with', 'should start with', 'sleep',
  'variable should exist', 'variable should not exist', 'wait until keyword succeeds',
  'skip', 'skip if',
  // String library
  'convert to lowercase', 'convert to uppercase', 'decode bytes to string',
  'encode string to bytes', 'fetch from left', 'fetch from right',
  'generate random string', 'get line', 'get line count',
  'get lines containing string', 'get lines matching pattern', 'get lines matching regexp',
  'get regexp matches', 'get substring', 'remove string', 'remove string using regexp',
  'replace string', 'replace string using regexp', 'should be byte string',
  'should be lowercase', 'should be string', 'should be titlecase',
  'should be unicode string', 'should be uppercase', 'should not be string',
  'split string', 'split string from right', 'split string to characters', 'split to lines',
  // Collections library
  'append to list', 'combine lists', 'convert to dictionary', 'convert to list',
  'copy dictionary', 'copy list', 'count values in list', 'dictionaries should be equal',
  'dictionary should contain item', 'dictionary should contain key',
  'dictionary should contain sub dictionary', 'dictionary should contain value',
  'dictionary should not contain key', 'dictionary should not contain value',
  'get dictionary items', 'get dictionary keys', 'get dictionary values',
  'get from dictionary', 'get from list', 'get index from list',
  'get match count', 'get matches', 'get slice from list', 'insert into list',
  'keep in dictionary', 'list should contain sub list', 'list should contain value',
  'list should not contain duplicates', 'list should not contain value',
  'lists should be equal', 'log dictionary', 'log list', 'pop from dictionary',
  'remove duplicates', 'remove from dictionary', 'remove from list',
  'remove values from list', 'reverse list', 'set list value', 'set to dictionary',
  'should contain match', 'should not contain match', 'sort list',
  // DateTime library
  'add time to date', 'add time to time', 'convert date', 'convert time',
  'get current date', 'subtract date from date', 'subtract time from date',
  'subtract time from time',
  // OperatingSystem library
  'append to environment variable', 'append to file', 'copy directory', 'copy file',
  'copy files', 'count directories in directory', 'count files in directory',
  'count items in directory', 'create binary file', 'create directory', 'create file',
  'directory should be empty', 'directory should exist', 'directory should not be empty',
  'directory should not exist', 'empty directory', 'environment variable should be set',
  'environment variable should not be set', 'file should be empty', 'file should exist',
  'file should not be empty', 'file should not exist', 'get binary file',
  'get environment variable', 'get environment variables', 'get file', 'get file size',
  'get modified time', 'grep file', 'join path', 'join paths',
  'list directories in directory', 'list directory', 'list files in directory',
  'log environment variables', 'log file', 'move directory', 'move file', 'move files',
  'normalize path', 'remove directory', 'remove environment variable', 'remove file',
  'remove files', 'run', 'run and return rc', 'run and return rc and output',
  'set environment variable', 'set modified time', 'should exist', 'should not exist',
  'split extension', 'split path', 'touch', 'wait until created', 'wait until removed',
  // Process library
  'get process id', 'get process object', 'get process result', 'is process running',
  'join command line', 'process should be running', 'process should be stopped',
  'run process', 'send signal to process', 'split command line', 'start process',
  'stop all processes', 'stop process', 'switch process', 'terminate all processes',
  'terminate process', 'wait for process',
  // Telnet library
  'close all connections', 'close connection', 'execute command', 'login',
  'open connection', 'read', 'read until', 'read until prompt', 'read until regexp',
  'set default log level', 'set encoding', 'set newline', 'set prompt',
  'set telnetlib log level', 'set timeout', 'switch connection', 'write',
  'write bare', 'write control character', 'write until expected output',
  // XML library
  'add element', 'clear element', 'copy element', 'element attribute should be',
  'element attribute should match', 'element should exist', 'element should not exist',
  'element should not have attribute', 'element text should be', 'element text should match',
  'element to string', 'elements should be equal', 'elements should match',
  'evaluate xpath', 'get child elements', 'get element', 'get element attribute',
  'get element attributes', 'get element count', 'get element text', 'get elements',
  'get elements texts', 'log element', 'parse xml', 'remove element',
  'remove element attribute', 'remove element attributes', 'remove elements',
  'remove elements attribute', 'remove elements attributes', 'save xml',
  'set element attribute', 'set element tag', 'set element text',
  'set elements attribute', 'set elements tag', 'set elements text',
  // Screenshot library
  'set screenshot directory', 'take screenshot', 'take screenshot without embedding',
  // Dialogs library
  'execute manual step', 'get selection from user', 'get value from user', 'pause execution',
])

function robotLanguage() {
  return StreamLanguage.define({
    startState() {
      return { section: '' as string, isKeywordDef: false }
    },
    token(stream, state: { section: string; isKeywordDef: boolean }) {
      // Beginning of line
      if (stream.sol()) {
        state.isKeywordDef = false
        // Section headers: *** Settings ***, *** Test Cases ***, etc.
        if (stream.match(/^\*{3}\s*(Settings?|Variables?|Test Cases?|Tasks?|Keywords?|Comments?)\s*\*{0,3}/i)) {
          const m = stream.current().toLowerCase()
          if (m.includes('setting')) state.section = 'settings'
          else if (m.includes('variable')) state.section = 'variables'
          else if (m.includes('test') || m.includes('task')) state.section = 'testcases'
          else if (m.includes('keyword')) state.section = 'keywords'
          else state.section = 'comments'
          return 'heading'
        }
        // Comment section: everything is a comment
        if (state.section === 'comments') {
          stream.skipToEnd()
          return 'comment'
        }
        // Test case / keyword name definitions (not indented)
        if ((state.section === 'testcases' || state.section === 'keywords') && !stream.match(/^\s/,false)) {
          state.isKeywordDef = true
          stream.skipToEnd()
          return 'definition'
        }
      }

      // Comments
      if (stream.match(/^#.*/)) return 'comment'
      // Separator: two or more spaces
      if (stream.match(/^  +/)) return 'punctuation'
      // Variables ${}, @{}, %{}, &{} with nested support
      if (stream.match(/^[$@%&]\{/)) {
        let depth = 1
        while (depth > 0 && !stream.eol()) {
          const ch = stream.next()
          if (ch === '{') depth++
          else if (ch === '}') depth--
        }
        return 'variableName'
      }
      // Test/keyword setting tags: [Setup], [Tags], [Teardown], [Arguments], [Documentation], [Return], [Template], [Timeout]
      if (stream.match(/^\[(Setup|Tags|Teardown|Documentation|Arguments|Return|Template|Timeout)\]/i)) {
        return 'meta'
      }
      // Settings section keywords
      if (state.section === 'settings' && stream.match(/^(Library|Resource|Variables|Suite Setup|Suite Teardown|Test Setup|Test Teardown|Test Template|Test Timeout|Force Tags|Default Tags|Metadata)\b/i)) {
        return 'meta'
      }
      // Control flow (RF5+)
      if (stream.match(/^\b(FOR|END|IF|ELSE IF|ELSE|TRY|EXCEPT|FINALLY|WHILE|BREAK|CONTINUE|RETURN|IN|IN RANGE|IN ENUMERATE|IN ZIP)\b/)) {
        return 'keyword'
      }
      // BDD prefixes
      if (stream.match(/^\b(Given|When|Then|And|But)\b/i)) {
        return 'keyword'
      }
      // Built-in keywords: match word sequences (single-space separated, stops at double-space separators)
      if (stream.match(/^[A-Za-z]/, false)) {
        const remaining = stream.string.slice(stream.pos)
        const m = remaining.match(/^[A-Za-z][A-Za-z0-9]*(?: [A-Za-z][A-Za-z0-9]*)*/)
        if (m) {
          const cellText = m[0]
          const words = cellText.split(' ')
          // Greedy: try longest keyword match first
          for (let len = words.length; len >= 1; len--) {
            const candidate = words.slice(0, len).join(' ')
            if (RF_BUILTINS.has(candidate.toLowerCase())) {
              stream.pos += candidate.length
              return 'function'
            }
          }
          // Not a keyword — consume the first word
          stream.pos += words[0].length
          return null
        }
        stream.next()
        return null
      }
      // Strings (quoted)
      if (stream.match(/^"(?:[^"\\]|\\.)*"/)) return 'string'
      if (stream.match(/^'(?:[^'\\]|\\.)*'/)) return 'string'
      // Numbers
      if (stream.match(/^-?\d+(\.\d+)?/)) return 'number'
      // Named arguments (arg=value)
      if (stream.match(/^[a-zA-Z_]\w*(?==)/)) return 'attributeName'
      // Skip whitespace
      if (stream.eatSpace()) return null
      stream.next()
      return null
    },
  })
}

function getLanguageExtension() {
  const ext = explorer.selectedFile?.extension?.toLowerCase()
  if (ext === '.py') return python()
  if (ext === '.robot' || ext === '.resource') return new LanguageSupport(robotLanguage())
  return []
}

function initEditor() {
  if (editorView.value) {
    editorView.value.destroy()
    editorView.value = null
  }
  if (!editorContainer.value || !explorer.selectedFile) return
  if (!isEditable.value) return

  const state = EditorState.create({
    doc: explorer.selectedFile.content,
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      highlightSpecialChars(),
      history(),
      keymap.of([...defaultKeymap, ...historyKeymap]),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      getLanguageExtension(),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          editorContent.value = update.state.doc.toString()
          isDirty.value = editorContent.value !== explorer.selectedFile?.content
        }
      }),
      EditorView.theme({
        '&': { height: '100%', fontSize: '13px' },
        '.cm-content': { fontFamily: "'Fira Code', 'Consolas', 'Monaco', monospace", padding: '8px 0' },
        '.cm-gutters': { background: '#f8f9fa', borderRight: '1px solid #e0e0e0', color: '#999' },
        '.cm-activeLine': { background: 'rgba(60, 181, 161, 0.06)' },
        '.cm-activeLineGutter': { background: 'rgba(60, 181, 161, 0.1)' },
      }),
    ],
  })

  editorView.value = new EditorView({
    state,
    parent: editorContainer.value,
  })
}

// --- File actions ---

async function handleSave() {
  if (!selectedRepoId.value || !explorer.selectedFile || !isDirty.value) return
  saving.value = true
  try {
    await explorer.saveFile(selectedRepoId.value, explorer.selectedFile.path, editorContent.value)
    isDirty.value = false
  } finally {
    saving.value = false
  }
}

function openCreateDialog(parentNode?: TreeNode) {
  const prefix = parentNode && parentNode.type === 'directory' ? parentNode.path + '/' : ''
  newFilePath.value = prefix
  showCreateDialog.value = true
}

async function handleCreate() {
  if (!selectedRepoId.value || !newFilePath.value) return
  const path = newFilePath.value
  await explorer.createFile(selectedRepoId.value, path)
  showCreateDialog.value = false
  newFilePath.value = ''
  // Expand parent directories so new file is visible
  const parts = path.split('/')
  for (let i = 1; i < parts.length; i++) {
    expandedPaths.value.add(parts.slice(0, i).join('/'))
  }
  // Open the newly created file
  await explorer.openFile(selectedRepoId.value, path)
  editorContent.value = explorer.selectedFile?.content || ''
  await nextTick()
  initEditor()
}

function openRenameDialog(node: TreeNode) {
  contextTarget.value = node
  renameNewName.value = node.name
  showRenameDialog.value = true
}

async function handleRename() {
  if (!selectedRepoId.value || !contextTarget.value || !renameNewName.value) return
  const oldPath = contextTarget.value.path
  const parts = oldPath.split('/')
  parts[parts.length - 1] = renameNewName.value
  const newPath = parts.join('/')
  await explorer.renameFileAction(selectedRepoId.value, oldPath, newPath)
  showRenameDialog.value = false
  contextTarget.value = null
}

function openDeleteConfirm(node: TreeNode) {
  contextTarget.value = node
  showDeleteConfirm.value = true
}

async function handleDelete() {
  if (!selectedRepoId.value || !contextTarget.value) return
  await explorer.deleteFileAction(selectedRepoId.value, contextTarget.value.path)
  showDeleteConfirm.value = false
  contextTarget.value = null
}

async function handleOpenInEditor(node: TreeNode) {
  if (!selectedRepoId.value) return
  await explorer.openInEditorAction(selectedRepoId.value, node.path)
}

async function handleOpenInFileBrowser(node: TreeNode) {
  if (!selectedRepoId.value) return
  await explorer.openInFileBrowserAction(selectedRepoId.value, node.path)
}

async function handleOpenRootFolder() {
  if (!selectedRepoId.value) return
  await explorer.openInFileBrowserAction(selectedRepoId.value, '.')
}

function handleRunRobot(node: TreeNode) {
  if (!selectedRepoId.value) return
  if (envs.environments.length === 0) {
    pendingRunNode.value = node
    showEnvPrompt.value = true
    return
  }
  doRunRobot(node)
}

async function doRunRobot(node: TreeNode) {
  if (!selectedRepoId.value) return
  runningFile.value = node.path
  runOverlay.value = { show: true, fileName: node.name, runId: null, error: null }
  try {
    const defaultEnv = envs.environments.find(e => e.is_default)
    const runPayload: Record<string, any> = {
      repository_id: selectedRepoId.value,
      target_path: node.path,
    }
    if (defaultEnv) {
      runPayload.environment_id = defaultEnv.id
      runPayload.runner_type = defaultEnv.default_runner_type
    }
    const run = await createRun(runPayload as any)
    runOverlay.value.runId = run.id
  } catch (e: any) {
    runOverlay.value.error = e.response?.data?.detail || e.message
  } finally {
    runningFile.value = null
  }
}

async function setupDefaultFromExplorer() {
  settingUpDefaultEnv.value = true
  try {
    await envs.setupDefault()
    showEnvPrompt.value = false
    toast.success(t('environments.setupDefault.toastSuccess'))
    if (pendingRunNode.value) {
      doRunRobot(pendingRunNode.value)
      pendingRunNode.value = null
    }
  } catch (e: any) {
    if (e.response?.status === 409) {
      toast.error(t('environments.setupDefault.alreadyExists'))
    } else {
      toast.error(t('environments.setupDefault.toastError'))
    }
  } finally {
    settingUpDefaultEnv.value = false
  }
}

function skipEnvAndRun() {
  showEnvPrompt.value = false
  if (pendingRunNode.value) {
    doRunRobot(pendingRunNode.value)
    pendingRunNode.value = null
  }
}

function goToExecution() {
  const runId = runOverlay.value.runId
  runOverlay.value.show = false
  router.push({ path: '/runs', query: runId ? { run: String(runId) } : undefined })
}

async function handleSearch() {
  if (!selectedRepoId.value || !searchQuery.value) return
  await explorer.searchInRepo(selectedRepoId.value, searchQuery.value)
}

async function onSearchResultClick(filePath: string) {
  if (!selectedRepoId.value) return
  explorer.clearSelection()
  await explorer.openFile(selectedRepoId.value, filePath)
  editorContent.value = explorer.selectedFile?.content || ''
  await nextTick()
  initEditor()
}

function getFileIcon(node: TreeNode): string {
  if (node.type === 'directory') return isExpanded(node) ? '\uD83D\uDCC2' : '\uD83D\uDCC1'
  const ext = node.extension?.toLowerCase()
  if (ext === '.robot') return '\uD83E\uDD16'
  if (ext === '.resource') return '\uD83D\uDD27'
  if (ext === '.py') return '\uD83D\uDC0D'
  if (ext === '.yaml' || ext === '.yml') return '\uD83D\uDCDD'
  if (ext === '.json') return '{ }'
  if (ext === '.xml') return '\uD83D\uDCCB'
  if (ext === '.md' || ext === '.rst' || ext === '.txt') return '\uD83D\uDCC4'
  return '\uD83D\uDCC4'
}

function getNodeDepthStyle(depth: number) {
  return { paddingLeft: `${12 + depth * 16}px` }
}

// Flatten tree to list with depth for rendering
function flattenTree(node: TreeNode, depth: number = 0): { node: TreeNode; depth: number }[] {
  const result: { node: TreeNode; depth: number }[] = []
  if (node.children) {
    for (const child of node.children) {
      result.push({ node: child, depth })
      if (child.type === 'directory' && isExpanded(child) && child.children) {
        result.push(...flattenTree(child, depth + 1))
      }
    }
  }
  return result
}

const flatNodes = computed(() => {
  if (!explorer.tree) return []
  return flattenTree(explorer.tree)
})
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('explorer.title') }}</h1>
      <div class="flex gap-2 items-center">
        <select v-model="selectedRepoId" class="form-select" style="width: 200px">
          <option v-for="repo in repos.repos" :key="repo.id" :value="repo.id">
            {{ repo.name }}
          </option>
        </select>
      </div>
    </div>

    <!-- Search -->
    <div class="card mb-4">
      <form @submit.prevent="handleSearch" class="flex gap-2">
        <input v-model="searchQuery" class="form-input" :placeholder="t('explorer.searchPlaceholder')" />
        <BaseButton type="submit" :disabled="!searchQuery">{{ t('common.search') }}</BaseButton>
      </form>
    </div>

    <BaseSpinner v-if="explorer.loading && !explorer.tree" />

    <div v-else class="explorer-layout">
      <!-- File Tree -->
      <div class="card tree-panel">
        <div class="tree-header">
          <strong>{{ t('explorer.files') }}</strong>
          <div class="tree-header-actions">
            <span class="text-muted text-sm" v-if="explorer.tree">
              {{ explorer.tree.test_count || 0 }} {{ t('explorer.tests') }}
            </span>
            <button v-if="isLocalhost" class="icon-btn" @click="handleOpenRootFolder" :title="t('explorer.openRootFolder')">📂</button>
            <button class="icon-btn" @click="expandAll" :title="t('explorer.expandAll')">⊞</button>
            <button class="icon-btn" @click="collapseAll" :title="t('explorer.collapseAll')">⊟</button>
            <button class="icon-btn" @click="openCreateDialog()" :title="t('explorer.newFile')">+</button>
          </div>
        </div>
        <div class="tree-content" v-if="explorer.tree?.children">
          <div
            v-for="{ node, depth } in flatNodes"
            :key="node.path"
            class="tree-node"
            :class="{
              active: explorer.selectedFile?.path === node.path,
              directory: node.type === 'directory',
            }"
            :style="getNodeDepthStyle(depth)"
            @click="onNodeClick(node)"
          >
            <span class="node-icon">{{ getFileIcon(node) }}</span>
            <span class="node-name">{{ node.name }}</span>
            <span v-if="node.test_count" class="node-badge">{{ node.test_count }}</span>
            <!-- Action buttons on hover -->
            <span class="node-actions" @click.stop>
              <button
                v-if="node.type === 'file' && node.extension === '.robot'"
                class="node-action-btn run"
                @click="handleRunRobot(node)"
                :title="t('explorer.runTest')"
              >▶</button>
              <button
                v-if="node.type === 'directory' && isLocalhost"
                class="node-action-btn"
                @click="handleOpenInFileBrowser(node)"
                :title="t('explorer.openInFileBrowser')"
              >📂</button>
              <button
                v-if="node.type === 'directory'"
                class="node-action-btn"
                @click="openCreateDialog(node)"
                :title="t('explorer.newFileHere')"
              >+</button>
              <button class="node-action-btn" @click="openRenameDialog(node)" :title="t('explorer.rename')">✏️</button>
              <button
                v-if="node.type === 'file'"
                class="node-action-btn"
                @click="handleOpenInEditor(node)"
                :title="t('explorer.openInEditor')"
              >↗</button>
              <button class="node-action-btn danger" @click="openDeleteConfirm(node)" :title="t('common.delete')">🗑</button>
            </span>
          </div>
        </div>
        <div v-else class="empty-state-sm">
          <p class="text-muted text-sm">{{ t('explorer.noRepoSelected') }}</p>
        </div>
      </div>

      <!-- Content / Preview -->
      <div class="card preview-panel">
        <!-- Search Results -->
        <template v-if="explorer.searchResults.length">
          <div class="preview-header">
            <strong>{{ t('explorer.searchResults', { count: explorer.searchResults.length }) }}</strong>
            <BaseButton variant="ghost" size="sm" @click="explorer.clearSelection()">{{ t('common.close') }}</BaseButton>
          </div>
          <div class="search-results">
            <div
              v-for="(result, i) in explorer.searchResults.slice(0, 50)"
              :key="i"
              class="search-item"
              @click="onSearchResultClick(result.file_path)"
            >
              <span class="result-type">{{ result.type }}</span>
              <span class="result-name">{{ result.name }}</span>
              <span class="text-muted text-sm">{{ result.file_path }}:{{ result.line_number }}</span>
            </div>
          </div>
        </template>

        <!-- File Editor -->
        <template v-else-if="explorer.selectedFile">
          <div class="preview-header">
            <div class="preview-header-left">
              <div class="preview-header-info">
                <div class="preview-header-top">
                  <nav class="breadcrumb">
                    <template v-for="(crumb, i) in breadcrumb" :key="crumb.path">
                      <span v-if="i > 0" class="breadcrumb-sep">/</span>
                      <span :class="{ 'breadcrumb-current': crumb.isLast }">{{ crumb.name }}</span>
                    </template>
                  </nav>
                  <span class="text-muted text-sm">{{ t('explorer.lines', { count: explorer.selectedFile.line_count }) }}</span>
                </div>
                <div v-if="absolutePath" class="absolute-path">
                  {{ t('explorer.absolutePath') }}: {{ absolutePath }}
                </div>
              </div>
            </div>
            <div class="preview-header-actions">
              <span v-if="isDirty" class="unsaved-badge">{{ t('explorer.unsaved') }}</span>
              <BaseButton
                v-if="isEditable && isDirty"
                size="sm"
                @click="handleSave"
                :disabled="saving"
              >
                {{ saving ? t('explorer.saving') : t('common.save') }}
              </BaseButton>
              <button
                v-if="isRobot"
                class="action-btn run-btn"
                @click="handleRunRobot({ path: explorer.selectedFile.path, name: explorer.selectedFile.name, type: 'file', extension: explorer.selectedFile.extension, test_count: 0 } as TreeNode)"
                :disabled="!!runningFile"
                :title="t('explorer.runRobot')"
              >▶ {{ t('explorer.run') }}</button>
            </div>
          </div>
          <!-- CodeMirror editor for editable files -->
          <div v-if="isEditable" ref="editorContainer" class="editor-container"></div>
          <!-- Fallback for non-editable files -->
          <pre v-else class="code-preview"><code>{{ explorer.selectedFile.content }}</code></pre>
        </template>

        <!-- Empty State -->
        <div v-else class="empty-state">
          <p class="text-muted">{{ t('explorer.selectFile') }}</p>
        </div>
      </div>
    </div>

    <!-- Create File Dialog -->
    <BaseModal v-model="showCreateDialog" :title="t('explorer.createDialog.title')" size="sm">
      <form @submit.prevent="handleCreate">
        <div class="form-group">
          <label class="form-label">{{ t('explorer.createDialog.pathLabel') }}</label>
          <input v-model="newFilePath" class="form-input" :placeholder="t('explorer.createDialog.pathPlaceholder')" required />
          <p class="text-muted text-sm" style="margin-top: 4px">{{ t('explorer.createDialog.pathHint') }}</p>
        </div>
      </form>
      <template #footer>
        <BaseButton variant="secondary" size="sm" @click="showCreateDialog = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton size="sm" @click="handleCreate" :disabled="!newFilePath">{{ t('explorer.createDialog.create') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Rename Dialog -->
    <BaseModal v-model="showRenameDialog" :title="t('explorer.renameDialog.title')" size="sm">
      <form @submit.prevent="handleRename">
        <div class="form-group">
          <label class="form-label">{{ t('explorer.renameDialog.newName') }}</label>
          <input v-model="renameNewName" class="form-input" required />
        </div>
      </form>
      <template #footer>
        <BaseButton variant="secondary" size="sm" @click="showRenameDialog = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton size="sm" @click="handleRename" :disabled="!renameNewName">{{ t('explorer.rename') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Delete Confirmation -->
    <BaseModal v-model="showDeleteConfirm" :title="t('explorer.deleteDialog.title')" size="sm">
      <p>{{ t('explorer.deleteDialog.message', { name: contextTarget?.name }) }}</p>
      <p class="text-muted text-sm" style="margin-top: 8px">{{ t('explorer.deleteDialog.warning') }}</p>
      <template #footer>
        <BaseButton variant="secondary" size="sm" @click="showDeleteConfirm = false">{{ t('common.cancel') }}</BaseButton>
        <BaseButton variant="danger" size="sm" @click="handleDelete">{{ t('common.delete') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Environment Setup Prompt -->
    <BaseModal v-model="showEnvPrompt" :title="t('execution.envPrompt.title')">
      <div class="env-prompt-body">
        <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="env-prompt-icon">
          <path d="M16.5 9.4l-9-5.19M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
          <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
          <line x1="12" y1="22.08" x2="12" y2="12"/>
        </svg>
        <p>{{ t('execution.envPrompt.message') }}</p>
        <div class="env-prompt-packages">
          <span class="env-prompt-tag">robotframework</span>
          <span class="env-prompt-tag">seleniumlibrary</span>
          <span class="env-prompt-tag">browser</span>
          <span class="env-prompt-tag">requests</span>
        </div>
      </div>
      <template #footer>
        <BaseButton variant="secondary" @click="skipEnvAndRun">{{ t('execution.envPrompt.skip') }}</BaseButton>
        <BaseButton :loading="settingUpDefaultEnv" @click="setupDefaultFromExplorer">{{ t('execution.envPrompt.setup') }}</BaseButton>
      </template>
    </BaseModal>

    <!-- Run Overlay -->
    <BaseModal v-model="runOverlay.show" :title="runOverlay.error ? t('explorer.runOverlay.error') : t('explorer.runOverlay.started')" size="sm">
      <div v-if="runOverlay.error" class="run-overlay-error">
        <p>{{ runOverlay.error }}</p>
      </div>
      <div v-else class="run-overlay-success">
        <p>{{ t('explorer.runOverlay.running', { name: runOverlay.fileName }) }}</p>
        <p class="text-muted text-sm" style="margin-top: 8px">
          {{ t('explorer.runOverlay.runId') }} {{ runOverlay.runId }}
        </p>
      </div>
      <template #footer>
        <BaseButton variant="secondary" size="sm" @click="runOverlay.show = false">{{ t('common.close') }}</BaseButton>
        <BaseButton v-if="!runOverlay.error" size="sm" @click="goToExecution">{{ t('explorer.runOverlay.goToExecution') }}</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.explorer-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
  height: calc(100vh - 200px);
}

/* --- Tree Panel --- */
.tree-panel {
  overflow-y: auto;
  padding: 0;
}

.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-border-light);
  position: sticky;
  top: 0;
  background: var(--color-bg-card);
  z-index: 2;
}

.tree-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon-btn {
  width: 24px;
  height: 24px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-muted);
  transition: all 0.15s;
}

.icon-btn:hover {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}

.tree-content {
  padding: 4px 0;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  padding-right: 4px;
  cursor: pointer;
  font-size: 13px;
  position: relative;
  user-select: none;
}

.tree-node:hover { background: var(--color-border-light); }
.tree-node.active { background: rgba(60, 181, 161, 0.12); color: var(--color-primary); }
.tree-node.directory { font-weight: 500; }

.node-icon { font-size: 13px; flex-shrink: 0; width: 18px; text-align: center; }
.node-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-badge {
  font-size: 10px;
  background: var(--color-primary-light);
  color: var(--color-primary-dark);
  padding: 1px 5px;
  border-radius: 8px;
  flex-shrink: 0;
}

.node-actions {
  display: none;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.tree-node:hover .node-actions {
  display: flex;
}

.tree-node:hover .node-badge {
  display: none;
}

.node-action-btn {
  width: 22px;
  height: 22px;
  border: none;
  background: none;
  cursor: pointer;
  border-radius: 3px;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.1s;
  padding: 0;
}

.node-action-btn:hover { background: rgba(0, 0, 0, 0.08); }
.node-action-btn.danger:hover { background: rgba(220, 53, 69, 0.15); }
.node-action-btn.run { color: var(--color-primary); }
.node-action-btn.run:hover { background: rgba(60, 181, 161, 0.15); }

.empty-state-sm {
  padding: 24px;
  text-align: center;
}

/* --- Preview Panel --- */
.preview-panel {
  overflow: hidden;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
  min-height: 42px;
}

.preview-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  overflow: hidden;
}

.preview-header-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}

.preview-header-top {
  display: flex;
  align-items: center;
  gap: 12px;
}

.absolute-path {
  font-size: 11px;
  color: var(--color-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  opacity: 0.7;
}

.preview-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 13px;
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.breadcrumb-sep { color: var(--color-border); margin: 0 2px; }
.breadcrumb-current { color: var(--color-text); font-weight: 600; }

.unsaved-badge {
  font-size: 11px;
  color: var(--color-accent);
  font-weight: 600;
  padding: 2px 8px;
  background: rgba(223, 170, 64, 0.12);
  border-radius: 4px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.run-btn {
  background: var(--color-primary);
  color: white;
}

.run-btn:hover { filter: brightness(0.9); }
.run-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.editor-container {
  flex: 1;
  overflow: auto;
}

.editor-container :deep(.cm-editor) {
  height: 100%;
}

.code-preview {
  padding: 16px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre;
  overflow: auto;
  background: #fafafa;
  margin: 0;
  flex: 1;
}

.search-results { padding: 8px; overflow-y: auto; flex: 1; }
.search-item {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px;
  border-bottom: 1px solid var(--color-border-light);
  font-size: 13px;
  cursor: pointer;
}

.search-item:hover { background: var(--color-border-light); }

.result-type {
  font-size: 10px;
  text-transform: uppercase;
  padding: 1px 5px;
  background: var(--color-border-light);
  border-radius: 3px;
  font-weight: 600;
  flex-shrink: 0;
}

.result-name { flex: 1; }

.env-prompt-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 8px 0;
  gap: 12px;
}

.env-prompt-icon {
  color: var(--color-primary, #3B7DD8);
}

.env-prompt-body p {
  color: var(--color-text-muted, #5C688C);
  font-size: 14px;
  max-width: 380px;
  line-height: 1.5;
}

.env-prompt-packages {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
}

.env-prompt-tag {
  display: inline-block;
  padding: 3px 10px;
  background: rgba(60, 181, 161, 0.1);
  color: var(--color-primary, #3B7DD8);
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
}
</style>
