# Control Table: Corpus G (Synthetic SLA Benchmark)

> **Document**: `corpus_G_sla_document.json`  
> **Raw SHA-256**: `558fe436490edf9e64d46a112ce90905903290ddd4e954ea5eae8d5388fd61e0`  
> **Byte Length**: 49762 bytes  
> **Groups**: 12 (>=12) | **Units**: 24 (>=24) | **Quote u-05**: 11982 chars (>=8,000)  
> **Graph**: 8 nodes / 9 edges (all 6 relations, branch, cross-group, cycle)  
> **Assets**: 3 embedded raster assets (PNG, JPEG, WebP)

---

## 1. Core Semantic Deductions (AC-13 Ground Truth)

| Component | Target ID | Verified Truth / Ground Truth Value |
|---|---|---|
| **Предварительный вывод** | `u-09` / `node-prelim-compl` | Предварительное соответствие SLA 99.95% (условное) |
| **Основание 1 (Premise 1)** | `u-02` / `node-multi-az` | Архитектура Multi-AZ с автоматическим failover < 45 сек (`supports` -> `u-09`) |
| **Основание 2 (Premise 2)** | `u-03` / `node-uptime-claim` | Исторический показатель аптайма провайдера 99.99% (`supports` -> `u-09`) |
| **Критическая оговорка (Qualification)** | `u-04` / `node-maint-clause` | Исключение плановых работ квалифицирует вывод (`qualifies` -> `node-prelim-compl`) |
| **Рекомендуемое действие** | `u-11` / `node-method-request` | Запросить подробную методику расчета доступности и исходные журналы ТО (`depends_on`) |
| **Почему 99.99% не является доказательством** | - | Время ТО вычитается из знаменателя; без первичных журналов возможно сокрытие аварий |

---

## 2. Cross-Highlighting Matrix (AC-14 & AC-15 Ground Truth)

| Graph Node / Edge ID | Connected Unit IDs | Description / Invariant |
|---|---|---|
| `node-sla-req` | `u-01` | Требование SLA 99.95% |
| `node-multi-az` | `u-02` | Архитектурная модель |
| `node-uptime-claim` | `u-03` | Декларация поставщика 99.99% |
| `node-maint-clause` | `u-04` | Исключение регламентных окон |
| `node-meas-window` | `u-07` | Неопределенность окна измерений |
| `node-prelim-compl` | `u-09` | Предварительный вывод |
| `node-method-request` | `u-11` | Запрос методики и журналов ТО |
| `node-audit-prep` | `u-12` | Подготовка внешнего аудита |
| `edge-01` (`supports`) | `u-02`, `u-09` | Multi-AZ -> Соответствие |
| `edge-02` (`supports`) | `u-03`, `u-09` | Заявление 99.99% -> Соответствие |
| `edge-03` (`qualifies`) | `u-04`, `u-09`, `u-10` | Исключение ТО -> Соответствие |
| `edge-04` (`qualifies`) | `u-07`, `u-03` | Дискретность мониторинга -> Заявление |
| `edge-05` (`contradicts`) | `u-04`, `u-03`, `u-08` | Исключение ТО <-> Заявление 99.99% |
| `edge-06` (`depends_on`) | `u-09`, `u-11` | Соответствие -> Запрос логов |
| `edge-07` (`precedes`) | `u-11`, `u-12` | Запрос логов -> Подготовка аудита |
| `edge-08` (`compares`) | `u-01`, `u-03` | Требование 99.95% <-> Заявление 99.99% |
| `edge-09` (`depends_on`) | `u-12`, `u-11` | Аудит -> Запрос логов (Cross-group cycle) |

---

## 3. 10 Literal Search Test Queries (AC-32 Ground Truth)

1. `"99.95%"` -> Находит `u-01`, `u-01b`, `u-03b`, `u-09`
2. `"Multi-AZ"` -> Находит `u-02`, `u-02b`, `u-09`
3. `"РЕГЛАМЕНТНЫЙ_МАРКЕР_7749"` -> Находит `u-05` (в свернутой длинной цитате)
4. `"48 часов"` -> Находит `u-01`, `u-05`
5. `"21.6 минут"` -> Находит `u-01b`, `u-03b`
6. `"failover"` -> Находит `u-02`
7. `"ast-g-01"` -> Находит `u-02`, `u-06`, `u-06b`
8. `"Статья 5.2"` -> Находит `u-05`, `u-05b`
9. `"бремя доказывания"` -> Находит `u-05`, `u-05b`
10. `"независимый аудит"` -> Находит `u-10`, `u-12`, `u-12b`
