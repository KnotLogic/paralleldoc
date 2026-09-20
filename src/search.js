/**
 * ParallelDoc 3.0 (r2 / V3-ONLY) — Literal Full-Text Search & Browser Find Engine
 * Path: src/search.js
 * Strictly compliant with Spec r2 §6, §11 (F25, F26, AC-32, AC-33).
 *
 * Capabilities:
 * - Pure literal case-insensitive substring search (ZERO regex interpretation).
 * - Matches across units (text, title, id), assets (alt, caption, id), and visual graphs (labels, id).
 * - Circular navigation with Enter (forward) / Shift+Enter (backward).
 * - Auto-expansion of collapsed quotes and group containers upon navigation.
 * - Browser Find (Ctrl+F) compatibility unrolling mode.
 */

(function(root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.ParallelDocSearch = factory();
  }
})(typeof self !== 'undefined' ? self : (typeof globalThis !== 'undefined' ? globalThis : this), function() {
  'use strict';

  class SearchEngine {
    constructor(docData, rootEl, options = {}) {
      this.doc = docData;
      this.root = rootEl;
      this.matches = [];
      this.currentIndex = -1;
      this.unrollMode = false;
      this.onNavigate = options.onNavigate || null;
      this.onCountChange = options.onCountChange || null;
    }

    /**
     * Executes case-insensitive literal search across all units, IDs, alts, and graph elements.
     * Guaranteed ZERO regex evaluation.
     * @param {string} rawQuery
     * @returns {Array} List of match descriptors
     */
    search(rawQuery) {
      this.clearHighlights();
      this.matches = [];
      this.currentIndex = -1;

      const query = (rawQuery || '').trim().toLowerCase();
      if (!query) {
        this.updateCounter(0, 0);
        return [];
      }

      // 1. Search units
      if (this.doc && Array.isArray(this.doc.units)) {
        for (const unit of this.doc.units) {
          const text = (unit.text || '').toLowerCase();
          const title = (unit.title || '').toLowerCase();
          const id = (unit.id || '').toLowerCase();
          const prov = (unit.provenance && unit.provenance.label ? unit.provenance.label : '').toLowerCase();

          if (text.includes(query) || title.includes(query) || id.includes(query) || prov.includes(query)) {
            this.matches.push({
              type: 'unit',
              id: unit.id,
              elId: `unit-${unit.id}`,
              label: unit.title || unit.id
            });
          }
        }
      }

      // 2. Search assets
      if (this.doc && Array.isArray(this.doc.assets)) {
        for (const asset of this.doc.assets) {
          const alt = (asset.alt || '').toLowerCase();
          const cap = (asset.caption || '').toLowerCase();
          const id = (asset.id || '').toLowerCase();

          if (alt.includes(query) || cap.includes(query) || id.includes(query)) {
            this.matches.push({
              type: 'asset',
              id: asset.id,
              elId: `asset-${asset.id}`,
              label: asset.caption || asset.alt || asset.id
            });
          }
        }
      }

      // 3. Search visual relationship graphs (nodes & edges)
      if (this.doc && Array.isArray(this.doc.visuals)) {
        for (const visual of this.doc.visuals) {
          const vTitle = (visual.title || '').toLowerCase();
          const vQuestion = (visual.question || '').toLowerCase();
          const vFallback = (visual.fallback || '').toLowerCase();

          if (vTitle.includes(query) || vQuestion.includes(query) || vFallback.includes(query)) {
            this.matches.push({
              type: 'visual',
              id: visual.id,
              elId: `visual-${visual.id}`,
              label: visual.title || visual.id
            });
          }

          if (Array.isArray(visual.nodes)) {
            for (const node of visual.nodes) {
              const nLabel = (node.label || '').toLowerCase();
              const nId = (node.id || '').toLowerCase();
              if (nLabel.includes(query) || nId.includes(query)) {
                this.matches.push({
                  type: 'graph-node',
                  id: node.id,
                  elId: `node-${node.id}`,
                  label: node.label
                });
              }
            }
          }

          if (Array.isArray(visual.edges)) {
            for (const edge of visual.edges) {
              const eLabel = (edge.label || '').toLowerCase();
              const eId = (edge.id || '').toLowerCase();
              if (eLabel.includes(query) || eId.includes(query)) {
                this.matches.push({
                  type: 'graph-edge',
                  id: edge.id,
                  elId: `edge-${edge.id}`,
                  label: edge.label || edge.id
                });
              }
            }
          }
        }
      }

      const total = this.matches.length;
      if (total > 0) {
        this.navigate(0);
      } else {
        this.updateCounter(0, 0);
        this.announceA11y('По запросу совпадений не найдено');
      }

      return this.matches;
    }

    /**
     * Circular navigation: jumps to match index, auto-expanding folded elements.
     */
    navigate(targetIndex) {
      const total = this.matches.length;
      if (total === 0) return;

      // Circular wrapping
      if (targetIndex >= total) targetIndex = 0;
      if (targetIndex < 0) targetIndex = total - 1;

      this.currentIndex = targetIndex;
      const match = this.matches[targetIndex];

      this.updateCounter(targetIndex + 1, total);

      if (typeof document === 'undefined') {
        if (this.onNavigate) this.onNavigate(match, targetIndex, total);
        return;
      }

      this.clearActiveHighlight();

      // Find element in DOM (supports both unit- and pd-unit- prefixes)
      const targetEl = document.getElementById(match.elId) ||
                       document.getElementById(`pd-${match.elId}`) ||
                       document.querySelector(`[data-unit-id="${match.id}"]`) ||
                       document.querySelector(`[data-node-id="${match.id}"]`) ||
                       document.querySelector(`[data-edge-id="${match.id}"]`);

      if (targetEl) {
        // Auto-expand group if collapsed
        const enclosingGroup = targetEl.closest('.group-section, .pd-group-row');
        if (enclosingGroup) {
          const bodyEl = enclosingGroup.querySelector('.group-body, .pd-group-body');
          const toggleBtn = enclosingGroup.querySelector('.group-toggle, .pd-group-toggle');
          if (bodyEl && bodyEl.style.display === 'none') {
            bodyEl.style.display = 'block';
            if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'true');
          }
        }

        // Auto-expand quote disclosure if inside collapsed quote
        const parentFoldable = targetEl.closest('.pd-quote-foldable, .disclosure-wrapper');
        if (parentFoldable) {
          const fullDiv = parentFoldable.querySelector('.disclosure-full, .pd-quote-full');
          const previewDiv = parentFoldable.querySelector('.disclosure-preview, .pd-quote-preview');
          const toggleBtn = parentFoldable.querySelector('.disclosure-btn, .pd-quote-toggle-btn');
          if (fullDiv && fullDiv.style.display === 'none') {
            fullDiv.style.display = 'block';
            if (previewDiv) previewDiv.style.display = 'none';
            if (toggleBtn) {
              toggleBtn.textContent = 'Свернуть';
              toggleBtn.setAttribute('aria-expanded', 'true');
            }
            parentFoldable.classList.remove('pd-quote-collapsed');
          }
        }

        targetEl.classList.add('pd-search-highlight-active', 'search-match-active');

        // Scroll offset by sticky header
        const headerEl = document.querySelector('.sticky-header, .pd-header');
        const headerHeight = headerEl ? headerEl.offsetHeight : 120;
        const rect = targetEl.getBoundingClientRect();
        const currentScrollY = window.pageYOffset || (document.documentElement && document.documentElement.scrollTop) || 0;
        const absoluteTop = currentScrollY + rect.top;
        const scrollY = Math.max(0, absoluteTop - headerHeight - 16);

        const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (window.scrollTo) {
          window.scrollTo({
            top: scrollY,
            behavior: prefersReducedMotion ? 'auto' : 'smooth'
          });
        }

        this.announceA11y(`Совпадение ${targetIndex + 1} из ${total}: ${match.id}`);
      }

      if (this.onNavigate) {
        this.onNavigate(match, targetIndex, total);
      }
    }

    next() {
      this.navigate(this.currentIndex + 1);
    }

    prev() {
      this.navigate(this.currentIndex - 1);
    }

    clearHighlights() {
      if (typeof document === 'undefined') return;
      document.querySelectorAll('.pd-search-highlight-active, .search-match-active').forEach(el => {
        el.classList.remove('pd-search-highlight-active', 'search-match-active');
      });
    }

    clearActiveHighlight() {
      if (typeof document === 'undefined') return;
      document.querySelectorAll('.pd-search-highlight-active, .search-match-active').forEach(el => {
        el.classList.remove('pd-search-highlight-active', 'search-match-active');
      });
    }

    updateCounter(current, total) {
      if (typeof document !== 'undefined') {
        const counterEl = document.getElementById('pd-search-counter') || document.getElementById('search-counter');
        if (counterEl) {
          if (total === 0) {
            counterEl.textContent = '0 совпадений';
          } else {
            counterEl.textContent = `${current} из ${total}`;
          }
        }
      }
      if (this.onCountChange) {
        this.onCountChange(current, total);
      }
    }

    /**
     * Toggles native browser Find (Ctrl+F) compatibility unrolling mode (AC-33).
     */
    toggleUnrollMode() {
      this.unrollMode = !this.unrollMode;
      if (typeof document === 'undefined') return this.unrollMode;

      const body = document.body;
      const btn = document.getElementById('pd-unroll-toggle-btn') || document.getElementById('btn-unroll-mode');

      if (this.unrollMode) {
        body.classList.add('pd-unroll-all');
        if (btn) {
          btn.classList.add('active');
          btn.setAttribute('aria-pressed', 'true');
          btn.textContent = 'Свернуть режим поиска браузера';
        }
        this.announceA11y('Включен полный текст для поиска браузером (Ctrl+F)');
      } else {
        body.classList.remove('pd-unroll-all');
        if (btn) {
          btn.classList.remove('active');
          btn.setAttribute('aria-pressed', 'false');
          btn.textContent = 'Полный текст для Ctrl+F';
        }
        this.announceA11y('Выключен режим поиска браузера');
      }

      return this.unrollMode;
    }

    announceA11y(message) {
      if (typeof document === 'undefined') return;
      const liveRegion = document.getElementById('pd-live-region');
      if (liveRegion) {
        liveRegion.textContent = '';
        setTimeout(() => { liveRegion.textContent = message; }, 50);
      }
    }
  }

  return {
    SearchEngine
  };
});
