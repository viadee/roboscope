import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { driver, type DriveStep } from 'driver.js'
import 'driver.js/dist/driver.css'
import { getDockerStatus } from '@/api/settings.api'
import { useAuthStore } from '@/stores/auth.store'
import { useUiStore } from '@/stores/ui.store'

const STORAGE_KEY = 'roboscope_tour_completed'

const isRunning = ref(false)
const tourCompleted = ref(localStorage.getItem(STORAGE_KEY) === 'true')
const dockerAvailable = ref(false)

export function useTour() {
  const router = useRouter()
  const { t } = useI18n()
  const auth = useAuthStore()
  const ui = useUiStore()

  async function checkDockerAvailability(): Promise<boolean> {
    try {
      const status = await getDockerStatus()
      return !!status?.connected
    } catch {
      return false
    }
  }

  function navigateAndAdvance(driverObj: ReturnType<typeof driver>, path: string) {
    router.push(path)
    setTimeout(() => {
      driverObj.moveNext()
    }, 600)
  }

  function navigateAndGoBack(driverObj: ReturnType<typeof driver>, path: string) {
    router.push(path)
    setTimeout(() => {
      driverObj.movePrevious()
    }, 600)
  }

  function buildSteps(): DriveStep[] {
    const steps: DriveStep[] = []
    const isEditor = auth.hasMinRole('editor')
    const isAdmin = auth.hasMinRole('admin')

    // Step 1: Welcome (Dashboard — sidebar header)
    steps.push({
      element: '.sidebar-header',
      popover: {
        title: t('tour.welcome.title'),
        description: t('tour.welcome.description'),
      },
    })

    // Step 2: Navigation (Dashboard — sidebar nav)
    steps.push({
      element: '.sidebar-nav',
      popover: {
        title: t('tour.navigation.title'),
        description: t('tour.navigation.description'),
      },
    })

    // Step 3: Header controls
    steps.push({
      element: '.header-right',
      popover: {
        title: t('tour.header.title'),
        description: t('tour.header.description'),
      },
    })

    // Step 4: Language switcher
    steps.push({
      element: '.lang-switcher',
      popover: {
        title: t('tour.langSwitcher.title'),
        description: t('tour.langSwitcher.description'),
      },
    })

    // Step 5: Dashboard KPI cards
    steps.push({
      element: '.kpi-card',
      popover: {
        title: t('tour.dashboard.title'),
        description: t('tour.dashboard.description'),
      },
    })

    // Step 6: Dashboard recent runs → navigate to /repos
    steps.push({
      element: '.data-table',
      popover: {
        title: t('tour.dashboardRuns.title'),
        description: t('tour.dashboardRuns.description'),
      },
    })

    // Step 7: Projects page header
    steps.push({
      element: '.page-header',
      popover: {
        title: t('tour.projects.title'),
        description: t('tour.projects.description'),
      },
    })

    // Step 8: Project card → navigate to /explorer
    steps.push({
      element: '.card',
      popover: {
        title: t('tour.projectCard.title'),
        description: t('tour.projectCard.description'),
      },
    })

    // Step 9: Explorer page header → navigate to /runs
    steps.push({
      element: '.page-header',
      popover: {
        title: t('tour.explorer.title'),
        description: t('tour.explorer.description'),
      },
    })

    // Step 10: Execution page header → navigate to /environments (if editor+) or /stats
    steps.push({
      element: '.page-header',
      popover: {
        title: t('tour.execution.title'),
        description: t('tour.execution.description'),
      },
    })

    // Step 11: Environments (editor+ only)
    if (isEditor) {
      steps.push({
        element: '.page-header',
        popover: {
          title: t('tour.environments.title'),
          description: t('tour.environments.description'),
        },
      })

      // Step 12: Docker section (only if Docker available)
      if (dockerAvailable.value) {
        steps.push({
          element: '.docker-section',
          popover: {
            title: t('tour.docker.title'),
            description: t('tour.docker.description'),
          },
        })
      }
    }

    // Step 13: Stats → navigate to /settings (if admin)
    steps.push({
      element: '.page-header',
      popover: {
        title: t('tour.stats.title'),
        description: t('tour.stats.description'),
      },
    })

    // Step 14: Settings (admin only)
    if (isAdmin) {
      steps.push({
        element: '.page-header',
        popover: {
          title: t('tour.settings.title'),
          description: t('tour.settings.description'),
        },
      })
    }

    // Step 15: Finish (no element — centered)
    steps.push({
      popover: {
        title: t('tour.finish.title'),
        description: t('tour.finish.description'),
      },
    })

    return steps
  }

  // Determine which view each step index should be on
  function getStepRoute(stepIndex: number, steps: DriveStep[]): string | null {
    // Find the step's title to determine which view it belongs to
    const step = steps[stepIndex]
    if (!step) return null
    const title = step.popover?.title

    const isEditor = auth.hasMinRole('editor')
    const isAdmin = auth.hasMinRole('admin')

    if (title === t('tour.welcome.title') ||
        title === t('tour.navigation.title') ||
        title === t('tour.header.title') ||
        title === t('tour.langSwitcher.title') ||
        title === t('tour.dashboard.title') ||
        title === t('tour.dashboardRuns.title')) {
      return '/dashboard'
    }
    if (title === t('tour.projects.title') || title === t('tour.projectCard.title')) {
      return '/repos'
    }
    if (title === t('tour.explorer.title')) {
      return '/explorer'
    }
    if (title === t('tour.execution.title')) {
      return '/runs'
    }
    if (title === t('tour.environments.title') || title === t('tour.docker.title')) {
      return '/environments'
    }
    if (title === t('tour.stats.title')) {
      return '/stats'
    }
    if (title === t('tour.settings.title')) {
      return '/settings'
    }
    return null // finish step
  }

  function needsNavigation(currentPath: string, targetPath: string | null): boolean {
    if (!targetPath) return false
    // Normalize paths for comparison
    const current = currentPath.replace(/\/$/, '') || '/'
    const target = targetPath.replace(/\/$/, '') || '/'
    return current !== target
  }

  async function startTour() {
    if (isRunning.value) return

    // Ensure sidebar is expanded
    ui.sidebarOpen = true

    // Check Docker availability
    dockerAvailable.value = await checkDockerAvailability()

    const steps = buildSteps()
    isRunning.value = true

    // Start on dashboard
    await router.push('/dashboard')
    await new Promise(resolve => setTimeout(resolve, 400))

    const driverObj = driver({
      showProgress: true,
      animate: true,
      popoverClass: 'roboscope-tour-popover',
      steps,
      onNextClick: () => {
        const currentIndex = driverObj.getActiveIndex() ?? 0
        const nextIndex = currentIndex + 1
        if (nextIndex >= steps.length) {
          driverObj.moveNext()
          return
        }
        const nextRoute = getStepRoute(nextIndex, steps)
        const currentRoute = router.currentRoute.value.path
        if (needsNavigation(currentRoute, nextRoute)) {
          router.push(nextRoute!)
          setTimeout(() => driverObj.moveNext(), 600)
        } else {
          driverObj.moveNext()
        }
      },
      onPrevClick: () => {
        const currentIndex = driverObj.getActiveIndex() ?? 0
        const prevIndex = currentIndex - 1
        if (prevIndex < 0) {
          driverObj.movePrevious()
          return
        }
        const prevRoute = getStepRoute(prevIndex, steps)
        const currentRoute = router.currentRoute.value.path
        if (needsNavigation(currentRoute, prevRoute)) {
          router.push(prevRoute!)
          setTimeout(() => driverObj.movePrevious(), 600)
        } else {
          driverObj.movePrevious()
        }
      },
      onDestroyStarted: () => {
        isRunning.value = false
        tourCompleted.value = true
        localStorage.setItem(STORAGE_KEY, 'true')
        driverObj.destroy()
      },
    })

    driverObj.drive()
  }

  function resetTour() {
    tourCompleted.value = false
    localStorage.removeItem(STORAGE_KEY)
  }

  return { startTour, isRunning, tourCompleted, resetTour }
}
