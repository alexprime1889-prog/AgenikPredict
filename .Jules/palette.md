## 2025-04-19 - Added ARIA labels to close buttons
**Learning:** Icon-only close buttons (like "×") in modals and side panels are heavily used across this app but lacked screen reader support.
**Action:** Consistently use `:aria-label="$t('common.close')"` on any new icon-only close buttons to maintain accessibility and translation support.
