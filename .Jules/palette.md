## 2024-05-16 - Add ARIA attributes to LanguageSwitcher
**Learning:** Missing `aria-expanded` on dropdown buttons creates a confusing experience for screen reader users as they don't know the state of the menu.
**Action:** Ensure all interactive elements that control visibility of other elements have an appropriate `aria-expanded` attribute that updates dynamically.
