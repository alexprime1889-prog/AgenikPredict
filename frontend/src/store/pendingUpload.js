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
  isPending: false
})

export function setPendingUpload(files, requirement, urls = []) {
  state.files = files
  state.urls = urls
  state.simulationRequirement = requirement
  state.isPending = true
}

export function getPendingUpload() {
  return {
    files: state.files,
    urls: state.urls,
    simulationRequirement: state.simulationRequirement,
    isPending: state.isPending
  }
}

export function clearPendingUpload() {
  state.files = []
  state.urls = []
  state.simulationRequirement = ''
  state.isPending = false
}

export default state
