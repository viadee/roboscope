/**
 * Chinese (Simplified) locale — 中文（简体）.
 *
 * Translations are deep-merged OVER the English base so EVERY key resolves:
 * high-traffic UI is translated here; any not-yet-translated long-tail key
 * falls back to the English text under the `zh` locale (extend `overrides`
 * over time). This guarantees structural completeness (no missing keys, no
 * German leakage) — pinned by `ZhLocaleParity.spec.ts`.
 *
 * vue-i18n reserved chars: placeholders like {name} are preserved verbatim and
 * `@` is escaped as `{'@'}` exactly as in the English source.
 */
import en from './en'

type Dict = { [k: string]: string | Dict }

function deepMerge<T extends Dict>(base: T, over: Dict): T {
  const out: Dict = Array.isArray(base) ? base : { ...base }
  for (const key of Object.keys(over)) {
    const o = over[key]
    const b = (out as Dict)[key]
    if (o && typeof o === 'object' && b && typeof b === 'object') {
      out[key] = deepMerge(b as Dict, o as Dict)
    } else {
      out[key] = o
    }
  }
  return out as T
}

const overrides: Dict = {
  common: {
    save: '保存', cancel: '取消', delete: '删除', close: '关闭', back: '返回',
    add: '添加', edit: '编辑', create: '创建', error: '错误', loading: '加载中…',
    noData: '暂无数据。', confirm: '确认', yes: '是', no: '否', search: '搜索',
    install: '安装', installed: '已安装', upgrade: '升级', remove: '移除',
    clone: '克隆', retry: '重试', dismiss: '忽略', start: '启动', id: 'ID',
    status: '状态', duration: '耗时', created: '创建时间', actions: '操作',
    name: '名称', date: '日期', type: '类型',
    prevPage: '← 上一页', nextPage: '下一页 →',
    pageOf: '第 {current} / {total} 页', logout: '退出登录', menu: '菜单',
  },
  a11y: { skipToMain: '跳转到主要内容', languageSwitcher: '语言' },
  nav: {
    dashboard: '仪表盘', repos: '项目', explorer: '浏览器', execution: '执行',
    reports: '报告', stats: '统计', environments: '包管理器', settings: '设置',
    docs: '文档', identityProviders: '身份提供商', recorder: '录制器',
    teams: '团队', emergencyBypass: '紧急绕过', more: '更多',
    previewBadge: '预览', previewHint: '预览功能 — 界面和行为可能随时变更。',
  },
  auth: {
    tagline: 'Robot Framework 测试管理',
    subtitle: '在一处管理、执行并分析你的 Robot Framework 测试。',
    login: '登录', loginDesc: '登录到你的 RoboScope 实例',
    email: '邮箱', password: '密码', loginFailed: '登录失败',
    hint: "默认：admin{'@'}roboscope.local / admin123",
    pwChange: {
      title: '修改密码', intro: '为你的账户设置新密码。',
      current: '当前密码', newPw: '新密码', confirm: '确认新密码',
      submit: '修改密码', minLength: '至少 8 个字符。',
      mismatch: '两次输入的新密码不一致。',
      sameAsCurrent: '新密码必须与当前密码不同。',
      wrongCurrent: '当前密码不正确。', invalid: '新密码不符合要求。',
    },
    defaultPwBanner: {
      message: '你仍在使用默认管理员密码。在公开此实例前，请考虑更换密码。',
      action: '修改密码', dontShowAgain: '不再显示',
      dontShowAgainTitle: '为当前用户永久隐藏此横幅。更换浏览器或清除站点数据后会再次出现。',
    },
    features: {
      explorer: '测试浏览与编辑', execution: '测试执行与计划',
      reports: '报告分析与比较', environments: '环境与包管理',
      ai: 'AI 驱动的测试生成', rbac: '基于角色的访问控制',
    },
    install: {
      title: '快速开始 — 离线 ZIP',
      hint: '下载 ZIP、解压并运行上面的脚本。无需联网。',
    },
    ssoError: {
      heading: '无法登录', tryAgain: '重试',
      contactAdmin: '如果问题持续，请联系 {email}。',
      idpUnreachable: '无法连接到你的身份提供商，请稍后重试。',
      stateExpired: '登录尝试已超时，请重新开始。',
      stateNotFound: '此登录链接已失效，请重新登录。',
      returnToInvalid: '登录跳转无效，请从登录页重新开始。',
      tokenExchangeFailed: '无法完成登录令牌交换，请重试。',
      claimsEmailUnverified: '你的账户邮箱未在身份提供商处验证。',
      claimsAzpMissing: '身份提供商的响应不完整，请重试。',
      userDisabled: '你的账户已被停用，请联系管理员。',
      idpNotFound: '该身份提供商已不可用，请选择其他登录方式。',
      syncFailed: '无法同步你的组成员关系，请重试。',
      generic: '登录失败，请重试。',
    },
  },
  notifications: {
    title: '通知', empty: '暂无通知。', markAllRead: '全部标记为已读',
  },
  flowEditor: {
    libraries: '库', librariesTitle: '管理此文件的 Library 与 Resource 导入',
    librariesNone: '尚无 Library 或 Resource 导入。',
    libraryAdd: '添加', libraryRemoveTitle: '移除 {name}',
    variables: '变量', variablesTitle: '为此文件定义套件变量（*** Variables ***）',
    variablesNone: '尚未定义变量。', variableNamePlaceholder: '${名称}',
    variableValuePlaceholder: '值', variableAdd: '添加',
    variableRemoveTitle: '移除 {name}',
    suiteSettings: '设置',
    suiteSettingsTitle: '套件设置（Setup/Teardown、标签、文档、Metadata）',
    suiteSettingsNone: '尚无套件设置。', suiteSettingRemoveTitle: '移除 {name}',
    envVarsUsed: '使用的环境变量：',
    templateAddRow: '添加行', templateAddColumn: '添加列', templateRemoveRow: '移除行',
  },
  welcome: {
    cta: { openRepo: '打开 {repo}', browseTeams: '浏览团队' },
  },
}

export default deepMerge(structuredClone(en) as unknown as Dict, overrides) as unknown as typeof en
