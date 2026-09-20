"""
fixtures/generate_corpus_g.py — Generator for Corpus G (Synthetic SLA Benchmark Document).
Materializes synthetic SLA comparison document (>=12 groups, >=24 units, Russian quote >=8,000 chars,
3 raster assets, 8 nodes / 9 edges graph with branch, cross-group link, cycle in depends_on,
and critical qualification edge) plus control answer tables (corpus_G_control.json and corpus_G_control.md).
Complies strictly with Spec r2 §2, §3, §4, §5, §11 (AC-12, AC-13, AC-14, AC-15, AC-16, AC-31, AC-32).
"""

import base64
import hashlib
import json
from pathlib import Path
import struct
import zlib


def make_png_bytes(width: int, height: int, rgba: tuple = (30, 144, 255, 255)) -> bytes:
    raw_scanlines = bytearray()
    r, g, b, a = rgba
    for _ in range(height):
        raw_scanlines.append(0)
        raw_scanlines.extend([r, g, b, a] * width)
    compressed = zlib.compress(bytes(raw_scanlines), level=6)

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xffffffff
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr_data) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


def make_jpeg_bytes(width: int, height: int) -> bytes:
    return (
        bytes([
            0xFF, 0xD8,
            0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x01, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00,
            0xFF, 0xC0, 0x00, 0x0B, 0x08,
        ])
        + struct.pack(">HH", height, width)
        + bytes([0x01, 0x01, 0x11, 0x00, 0xFF, 0xD9])
    )


def make_webp_bytes(width: int, height: int) -> bytes:
    hdr = (
        bytes([
            0x52, 0x49, 0x46, 0x46,
            0x1E, 0x00, 0x00, 0x00,
            0x57, 0x45, 0x42, 0x50,
            0x56, 0x50, 0x38, 0x20,
            0x12, 0x00, 0x00, 0x00,
            0x30, 0x01, 0x00,
            0x9D, 0x01, 0x2A
        ])
        + struct.pack("<HH", width & 0x3FFF, height & 0x3FFF)
        + b"\x00" * 10
    )
    return hdr


def generate_corpus_g(target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Synthesize 3 valid raster assets
    png_bytes = make_png_bytes(240, 140, (41, 128, 185, 255))
    jpeg_bytes = make_jpeg_bytes(160, 100)
    webp_bytes = make_webp_bytes(180, 90)

    asset_png = {
        "id": "ast-g-01",
        "mime": "image/png",
        "sha256": hashlib.sha256(png_bytes).hexdigest().lower(),
        "byte_length": len(png_bytes),
        "width": 240,
        "height": 140,
        "alt": "Схема архитектуры Multi-AZ резервирования облачных сервисов",
        "caption": "Рис. 1: Топология Multi-AZ отказоустойчивости (PNG 240x140)",
        "author_refs": ["auth-lead-arch"],
        "provenance": {"label": "Архитектурный чертеж Multi-AZ v3.1"},
        "locator": {
            "mode": "embedded",
            "data_uri": f"data:image/png;base64,{base64.b64encode(png_bytes).decode('ascii')}"
        }
    }

    asset_jpeg = {
        "id": "ast-g-02",
        "mime": "image/jpeg",
        "sha256": hashlib.sha256(jpeg_bytes).hexdigest().lower(),
        "byte_length": len(jpeg_bytes),
        "width": 160,
        "height": 100,
        "alt": "График распределения регламентных окон обслуживания",
        "caption": "Рис. 2: Календарный план планового ТО (JPEG 160x100)",
        "author_refs": ["auth-lead-arch"],
        "provenance": {"label": "Журнал регламентных окон 2026"},
        "locator": {
            "mode": "embedded",
            "data_uri": f"data:image/jpeg;base64,{base64.b64encode(jpeg_bytes).decode('ascii')}"
        }
    }

    asset_webp = {
        "id": "ast-g-03",
        "mime": "image/webp",
        "sha256": hashlib.sha256(webp_bytes).hexdigest().lower(),
        "byte_length": len(webp_bytes),
        "width": 180,
        "height": 90,
        "alt": "Диаграмма мониторинга доступности и порогов эскалации",
        "caption": "Рис. 3: Пороги алертов MTTR и MTTA (WebP 180x90)",
        "author_refs": ["auth-lead-arch"],
        "provenance": {"label": "Дашборд метрик Prometheus/Grafana"},
        "locator": {
            "mode": "embedded",
            "data_uri": f"data:image/webp;base64,{base64.b64encode(webp_bytes).decode('ascii')}"
        }
    }

    # 2. Build Russian Quote >= 8,000 characters with search marker in the middle
    p1 = (
        "Статья 5.2. Методология и правила расчета коэффициента совокупной эксплуатационной доступности облачных вычислительных ресурсов. "
        "Настоящим согласовано и юридически зафиксировано сторонами соглашения, что ежемесячный процент эксплуатационной доступности "
        "(Service Availability SLA Metric) вычисляется строго как частное от деления разницы между общим количеством минут в расчетном календарном месяце "
        "и суммарным количеством минут зафиксированного и подтвержденного непрерывного технологического простоя сервиса к общему количеству минут в расчетном календарном месяце. "
        "При проведении математического расчета из числителя и знаменателя безусловно и безоговорочно исключаются все интервалы времени планового регламентного "
        "профилактического обслуживания, заранее анонсированные Исполнителем в письменной электронной форме не менее чем за 48 часов (сорок восемь часов) до их фактического начала. "
    ) * 8

    marker_paragraph = (
        "\n\nОСОБЫЙ РЕГЛАМЕНТНЫЙ РАЗДЕЛ §5.2.14: Настоящим вводится уникальный протокольный идентификатор "
        "РЕГЛАМЕНТНЫЙ_МАРКЕР_7749 для сквозного поиска и доказательного сопоставления контрольных точек журнала измерений. "
        "Любое аварийное событие, длительность которого превышает пятнадцать минут подряд, подлежит обязательной регистрации в первичной базе данных аудита.\n\n"
    )

    p2 = (
        "В случае разногласий между сторонами относительно того, квалифицируется ли конкретный технологический инцидент как плановое обслуживание "
        "либо как аварийный внеплановый сбой инфраструктуры, бремя доказывания возлагается на Исполнителя с предоставлением криптографически подписанных "
        "логов системного журнала мониторинга событий операционной системы и аппаратных гипервизоров. Непредоставление указанных первичных логов "
        "в течение семидесяти двух часов влечет автоматическую переквалификацию спорного временного интервала в статус внепланового коммерческого простоя. "
    ) * 8

    full_quote_8k = p1 + marker_paragraph + p2
    assert len(full_quote_8k) >= 8000, f"Quote length {len(full_quote_8k)} must be >= 8,000 characters"

    # 3. Define Units (24 units across 12 groups)
    units = [
        # Group 1: SLA Requirement (g-01)
        {
            "id": "u-01",
            "kind": "source",
            "title": "Требование SLA 99.95% доступности",
            "text": "1. Требования к доступности сервиса: Исполнитель гарантирует ежемесячную доступность сервиса не менее 99.95%, исключая плановые регламентные работы, анонсированные за 48 часов.",
            "text_format": "plain",
            "summary": "Базовое договорное обязательство 99.95%",
            "author_refs": ["auth-legal-01"],
            "epistemic": "reported",
            "status": "reviewed",
            "source_refs": [],
            "asset_ids": [],
            "provenance": {"label": "Договор SLA №2026-A4, Раздел 1.1"}
        },
        {
            "id": "u-01b",
            "kind": "analysis",
            "title": "Анализ порога допустимого простоя 99.95%",
            "text": "При целевом уровне 99.95% суммарный допустимый аварийный простой в месяц составляет не более 21.6 минут.",
            "text_format": "plain",
            "author_refs": ["auth-eng-01"],
            "epistemic": "supported",
            "status": "reviewed",
            "source_refs": ["u-01"],
            "asset_ids": []
        },

        # Group 2: Architecture Multi-AZ (g-02)
        {
            "id": "u-02",
            "kind": "model",
            "title": "Архитектурная модель Multi-AZ",
            "text": "Архитектурная модель обеспечения высокой доступности: кластер баз данных и пулы приложений развернуты в трех независимых зонах доступности (Multi-AZ) с автоматическим failover за время менее 45 секунд (схема ast-g-01).",
            "text_format": "markdown-safe",
            "summary": "Инженерная модель Multi-AZ",
            "author_refs": ["auth-lead-arch"],
            "epistemic": "hypothesis",
            "status": "reviewed",
            "source_refs": [],
            "asset_ids": ["ast-g-01"]
        },
        {
            "id": "u-02b",
            "kind": "analysis",
            "title": "Оценка времени восстановления MTTR",
            "text": "Показатель MTTR <= 45s для конфигурации Multi-AZ подтверждает техническую возможность сохранения аптайма в рамках 99.95%.",
            "text_format": "plain",
            "author_refs": ["auth-eng-01"],
            "epistemic": "supported",
            "status": "reviewed",
            "source_refs": ["u-01"],
            "asset_ids": []
        },

        # Group 3: Provider Claim (g-03)
        {
            "id": "u-03",
            "kind": "source",
            "title": "Декларация поставщика об историческом аптайме 99.99%",
            "text": "Заявление облачного провайдера: 'За последние 24 месяца историческая совокупная доступность сервиса в регионе составила 99.99%'.",
            "text_format": "plain",
            "summary": "Рекламное заявление поставщика 99.99%",
            "author_refs": ["auth-vendor-rep"],
            "epistemic": "reported",
            "status": "reviewed",
            "source_refs": [],
            "asset_ids": [],
            "provenance": {"label": "Cloud Provider Regional Status Report 2026"}
        },
        {
            "id": "u-03b",
            "kind": "analysis",
            "title": "Сравнение 99.95% и 99.99%",
            "text": "Разница между 99.95% (21.6 минут) и 99.99% (4.32 минут) составляет пятикратный запас по допустимому времени сбоя.",
            "text_format": "plain",
            "author_refs": ["auth-eng-01"],
            "epistemic": "supported",
            "status": "reviewed",
            "source_refs": ["u-01", "u-03"],
            "asset_ids": []
        },

        # Group 4: Maintenance Clause (g-04)
        {
            "id": "u-04",
            "kind": "source",
            "title": "Пункт договора об исключении плановых работ",
            "text": "Пункт 4.3 Договора: 'Любое время, затраченное на плановое техническое обслуживание и обновление платформы, полностью исключается из расчета общего процента доступности'.",
            "text_format": "plain",
            "summary": "Исключение регламентных окон",
            "author_refs": ["auth-legal-01"],
            "epistemic": "reported",
            "status": "reviewed",
            "source_refs": [],
            "asset_ids": [],
            "provenance": {"label": "Договор SLA №2026-A4, Статья 4.3"}
        },
        {
            "id": "u-04b",
            "kind": "analysis",
            "title": "Квалификация влияния регламентных окон",
            "text": "Исключение регламентных работ создает риск сокрытия аварийных сбоев под видом планового техобслуживания.",
            "text_format": "plain",
            "author_refs": ["auth-legal-01"],
            "epistemic": "supported",
            "status": "reviewed",
            "source_refs": ["u-04"],
            "asset_ids": []
        },

        # Group 5: Full Legal Text (g-05) — >= 8,000 chars
        {
            "id": "u-05",
            "kind": "source",
            "title": "Полный текст регламента измерения SLA (Статья 5.2)",
            "text": full_quote_8k,
            "text_format": "plain",
            "summary": "Нормативный регламент учета простоев с маркером 7749",
            "author_refs": ["auth-legal-01"],
            "epistemic": "reported",
            "status": "reviewed",
            "source_refs": [],
            "asset_ids": [],
            "provenance": {"label": "Договор SLA №2026-A4, Статья 5.2"}
        },
        {
            "id": "u-05b",
            "kind": "analysis",
            "title": "Анализ бремени доказывания по Статье 5.2",
            "text": "Статья 5.2 возлагает бремя доказывания статуса работ на Исполнителя в течение 72 часов.",
            "text_format": "plain",
            "author_refs": ["auth-legal-01"],
            "epistemic": "supported",
            "status": "reviewed",
            "source_refs": ["u-05"],
            "asset_ids": []
        },

        # Group 6: Media Attachments (g-06)
        {
            "id": "u-06",
            "kind": "model",
            "title": "Комплект графических материалов и регламентов",
            "text": "Графические приложения: архитектура Multi-AZ, календарный план ТО и дашборд алертов приведены во вложениях (ast-g-01, ast-g-02, ast-g-03).",
            "text_format": "plain",
            "summary": "Растровые схемы архитектуры и ТО",
            "author_refs": ["auth-lead-arch"],
            "epistemic": "hypothesis",
            "status": "reviewed",
            "source_refs": [],
            "asset_ids": ["ast-g-01", "ast-g-02", "ast-g-03"]
        },
        {
            "id": "u-06b",
            "kind": "action",
            "title": "Валидация форматов графических приложений",
            "text": "Проверить контрольные суммы растровых вложений PNG, JPEG и WebP (ast-g-01, ast-g-02, ast-g-03).",
            "text_format": "plain",
            "author_refs": ["auth-lead-arch"],
            "epistemic": "not-applicable",
            "status": "done",
            "source_refs": [],
            "asset_ids": ["ast-g-01", "ast-g-02", "ast-g-03"]
        },

        # Group 7: Measurement Window Uncertainty (g-07)
        {
            "id": "u-07",
            "kind": "analysis",
            "title": "Неопределенность окна измерений провайдера",
            "text": "Провайдер не раскрыл интервалы зондирования health check (1с, 30с или 5 минут). При интервале 5 минут кратковременные простои до 4 минут не фиксируются в метрике 99.99%.",
            "text_format": "plain",
            "summary": "Риск скрытых простоев из-за дискретности мониторинга",
            "author_refs": ["auth-eng-01"],
            "epistemic": "supported",
            "status": "reviewed",
            "source_refs": ["u-03"],
            "asset_ids": []
        },
        {
            "id": "u-07b",
            "kind": "analysis",
            "title": "Анализ дискретности интервалов",
            "text": "Дискретность зондирования свыше 60 секунд признана недопустимой для критических транзакций.",
            "text_format": "plain",
            "author_refs": ["auth-eng-01"],
            "epistemic": "supported",
            "status": "reviewed",
            "source_refs": ["u-03"],
            "asset_ids": []
        },

        # Group 8: Contradiction Analysis (g-08)
        {
            "id": "u-08",
            "kind": "analysis",
            "title": "Противоречие между формулой SLA и маркетинговым аптаймом",
            "text": "Формула в договоре исключает плановые окна, тогда как заявление 99.99% подается без уточнения доли вычтенного времени обслуживания.",
            "text_format": "markdown-safe",
            "summary": "Противоречие между декларацией и методикой",
            "author_refs": ["auth-eng-01", "auth-legal-01"],
            "epistemic": "supported",
            "status": "reviewed",
            "source_refs": ["u-03", "u-04"],
            "asset_ids": []
        },
        {
            "id": "u-08b",
            "kind": "action",
            "title": "Фиксация разногласий в протоколе",
            "text": "Внести обнаруженное противоречие в протокол юридических разногласий.",
            "text_format": "plain",
            "author_refs": ["auth-legal-01"],
            "epistemic": "not-applicable",
            "status": "reviewed",
            "source_refs": [],
            "asset_ids": []
        },

        # Group 9: Preliminary Conclusion (g-09)
        {
            "id": "u-09",
            "kind": "analysis",
            "title": "Предварительный вывод о соответствии SLA 99.95%",
            "text": "Предварительный вывод: Архитектура Multi-AZ и исторические показатели провайдера подтверждают выполнимость требования 99.95%, однако вывод носит условный характер до проверки журналов плановых работ.",
            "text_format": "markdown-safe",
            "summary": "Предварительное соответствие требованиям",
            "author_refs": ["auth-lead-arch", "auth-legal-01"],
            "epistemic": "supported",
            "status": "reviewed",
            "source_refs": ["u-01", "u-03"],
            "asset_ids": []
        },
        {
            "id": "u-09b",
            "kind": "analysis",
            "title": "Ограничения доверия к выводу",
            "text": "Доверие ограничено отсутствием первичных журналов плановых работ за 2025-2026 годы.",
            "text_format": "plain",
            "author_refs": ["auth-lead-arch"],
            "epistemic": "supported",
            "status": "reviewed",
            "source_refs": ["u-01"],
            "asset_ids": []
        },

        # Group 10: Qualification Boundaries (g-10)
        {
            "id": "u-10",
            "kind": "analysis",
            "title": "Квалификация: Влияние регламентного окна на вывод",
            "text": "Исключение планового обслуживания квалифицирует предварительный вывод о соответствии: пока не проведен независимый аудит журналов ТО, показатель 99.99% не является доказательством надёжности.",
            "text_format": "plain",
            "summary": "Квалифицирующее условие вывода",
            "author_refs": ["auth-legal-01"],
            "epistemic": "supported",
            "status": "reviewed",
            "source_refs": ["u-04"],
            "asset_ids": []
        },
        {
            "id": "u-10b",
            "kind": "action",
            "title": "Утверждение перечня критических оговорок",
            "text": "Утвердить оговорку о плановых работах в финальном отчете для руководства.",
            "text_format": "plain",
            "author_refs": ["auth-legal-01"],
            "epistemic": "not-applicable",
            "status": "draft",
            "source_refs": [],
            "asset_ids": []
        },

        # Group 11: Recommended Action: Method & Logs (g-11)
        {
            "id": "u-11",
            "kind": "action",
            "title": "Запрос методики расчета и журналов регламентных окон",
            "text": "Рекомендуемое действие 1: Направить официальный запрос поставщику на предоставление детальной методики зондирования доступности и исходных журналов учета регламентных окон за 12 месяцев.",
            "text_format": "plain",
            "summary": "Запрос первичных журналов ТО",
            "author_refs": ["auth-legal-01"],
            "epistemic": "not-applicable",
            "status": "draft",
            "source_refs": [],
            "asset_ids": []
        },
        {
            "id": "u-11b",
            "kind": "action",
            "title": "Установление дедлайна ответа поставщика",
            "text": "Установить срок ответа провайдера в 10 рабочих дней с момента вручения запроса.",
            "text_format": "plain",
            "author_refs": ["auth-legal-01"],
            "epistemic": "not-applicable",
            "status": "draft",
            "source_refs": [],
            "asset_ids": []
        },

        # Group 12: Escalation & Audit (g-12)
        {
            "id": "u-12",
            "kind": "action",
            "title": "Подготовка к независимому аудиту доступности",
            "text": "Рекомендуемое действие 2: Подготовить техническое задание на независимый аудит телеметрии с привлечением внешней аудиторской компании при отказе в предоставлении журналов.",
            "text_format": "plain",
            "summary": "Внешний аудит телеметрии",
            "author_refs": ["auth-eng-01"],
            "epistemic": "not-applicable",
            "status": "draft",
            "source_refs": [],
            "asset_ids": []
        },
        {
            "id": "u-12b",
            "kind": "action",
            "title": "Формирование бюджета: независимый аудит",
            "text": "Зарезервировать бюджет на процедуру: внешний независимый аудит телеметрии.",
            "text_format": "plain",
            "author_refs": ["auth-eng-01"],
            "epistemic": "not-applicable",
            "status": "draft",
            "source_refs": [],
            "asset_ids": []
        }
    ]

    # 4. Define 12 Groups
    groups = [
        {"id": "g-01", "title": "1. Требования к доступности сервиса (SLA)", "unit_refs": ["u-01", "u-01b"]},
        {"id": "g-02", "title": "2. Архитектура высокой доступности (Multi-AZ)", "unit_refs": ["u-02", "u-02b"]},
        {"id": "g-03", "title": "3. Заявление поставщика об историческом аптайме (99.99%)", "unit_refs": ["u-03", "u-03b"]},
        {"id": "g-04", "title": "4. Исключения из расчета доступности (Плановые работы)", "unit_refs": ["u-04", "u-04b"]},
        {"id": "g-05", "title": "5. Методика и журнал учета времени простоя (Полный текст договора)", "unit_refs": ["u-05", "u-05b"]},
        {"id": "g-06", "title": "6. График регламентного обслуживания (Вложения)", "unit_refs": ["u-06", "u-06b"]},
        {"id": "g-07", "title": "7. Оценка окна измерения и интервалов мониторинга", "unit_refs": ["u-07", "u-07b"]},
        {"id": "g-08", "title": "8. Анализ противоречий между заявлением и формулой SLA", "unit_refs": ["u-08", "u-08b"]},
        {"id": "g-09", "title": "9. Предварительный вывод о соответствии", "unit_refs": ["u-09", "u-09b"]},
        {"id": "g-10", "title": "10. Ограничения предварительного вывода", "unit_refs": ["u-10", "u-10b"]},
        {"id": "g-11", "title": "11. Рекомендуемые юридические и инженерные действия", "unit_refs": ["u-11", "u-11b"]},
        {"id": "g-12", "title": "12. Связанные процедуры эскалации", "unit_refs": ["u-12", "u-12b"]}
    ]

    # 5. Define 8 Nodes and 9 Edges (all 6 relations represented)
    nodes = [
        {"id": "node-sla-req", "label": "Требование SLA 99.95%", "unit_refs": ["u-01"]},
        {"id": "node-multi-az", "label": "Архитектура Multi-AZ", "unit_refs": ["u-02"]},
        {"id": "node-uptime-claim", "label": "Заявление 99.99%", "unit_refs": ["u-03"]},
        {"id": "node-maint-clause", "label": "Исключение регламентных работ", "unit_refs": ["u-04"]},
        {"id": "node-meas-window", "label": "Неизвестность окна измерений", "unit_refs": ["u-07"]},
        {"id": "node-prelim-compl", "label": "Предварительное соответствие", "unit_refs": ["u-09"]},
        {"id": "node-method-request", "label": "Запрос журнала и методики", "unit_refs": ["u-11"]},
        {"id": "node-audit-prep", "label": "Подготовка независимого аудита", "unit_refs": ["u-12"]}
    ]

    edges = [
        # edge-01: supports (Multi-AZ supports preliminary compliance)
        {
            "id": "edge-01",
            "from": "node-multi-az",
            "to": "node-prelim-compl",
            "relation": "supports",
            "label": "Архитектурная основа соответствия",
            "unit_refs": ["u-02", "u-09"]
        },
        # edge-02: supports (Uptime claim supports preliminary compliance)
        {
            "id": "edge-02",
            "from": "node-uptime-claim",
            "to": "node-prelim-compl",
            "relation": "supports",
            "label": "Эмпирическое основание надежности",
            "unit_refs": ["u-03", "u-09"]
        },
        # edge-03: qualifies (CRITICAL QUALIFICATION: Maintenance clause qualifies compliance conclusion)
        {
            "id": "edge-03",
            "from": "node-maint-clause",
            "to": "node-prelim-compl",
            "relation": "qualifies",
            "label": "Квалификация: исключение планового ТО",
            "unit_refs": ["u-04", "u-09", "u-10"]
        },
        # edge-04: qualifies (Measurement window qualifies uptime claim)
        {
            "id": "edge-04",
            "from": "node-meas-window",
            "to": "node-uptime-claim",
            "relation": "qualifies",
            "label": "Дискретность зондирования ослабляет оценку",
            "unit_refs": ["u-07", "u-03"]
        },
        # edge-05: contradicts (Maintenance clause contradicts raw 99.99% marketing claim)
        {
            "id": "edge-05",
            "from": "node-maint-clause",
            "to": "node-uptime-claim",
            "relation": "contradicts",
            "label": "Противоречие: вычет планового простоя",
            "unit_refs": ["u-04", "u-03", "u-08"]
        },
        # edge-06: depends_on (Compliance verification depends on method request)
        {
            "id": "edge-06",
            "from": "node-prelim-compl",
            "to": "node-method-request",
            "relation": "depends_on",
            "label": "Финальный статус зависит от проверки логов",
            "unit_refs": ["u-09", "u-11"]
        },
        # edge-07: precedes (Method request precedes external audit)
        {
            "id": "edge-07",
            "from": "node-method-request",
            "to": "node-audit-prep",
            "relation": "precedes",
            "label": "Запрос предшествует назначению аудита",
            "unit_refs": ["u-11", "u-12"]
        },
        # edge-08: compares (Symmetric comparison between SLA 99.95% requirement and 99.99% claim)
        {
            "id": "edge-08",
            "from": "node-sla-req",
            "to": "node-uptime-claim",
            "relation": "compares",
            "label": "Сравнение: требование 99.95% против декларации 99.99%",
            "unit_refs": ["u-01", "u-03"]
        },
        # edge-09: depends_on (Audit preparation depends on method request outcome — creates cycle in depends_on)
        {
            "id": "edge-09",
            "from": "node-audit-prep",
            "to": "node-method-request",
            "relation": "depends_on",
            "label": "Аудит зависит от непредоставления журналов",
            "unit_refs": ["u-12", "u-11"]
        }
    ]

    visual = {
        "id": "vis-g-01",
        "type": "relationship-graph",
        "title": "Семантический граф оценки SLA и исключений планового ТО",
        "question": "Подтверждает ли заявление провайдера 99.99% выполнение требования 99.95% с учетом исключения планового ТО?",
        "fallback": "Таблица отношений: 8 узлов и 9 ребер, связывающих архитектуру, заявление провайдера, исключение ТО и выводы.",
        "owner_unit_id": "u-02",  # kind=model, required!
        "author_refs": ["auth-lead-arch"],
        "nodes": nodes,
        "edges": edges
    }

    doc = {
        "format": "paralleldoc",
        "version": "3.0",
        "metadata": {
            "document_id": "doc-sla-benchmark-g",
            "revision": "rev-1.0",
            "title": "Оценка соответствия SLA облачной инфраструктуры (99.95% vs 99.99%)",
            "created_at": "2026-09-06T19:00:00Z",
            "language": "ru",
            "author_refs": ["auth-lead-arch", "auth-legal-01", "auth-eng-01"],
            "default_profile_id": "builtin:3"
        },
        "authors": [
            {"id": "auth-lead-arch", "kind": "human", "name": "Главный системный архитектор"},
            {"id": "auth-legal-01", "kind": "human", "name": "Ведущий юрисконсульт по SLA"},
            {"id": "auth-eng-01", "kind": "human", "name": "Инженер по надежности инфраструктуры (SRE)"},
            {"id": "auth-vendor-rep", "kind": "human", "name": "Представитель облачного провайдера"}
        ],
        "units": units,
        "groups": groups,
        "visuals": [visual],
        "assets": [asset_png, asset_jpeg, asset_webp],
        "profiles": []
    }

    doc_bytes = json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8")
    doc_path = target_dir / "corpus_G_sla_document.json"
    doc_path.write_bytes(doc_bytes)
    doc_sha256 = hashlib.sha256(doc_bytes).hexdigest().lower()

    # 6. Generate Control Answer Table (JSON & Markdown)
    control_data = {
        "document": {
            "file": "corpus_G_sla_document.json",
            "sha256": doc_sha256,
            "bytes": len(doc_bytes),
            "groups_count": len(groups),
            "units_count": len(units),
            "nodes_count": len(nodes),
            "edges_count": len(edges),
            "assets_count": 3,
            "long_quote_chars": len(full_quote_8k)
        },
        "semantic_deductions": {
            "preliminary_conclusion": {
                "unit_id": "u-09",
                "node_id": "node-prelim-compl",
                "text_snippet": "Предварительное соответствие SLA 99.95%"
            },
            "premises": [
                {
                    "unit_id": "u-02",
                    "node_id": "node-multi-az",
                    "label": "Архитектура Multi-AZ",
                    "edge_id": "edge-01",
                    "relation": "supports"
                },
                {
                    "unit_id": "u-03",
                    "node_id": "node-uptime-claim",
                    "label": "Заявление провайдера об историческом аптайме 99.99%",
                    "edge_id": "edge-02",
                    "relation": "supports"
                }
            ],
            "critical_qualification": {
                "unit_id": "u-04",
                "node_id": "node-maint-clause",
                "edge_id": "edge-03",
                "relation": "qualifies",
                "target_node_id": "node-prelim-compl",
                "reasoning": "Исключение регламентных окон обслуживания ослабляет вывод: без проверки журналов плановых работ заявление 99.99% не является доказательством надёжности."
            },
            "recommended_action": {
                "unit_id": "u-11",
                "node_id": "node-method-request",
                "edge_id": "edge-06",
                "relation": "depends_on",
                "action_summary": "Запросить подробную методику расчета доступности и исходные журналы регламентных окон."
            },
            "why_claim_is_not_proof": (
                "Заявление 99.99% не является строгим доказательством, поскольку регламентные работы "
                "вычитаются из знаменателя времени расчета, и без первичных журналов невозможно "
                "исключить сокрытие аварийных простоев под видом планового техобслуживания."
            )
        },
        "cross_highlighting": {
            "node_to_units": {n["id"]: n["unit_refs"] for n in nodes},
            "edge_to_units": {e["id"]: e["unit_refs"] for e in edges},
            "unit_to_graph": {
                "u-01": {"nodes": ["node-sla-req"], "edges": ["edge-08"]},
                "u-02": {"nodes": ["node-multi-az"], "edges": ["edge-01"]},
                "u-03": {"nodes": ["node-uptime-claim"], "edges": ["edge-02", "edge-04", "edge-05", "edge-08"]},
                "u-04": {"nodes": ["node-maint-clause"], "edges": ["edge-03", "edge-05"]},
                "u-07": {"nodes": ["node-meas-window"], "edges": ["edge-04"]},
                "u-09": {"nodes": ["node-prelim-compl"], "edges": ["edge-01", "edge-02", "edge-03", "edge-06"]},
                "u-11": {"nodes": ["node-method-request"], "edges": ["edge-06", "edge-07", "edge-09"]},
                "u-12": {"nodes": ["node-audit-prep"], "edges": ["edge-07", "edge-09"]}
            },
            "dual_conclusion_test": {
                "source_unit": "u-03",
                "connected_edges": ["edge-02", "edge-08"],
                "connected_targets": ["node-prelim-compl", "node-sla-req"]
            }
        },
        "navigation_jump_targets": [
            {"target": "u-05", "description": "Длинная цитата договора (>8000 символов, автоматическое раскрытие)"},
            {"target": "u-12", "description": "Нижний блок действий (планирование аудита)"},
            {"target": "u-02", "description": "Модель Multi-AZ с растровой схемой ast-g-01"},
            {"target": "u-06", "description": "Галерея из 3 растровых вложений"},
            {"target": "u-04", "description": "Пункт договора об исключении ТО"},
            {"target": "u-07", "description": "Анализ окна измерений провайдера"},
            {"target": "u-09", "description": "Предварительный вывод о соответствии"},
            {"target": "u-11", "description": "Рекомендуемое действие (запрос логов)"},
            {"target": "u-01", "description": "Первое требование SLA 99.95%"},
            {"target": "u-03", "description": "Декларация исторического аптайма 99.99%"}
        ],
        "literal_search_queries": [
            {"query": "99.95%", "expected_units": ["u-01", "u-01b", "u-03b", "u-09"], "description": "Спецификация SLA"},
            {"query": "Multi-AZ", "expected_units": ["u-02", "u-02b", "u-09"], "description": "Архитектурный термин"},
            {"query": "РЕГЛАМЕНТНЫЙ_МАРКЕР_7749", "expected_units": ["u-05"], "description": "Уникальный токен в середине длинной цитаты"},
            {"query": "48 часов", "expected_units": ["u-01", "u-05"], "description": "Срок анонсирования плановых окон"},
            {"query": "21.6 минут", "expected_units": ["u-01b", "u-03b"], "description": "Числовое значение предельного простоя"},
            {"query": "failover", "expected_units": ["u-02"], "description": "Технический термин времени переключения"},
            {"query": "ast-g-01", "expected_units": ["u-02", "u-06", "u-06b"], "description": "Идентификатор ассета схемы"},
            {"query": "Статья 5.2", "expected_units": ["u-05", "u-05b"], "description": "Нормативная ссылка договора"},
            {"query": "бремя доказывания", "expected_units": ["u-05", "u-05b"], "description": "Юридический термин"},
            {"query": "независимый аудит", "expected_units": ["u-10", "u-12", "u-12b"], "description": "Эскалационное действие"}
        ]
    }

    (target_dir / "corpus_G_control.json").write_text(json.dumps(control_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Generate Markdown control table
    md_content = f"""# Control Table: Corpus G (Synthetic SLA Benchmark)

> **Document**: `corpus_G_sla_document.json`  
> **Raw SHA-256**: `{doc_sha256}`  
> **Byte Length**: {len(doc_bytes)} bytes  
> **Groups**: {len(groups)} (>=12) | **Units**: {len(units)} (>=24) | **Quote u-05**: {len(full_quote_8k)} chars (>=8,000)  
> **Graph**: {len(nodes)} nodes / {len(edges)} edges (all 6 relations, branch, cross-group, cycle)  
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
"""
    (target_dir / "corpus_G_control.md").write_text(md_content, encoding="utf-8")
    print(f"Corpus G successfully materialized in {target_dir} ({doc_path.name}, {len(doc_bytes)} bytes, {doc_sha256[:16]}...).")


if __name__ == "__main__":
    generate_corpus_g(Path("fixtures/corpus_G"))
