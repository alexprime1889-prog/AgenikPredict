/**
 * Temporary store for files and requirements pending upload.
 * Used when the user clicks "Start Engine" on the home page and is immediately
 * redirected to the Process page, where the actual API calls are made.
 */
import { reactive } from 'vue'

const state = reactive({
  files: [],
  urls: [],
  simulationRequirement: '',
  enrichWithMarketData: false,
  isPending: false
})

export function setPendingUpload(files, requirement, urls = [], enrichWithMarketData = false) {
  state.files = files
  state.urls = urls
  state.simulationRequirement = requirement
  state.enrichWithMarketData = enrichWithMarketData
  state.isPending = true
}

export function getPendingUpload() {
  return {
    files: state.files,
    urls: state.urls,
    simulationRequirement: state.simulationRequirement,
    enrichWithMarketData: state.enrichWithMarketData,
    isPending: state.isPending
  }
}

export function clearPendingUpload() {
  state.files = []
  state.urls = []
  state.simulationRequirement = ''
  state.enrichWithMarketData = false
  state.isPending = false
}

export default state
