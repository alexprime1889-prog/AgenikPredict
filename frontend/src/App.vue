<template>
  <router-view />
</template>

<script setup>
// Vue Router manages page navigation
</script>

<style>
/* Global style reset */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: 'JetBrains Mono', 'Space Grotesk', 'Noto Sans Hebrew', system-ui, monospace;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #FAFAFA;
  background-color: #000000;
}

/* RTL support via CSS logical properties */
[dir="rtl"] .text-left { text-align: start; }
[dir="rtl"] .text-right { text-align: end; }

/* Scrollbar styles */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #111111;
}

::-webkit-scrollbar-thumb {
  background: #333333;
}

::-webkit-scrollbar-thumb:hover {
  background: #555555;
}

/* Global button styles */
button {
  font-family: inherit;
}
</style>
