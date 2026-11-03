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

const setMessage = (text, tone = 'info') => {
  messageBox.textContent = text;
  messageBox.className = `message ${tone}`;
};

const renderRagStatus = async () => {
  try {
    const response = await fetch('/api/rag/status');
    const payload = await response.json();
    ragStatus.catalogCount.textContent = payload.catalog_entries ?? '0';
    ragStatus.faissStatus.textContent = payload.faiss_index_exists && payload.codes_index_exists ? 'Sí' : 'No';
    ragStatus.providerName.textContent = (payload.provider || 'ollama').toUpperCase();
    ragStatus.detail.innerHTML = `
      <div>Modelo: ${payload.model || 'N/A'}</div>
      <div>Ollama: ${payload.ollama_url || 'N/A'}</div>
      <div>FAISS: ${payload.faiss_index_exists ? 'disponible' : 'sin índice'}</div>
    `;
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

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = document.getElementById('clinical-note').value.trim();
  if (!text) {
    setMessage('Escribe una nota clínica antes de codificar.', 'error');
    return;
  }

  const payload = {
    text,
    top_k: Number(topKSlider.value),
  };

  setMessage('Procesando nota con Ollama…', 'info');
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
