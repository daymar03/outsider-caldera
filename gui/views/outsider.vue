<script setup>
import { ref, inject, watch, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useOutsiderStore } from '@/stores/outsiderStore';

const $api = inject('$api');
const store = useOutsiderStore();

// Usar storeToRefs para las propiedades reactivas
const {
  selectedAsset,
  offset,
  filters,
  selectedPayloads,
  currentScript,
  scriptTemplates
} = storeToRefs(store);

// Acciones/métodos del store
const {
  togglePayload,
  isSelected,
  clearSelections,
  setCurrentScript,
  setScriptTemplates,
  clearCurrentScript
} = store;

// ===============================
// SPA view state (#payloads | #script)
// ===============================
const currentView = ref(window.location.hash.replace('#', '') || 'payloads');

const setView = (view) => {
  currentView.value = view;
  window.location.hash = view;
};

// ===============================
// Estado local
// ===============================
const assets = ref([]);
const payloads = ref([]);
const size = 10;

const isLoadingAssets = ref(false);
const isLoadingPayloads = ref(false);
const isLoadingInfo = ref(false);
const isLoadingScripts = ref(false);
const isLoadingScriptContent = ref(false);

// Script execution
const isExecutingScript = ref(false);
const isPaused = ref(false);
const currentExecutionIndex = ref(0);
const executionResults = ref({}); // { [payloadName]: { success: boolean, response: string } }
const showResponseModal = ref(false);
const selectedResponse = ref(null);
const executionProgress = ref(0);

// Target configuration
const targetInput = ref('');
const isSettingTarget = ref(false);
const currentTarget = ref('');

// Modal states
const showCreateScriptModal = ref(false);
const showLoadTemplateModal = ref(false);
const isCreatingScript = ref(false);
const scriptCreationResult = ref(null);
const scriptForm = ref({
  name: '',
  description: ''
});

const openInfoId = ref(null);
const payloadInfo = ref({});

// Inputs de filtros (no aplicados)
const categoryInput = ref(filters.value.category);
const tagInput = ref(filters.value.tag);

// ===============================
// Cargar assets
// ===============================
onMounted(async () => {
  try {
    isLoadingAssets.value = true;
    const res = await $api.get('/plugin/outsider/assets');
    assets.value = res.data || [];
  } catch (err) {
    console.error('Error fetching assets:', err);
  } finally {
    isLoadingAssets.value = false;
  }
});

// ===============================
// Cargar payloads
// ===============================
const loadPayloads = async () => {
  if (!selectedAsset.value) return;

  try {
    isLoadingPayloads.value = true;

    const params = new URLSearchParams({
      offset: offset.value,
      size: size
    });

    if (filters.value.category) {
      params.append('category', filters.value.category);
    }

    if (filters.value.tag) {
      params.append('tag', filters.value.tag);
    }

    const res = await $api.get(
      `/plugin/outsider/${selectedAsset.value}/payloads?${params.toString()}`
    );

    const data = res.data?.payloads || [];

    if (data.length === 0 && offset.value > 0) {
      offset.value = Math.max(0, offset.value - size);
      await loadPayloads();
      return;
    }

    payloads.value = data;
    openInfoId.value = null;

  } catch (err) {
    console.error('Error fetching payloads:', err);
  } finally {
    isLoadingPayloads.value = false;
  }
};

// ===============================
// Set target
// ===============================
const setTarget = async () => {
  if (!selectedAsset.value) {
    alert('Please select an asset first');
    return;
  }

  if (!targetInput.value.trim()) {
    alert('Please enter a target URL');
    return;
  }

  try {
    isSettingTarget.value = true;
    
    await $api.post(
      `/plugin/outsider/${selectedAsset.value}/target`,
      { target: targetInput.value.trim() }
    );
    
    currentTarget.value = targetInput.value.trim();
    targetInput.value = '';
    
    alert('Target set successfully');
    
  } catch (err) {
    console.error('Error setting target:', err);
    alert('Error setting target: ' + (err.response?.data?.message || err.message));
  } finally {
    isSettingTarget.value = false;
  }
};

// ===============================
// Cargar templates de scripts
// ===============================
const loadScriptTemplates = async () => {
  if (!selectedAsset.value) {
    alert('Please select an asset first');
    return;
  }

  try {
    isLoadingScripts.value = true;
    const res = await $api.get(`/plugin/outsider/${selectedAsset.value}/scripts`);
    
    setScriptTemplates(res.data || []);
    showLoadTemplateModal.value = true;
    
  } catch (err) {
    console.error('Error loading script templates:', err);
    alert('Error loading templates: ' + (err.response?.data?.message || err.message));
  } finally {
    isLoadingScripts.value = false;
  }
};

// ===============================
// Cargar un script específico
// ===============================
const loadScript = async (scriptName) => {
  if (!selectedAsset.value) return;

  try {
    isLoadingScriptContent.value = true;
    const res = await $api.get(`/plugin/outsider/${selectedAsset.value}/scripts/${scriptName}`);
    
    const scriptData = res.data;
    
    setCurrentScript({
      name: scriptData.name || scriptName,
      payloads: scriptData.payloads || [],
      description: scriptData.description || '',
      script_id: scriptData.script_id || ''
    });
    
    // Reset execution state cuando se carga un nuevo script
    resetExecutionState();
    
    showLoadTemplateModal.value = false;
    
  } catch (err) {
    console.error('Error loading script:', err);
    alert('Error loading script: ' + (err.response?.data?.message || err.message));
  } finally {
    isLoadingScriptContent.value = false;
  }
};

// ===============================
// Resetear estado de ejecución
// ===============================
const resetExecutionState = () => {
  isExecutingScript.value = false;
  isPaused.value = false;
  currentExecutionIndex.value = 0;
  executionResults.value = {};
  executionProgress.value = 0;
};

// ===============================
// Esperar 1 segundo
// ===============================
const waitOneSecond = () => {
  return new Promise(resolve => setTimeout(resolve, 1000));
};

// ===============================
// Ejecutar un payload individual
// ===============================
const executeSinglePayload = async (payloadName) => {
  if (!selectedAsset.value) return null;

  try {
    const res = await $api.post(
      `/plugin/outsider/${selectedAsset.value}/payloads/${payloadName}/execute`
    );
    console.log(res.data.success)
    return res.data.result;
  } catch (err) {
    console.error(`Error executing payload ${payloadName}:`, err);
    return {
      success: false,
      response: `Error: ${err.message}`
    };
  }
};

// ===============================
// Ejecutar script completo
// ===============================
const executeScript = async () => {
  if (!currentScript.value || currentScript.value.payloads.length === 0) return;
  
  // Verificar si hay target configurado
  if (!currentTarget.value && currentScript.value.payloads.length > 0) {
    alert('Please set a target before executing the script');
    return;
  }
  
  // Si está pausado, continuar desde donde se quedó
  if (isPaused.value) {
    isPaused.value = false;
    continueScriptExecution();
    return;
  }
  
  // Si no está pausado, empezar desde el principio
  resetExecutionState();
  isExecutingScript.value = true;
  currentExecutionIndex.value = 0;
  
  await continueScriptExecution();
};

// ===============================
// Continuar ejecución de script
// ===============================
const continueScriptExecution = async () => {
  if (!isExecutingScript.value || !currentScript.value) return;
  
  const payloads = currentScript.value.payloads;
  
  // Ejecutar payloads en orden
  for (let i = currentExecutionIndex.value; i < payloads.length; i++) {
    if (!isExecutingScript.value || isPaused.value) {
      break; // Detener si se pausó o se detuvo
    }
    
    const payloadName = payloads[i];
    currentExecutionIndex.value = i;
    
    // Actualizar progreso
    executionProgress.value = Math.round((i / payloads.length) * 100);
    
    try {
      // Ejecutar payload
      const result = await executeSinglePayload(payloadName);
      
      // Guardar resultado
      executionResults.value[payloadName] = result;
      
      // Esperar 1 segundo antes del siguiente payload
      if (i < payloads.length - 1) {
        await waitOneSecond();
      }
      
    } catch (err) {
      console.error(`Error executing payload ${payloadName}:`, err);
      executionResults.value[payloadName] = {
        success: false,
        response: `Execution error: ${err.message}`
      };
      
      // Esperar 1 segundo incluso en caso de error
      if (i < payloads.length - 1) {
        await waitOneSecond();
      }
    }
  }
  
  // Si llegamos al final
  if (currentExecutionIndex.value >= payloads.length - 1 && isExecutingScript.value) {
    isExecutingScript.value = false;
    executionProgress.value = 100;
    alert('Script execution completed!');
  }
};

// ===============================
// Pausar script
// ===============================
const pauseScript = () => {
  if (isExecutingScript.value) {
    isPaused.value = true;
  }
};

// ===============================
// Detener script completamente
// ===============================
const stopScript = () => {
  isExecutingScript.value = false;
  isPaused.value = false;
  executionProgress.value = 0;
  alert('Script execution stopped');
};

// ===============================
// Ver respuesta de ejecución
// ===============================
const viewResponse = (payloadName) => {
  if (executionResults.value[payloadName]) {
    selectedResponse.value = {
      payload: payloadName,
      ...executionResults.value[payloadName]
    };
    showResponseModal.value = true;
  }
};

// ===============================
// Obtener estado de un payload
// ===============================
const getPayloadStatus = (payloadName) => {
  if (!executionResults.value[payloadName]) {
    return {
      status: 'pending',
      label: 'Pending',
      class: 'is-light',
      icon: 'fa-clock'
    };
  }
  
  const result = executionResults.value[payloadName];
  if (result.success) {
    return {
      status: 'success',
      label: 'Success',
      class: 'is-success is-light',
      icon: 'fa-check-circle'
    };
  } else {
    return {
      status: 'failed',
      label: 'Failed',
      class: 'is-danger is-light',
      icon: 'fa-times-circle'
    };
  }
};

// ===============================
// Aplicar filtros
// ===============================
const applyFilters = async () => {
  filters.value.category = categoryInput.value.trim();
  filters.value.tag = tagInput.value.trim();

  offset.value = 0;
  payloads.value = [];
  openInfoId.value = null;
  payloadInfo.value = {};

  await loadPayloads();
};

// ===============================
// Limpiar filtros
// ===============================
const clearFilters = async () => {
  categoryInput.value = '';
  tagInput.value = '';

  filters.value.category = '';
  filters.value.tag = '';

  offset.value = 0;
  payloads.value = [];
  openInfoId.value = null;
  payloadInfo.value = {};

  await loadPayloads();
};

// ===============================
// Watch asset - reset target when asset changes
// ===============================
watch(selectedAsset, async (newAsset, oldAsset) => {
  if (newAsset !== oldAsset) {
    currentTarget.value = '';
    targetInput.value = '';
  }
  
  offset.value = 0;
  payloads.value = [];
  openInfoId.value = null;
  payloadInfo.value = {};
  clearSelections();

  if (selectedAsset.value) {
    await loadPayloads();
  }
});

// ===============================
// Watch currentScript - reset execution state
// ===============================
watch(currentScript, () => {
  resetExecutionState();
});

// ===============================
// Paginación
// ===============================
const nextPage = async () => {
  const prevOffset = offset.value;
  offset.value += size;
  await loadPayloads();
  if (payloads.value.length === 0) {
    offset.value = prevOffset;
  }
};

const prevPage = async () => {
  if (offset.value >= size) {
    offset.value -= size;
    await loadPayloads();
  }
};

// ===============================
// Info payload
// ===============================
const toggleInfo = async (id) => {
  if (openInfoId.value === id) {
    openInfoId.value = null;
    return;
  }

  openInfoId.value = null;

  if (payloadInfo.value[id]) {
    openInfoId.value = id;
    return;
  }

  try {
    isLoadingInfo.value = true;
    const res = await $api.get(
      `/plugin/outsider/${selectedAsset.value}/payloads/${id}`
    );
    payloadInfo.value[id] = res.data;
    openInfoId.value = id;
  } catch (err) {
    console.error('Error fetching payload info:', err);
  } finally {
    isLoadingInfo.value = false;
  }
};

// ===============================
// Selección persistente
// ===============================
const toggleSelectPayload = (name) => {
  togglePayload(name);
};

// ===============================
// Create Script Modal
// ===============================
const openCreateScriptModal = () => {
  if (!selectedAsset.value || selectedPayloads.value.length === 0) {
    alert('Please select an asset and at least one payload');
    return;
  }
  
  scriptForm.value = {
    name: '',
    description: ''
  };
  scriptCreationResult.value = null;
  showCreateScriptModal.value = true;
};

const closeCreateScriptModal = () => {
  showCreateScriptModal.value = false;
  scriptCreationResult.value = null;
};

const submitCreateScript = async () => {
  if (!scriptForm.value.name.trim()) {
    alert('Please enter a script name');
    return;
  }
  
  try {
    isCreatingScript.value = true;
    
    const payloadData = {
      name: scriptForm.value.name.trim(),
      description: scriptForm.value.description.trim(),
      payloads: selectedPayloads.value
    };
    
    const res = await $api.post(
      `/plugin/outsider/${selectedAsset.value}/create_script`,
      payloadData
    );
    
    // Guardar resultado
    scriptCreationResult.value = res.data;
    
    // Cargar el script recién creado
    await loadScript(res.data.name);
    
  } catch (err) {
    console.error('Error creating script:', err);
    alert('Error creating script: ' + (err.response?.data?.message || err.message));
  } finally {
    isCreatingScript.value = false;
  }
};

const finishCreateScript = () => {
  closeCreateScriptModal();
  setView('script');
};
</script>

<template lang="pug">
.content
  // ===============================
  // Header SPA
  // ===============================
  .tabs.is-boxed.mb-4
    ul
      li(:class="{ 'is-active': currentView === 'payloads' }")
        a(@click="setView('payloads')") Payloads
      li(:class="{ 'is-active': currentView === 'script' }")
        a(@click="setView('script')") Run a Script

  // ===============================
  // VIEW: PAYLOADS
  // ===============================
  template(v-if="currentView === 'payloads'")
    h2 Outsider
    p This is a plugin oriented to simulate Real Adversary Behaivor against Services, in order to test SIEM, WAF, and other Defense oriented solutions.
    
    hr.divider
    
    //- Configuración de Asset y Target
    .columns.mt-4.is-vcentered
      .column
        label.label Asset Type
        .control
          .select
            select(v-model="selectedAsset" :disabled="isLoadingAssets")
              option(disabled value="") Select an asset
              option(v-for="ass in assets" :key="ass" :value="ass") {{ ass }}
        p.mt-2(v-if="isLoadingAssets") Loading assets...
      
      .column
        label.label Target Configuration
        .field.has-addons
          .control.is-expanded
            input.input(
              type="text"
              placeholder="Enter target URL (e.g., http://example.com)"
              v-model="targetInput"
              :disabled="!selectedAsset"
            )
          .control
            button.button.caldera-button(
              @click="setTarget"
              :disabled="!selectedAsset || !targetInput.trim() || isSettingTarget"
              :class="{ 'is-loading': isSettingTarget }"
            ) Set Target
        
        p.help.has-text-grey.mt-1(v-if="currentTarget")
          | Current target: 
          strong {{ currentTarget }}
    
    .columns.mt-4.is-vcentered
      .column
      .column.is-narrow
        .field
          label.label &nbsp;
          button.button.caldera-button(
            :disabled="!selectedAsset || selectedPayloads.length === 0"
            @click="openCreateScriptModal"
          ) Create Script
          p.help.has-text-grey.mt-1(v-if="selectedAsset")
            | Selected: {{ selectedPayloads.length }} payload(s)

    //- Filtros
    .columns.mt-4(v-if="selectedAsset")
      .column
        label.label Category
        input.input(
          type="text"
          placeholder="e.g. xss"
          v-model="categoryInput"
        )
      .column
        label.label Tag
        input.input(
          type="text"
          placeholder="e.g. reflected"
          v-model="tagInput"
        )
      .column.is-narrow
        label.label &nbsp;
        .buttons
          button.button.caldera-button(@click="applyFilters") Apply
          button.button.is-light(@click="clearFilters") Clear

    //- Tabla
    .mt-4
      .notification.is-info.is-light(v-if="isLoadingPayloads && selectedAsset")
        p Loading payloads...

      table.table.is-fullwidth.is-striped(v-if="selectedAsset && !isLoadingPayloads")
        thead
          tr
            th Payload
            th Description
            th Info
            th Select
        tbody
          template(v-if="payloads.length > 0")
            template(v-for="pl in payloads" :key="pl.name")
              tr
                td {{ pl.name }}
                td {{ pl.description }}
                td
                  button.button.is-small.caldera-button(
                    @click="toggleInfo(pl.name)"
                    :class="{ 'is-loading': isLoadingInfo && openInfoId === pl.name }"
                  )
                    span(v-if="openInfoId === pl.name") Hide
                    span(v-else) Info
                td
                  input(
                    type="checkbox"
                    :checked="isSelected(pl.name)"
                    @change="toggleSelectPayload(pl.name)"
                  )

              tr(v-if="openInfoId === pl.name")
                td(colspan="4")
                  .notification.is-light
                    pre {{ JSON.stringify(payloadInfo[pl.name], null, 2) }}

          tr(v-else)
            td(colspan="4") No payloads available.

    //- Paginación
    .buttons.mt-3(v-if="selectedAsset && !isLoadingPayloads")
      button.button.caldera-button(@click="prevPage" :disabled="offset === 0") Previous
      button.button.caldera-button(@click="nextPage") Next

  // ===============================
  // VIEW: SCRIPT
  // ===============================
  template(v-if="currentView === 'script'")
    h2.title.is-3 Run Script
    p.subtitle.is-5 Execute and manage your attack scripts
    
    hr.divider
    
    //- Botones principales
    .buttons.mb-4
      button.button.caldera-button(
        @click="loadScriptTemplates"
        :disabled="!selectedAsset"
        :class="{ 'is-loading': isLoadingScripts }"
      ) Load Template
      button.button.is-light(@click="clearCurrentScript" v-if="currentScript") Clear Script

    //- Información del script actual
    .notification.is-info.is-light.mb-4(v-if="scriptCreationResult && !currentScript")
      h3.title.is-5 Script Created Successfully
      p.mb-2
        strong ID: 
        | {{ scriptCreationResult.script_id }}
      p.mb-2
        strong Name: 
        | {{ scriptCreationResult.name }}
      p.mb-2
        strong Total Payloads: 
        | {{ scriptCreationResult.payload_count }}
      p.mt-3 Click "Load Template" to load this script.

    //- Script cargado actualmente
    template(v-if="currentScript")
      .box.mb-4
        .media
          .media-left
            span.icon.is-large.has-text-primary
              i.fas.fa-scroll.fa-2x
          .media-content
            .content
              h4.title.is-4 {{ currentScript.name }}
              p.subtitle.is-6 {{ currentScript.description }}
              .tags
                span.tag.caldera-tag
                  strong ID: 
                  | {{ currentScript.script_id }}
                span.tag.caldera-tag
                  strong Asset: 
                  | {{ selectedAsset }}
                span.tag.caldera-tag
                  strong Payloads: 
                  | {{ currentScript.payloads.length }}
        
        //- Target info
        .notification.is-light.mt-3(v-if="currentTarget")
          p
            strong Current Target: 
            | {{ currentTarget }}
        .notification.is-warning.mt-3(v-else)
          p
            strong Warning: 
            | No target set. Please set a target in the Payloads view before executing.

      //- Botones de ejecución y progreso
      .box.mb-4
        //- Barra de progreso
        .mb-4(v-if="isExecutingScript || executionProgress > 0")
          .level
            .level-left
              .level-item
                span.tag.is-info
                  | Progress: {{ executionProgress }}%
            .level-right
              .level-item
                span.tag.is-light
                  | {{ currentExecutionIndex + 1 }}/{{ currentScript.payloads.length }} payloads
          
          progress.progress.is-info(
            :value="executionProgress" 
            max="100"
          ) {{ executionProgress }}%
        
        //- Botones de control
        .buttons
          button.button.wine-button(
            @click="executeScript"
            :disabled="currentScript.payloads.length === 0 || !currentTarget"
            :class="{ 'is-loading': isExecutingScript && !isPaused }"
          ) 
            span.icon
              i.fas(:class="isPaused ? 'fa-play' : 'fa-play'")
            span(v-if="isPaused") Continue
            span(v-else) Execute Script
          
          button.button.is-warning(
            @click="pauseScript"
            v-if="isExecutingScript && !isPaused"
          )
            span.icon
              i.fas.fa-pause
            span Pause
          
          button.button.is-danger(
            @click="stopScript"
            v-if="isExecutingScript || isPaused"
          )
            span.icon
              i.fas.fa-stop
            span Stop Script
          
          button.button.caldera-button(@click="loadScriptTemplates")
            span.icon
              i.fas.fa-sync
            span Load Different Template

      //- Tabla de payloads del script
      .box
        h4.title.is-5.mb-4 Script Payloads
        .notification.is-warning.is-light.mb-4(v-if="isLoadingScriptContent")
          p Loading script content...
        
        table.table.is-fullwidth.is-striped.is-hoverable(v-if="!isLoadingScriptContent")
          thead
            tr
              th #
              th Payload Name
              th Type
              th Status
              th Response
          tbody
            template(v-if="currentScript.payloads.length > 0")
              tr(v-for="(payload, index) in currentScript.payloads" :key="payload")
                td {{ index + 1 }}
                td {{ payload }}
                td
                  span.tag.is-info.is-light {{ payload.split('_')[1] || 'Unknown' }}
                td
                  span.tag(:class="getPayloadStatus(payload).class")
                    span.icon.is-small
                      i.fas(:class="getPayloadStatus(payload).icon")
                    span {{ getPayloadStatus(payload).label }}
                td
                  button.button.is-small.is-info(
                    @click="viewResponse(payload)"
                    :disabled="!executionResults[payload]"
                  )
                    span.icon.is-small
                      i.fas.fa-eye
                    span View
            tr(v-else)
              td(colspan="5")
                .notification.is-warning.is-light
                  p No payloads in this script.
    
    //- Sin script cargado
    .notification.is-light.mt-6(v-else)
      .content.has-text-centered
        p.title.is-5 No Script Loaded
        p
          | Load a template or create a new script from the Payloads view.
        .buttons.is-centered.mt-4
          button.button.caldera-button(
            @click="loadScriptTemplates" 
            :disabled="!selectedAsset"
          ) Load Template
          button.button.is-info(@click="setView('payloads')") Back to Payloads

  // ===============================
  // MODAL: Create Script
  // ===============================
  .modal(:class="{ 'is-active': showCreateScriptModal }")
    .modal-background(@click="!isCreatingScript && closeCreateScriptModal()")
    .modal-card
      header.modal-card-head
        p.modal-card-title Create New Script
        button.delete(
          aria-label="close"
          @click="closeCreateScriptModal"
          :disabled="isCreatingScript"
        )
      
      section.modal-card-body
        //- Formulario para crear script
        template(v-if="!scriptCreationResult")
          .field
            label.label Script Name
            .control
              input.input(
                type="text"
                placeholder="e.g., XSS-Script"
                v-model="scriptForm.name"
                :disabled="isCreatingScript"
                required
              )
            p.help Required. Choose a descriptive name for your script.
          
          .field.mt-4
            label.label Description
            .control
              textarea.textarea(
                placeholder="e.g., Script that automates XSS Attacks adversary emulation"
                v-model="scriptForm.description"
                :disabled="isCreatingScript"
                rows="3"
              )
            p.help Optional. Describe what this script does.
          
          .notification.is-light.mt-4
            p
              strong Asset: 
              | {{ selectedAsset }}
            p
              strong Selected Payloads: 
              | {{ selectedPayloads.length }}
            ul.mt-2
              li(v-for="payload in selectedPayloads.slice(0, 5)" :key="payload")
                | {{ payload }}
              li(v-if="selectedPayloads.length > 5") ... and {{ selectedPayloads.length - 5 }} more
        
        //- Resultado después de crear
        template(v-else)
          .notification.is-success
            h3.title.is-5 Script Successfully Created!
            
            .content.mt-3
              p
                strong ID: 
                | {{ scriptCreationResult.script_id }}
              p
                strong Name: 
                | {{ scriptCreationResult.name }}
              p
                strong Total Payloads: 
                | {{ scriptCreationResult.payload_count }}
            
            p.mt-4 Your script has been created and saved successfully.
      
      footer.modal-card-foot
        template(v-if="!scriptCreationResult")
          button.button.caldera-button(
            @click="submitCreateScript"
            :disabled="isCreatingScript || !scriptForm.name.trim()"
            :class="{ 'is-loading': isCreatingScript }"
          ) Create Script
          button.button.is-light(@click="closeCreateScriptModal" :disabled="isCreatingScript") Cancel
        
        template(v-else)
          button.button.caldera-button(@click="finishCreateScript") Go to Script View
          button.button.is-light(@click="closeCreateScriptModal") Close

  // ===============================
  // MODAL: Load Template
  // ===============================
  .modal(:class="{ 'is-active': showLoadTemplateModal }")
    .modal-background(@click="showLoadTemplateModal = false")
    .modal-card
      header.modal-card-head
        p.modal-card-title Load Script Template
        button.delete(aria-label="close" @click="showLoadTemplateModal = false")
      
      section.modal-card-body
        .notification.is-info.is-light.mb-4(v-if="isLoadingScripts")
          p Loading available templates...
        
        template(v-else)
          .columns.is-multiline
            .column.is-6(v-for="template in scriptTemplates" :key="template.name")
              .card.is-clickable(
                @click="loadScript(template.name)"
                :class="{ 'is-loading': isLoadingScriptContent && currentScript?.name === template.name }"
              )
                .card-content
                  .media
                    .media-left
                      span.icon.has-text-primary
                        i.fas.fa-file-code
                    .media-content
                      p.title.is-6 {{ template.name }}
                      p.subtitle.is-7.has-text-grey {{ template.script_id || '' }}
                  .content
                    hr
                    p {{ template.description || 'No description available' }}
                    .tags
                      span.tag.is-light.is-small
                        | {{ template.payload_count || 0 }} payloads
          
          .notification.is-warning.is-light.mt-4(v-if="scriptTemplates.length === 0")
            p No script templates available for this asset.
      
      footer.modal-card-foot
        .buttons
          button.button.is-light(@click="showLoadTemplateModal = false") Close
          button.button.caldera-button(@click="loadScriptTemplates" :class="{ 'is-loading': isLoadingScripts }") Refresh

  // ===============================
  // MODAL: View Response
  // ===============================
  .modal(:class="{ 'is-active': showResponseModal }")
    .modal-background(@click="showResponseModal = false")
    .modal-card
      header.modal-card-head
        p.modal-card-title Execution Response
        button.delete(aria-label="close" @click="showResponseModal = false")
      
      section.modal-card-body
        template(v-if="selectedResponse")
          .notification(:class="selectedResponse.success ? 'is-success' : 'is-danger'")
            p
              strong Payload: 
              | {{ selectedResponse.payload }}
            p
              strong Status: 
              | {{ selectedResponse.success ? 'Success' : 'Failed' }}
          
          .content.mt-4
            h5.title.is-6 Response Details:
            pre.response-pre {{ selectedResponse.response }}
      
      footer.modal-card-foot
        .buttons
          button.button.is-light(@click="showResponseModal = false") Close
</template>

<style scoped>
/* Estilo Caldera (color morado) */
:root {
  --caldera-purple: #6a0dad;
  --caldera-purple-light: #8a2be2;
  --caldera-purple-dark: #4b0082;
  --wine-green: #228B22;
  --wine-green-light: #32CD32;
  --wine-green-dark: #006400;
}

/* Línea divisora */
hr.divider {
  background-color: var(--caldera-purple);
  height: 2px;
  border: none;
  margin: 1rem 0 1.5rem 0;
}

/* Botones estilo Caldera */
.button.caldera-button {
  background-color: #6a0dad;
  border-color: #6a0dad);
  color: white;
}

.button.caldera-button:hover {
  background-color: #8a2be2;
  border-color: #8a2be2;
  color: white;
}

.button.caldera-button:disabled {
  background-color: #cccccc;
  border-color: #cccccc;
  color: #666666;
}

/* Botón Execute Script verde vino */
.button.wine-button {
  background-color: var(--wine-green);
  border-color: var(--wine-green);
  color: white;
  border: none;
}

.button.wine-button:hover {
  background-color: var(--wine-green-light);
  border-color: var(--wine-green-light);
  color: white;
}

.button.wine-button:active {
  background-color: var(--wine-green-dark);
  border-color: var(--wine-green-dark);
  transform: translateY(0);
}

.button.wine-button:disabled {
  background-color: #cccccc;
  border-color: #cccccc;
  color: #666666;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* Botón Pause (amarillo/warning) */
.button.is-warning {
  background-color: #ffdd57;
  border-color: transparent;
  color: rgba(0, 0, 0, 0.7);
}

.button.is-warning:hover {
  background-color: #ffd324;
  border-color: transparent;
  color: rgba(0, 0, 0, 0.7);
}

/* Botón Stop (rojo/danger) */
.button.is-danger {
  background-color: #f14668;
  border-color: transparent;
  color: white;
}

.button.is-danger:hover {
  background-color: #f03a5f;
  border-color: transparent;
  color: white;
}

/* Tags estilo Caldera */
.tag.caldera-tag {
  background-color: #6a0dad;
  color: white;
  font-weight: 600;
}

.tag.caldera-tag strong {
  color: white;
  margin-right: 4px;
}

/* Tabs activos */
.tabs.is-boxed li.is-active a {
  background-color: #6a0dad;
  border-color: #6a0dad;
  color: white;
}

/* Modal */
.modal-card {
  max-width: 800px;
  margin: 0 auto;
}

.modal-card-body {
  max-height: 70vh;
  overflow-y: auto;
}

/* Estilos para pre (info payload) */
pre {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-wrap: break-word;
  max-height: 300px;
  overflow-y: auto;
  background-color: #0e0c0c;
  padding: 1rem;
  border-radius: 4px;
  border-left: 4px solid #6a0dad;
}

/* Estilo para respuesta de ejecución */
pre.response-pre {
  background-color: #1a1a1a;
  color: #f8f8f2;
  border-left: 4px solid #3498db;
  max-height: 400px;
}

.textarea {
  min-height: 100px;
  resize: vertical;
}

.notification.is-success {
  border-left: 4px solid #48c78e;
}

/* Cards en modal de templates */
.card.is-clickable {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  height: 100%;
  border: 1px solid #e0e0e0;
}

.card.is-clickable:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(106, 13, 173, 0.2);
  border-color: #6a0dad;
}

.card.is-clickable .card-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card.is-clickable .content {
  flex-grow: 1;
}

.card.is-clickable hr {
  margin: 0.75rem 0;
  background-color: #6a0dad;
  height: 1px;
}

.tags {
  margin-top: 0.5rem;
}

/* Barra de progreso */
.progress {
  height: 12px;
  border-radius: 6px;
}

.progress.is-info::-webkit-progress-value {
  background-color: #6a0dad;
}

.progress.is-info::-moz-progress-bar {
  background-color: #6a0dad;
}

/* Botones con iconos */
.button .icon {
  margin-right: 8px;
}

/* Status tags */
.tag.is-success.is-light {
  background-color: #effaf3;
  color: #257942;
}

.tag.is-danger.is-light {
  background-color: #feecf0;
  color: #cc0f35;
}

.tag.is-warning.is-light {
  background-color: #fffbeb;
  color: #947600;
}

/* Botones en grupo */
.buttons .button {
  margin-right: 0.5rem;
  margin-bottom: 0.5rem;
}

.buttons .button:last-child {
  margin-right: 0;
}

/* Responsive */
@media (max-width: 768px) {
  .columns.is-vcentered {
    flex-direction: column;
  }
  
  .column.is-narrow {
    width: 100%;
    margin-top: 1rem;
  }
  
  .buttons {
    flex-wrap: wrap;
  }
  
  .button {
    margin-bottom: 0.5rem;
    flex: 1;
  }
}
</style>