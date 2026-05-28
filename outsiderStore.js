// stores/outsiderStore.js
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export const useOutsiderStore = defineStore('outsider', () => {
  // ===============================
  // Estado del store
  // ===============================
  
  // Asset seleccionado
  const selectedAsset = ref('');
  
  // Paginación
  const offset = ref(0);
  
  // Filtros
  const filters = ref({
    category: '',
    tag: ''
  });
  
  // Payloads seleccionados
  const selectedPayloads = ref([]);
  
  // Scripts
  const currentScript = ref(null);
  const scriptTemplates = ref([]);
  
  // ===============================
  // Getters (computed properties)
  // ===============================
  
  // Puedes agregar getters si los necesitas
  const selectedPayloadsCount = computed(() => selectedPayloads.value.length);
  
  // ===============================
  // Acciones (métodos)
  // ===============================
  
  // Payloads
  const togglePayload = (payloadName) => {
    const index = selectedPayloads.value.indexOf(payloadName);
    if (index > -1) {
      // Remover si ya está seleccionado
      selectedPayloads.value.splice(index, 1);
    } else {
      // Agregar si no está seleccionado
      selectedPayloads.value.push(payloadName);
    }
  };
  
  const isSelected = (payloadName) => {
    return selectedPayloads.value.includes(payloadName);
  };
  
  const clearSelections = () => {
    selectedPayloads.value = [];
  };
  
  // Scripts
  const setCurrentScript = (script) => {
    currentScript.value = script;
  };
  
  const setScriptTemplates = (templates) => {
    scriptTemplates.value = templates;
  };
  
  const clearCurrentScript = () => {
    currentScript.value = null;
  };
  
  // Filtros
  const setFilter = (filterName, value) => {
    if (filters.value.hasOwnProperty(filterName)) {
      filters.value[filterName] = value;
    }
  };
  
  // Resetear store
  const reset = () => {
    selectedAsset.value = '';
    offset.value = 0;
    filters.value = { category: '', tag: '' };
    selectedPayloads.value = [];
    currentScript.value = null;
    scriptTemplates.value = [];
  };
  
  // ===============================
  // Retornar todo
  // ===============================
  return {
    // Estado
    selectedAsset,
    offset,
    filters,
    selectedPayloads,
    currentScript,
    scriptTemplates,
    
    // Getters
    selectedPayloadsCount,
    
    // Acciones
    togglePayload,
    isSelected,
    clearSelections,
    setCurrentScript,
    setScriptTemplates,
    clearCurrentScript,
    setFilter,
    reset
  };
});
