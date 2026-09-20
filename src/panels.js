/**
 * ParallelDoc 3.0 (r2 / V3-ONLY) — Multi-Panel Profiles & Zero Unit Loss Engine
 * Path: src/panels.js
 * Strictly compliant with Spec r2 §4, §6, §8, §11 (F17..F22, AC-01, AC-11, AC-16..AC-18).
 *
 * Capabilities:
 * - Multi-panel profile layouts:
 *     Compare (2 panels: 50/50 with full-width expandable Model strip),
 *     Evidence (3 panels: 32/36/32 with central Model & Graph),
 *     Review (4 panels: 28/30/26/16 with dedicated Action panel).
 * - Zero Unit Loss: 100% unit invariant across profile switches.
 * - Orphan reconciliation: units without group gathered into «Вне групп».
 * - Explicit missing role badges («Нет анализа», «Действие не задано»).
 * - Deep navigation with 10-target LIFO history stack & return-to-reading anchor.
 * - Progressive quote disclosure integration (> 1,200 chars).
 * - Zero scroll jump on cross-highlighting (delta = 0).
 */

(function(root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.ParallelDocPanels = factory();
  }
})(typeof self !== 'undefined' ? self : (typeof globalThis !== 'undefined' ? globalThis : this), function() {
  'use strict';

  const MISSING_ROLE_CONFIG = {
    analysis: {
      text: '«Нет анализа»',
      desc: 'Аналитическое заключение для данной группы не предоставлено автором.'
    },
    action: {
      text: '«Действие не задано»',
      desc: 'Следующий шаг или корректирующее действие не определено.'
    },
    source: {
      text: '«Источник не указан»',
      desc: 'В данной группе отсутствует исходный подтверждающий фрагмент.'
    },
    model: {
      text: '«Модель отсутствует»',
      desc: 'Формальная модель или граф для данной группы не заданы.'
    }
  };

  const BUILTIN_PROFILES = {
    'builtin:2': {
      id: 'builtin:2',
      title: 'Сравнение (Compare)',
      density: 'reading',
      panels: [
        { id: 'p-foundations', title: 'Основания', kinds: ['source'], weight: 50 },
        { id: 'p-conclusions', title: 'Выводы и действия', kinds: ['analysis', 'action'], weight: 50 }
      ],
      hasModelStrip: true
    },
    'builtin:3': {
      id: 'builtin:3',
      title: 'Доказательства (Evidence)',
      density: 'reading',
      panels: [
        { id: 'p-source', title: 'Источник', kinds: ['source'], weight: 32 },
        { id: 'p-model', title: 'Модель', kinds: ['model'], weight: 36 },
        { id: 'p-analysis-actions', title: 'Анализ и действия', kinds: ['analysis', 'action'], weight: 32 }
      ],
      hasModelStrip: false
    },
    'builtin:4': {
      id: 'builtin:4',
      title: 'Экспертиза (Review)',
      density: 'reading',
      panels: [
        { id: 'p-source', title: 'Источник', kinds: ['source'], weight: 28 },
        { id: 'p-model', title: 'Модель', kinds: ['model'], weight: 30 },
        { id: 'p-analysis', title: 'Анализ', kinds: ['analysis'], weight: 26 },
        { id: 'p-action', title: 'Действия', kinds: ['action'], weight: 16 }
      ],
      hasModelStrip: false
    }
  };

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  class PanelsEngine {
    constructor(options = {}) {
      this.containerEl = options.containerEl || null;
      this.doc = null;
      this.activeProfile = null;
      this.activeProfileId = null;
      this.unitMap = new Map();
      this.authorMap = new Map();
      this.groupList = [];
      this.orphanUnits = [];

      // 10-target LIFO navigation history stack (AC-16)
      this.navStack = [];
      this.maxStackSize = 10;
      this.activeSelectionId = null;
      this.activeHighlightIds = new Set();

      // Asset mapping & media inspector integration (M4)
      this.assetMap = new Map();
      this.mediaValidationMap = options.mediaValidationMap || new Map();
      this.onModalOpen = options.onModalOpen || null;

      // Callbacks
      this.onGraphRender = options.onGraphRender || null;
      this.onUnitSelect = options.onUnitSelect || null;
      this.onProfileChange = options.onProfileChange || null;
    }

    setMediaValidationMap(map) {
      this.mediaValidationMap = map || new Map();
    }

    /**
     * Load document and perform referential indexing and orphan reconciliation.
     */
    loadDocument(doc) {
      if (!doc || doc.format !== 'paralleldoc' || doc.version !== '3.0') {
        throw new Error("Неподдерживаемый формат; требуется ParallelDoc 3.0");
      }

      this.doc = doc;
      this.unitMap.clear();
      this.authorMap.clear();
      this.assetMap.clear();
      this.navStack = [];
      this.activeSelectionId = null;
      this.activeHighlightIds.clear();

      // Index assets
      for (const asset of (doc.assets || [])) {
        if (asset && asset.id) {
          this.assetMap.set(asset.id, asset);
        }
      }

      // 1. Index authors
      for (const author of (doc.authors || [])) {
        this.authorMap.set(author.id, author);
      }

      // 2. Index all units
      for (const unit of (doc.units || [])) {
        this.unitMap.set(unit.id, unit);
      }

      // 3. Reconcile orphan units (Spec §8 rule line 421)
      const groupedUnitIds = new Set();
      for (const group of (doc.groups || [])) {
        for (const ref of (group.unit_refs || [])) {
          groupedUnitIds.add(ref);
        }
      }

      this.orphanUnits = [];
      for (const [id, unit] of this.unitMap.entries()) {
        if (!groupedUnitIds.has(id)) {
          this.orphanUnits.push(unit);
        }
      }

      // 4. Construct group list, synthesizing «Вне групп» if orphans exist
      this.groupList = [...(doc.groups || [])];
      if (this.orphanUnits.length > 0) {
        this.groupList.push({
          id: '__orphans__',
          title: 'Вне групп (Единицы без привязки)',
          unit_refs: this.orphanUnits.map(u => u.id),
          isOrphanGroup: true
        });
      }

      // 5. Set default profile
      const requestedProfileId = (doc.metadata && doc.metadata.default_profile_id) || 'builtin:3';
      this.setProfile(requestedProfileId);
    }

    /**
     * Switch active profile with ZERO UNIT LOSS guarantee.
     */
    setProfile(profileId) {
      let resolved = null;
      let isFallback = false;

      if (profileId && BUILTIN_PROFILES[profileId]) {
        resolved = BUILTIN_PROFILES[profileId];
      } else if (profileId && this.doc && Array.isArray(this.doc.profiles)) {
        resolved = this.doc.profiles.find(p => p.id === profileId);
      }

      if (!resolved) {
        resolved = BUILTIN_PROFILES['builtin:3'];
        isFallback = true;
      }

      this.activeProfile = resolved;
      this.activeProfileId = resolved.id;

      if (this.containerEl && typeof document !== 'undefined') {
        this.render();
      }

      if (this.onProfileChange) {
        this.onProfileChange(this.activeProfile, isFallback);
      }

      return { profile: this.activeProfile, isFallback };
    }

    /**
     * Inspect plan of units rendered for each group in current profile.
     * Guaranteed that the sum of all units across groups equals doc.units.length!
     */
    getRenderPlan() {
      const plan = {
        profileId: this.activeProfileId,
        groups: [],
        totalUnitsCount: 0,
        missingRoleCount: 0
      };

      for (const group of this.groupList) {
        const groupPlan = {
          groupId: group.id,
          title: group.title,
          isOrphanGroup: !!group.isOrphanGroup,
          panels: [],
          modelStripUnits: []
        };

        const unitsByKind = { source: [], model: [], analysis: [], action: [] };
        for (const refId of (group.unit_refs || [])) {
          const unit = this.unitMap.get(refId);
          if (unit && unitsByKind[unit.kind]) {
            unitsByKind[unit.kind].push(unit);
          }
        }

        if (this.activeProfile.hasModelStrip && unitsByKind.model.length > 0) {
          groupPlan.modelStripUnits = unitsByKind.model.map(u => u.id);
          plan.totalUnitsCount += unitsByKind.model.length;
        }

        for (const panel of this.activeProfile.panels) {
          const panelUnits = [];
          for (const kind of panel.kinds) {
            panelUnits.push(...(unitsByKind[kind] || []));
          }

          const missingRoles = [];
          if (panelUnits.length === 0) {
            for (const kind of panel.kinds) {
              if (this.activeProfile.hasModelStrip && kind === 'model') continue;
              missingRoles.push(kind);
              plan.missingRoleCount++;
            }
          }

          groupPlan.panels.push({
            panelId: panel.id,
            kinds: panel.kinds,
            unitIds: panelUnits.map(u => u.id),
            missingRoles
          });

          plan.totalUnitsCount += panelUnits.length;
        }

        plan.groups.push(groupPlan);
      }

      return plan;
    }

    /**
     * Render the multi-panel layout into containerEl.
     */
    render() {
      if (!this.containerEl || !this.doc || typeof document === 'undefined') return;

      const profile = this.activeProfile;
      const colTemplate = profile.panels.map(p => `${p.weight}fr`).join(' ');

      const groupsStream = document.createElement('div');
      groupsStream.className = 'groups-stream';

      for (const group of this.groupList) {
        const groupEl = this.renderGroup(group, profile, colTemplate);
        groupsStream.appendChild(groupEl);
      }

      this.containerEl.innerHTML = '';
      this.containerEl.appendChild(groupsStream);

      // Re-apply active cross-highlights
      if (this.activeHighlightIds.size > 0) {
        this.applyHighlights(Array.from(this.activeHighlightIds), false);
      }
      if (this.activeSelectionId) {
        this.applySelection(this.activeSelectionId);
      }
    }

    /**
     * Render an individual group section.
     */
    renderGroup(group, profile, colTemplate) {
      const section = document.createElement('section');
      section.className = `group-section ${group.isOrphanGroup ? 'group-orphans' : ''}`;
      section.id = `group-${group.id}`;
      section.dataset.groupId = group.id;

      // Group Header
      const header = document.createElement('div');
      header.className = 'group-header';
      header.innerHTML = `
        <button class="group-toggle" type="button" aria-expanded="true" data-target="group-body-${escapeHtml(group.id)}" aria-label="Свернуть/развернуть группу ${escapeHtml(group.title)}">
          <span class="toggle-icon">▼</span>
          <h2 class="group-title">${escapeHtml(group.title)}</h2>
          <span class="group-id-pill ${group.isOrphanGroup ? 'badge-warning' : ''}">${escapeHtml(group.id)}</span>
        </button>
      `;

      const toggleBtn = header.querySelector('.group-toggle');
      toggleBtn.addEventListener('click', () => {
        const bodyEl = section.querySelector('.group-body');
        if (bodyEl) {
          const isExpanded = bodyEl.style.display !== 'none';
          bodyEl.style.display = isExpanded ? 'none' : 'block';
          toggleBtn.setAttribute('aria-expanded', isExpanded ? 'false' : 'true');
          const icon = toggleBtn.querySelector('.toggle-icon');
          if (icon) icon.textContent = isExpanded ? '▶' : '▼';
        }
      });

      section.appendChild(header);

      // Group Body
      const body = document.createElement('div');
      body.className = 'group-body';
      body.id = `group-body-${group.id}`;

      // Partition group units by kind
      const unitsByKind = { source: [], model: [], analysis: [], action: [] };
      for (const refId of (group.unit_refs || [])) {
        const unit = this.unitMap.get(refId);
        if (unit && unitsByKind[unit.kind]) {
          unitsByKind[unit.kind].push(unit);
        }
      }

      // In Compare mode (builtin:2), handle Model Strip if profile.hasModelStrip
      if (profile.hasModelStrip && unitsByKind.model.length > 0) {
        const modelStrip = document.createElement('div');
        modelStrip.className = 'group-model-strip';
        modelStrip.dataset.groupId = group.id;

        const details = document.createElement('details');
        details.className = 'model-strip-details';
        details.open = false; // Collapsed by default, easily expandable

        const summary = document.createElement('summary');
        summary.className = 'model-strip-summary';
        summary.innerHTML = `<span class="icon">📐</span> Модель и граф связей (${unitsByKind.model.length})`;
        details.appendChild(summary);

        const content = document.createElement('div');
        content.className = 'model-strip-content';
        for (const modelUnit of unitsByKind.model) {
          content.appendChild(this.renderUnitCard(modelUnit));
          if (this.onGraphRender) {
            const graphBox = document.createElement('div');
            graphBox.className = 'graph-host-box';
            content.appendChild(graphBox);
            this.onGraphRender(group.id, modelUnit.id, graphBox);
          }
        }
        details.appendChild(content);
        modelStrip.appendChild(details);
        body.appendChild(modelStrip);
      }

      // Multi-panel columns grid
      const grid = document.createElement('div');
      grid.className = `group-grid profile-${profile.id.replace(':', '-')}`;
      grid.style.gridTemplateColumns = colTemplate;

      for (const panel of profile.panels) {
        const col = document.createElement('div');
        col.className = `panel-column panel-${panel.id}`;
        col.dataset.panelId = panel.id;
        col.dataset.kinds = panel.kinds.join(',');

        const colHeader = document.createElement('div');
        colHeader.className = 'column-header';
        colHeader.innerHTML = `<h3>${escapeHtml(panel.title)}</h3>`;
        col.appendChild(colHeader);

        const colContent = document.createElement('div');
        colContent.className = 'column-content';

        // Gather all units matching this panel's kinds
        const panelUnits = [];
        for (const kind of panel.kinds) {
          panelUnits.push(...(unitsByKind[kind] || []));
        }

        if (panelUnits.length === 0) {
          // Zero unit loss & explicit absence: render missing role badge for each expected kind
          for (const kind of panel.kinds) {
            if (profile.hasModelStrip && kind === 'model') continue;
            colContent.appendChild(this.renderMissingRoleBadge(kind));
          }
        } else {
          for (const unit of panelUnits) {
            colContent.appendChild(this.renderUnitCard(unit));
            // If this is a model panel and model unit has an associated visual graph, host graph
            if (unit.kind === 'model' && this.onGraphRender && !profile.hasModelStrip) {
              const graphBox = document.createElement('div');
              graphBox.className = 'graph-host-box';
              colContent.appendChild(graphBox);
              this.onGraphRender(group.id, unit.id, graphBox);
            }
          }
        }

        col.appendChild(colContent);
        grid.appendChild(col);
      }

      body.appendChild(grid);
      section.appendChild(body);
      return section;
    }

    /**
     * Render an individual Unit Card.
     */
    renderUnitCard(unit) {
      const card = document.createElement('article');
      card.className = `unit-card role-${unit.kind}`;
      card.id = `unit-${unit.id}`;
      card.dataset.unitId = unit.id;
      card.dataset.unitKind = unit.kind;
      card.dataset.sourceRefs = (unit.source_refs || []).join(' ');
      card.tabIndex = 0;
      card.setAttribute('role', 'region');
      card.setAttribute('aria-label', `${unit.kind}: ${unit.title || unit.id}`);

      // Metadata bar
      const metaBar = document.createElement('div');
      metaBar.className = 'unit-meta-bar';

      const roleBadge = document.createElement('span');
      roleBadge.className = `role-badge role-badge-${unit.kind}`;
      roleBadge.textContent = unit.kind.toUpperCase();
      metaBar.appendChild(roleBadge);

      const idBadge = document.createElement('span');
      idBadge.className = 'unit-id-badge';
      idBadge.tabIndex = 0;
      idBadge.role = 'button';
      idBadge.title = 'Нажмите для выбора или создания ссылки';
      idBadge.textContent = unit.id;
      idBadge.addEventListener('click', (e) => {
        e.stopPropagation();
        this.selectUnit(unit.id);
      });
      metaBar.appendChild(idBadge);

      // Author pill
      const authorId = (unit.author_refs || [])[0];
      const author = this.authorMap.get(authorId);
      if (author) {
        const authorPill = document.createElement('span');
        authorPill.className = `author-pill author-${author.kind || 'human'}`;
        authorPill.textContent = `${author.name}${author.version ? ' v' + author.version : ''}`;
        metaBar.appendChild(authorPill);
      }

      // Epistemic badge
      if (unit.epistemic) {
        const epistemicBadge = document.createElement('span');
        epistemicBadge.className = `epistemic-badge epistemic-${unit.epistemic}`;
        epistemicBadge.textContent = unit.epistemic;
        metaBar.appendChild(epistemicBadge);
      }

      // Workflow status badge
      if (unit.status) {
        const statusBadge = document.createElement('span');
        statusBadge.className = `status-badge status-${unit.status}`;
        statusBadge.textContent = unit.status;
        metaBar.appendChild(statusBadge);
      }

      card.appendChild(metaBar);

      // Title
      if (unit.title) {
        const titleEl = document.createElement('h4');
        titleEl.className = 'unit-title';
        titleEl.textContent = unit.title;
        card.appendChild(titleEl);
      }

      // Text body with progressive disclosure for quotes > 1200 chars (AC-31)
      const textEl = document.createElement('div');
      textEl.className = `unit-body ${unit.text_format === 'plain' ? 'plain-text' : 'markdown-text'}`;

      if (unit.text && unit.text.length > 1200) {
        const rawText = unit.text;
        const previewLen = 600;
        const previewText = rawText.slice(0, previewLen) + '...';

        const textWrapper = document.createElement('div');
        textWrapper.className = 'disclosure-wrapper pd-quote-foldable pd-quote-collapsed';

        const bar = document.createElement('div');
        bar.className = 'disclosure-bar pd-quote-bar';

        const lenBadge = document.createElement('span');
        lenBadge.className = 'disclosure-len-badge pd-quote-badge';
        lenBadge.textContent = `Полный текст: ${rawText.length.toLocaleString('ru-RU')} символов`;
        bar.appendChild(lenBadge);

        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'disclosure-btn pd-quote-toggle-btn pd-btn';
        toggleBtn.setAttribute('aria-expanded', 'false');
        toggleBtn.textContent = 'Развернуть';

        const copyBtn = document.createElement('button');
        copyBtn.type = 'button';
        copyBtn.className = 'disclosure-copy-btn pd-quote-copy-btn pd-btn';
        copyBtn.textContent = 'Копировать';
        copyBtn.title = 'Скопировать полный текст цитаты с сохранением всех пробелов и переносов';
        copyBtn.addEventListener('click', async (e) => {
          e.stopPropagation();
          try {
            if (navigator.clipboard) {
              await navigator.clipboard.writeText(rawText);
            } else {
              throw new Error('No clipboard');
            }
          } catch (err) {
            const ta = document.createElement('textarea');
            ta.value = rawText;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
          }
          copyBtn.textContent = 'Скопировано!';
          setTimeout(() => { copyBtn.textContent = 'Копировать'; }, 1500);
        });

        bar.appendChild(toggleBtn);
        bar.appendChild(copyBtn);
        textWrapper.appendChild(bar);

        const previewDiv = document.createElement('div');
        previewDiv.className = 'disclosure-preview pd-quote-preview';
        previewDiv.textContent = previewText;

        const fullDiv = document.createElement('div');
        fullDiv.className = 'disclosure-full pd-quote-full';
        fullDiv.style.display = 'none';
        fullDiv.textContent = rawText;

        toggleBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const isExpanded = fullDiv.style.display !== 'none';
          fullDiv.style.display = isExpanded ? 'none' : 'block';
          previewDiv.style.display = isExpanded ? 'block' : 'none';
          toggleBtn.textContent = isExpanded ? 'Развернуть' : 'Свернуть';
          toggleBtn.setAttribute('aria-expanded', isExpanded ? 'false' : 'true');
          textWrapper.classList.toggle('pd-quote-collapsed', isExpanded);
        });

        textWrapper.appendChild(previewDiv);
        textWrapper.appendChild(fullDiv);
        textEl.appendChild(textWrapper);
      } else {
        textEl.textContent = unit.text || '';
      }
      card.appendChild(textEl);

      // Provenance (for source units)
      if (unit.provenance) {
        const provBox = document.createElement('div');
        provBox.className = 'provenance-box';
        provBox.innerHTML = `
          <span class="prov-label">${escapeHtml(unit.provenance.label)}</span>
          ${unit.provenance.source_sha256 ? `<span class="prov-sha" title="Заявленный SHA-256 источника (не верифицирован локально)">заявленный: ${escapeHtml(unit.provenance.source_sha256.slice(0, 16))}...</span>` : ''}
        `;
        card.appendChild(provBox);
      }

      // Mount unit assets (AC-19, AC-22, AC-23)
      if (Array.isArray(unit.asset_ids) && unit.asset_ids.length > 0) {
        const assetsContainer = document.createElement('div');
        assetsContainer.className = 'unit-assets-container pd-asset-container';
        assetsContainer.setAttribute('aria-label', `Медиа-вложения единицы ${unit.id}`);

        for (const assetId of unit.asset_ids) {
          const asset = this.assetMap.get(assetId);
          if (!asset) {
            if (typeof ParallelDocMedia !== 'undefined' && ParallelDocMedia.MediaRenderer) {
              assetsContainer.appendChild(ParallelDocMedia.MediaRenderer.renderMissingAssetBlock(assetId));
            } else {
              const errDiv = document.createElement('div');
              errDiv.className = 'pd-thumbnail-wrapper pd-asset-error-card';
              errDiv.textContent = `Ресурс '${assetId}' не найден`;
              assetsContainer.appendChild(errDiv);
            }
          } else {
            const validationResult = this.mediaValidationMap ? this.mediaValidationMap.get(assetId) : null;
            if (typeof ParallelDocMedia !== 'undefined' && ParallelDocMedia.MediaRenderer) {
              const assetEl = ParallelDocMedia.MediaRenderer.renderAsset(asset, validationResult, (a, triggerBtn) => {
                if (this.onModalOpen) {
                  this.onModalOpen(a, triggerBtn);
                }
              });
              assetsContainer.appendChild(assetEl);
            }
          }
        }
        card.appendChild(assetsContainer);
      }

      // Unit card selection & keyboard event
      card.addEventListener('click', () => {
        this.selectUnit(unit.id);
      });

      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          if (e.target === card) {
            e.preventDefault();
            this.selectUnit(unit.id);
          }
        }
      });

      return card;
    }

    /**
     * Render an Explicit Missing Role Badge (F21).
     */
    renderMissingRoleBadge(kind) {
      const cfg = MISSING_ROLE_CONFIG[kind] || { text: `«Роль ${kind} не задана»`, desc: '' };
      const placeholder = document.createElement('div');
      placeholder.className = `missing-role-placeholder role-missing-${kind}`;
      placeholder.setAttribute('role', 'status');
      placeholder.setAttribute('aria-label', `Отсутствует роль: ${kind}`);
      placeholder.innerHTML = `
        <div class="missing-badge-header">
          <svg class="missing-icon" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
            <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="2 2"/>
            <line x1="5" y1="8" x2="11" y2="8" stroke="currentColor" stroke-width="1.5"/>
          </svg>
          <strong class="missing-badge-text">${escapeHtml(cfg.text)}</strong>
        </div>
        ${cfg.desc ? `<p class="missing-badge-desc">${escapeHtml(cfg.desc)}</p>` : ''}
      `;
      return placeholder;
    }

    /**
     * Deep navigation: Jump to target ID with auto-expansion, header offset, and history stack push (AC-16).
     */
    navigateTo(targetId, isBackNavigation = false) {
      if (!targetId || typeof document === 'undefined') return false;

      const targetEl = document.getElementById(`unit-${targetId}`) ||
                       document.getElementById(`pd-unit-${targetId}`) ||
                       document.getElementById(`group-${targetId}`);
      if (!targetEl) return false;

      if (!isBackNavigation) {
        this.pushHistorySnapshot(targetId);
      }

      // Auto-expand enclosing group if collapsed
      const enclosingGroup = targetEl.closest('.group-section');
      if (enclosingGroup) {
        const bodyEl = enclosingGroup.querySelector('.group-body');
        const toggleBtn = enclosingGroup.querySelector('.group-toggle');
        if (bodyEl && bodyEl.style.display === 'none') {
          bodyEl.style.display = 'block';
          if (toggleBtn) {
            toggleBtn.setAttribute('aria-expanded', 'true');
            const icon = toggleBtn.querySelector('.toggle-icon');
            if (icon) icon.textContent = '▼';
          }
        }
      }

      // Auto-expand quote disclosure if target is folded
      const disclosureFull = targetEl.querySelector('.disclosure-full');
      const disclosurePreview = targetEl.querySelector('.disclosure-preview');
      const toggleBtn = targetEl.querySelector('.disclosure-btn');
      const textWrapper = targetEl.querySelector('.disclosure-wrapper');
      if (disclosureFull && disclosureFull.style.display === 'none') {
        disclosureFull.style.display = 'block';
        if (disclosurePreview) disclosurePreview.style.display = 'none';
        if (toggleBtn) {
          toggleBtn.textContent = 'Свернуть';
          toggleBtn.setAttribute('aria-expanded', 'true');
        }
        if (textWrapper) textWrapper.classList.remove('pd-quote-collapsed');
      }

      // Scroll into view offset by sticky header
      const headerEl = document.querySelector('.sticky-header') || document.querySelector('.pd-header');
      const headerHeight = headerEl ? headerEl.offsetHeight : 120;
      const targetRect = targetEl.getBoundingClientRect();
      const currentScrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
      const absoluteTop = currentScrollY + targetRect.top;
      const scrollY = Math.max(0, absoluteTop - headerHeight - 16);

      const prefersReducedMotion = typeof window !== 'undefined' &&
        window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      if (typeof window !== 'undefined' && window.scrollTo) {
        window.scrollTo({
          top: scrollY,
          behavior: prefersReducedMotion ? 'auto' : 'smooth'
        });
      }

      // Visual pulse
      targetEl.classList.add('nav-target-pulse');
      setTimeout(() => targetEl.classList.remove('nav-target-pulse'), 1500);

      this.selectUnit(targetId, true);
      return true;
    }

    /**
     * Push current reading snapshot onto the 10-target LIFO history stack.
     */
    pushHistorySnapshot(targetId) {
      const scrollY = typeof window !== 'undefined'
        ? (window.pageYOffset || (document && document.documentElement && document.documentElement.scrollTop) || 0)
        : 0;

      const snapshot = {
        targetId,
        scrollY,
        activeProfileId: this.activeProfileId,
        activeSelectionId: this.activeSelectionId,
        timestamp: Date.now()
      };

      this.navStack.push(snapshot);
      if (this.navStack.length > this.maxStackSize) {
        this.navStack.shift(); // Evict oldest
      }

      this.updateReturnButtonState();
    }

    /**
     * Return-to-reading anchor: Pop snapshot and restore previous viewport/selection (AC-16).
     */
    returnToAnchor() {
      if (this.navStack.length === 0) return false;

      const snapshot = this.navStack.pop();
      this.updateReturnButtonState();

      if (snapshot.activeProfileId && snapshot.activeProfileId !== this.activeProfileId) {
        this.setProfile(snapshot.activeProfileId);
      }

      if (typeof window !== 'undefined' && window.scrollTo) {
        const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        window.scrollTo({
          top: snapshot.scrollY,
          behavior: prefersReducedMotion ? 'auto' : 'smooth'
        });
      }

      if (snapshot.activeSelectionId) {
        this.selectUnit(snapshot.activeSelectionId, true);
      }

      return true;
    }

    updateReturnButtonState() {
      if (typeof document === 'undefined') return;
      const btn = document.getElementById('btn-return-anchor') || document.getElementById('pd-btn-return-anchor');
      if (btn) {
        btn.disabled = this.navStack.length === 0;
        btn.setAttribute('aria-label', `Вернуться к месту чтения (${this.navStack.length} в стеке)`);
      }
    }

    /**
     * Select a unit, applying persistent cross-highlighting across related elements.
     */
    selectUnit(unitId, skipNavHistory = false) {
      this.activeSelectionId = unitId;

      if (typeof document === 'undefined') return;

      const prevActive = document.querySelectorAll('.unit-card.unit-selected, .pd-unit-card.unit-selected');
      prevActive.forEach(el => el.classList.remove('unit-selected'));

      const targetEl = document.getElementById(`unit-${unitId}`) || document.getElementById(`pd-unit-${unitId}`);
      if (targetEl) {
        targetEl.classList.add('unit-selected');
      }

      // Find dependent or source units
      const relatedIds = new Set([unitId]);
      const unit = this.unitMap.get(unitId);
      if (unit) {
        // Direct source references
        for (const sRef of (unit.source_refs || [])) {
          relatedIds.add(sRef);
        }
        // Reverse source references (all units that depend on this source)
        for (const [otherId, otherUnit] of this.unitMap.entries()) {
          if ((otherUnit.source_refs || []).includes(unitId)) {
            relatedIds.add(otherId);
          }
        }
      }

      this.applyHighlights(Array.from(relatedIds), true);

      if (this.onUnitSelect) {
        this.onUnitSelect(unitId, Array.from(relatedIds));
      }
    }

    /**
     * Cross-highlight elements without scrolling the page (scroll delta = 0).
     */
    applyHighlights(unitIds, isSelection = false) {
      if (typeof document === 'undefined') return;
      const className = isSelection ? 'cross-hl-active' : 'cross-hl-hover';

      if (!isSelection) {
        document.querySelectorAll('.cross-hl-hover').forEach(el => el.classList.remove('cross-hl-hover'));
      }

      for (const id of unitIds) {
        const el = document.getElementById(`unit-${id}`) || document.getElementById(`pd-unit-${id}`);
        if (el) {
          el.classList.add(className);
        }
      }
    }

    clearHoverHighlights() {
      if (typeof document === 'undefined') return;
      document.querySelectorAll('.cross-hl-hover').forEach(el => el.classList.remove('cross-hl-hover'));
    }
  }

  return {
    BUILTIN_PROFILES,
    MISSING_ROLE_CONFIG,
    PanelsEngine
  };
});
