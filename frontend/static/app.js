const ragStatus = {
  catalogCount: document.getElementById('catalog-count'),
  faissStatus: document.getElementById('faiss-status'),
  providerName: document.getElementById('provider-name'),
  detail: document.getElementById('rag-detail'),
};

const topKSlider = document.getElementById('top-k');
const topKLabel = document.getElementById('top-k-label');
const form = document.getElementById('coding-form');
const messageBox = document.getElementById('message');
const resultsPanel = document.getElementById('results-panel');
const resultSummary = document.getElementById('result-summary');
const resultsList = document.getElementById('results-list');
const deploymentModeInputs = document.querySelectorAll('input[name="provider-mode"]');
const cloudConfig = document.getElementById('cloud-config');
const cloudProviderSelect = document.getElementById('cloud-provider');
const cloudModelInput = document.getElementById('cloud-model');

const setMessage = (text, tone = 'info') => {
  messageBox.textContent = text;
  messageBox.className = `message ${tone}`;
};

const getSelectedProviderMode = () => {
  const selected = document.querySelector('input[name="provider-mode"]:checked');
  return selected ? selected.value : 'local';
};

const getCloudModelDefaults = (provider = cloudProviderSelect.value || 'gemini') => {
  if (provider === 'gemini') return 'gemini-3.5-flash';
  if (provider === 'anthropic') return 'claude-3-5-sonnet-20241022';
  if (provider === 'openai') return 'gpt-4o-mini';
  return 'openai/gpt-4o-mini';
};

const syncRagStatusFromSelection = () => {
  const mode = getSelectedProviderMode();
  const providerName = mode === 'cloud' ? (cloudProviderSelect.value || 'openrouter') : 'ollama';
  const modelName = mode === 'cloud' ? (cloudModelInput.value || getCloudModelDefaults(providerName)) : 'mistral';

  ragStatus.providerName.textContent = providerName.toUpperCase();
  ragStatus.detail.innerHTML = `
    <div>Modelo: ${modelName}</div>
    <div>Ollama: http://localhost:11434</div>
    <div>Modo: ${mode === 'cloud' ? 'nube' : 'local'}</div>
    <div>FAISS: disponible</div>
  `;
};

const updateProviderModeUI = (mode = 'local', provider = cloudProviderSelect.value || 'gemini') => {
  deploymentModeInputs.forEach((input) => {
    input.checked = input.value === mode;
  });
  cloudConfig.classList.toggle('hidden', mode !== 'cloud');

  if (mode === 'cloud') {
    if (provider && cloudProviderSelect.value !== provider) {
      cloudProviderSelect.value = provider;
    }
    cloudModelInput.value = getCloudModelDefaults(provider);
  }

  syncRagStatusFromSelection();
};

const renderRagStatus = async () => {
  try {
    const response = await fetch('/api/rag/status');
    const payload = await response.json();
    const providerName = payload.provider || 'ollama';
    const providerMode = payload.provider_mode || (providerName === 'gemini' || providerName === 'openai' || providerName === 'anthropic' || providerName === 'openrouter' ? 'cloud' : 'local');
    ragStatus.catalogCount.textContent = payload.catalog_entries ?? '0';
    ragStatus.faissStatus.textContent = payload.faiss_index_exists && payload.codes_index_exists ? 'Sí' : 'No';
    ragStatus.providerName.textContent = providerName.toUpperCase();
    ragStatus.detail.innerHTML = `
      <div>Modelo: ${payload.model || 'N/A'}</div>
      <div>Ollama: ${payload.ollama_url || 'N/A'}</div>
      <div>Modo: ${providerMode === 'cloud' ? 'nube' : 'local'}</div>
      <div>FAISS: ${payload.faiss_index_exists ? 'disponible' : 'sin índice'}</div>
    `;
    updateProviderModeUI(providerMode, providerName);
  } catch (error) {
    ragStatus.detail.textContent = 'No se pudo obtener el estado del RAG.';
  }
};

const renderResults = (payload) => {
  const codes = payload.codes || [];
  resultsPanel.classList.remove('hidden');
  resultSummary.innerHTML = `
    <span class="chip">Códigos: ${codes.length}</span>
    <span class="chip">Proveedor: ${payload.provider || 'N/A'}</span>
    <span class="chip">Modelo: ${payload.model || 'N/A'}</span>
    <span class="chip">Latencia: ${(payload.latency_ms || 0).toFixed(1)} ms</span>
  `;

  resultsList.innerHTML = codes.length
    ? codes.map(item => `
        <article class="result-card">
          <strong>${item.code} · ${item.description}</strong>
          <div class="meta">Estado: ${item.state} · Confianza: ${(item.confidence || 0).toFixed(2)}</div>
          <div class="evidence"><strong>Evidencia:</strong> ${item.evidence || 'Sin evidencia'}</div>
          <div class="rationale">${item.rationale || 'Sin explicación'}</div>
        </article>
      `).join('')
    : '<p>No hubo códigos para esta nota.</p>';
};

topKSlider.addEventListener('input', (event) => {
  topKLabel.textContent = event.target.value;
});

deploymentModeInputs.forEach((input) => {
  input.addEventListener('change', (event) => {
    updateProviderModeUI(event.target.value);
  });
});

updateProviderModeUI('cloud', 'gemini');

cloudProviderSelect.addEventListener('change', () => {
  cloudModelInput.value = getCloudModelDefaults(cloudProviderSelect.value);
  syncRagStatusFromSelection();
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = document.getElementById('clinical-note').value.trim();
  if (!text) {
    setMessage('Escribe una nota clínica antes de codificar.', 'error');
    return;
  }

  const providerMode = getSelectedProviderMode();
  if (providerMode === 'cloud') {
    const cloudModel = cloudModelInput.value.trim();
    if (!cloudModel) {
      setMessage('Introduce el nombre del modelo cloud.', 'error');
      return;
    }
  }

  const cloudProvider = providerMode === 'cloud' ? cloudProviderSelect.value : 'ollama';
  const payload = {
    text,
    top_k: Number(topKSlider.value),
    provider_mode: providerMode,
    provider_name: cloudProvider,
    api_key: null,
    ollama_base_url: 'http://localhost:11434',
    llm_model: providerMode === 'cloud' ? cloudModelInput.value.trim() : 'mistral',
  };

  const providerLabel = providerMode === 'cloud' ? cloudProvider.toUpperCase() : 'OLLAMA';
  setMessage(`Procesando nota con ${providerLabel}…`, 'info');
  resultsPanel.classList.add('hidden');

  try {
    const response = await fetch('/api/code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Error al codificar la nota');
    }

    const data = await response.json();
    renderResults(data);
    setMessage('Procesamiento completado.', 'success');
  } catch (error) {
    setMessage(error.message || 'No se pudo procesar la nota.', 'error');
  }
});

renderRagStatus();
