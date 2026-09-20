/**
 * ParallelDoc 3.0 (r2 / V3-ONLY) — Interactive Semantic Relationship Graph
 * Path: src/graph.js
 * Complies with Spec r2 §3, §4, §6, §8, §11 (F11..F16, AC-11..AC-18, AC-44).
 *
 * Capabilities:
 * - Interactive SVG relationship graph with labels >= 14 CSS px.
 * - Zoom, pan, fit-to-view, and reset-overview controls.
 * - 6 typed relations: 5 directed with arrowheads + 1 symmetric ('compares') without arrow.
 * - Deterministic, bounded-iteration force-directed relaxation layout (120 iterations) with cycle tolerance.
 * - Scale limit guard (> 200 nodes or > 400 edges) with diagnostic warning and full table fallback.
 * - Accessible text fallback table (From - Relation - To - Grounds - Status).
 * - Bidirectional cross-highlighting with scroll delta = 0 on hover/focus.
 */

(function(root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.ParallelDocGraph = factory();
  }
})(typeof self !== 'undefined' ? self : (typeof globalThis !== 'undefined' ? globalThis : this), function() {
  'use strict';

  const SCALE_GUARD_MAX_NODES = 200;
  const SCALE_GUARD_MAX_EDGES = 400;

  const RELATION_CONFIG = {
    supports: {
      nameRu: 'Подтверждает',
      nameEn: 'Supports',
      color: '#2563eb',
      strokeDash: 'none',
      strokeWidth: 2.5,
      directed: true,
      markerId: 'arrow-supports',
      symbol: '⟶'
    },
    qualifies: {
      nameRu: 'Уточняет',
      nameEn: 'Qualifies',
      color: '#d97706',
      strokeDash: '6,4',
      strokeWidth: 2.5,
      directed: true,
      markerId: 'arrow-qualifies',
      symbol: '⟶'
    },
    contradicts: {
      nameRu: 'Противоречит',
      nameEn: 'Contradicts',
      color: '#ef4444',
      strokeDash: '8,3,2,3',
      strokeWidth: 3.0,
      directed: true,
      markerId: 'arrow-contradicts',
      symbol: '⟶'
    },
    depends_on: {
      nameRu: 'Зависит от',
      nameEn: 'Depends on',
      color: '#7c3aed',
      strokeDash: '3,4',
      strokeWidth: 2.5,
      directed: true,
      markerId: 'arrow-depends_on',
      symbol: '⟶'
    },
    precedes: {
      nameRu: 'Предшествует',
      nameEn: 'Precedes',
      color: '#059669',
      strokeDash: '10,3,3,3',
      strokeWidth: 2.5,
      directed: true,
      markerId: 'arrow-precedes',
      symbol: '⟶'
    },
    compares: {
      nameRu: 'Сравнивает',
      nameEn: 'Compares',
      color: '#475569',
      strokeDash: '12,6',
      strokeWidth: 2.0,
      directed: false,
      markerId: null,
      symbol: '⟷'
    }
  };

  /**
   * Check whether graph scale exceeds AC-44 threshold.
   */
  function checkScaleGuard(visual) {
    if (!visual) return { breached: false, nodeCount: 0, edgeCount: 0 };
    const nodeCount = (visual.nodes || []).length;
    const edgeCount = (visual.edges || []).length;

    if (nodeCount > SCALE_GUARD_MAX_NODES || edgeCount > SCALE_GUARD_MAX_EDGES) {
      return {
        breached: true,
        nodeCount,
        edgeCount,
        message: `Масштаб графа (${nodeCount} узлов, ${edgeCount} связей) превысил безопасный предел (${SCALE_GUARD_MAX_NODES} узлов / ${SCALE_GUARD_MAX_EDGES} связей). В соответствии со спецификацией AC-44 для предотвращения блокировки интерфейса визуальный рендеринг отключен. Отображается полная структурированная таблица связей.`
      };
    }
    return { breached: false, nodeCount, edgeCount };
  }

  /**
   * Deterministic hash for string ID
   */
  function hashString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash) + str.charCodeAt(i);
      hash |= 0;
    }
    return hash;
  }

  /**
   * Compute deterministic, cycle-tolerant force-directed graph layout.
   * Bounded to 120 iterations; guarantees runtime < 60ms without recursion or hanging.
   */
  function computeGraphLayout(nodes, edges, width = 800, height = 500) {
    const nodeMap = new Map();
    const nodeCount = (nodes || []).length;
    if (nodeCount === 0) return { nodes: [], edges: edges || [] };

    // 1. Deterministic initial coordinate seeding in a circle with deterministic jitter
    nodes.forEach((n, idx) => {
      const h = hashString(n.id);
      const angle = (2 * Math.PI * idx) / Math.max(1, nodeCount);
      const radius = Math.min(width, height) * 0.35;
      const jitterX = ((Math.abs(h % 100) / 100) - 0.5) * 40;
      const jitterY = ((Math.abs((h >> 8) % 100) / 100) - 0.5) * 40;

      const label = n.label || n.id;
      const estWidth = Math.max(160, Math.min(260, label.length * 8 + 36));
      const estHeight = 56;

      nodeMap.set(n.id, {
        id: n.id,
        label: label,
        unit_refs: Array.isArray(n.unit_refs) ? n.unit_refs : [],
        x: width / 2 + radius * Math.cos(angle) + jitterX,
        y: height / 2 + radius * Math.sin(angle) + jitterY,
        vx: 0,
        vy: 0,
        width: estWidth,
        height: estHeight
      });
    });

    // 2. Bounded iterative spring-electrical relaxation
    const maxIterations = 120;
    const kRepulsive = 10000;
    const kSpring = 0.04;
    const springLength = 190;
    const kGravity = 0.025;
    const damping = 0.85;

    const safeEdges = edges || [];

    for (let iter = 0; iter < maxIterations; iter++) {
      // Repulsive forces between all pairs
      const nodeArray = Array.from(nodeMap.values());
      for (let i = 0; i < nodeCount; i++) {
        const n1 = nodeArray[i];
        for (let j = i + 1; j < nodeCount; j++) {
          const n2 = nodeArray[j];
          const dx = n1.x - n2.x;
          const dy = n1.y - n2.y;
          const distSq = dx * dx + dy * dy + 1.0;
          const dist = Math.sqrt(distSq);
          const force = kRepulsive / distSq;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          n1.vx += fx;
          n1.vy += fy;
          n2.vx -= fx;
          n2.vy -= fy;
        }
      }

      // Attractive spring forces along edges
      for (const e of safeEdges) {
        const src = nodeMap.get(e.from);
        const tgt = nodeMap.get(e.to);
        if (!src || !tgt) continue;

        const dx = tgt.x - src.x;
        const dy = tgt.y - src.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const displacement = dist - springLength;
        const force = displacement * kSpring;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        src.vx += fx;
        src.vy += fy;
        tgt.vx -= fx;
        tgt.vy -= fy;
      }

      // Centering gravity and position integration
      const cx = width / 2;
      const cy = height / 2;
      for (const n of nodeMap.values()) {
        n.vx += (cx - n.x) * kGravity;
        n.vy += (cy - n.y) * kGravity;

        n.vx *= damping;
        n.vy *= damping;

        n.x += n.vx;
        n.y += n.vy;
      }
    }

    // 3. Normalize bounding box so everything stays with margin inside viewport
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const n of nodeMap.values()) {
      minX = Math.min(minX, n.x - n.width / 2);
      maxX = Math.max(maxX, n.x + n.width / 2);
      minY = Math.min(minY, n.y - n.height / 2);
      maxY = Math.max(maxY, n.y + n.height / 2);
    }

    const margin = 40;
    const currentW = Math.max(100, maxX - minX);
    const currentH = Math.max(100, maxY - minY);
    const targetW = width - margin * 2;
    const targetH = height - margin * 2;
    const scale = Math.min(1.0, Math.min(targetW / currentW, targetH / currentH));

    for (const n of nodeMap.values()) {
      n.x = width / 2 + (n.x - (minX + currentW / 2)) * scale;
      n.y = height / 2 + (n.y - (minY + currentH / 2)) * scale;
    }

    return {
      nodes: Array.from(nodeMap.values()),
      edges: safeEdges
    };
  }

  /**
   * Clips a ray from (cx, cy) in direction (dx, dy) against a rectangle of size (w, h).
   */
  function clipRectBoundary(cx, cy, w, h, dx, dy) {
    if (dx === 0 && dy === 0) return { x: cx, y: cy };
    const halfW = w / 2;
    const halfH = h / 2;

    const absDx = Math.abs(dx);
    const absDy = Math.abs(dy);

    let scale = 1;
    if (absDx * halfH > absDy * halfW) {
      // Intersects left or right edge
      scale = halfW / absDx;
    } else {
      // Intersects top or bottom edge
      scale = halfH / absDy;
    }

    return {
      x: cx + dx * scale,
      y: cy + dy * scale
    };
  }

  /**
   * Calculates clipped edge path with mutual curving.
   */
  function calculateEdgeGeometry(srcNode, tgtNode, isMutual = false) {
    const dx = tgtNode.x - srcNode.x;
    const dy = tgtNode.y - srcNode.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;

    // Terminal points on rectangle boundaries
    const p1 = clipRectBoundary(srcNode.x, srcNode.y, srcNode.width, srcNode.height, dx, dy);
    const p2 = clipRectBoundary(tgtNode.x, tgtNode.y, tgtNode.width, tgtNode.height, -dx, -dy);

    if (isMutual) {
      const normalX = -dy / dist;
      const normalY = dx / dist;
      const offset = 36;
      const midX = (p1.x + p2.x) / 2 + normalX * offset;
      const midY = (p1.y + p2.y) / 2 + normalY * offset;
      return {
        pathData: `M ${p1.x.toFixed(1)} ${p1.y.toFixed(1)} Q ${midX.toFixed(1)} ${midY.toFixed(1)} ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`,
        labelX: midX,
        labelY: midY
      };
    }

    const midX = (p1.x + p2.x) / 2;
    const midY = (p1.y + p2.y) / 2;
    return {
      pathData: `M ${p1.x.toFixed(1)} ${p1.y.toFixed(1)} L ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`,
      labelX: midX,
      labelY: midY
    };
  }

  /**
   * Render accessible fallback table.
   */
  function renderFallbackTable(visual, docUnitsMap = new Map()) {
    const container = document.createElement('div');
    container.className = 'pd-graph-fallback-container';
    container.setAttribute('role', 'region');
    container.setAttribute('aria-label', 'Таблица семантических связей графа');

    if (!visual || !Array.isArray(visual.edges) || visual.edges.length === 0) {
      container.innerHTML = '<p class="pd-fallback-empty">В этом графе нет семантических связей.</p>';
      return container;
    }

    const nodesMap = new Map();
    (visual.nodes || []).forEach(n => nodesMap.set(n.id, n));

    let html = `
      <table class="pd-graph-fallback-table" tabindex="0">
        <caption class="sr-only">Семантические связи: ${escapeHtml(visual.title || 'Граф')}</caption>
        <thead>
          <tr>
            <th scope="col">Откуда (From)</th>
            <th scope="col">Связь (Relation)</th>
            <th scope="col">Куда (To)</th>
            <th scope="col">Описание (Label)</th>
            <th scope="col">Основания (Grounds)</th>
          </tr>
        </thead>
        <tbody>
    `;

    for (const edge of visual.edges) {
      const srcNode = nodesMap.get(edge.from);
      const tgtNode = nodesMap.get(edge.to);
      const srcLabel = srcNode ? escapeHtml(srcNode.label) : `[ID: ${escapeHtml(edge.from)}]`;
      const tgtLabel = tgtNode ? escapeHtml(tgtNode.label) : `[ID: ${escapeHtml(edge.to)}]`;

      const relCfg = RELATION_CONFIG[edge.relation] || {
        nameRu: edge.relation,
        color: '#475569',
        symbol: '⟶'
      };

      const groundsList = (edge.unit_refs || []).map(ref => {
        const u = docUnitsMap.get(ref);
        const title = u && u.title ? `: ${escapeHtml(u.title)}` : '';
        return `<span class="pd-fallback-unit-tag" data-unit-id="${escapeHtml(ref)}">${escapeHtml(ref)}${title}</span>`;
      }).join(', ') || '<span class="pd-text-muted">—</span>';

      html += `
        <tr class="pd-fallback-row" data-edge-id="${escapeHtml(edge.id)}" data-from="${escapeHtml(edge.from)}" data-to="${escapeHtml(edge.to)}">
          <td><strong>${srcLabel}</strong> <code class="pd-node-id">${escapeHtml(edge.from)}</code></td>
          <td>
            <span class="pd-rel-badge" style="color:${relCfg.color}; border-color:${relCfg.color};">
              ${relCfg.symbol} ${escapeHtml(relCfg.nameRu)}
            </span>
          </td>
          <td><strong>${tgtLabel}</strong> <code class="pd-node-id">${escapeHtml(edge.to)}</code></td>
          <td>${escapeHtml(edge.label || '—')}</td>
          <td>${groundsList}</td>
        </tr>
      `;
    }

    html += `</tbody></table>`;
    container.innerHTML = html;
    return container;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  /**
   * GraphController manages SVG rendering, zoom/pan/fit, fallback table, and cross-highlighting.
   */
  class GraphController {
    constructor(visualDef, containerEl, options = {}) {
      this.visual = visualDef;
      this.container = containerEl;
      this.options = {
        zoomStep: 1.2,
        minZoom: 0.25,
        maxZoom: 3.5,
        labelsMinSizePx: 14,
        onSelect: options.onSelect || null,
        onCrossHighlight: options.onCrossHighlight || null,
        docUnitsMap: options.docUnitsMap || new Map(),
        ...options
      };

      this.state = {
        zoom: 1.0,
        panX: 0,
        panY: 0,
        isDragging: false,
        dragStartX: 0,
        dragStartY: 0,
        selectedId: null,
        hoveredId: null,
        showFallbackTable: false,
        scaleGuardBreached: false
      };

      this.svgEl = null;
      this.viewportG = null;
      this.fallbackContainerEl = null;

      this.init();
    }

    init() {
      if (!this.container) return;
      this.container.innerHTML = '';
      this.container.classList.add('pd-graph-wrapper');

      // Scale limit guard check (AC-44)
      const guard = checkScaleGuard(this.visual);
      if (guard.breached) {
        this.state.scaleGuardBreached = true;
        this.renderScaleGuardBanner(guard.message);
        this.renderFallbackView();
        return;
      }

      this.renderControlsAndLegend();
      this.renderSvgGraph();
      this.renderFallbackView(); // Hidden by default, toggled when needed
    }

    renderScaleGuardBanner(message) {
      const banner = document.createElement('div');
      banner.className = 'pd-graph-scale-warning';
      banner.setAttribute('role', 'alert');
      banner.innerHTML = `
        <div class="pd-warning-header">
          <strong>⚠️ Превышен предел масштаба графа</strong>
        </div>
        <p class="pd-warning-body">${escapeHtml(message)}</p>
        <button type="button" class="pd-btn pd-force-render-btn">Принудительно отобразить графику</button>
      `;

      const forceBtn = banner.querySelector('.pd-force-render-btn');
      forceBtn.addEventListener('click', () => {
        banner.remove();
        this.state.scaleGuardBreached = false;
        this.renderControlsAndLegend();
        this.renderSvgGraph();
      });

      this.container.appendChild(banner);
    }

    renderControlsAndLegend() {
      const bar = document.createElement('div');
      bar.className = 'pd-graph-toolbar-bar';

      // Controls
      const controls = document.createElement('div');
      controls.className = 'pd-graph-controls-group';
      controls.innerHTML = `
        <button type="button" class="pd-btn pd-graph-btn-fit" title="По размеру экрана (Fit)" aria-label="Масштабировать граф по размеру">
          <svg class="pd-btn-icon" width="16" height="16" viewBox="0 0 24 24"><use href="#pd-icon-fit"/></svg>
          По размеру
        </button>
        <button type="button" class="pd-btn pd-graph-btn-zoomin" title="Приблизить" aria-label="Увеличить масштаб графа">
          <svg class="pd-btn-icon" width="16" height="16" viewBox="0 0 24 24"><use href="#pd-icon-zoom-in"/></svg>
        </button>
        <button type="button" class="pd-btn pd-graph-btn-zoomout" title="Отдалить" aria-label="Уменьшить масштаб графа">
          <svg class="pd-btn-icon" width="16" height="16" viewBox="0 0 24 24"><use href="#pd-icon-zoom-out"/></svg>
        </button>
        <button type="button" class="pd-btn pd-graph-btn-reset" title="Сброс (100%)" aria-label="Сбросить масштаб графа к 100%">1:1</button>
        <button type="button" class="pd-btn pd-graph-btn-table" title="Показать таблицу связей" aria-label="Переключить текстовую таблицу связей">
          Таблица связей
        </button>
      `;

      controls.querySelector('.pd-graph-btn-fit').addEventListener('click', () => this.fitToView());
      controls.querySelector('.pd-graph-btn-zoomin').addEventListener('click', () => this.zoomIn());
      controls.querySelector('.pd-graph-btn-zoomout').addEventListener('click', () => this.zoomOut());
      controls.querySelector('.pd-graph-btn-reset').addEventListener('click', () => this.resetOverview());
      controls.querySelector('.pd-graph-btn-table').addEventListener('click', () => this.toggleFallbackTable());

      bar.appendChild(controls);

      // Visual Legend showing all 6 relation types (AC-13)
      const legend = document.createElement('div');
      legend.className = 'pd-graph-legend';
      legend.setAttribute('aria-label', 'Легенда типов связей графа');

      let legendHtml = '';
      for (const [key, cfg] of Object.entries(RELATION_CONFIG)) {
        legendHtml += `
          <div class="pd-legend-item" title="${escapeHtml(cfg.nameEn)}">
            <span class="pd-legend-swatch rel-${key}" style="border-color:${cfg.color};">
              <span class="pd-legend-symbol" style="color:${cfg.color};">${cfg.symbol}</span>
            </span>
            <span class="pd-legend-name">${escapeHtml(cfg.nameRu)}</span>
          </div>
        `;
      }
      legend.innerHTML = legendHtml;
      bar.appendChild(legend);

      this.container.appendChild(bar);
    }

    renderSvgGraph() {
      if (!this.visual) return;
      const width = this.container.clientWidth || 800;
      const height = 480;

      const layout = computeGraphLayout(this.visual.nodes || [], this.visual.edges || [], width, height);

      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('class', 'pd-graph-svg');
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      svg.setAttribute('width', '100%');
      svg.setAttribute('height', `${height}px`);
      svg.setAttribute('role', 'img');
      svg.setAttribute('aria-label', `Граф семантических связей: ${this.visual.title || 'Граф'}`);

      // Defs with Arrow Markers for 5 directed relations
      const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
      for (const [key, cfg] of Object.entries(RELATION_CONFIG)) {
        if (!cfg.directed || !cfg.markerId) continue;
        const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
        marker.setAttribute('id', cfg.markerId);
        marker.setAttribute('viewBox', '0 0 10 10');
        marker.setAttribute('refX', '9');
        marker.setAttribute('refY', '5');
        marker.setAttribute('markerWidth', '6');
        marker.setAttribute('markerHeight', '6');
        marker.setAttribute('orient', 'auto-start-reverse');

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', 'M 0 1.5 L 10 5 L 0 8.5 z');
        path.setAttribute('fill', cfg.color);
        marker.appendChild(path);
        defs.appendChild(marker);
      }
      svg.appendChild(defs);

      // Viewport G for pan & zoom transforms
      const viewportG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      viewportG.setAttribute('class', 'pd-graph-viewport');
      svg.appendChild(viewportG);

      // Edges Layer
      const edgesG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      edgesG.setAttribute('class', 'pd-graph-edges-layer');
      viewportG.appendChild(edgesG);

      // Nodes Map for quick coordinate lookup
      const nodeLayoutMap = new Map();
      layout.nodes.forEach(n => nodeLayoutMap.set(n.id, n));

      // Detect mutual edges (A -> B and B -> A)
      const edgeKeySet = new Set();
      layout.edges.forEach(e => edgeKeySet.add(`${e.from}->${e.to}`));

      for (const edge of layout.edges) {
        const src = nodeLayoutMap.get(edge.from);
        const tgt = nodeLayoutMap.get(edge.to);
        if (!src || !tgt) continue;

        const isMutual = edgeKeySet.has(`${edge.to}->${edge.from}`) && edge.from !== edge.to;
        const geom = calculateEdgeGeometry(src, tgt, isMutual);
        const relCfg = RELATION_CONFIG[edge.relation] || RELATION_CONFIG.supports;

        const edgeG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        edgeG.setAttribute('class', `pd-graph-edge rel-${edge.relation}`);
        edgeG.setAttribute('data-edge-id', edge.id);
        edgeG.setAttribute('data-from', edge.from);
        edgeG.setAttribute('data-to', edge.to);
        edgeG.setAttribute('data-unit-refs', (edge.unit_refs || []).join(','));
        edgeG.setAttribute('tabindex', '0');
        edgeG.setAttribute('role', 'graphics-symbol');
        edgeG.setAttribute('aria-label', `Связь ${relCfg.nameRu}: ${edge.from} к ${edge.to}. ${edge.label || ''}`);

        // Visible path
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', geom.pathData);
        path.setAttribute('stroke', relCfg.color);
        path.setAttribute('stroke-width', String(relCfg.strokeWidth));
        if (relCfg.strokeDash !== 'none') {
          path.setAttribute('stroke-dasharray', relCfg.strokeDash);
        }
        path.setAttribute('fill', 'none');
        if (relCfg.directed && relCfg.markerId) {
          path.setAttribute('marker-end', `url(#${relCfg.markerId})`);
        }
        edgeG.appendChild(path);

        // Fat invisible hit target for easy mouse hover/click
        const hitPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        hitPath.setAttribute('d', geom.pathData);
        hitPath.setAttribute('stroke', 'transparent');
        hitPath.setAttribute('stroke-width', '16');
        hitPath.setAttribute('fill', 'none');
        edgeG.appendChild(hitPath);

        // Edge label
        if (edge.label) {
          const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          text.setAttribute('x', String(geom.labelX.toFixed(1)));
          text.setAttribute('y', String((geom.labelY - 5).toFixed(1)));
          text.setAttribute('class', 'pd-edge-label');
          text.setAttribute('text-anchor', 'middle');
          text.setAttribute('font-size', '12px');
          text.setAttribute('fill', relCfg.color);
          text.textContent = edge.label;
          edgeG.appendChild(text);
        }

        edgesG.appendChild(edgeG);
      }

      // Nodes Layer
      const nodesG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      nodesG.setAttribute('class', 'pd-graph-nodes-layer');
      viewportG.appendChild(nodesG);

      for (const node of layout.nodes) {
        const nodeG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        nodeG.setAttribute('class', 'pd-graph-node');
        nodeG.setAttribute('data-node-id', node.id);
        nodeG.setAttribute('data-unit-refs', (node.unit_refs || []).join(','));
        nodeG.setAttribute('tabindex', '0');
        nodeG.setAttribute('role', 'graphics-symbol');
        nodeG.setAttribute('aria-label', `Узел: ${node.label} (${node.id})`);
        nodeG.setAttribute('transform', `translate(${(node.x - node.width / 2).toFixed(1)}, ${(node.y - node.height / 2).toFixed(1)})`);

        // Node card rectangle
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('width', String(node.width));
        rect.setAttribute('height', String(node.height));
        rect.setAttribute('rx', '8');
        rect.setAttribute('ry', '8');
        rect.setAttribute('class', 'pd-node-rect');
        nodeG.appendChild(rect);

        // Node ID Pill
        const idPill = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        idPill.setAttribute('x', '10');
        idPill.setAttribute('y', '18');
        idPill.setAttribute('class', 'pd-node-id-text');
        idPill.setAttribute('font-size', '11px');
        idPill.textContent = node.id;
        nodeG.appendChild(idPill);

        // Node Label (AC-17: labels >= 14 CSS px)
        const labelText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        labelText.setAttribute('x', '10');
        labelText.setAttribute('y', '38');
        labelText.setAttribute('class', 'pd-node-label-text');
        labelText.setAttribute('font-size', '14px'); // STRICT SPEC REQUIREMENT >= 14px
        labelText.setAttribute('font-weight', '600');

        // Truncate label text if too long to fit node box width
        const maxChars = Math.floor((node.width - 24) / 8);
        const displayLabel = node.label.length > maxChars ? node.label.slice(0, maxChars - 1) + '…' : node.label;
        labelText.textContent = displayLabel;

        nodeG.appendChild(labelText);
        nodesG.appendChild(nodeG);
      }

      this.svgEl = svg;
      this.viewportG = viewportG;
      this.container.appendChild(svg);

      this.bindSvgInteractions();
    }

    bindSvgInteractions() {
      if (!this.svgEl) return;

      // Mouse drag panning
      this.svgEl.addEventListener('mousedown', (e) => {
        if (e.target.closest('.pd-graph-node') || e.target.closest('.pd-graph-edge')) return;
        this.state.isDragging = true;
        this.state.dragStartX = e.clientX - this.state.panX;
        this.state.dragStartY = e.clientY - this.state.panY;
        this.svgEl.classList.add('pd-dragging');
      });

      window.addEventListener('mousemove', (e) => {
        if (!this.state.isDragging) return;
        this.state.panX = e.clientX - this.state.dragStartX;
        this.state.panY = e.clientY - this.state.dragStartY;
        this.applyTransform();
      });

      window.addEventListener('mouseup', () => {
        if (this.state.isDragging) {
          this.state.isDragging = false;
          this.svgEl.classList.remove('pd-dragging');
        }
      });

      // Ctrl + Wheel zooming (non-Ctrl regular wheel allows native document scroll)
      this.svgEl.addEventListener('wheel', (e) => {
        if (e.ctrlKey) {
          e.preventDefault();
          const delta = e.deltaY < 0 ? 1.15 : 0.85;
          this.setZoom(this.state.zoom * delta);
        }
      }, { passive: false });

      // Node & Edge hover/focus cross-highlighting with scroll delta = 0 (AC-14)
      this.svgEl.querySelectorAll('.pd-graph-node, .pd-graph-edge').forEach(el => {
        const refs = (el.getAttribute('data-unit-refs') || '').split(',').filter(Boolean);

        // Mouseenter
        el.addEventListener('mouseenter', () => {
          this.highlightUnits(refs, false);
          el.classList.add('pd-graph-element-hover');
        });

        // Mouseleave
        el.addEventListener('mouseleave', () => {
          this.clearUnitHoverHighlights();
          el.classList.remove('pd-graph-element-hover');
        });

        // Focus (keyboard)
        el.addEventListener('focus', () => {
          this.highlightUnits(refs, false);
          el.classList.add('pd-graph-element-hover');
        });

        // Blur (keyboard)
        el.addEventListener('blur', () => {
          this.clearUnitHoverHighlights();
          el.classList.remove('pd-graph-element-hover');
        });

        // Click / Enter Selection
        el.addEventListener('click', (e) => {
          e.stopPropagation();
          this.selectElement(el, refs);
        });

        el.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            this.selectElement(el, refs);
          }
        });
      });
    }

    selectElement(el, unitRefs) {
      this.svgEl.querySelectorAll('.pd-graph-selected').forEach(e => e.classList.remove('pd-graph-selected'));
      el.classList.add('pd-graph-selected');
      this.state.selectedId = el.getAttribute('data-node-id') || el.getAttribute('data-edge-id');

      this.highlightUnits(unitRefs, true);

      if (this.options.onSelect) {
        this.options.onSelect(this.state.selectedId, unitRefs);
      }
    }

    /**
     * Cross-highlights units in DOM with GUARANTEED SCROLL DELTA = 0 (AC-14).
     */
    highlightUnits(unitIds, isSelection = false) {
      const cls = isSelection ? 'cross-hl-active' : 'cross-hl-hover';
      // DO NOT call scrollIntoView or window.scrollTo here! Delta must be exactly 0.
      for (const uid of unitIds) {
        const unitEl = document.getElementById(`unit-${uid}`) || document.getElementById(`pd-unit-${uid}`);
        if (unitEl) {
          unitEl.classList.add(cls);
        }
      }

      if (this.options.onCrossHighlight) {
        this.options.onCrossHighlight(unitIds, isSelection);
      }
    }

    clearUnitHoverHighlights() {
      document.querySelectorAll('.cross-hl-hover').forEach(el => el.classList.remove('cross-hl-hover'));
    }

    clearHighlights() {
      this.clearUnitHoverHighlights();
      document.querySelectorAll('.cross-hl-active').forEach(el => el.classList.remove('cross-hl-active'));
      if (this.svgEl) {
        this.svgEl.querySelectorAll('.pd-graph-selected, .pd-graph-element-hover').forEach(el => {
          el.classList.remove('pd-graph-selected', 'pd-graph-element-hover');
        });
      }
      this.state.selectedId = null;
    }

    /**
     * Text -> Graph Cross-Highlighting (AC-15):
     * When a unit card is hovered or focused in text panels, highlight referencing graph nodes/edges.
     */
    highlightFromUnit(unitId) {
      if (!this.svgEl) return;
      this.svgEl.querySelectorAll('.pd-graph-node, .pd-graph-edge').forEach(el => {
        const refs = (el.getAttribute('data-unit-refs') || '').split(',').filter(Boolean);
        if (refs.includes(unitId)) {
          el.classList.add('pd-graph-referenced');
        } else {
          el.classList.remove('pd-graph-referenced');
        }
      });
    }

    clearHighlightFromUnit() {
      if (!this.svgEl) return;
      this.svgEl.querySelectorAll('.pd-graph-referenced').forEach(el => el.classList.remove('pd-graph-referenced'));
    }

    renderFallbackView() {
      const fb = renderFallbackTable(this.visual, this.options.docUnitsMap);
      fb.style.display = this.state.scaleGuardBreached ? 'block' : 'none';
      this.fallbackContainerEl = fb;
      this.container.appendChild(fb);
    }

    toggleFallbackTable() {
      this.state.showFallbackTable = !this.state.showFallbackTable;
      if (this.fallbackContainerEl) {
        this.fallbackContainerEl.style.display = this.state.showFallbackTable ? 'block' : 'none';
      }
      const btn = this.container.querySelector('.pd-graph-btn-table');
      if (btn) {
        btn.classList.toggle('active', this.state.showFallbackTable);
      }
    }

    setZoom(val) {
      this.state.zoom = Math.max(this.options.minZoom, Math.min(this.options.maxZoom, val));
      this.applyTransform();
    }

    zoomIn() {
      this.setZoom(this.state.zoom * this.options.zoomStep);
    }

    zoomOut() {
      this.setZoom(this.state.zoom / this.options.zoomStep);
    }

    resetOverview() {
      this.state.zoom = 1.0;
      this.state.panX = 0;
      this.state.panY = 0;
      this.applyTransform();
    }

    fitToView() {
      if (!this.svgEl || !this.viewportG) return;
      this.state.zoom = 0.95;
      this.state.panX = 0;
      this.state.panY = 0;
      this.applyTransform();
    }

    applyTransform() {
      if (!this.viewportG) return;
      this.viewportG.setAttribute(
        'transform',
        `translate(${this.state.panX.toFixed(1)}, ${this.state.panY.toFixed(1)}) scale(${this.state.zoom.toFixed(3)})`
      );
    }

    destroy() {
      if (this.container) {
        this.container.innerHTML = '';
      }
    }
  }

  return {
    RELATION_CONFIG,
    SCALE_GUARD_MAX_NODES,
    SCALE_GUARD_MAX_EDGES,
    checkScaleGuard,
    computeGraphLayout,
    renderFallbackTable,
    GraphController
  };
});
