"""
ParallelDoc 3.0 (r2 / V3-ONLY) — Referential Integrity & Schema Validator.
Strict compliance with Spec r2 §7, §8, §9, §11 (AC-07, AC-08, AC-25, AC-26).
"""

import base64
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
import struct
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union
import unicodedata

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False


RFC3339_STRICT_PATTERN = re.compile(
    r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])"
    r"[Tt](?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?"
    r"(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)


def check_datetime(val: Any) -> bool:
    """Validate RFC 3339 Section 5.6 date-time with mandatory timezone offset."""
    if not isinstance(val, str):
        return True
    if not RFC3339_STRICT_PATTERN.match(val):
        return False
    try:
        norm = val[:-1] + "+00:00" if val.endswith(("Z", "z")) else val
        dt = datetime.fromisoformat(norm)
        return dt.tzinfo is not None
    except (ValueError, TypeError):
        return False


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    path: str  # RFC 6901 JSON Pointer (e.g. /units/0/id)
    message: str  # Russian descriptive message
    severity: IssueSeverity  # ERROR, WARNING, INFO
    code: str  # Machine-readable error code
    line: Optional[int] = None
    column: Optional[int] = None
    snippet: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentIntegrityReport:
    is_valid: bool
    structure_state: str  # 'valid', 'partial', 'invalid'
    document_status: str  # alias for structure_state ('valid', 'partial', 'invalid')
    issues: List[ValidationIssue]
    raw_sha256: str
    orphan_units: List[str]
    reconciled_groups: List[Dict[str, Any]]
    synthetic_orphan_group: Optional[Dict[str, Any]]
    stats: Dict[str, int]


@dataclass
class ManifestValidationReport:
    is_valid: bool
    issues: List[ValidationIssue]
    manifest: Optional[Dict[str, Any]]


def to_json_pointer(path_tokens: Iterable[Any]) -> str:
    """Convert an iterable of path keys/indexes to an RFC 6901 JSON Pointer."""
    tokens = list(path_tokens)
    if not tokens:
        return ""
    escaped = [
        str(token).replace("~", "~0").replace("/", "~1")
        for token in tokens
    ]
    return "/" + "/".join(escaped)


def get_default_format_checker() -> Optional[Any]:
    """Create Draft 2020-12 FormatChecker with strict RFC 3339 date-time verification."""
    if not JSONSCHEMA_AVAILABLE:
        return None
    checker = jsonschema.FormatChecker()

    @checker.checks("date-time")
    def _validate_datetime(val: Any) -> bool:
        return check_datetime(val)

    return checker

# Media Contract Constants per Spec r2 §5
MAX_ASSET_BYTES = 8 * 1024 * 1024        # 8 MiB = 8,388,608 bytes
MAX_DOC_MEDIA_BYTES = 32 * 1024 * 1024   # 32 MiB = 33,554,432 bytes
MAX_DOC_ASSET_COUNT = 50                 # 50 assets
MAX_IMAGE_PIXELS = 16 * 1024 * 1024      # 16 MP = 16,777,216 pixels
MAX_IMAGE_SIDE = 8192                    # 8,192 pixels
ALLOWED_MIMES = {"image/png", "image/jpeg", "image/webp"}


def parse_image_header(bytes_data: bytes, declared_mime: str) -> Tuple[bool, Dict[str, Any]]:
    """Inspect binary magic bytes, dimensions, and static animation constraints."""
    if not isinstance(bytes_data, (bytes, bytearray)) or len(bytes_data) < 12:
        return False, {"code": "ERR_ASSET_CORRUPTED_BASE64", "error": "Слишком короткий двоичный поток (менее 12 байт)"}

    # 1. Check PNG: \x89PNG\r\n\x1a\n
    if bytes_data.startswith(b"\x89PNG\r\n\x1a\n"):
        if declared_mime != "image/png":
            return False, {"code": "ERR_ASSET_MIME_SPOOFING", "error": f"Подмена типа: сигнатура PNG, но заявлен '{declared_mime}'"}
        if len(bytes_data) < 24:
            return False, {"code": "ERR_ASSET_CORRUPTED_BASE64", "error": "Повреждённый чанк IHDR в PNG"}
        if bytes_data[12:16] != b"IHDR":
            return False, {"code": "ERR_ASSET_CORRUPTED_BASE64", "error": "Отсутствует обязательный первый чанк IHDR в PNG"}
        width, height = struct.unpack(">II", bytes_data[16:24])
        if width == 0 or height == 0:
            return False, {"code": "ERR_ASSET_DIMENSIONS_MISMATCH", "error": "Нулевые размеры в чанке IHDR PNG"}
        return True, {"mime": "image/png", "width": width, "height": height, "is_animated": False}

    # 2. Check JPEG: \xFF\xD8\xFF
    if bytes_data.startswith(b"\xFF\xD8\xFF"):
        if declared_mime != "image/jpeg":
            return False, {"code": "ERR_ASSET_MIME_SPOOFING", "error": f"Подмена типа: сигнатура JPEG, но заявлен '{declared_mime}'"}
        offset = 2
        found_sof = False
        width = 0
        height = 0
        while offset < len(bytes_data) - 8:
            if bytes_data[offset] != 0xFF:
                offset += 1
                continue
            while offset < len(bytes_data) and bytes_data[offset] == 0xFF:
                offset += 1
            if offset >= len(bytes_data):
                break
            marker = bytes_data[offset]
            offset += 1
            if marker in (0xD9, 0xDA):
                break
            if (0xD0 <= marker <= 0xD7) or marker in (0x01, 0x00):
                continue
            if offset + 2 > len(bytes_data):
                break
            seg_len = struct.unpack(">H", bytes_data[offset:offset + 2])[0]
            if seg_len < 2:
                break
            is_sof = (
                (0xC0 <= marker <= 0xC3) or
                (0xC5 <= marker <= 0xC7) or
                (0xC9 <= marker <= 0xCB) or
                (0xCD <= marker <= 0xCF)
            )
            if is_sof and offset + 7 <= len(bytes_data):
                height, width = struct.unpack(">HH", bytes_data[offset + 3:offset + 7])
                found_sof = True
                break
            offset += seg_len

        if not found_sof or width == 0 or height == 0:
            return False, {"code": "ERR_ASSET_CORRUPTED_BASE64", "error": "Не найден маркер кадра SOF в JPEG или нулевые размеры"}
        return True, {"mime": "image/jpeg", "width": width, "height": height, "is_animated": False}

    # 3. Check WebP: RIFF....WEBP
    if bytes_data.startswith(b"RIFF") and len(bytes_data) >= 12 and bytes_data[8:12] == b"WEBP":
        if declared_mime != "image/webp":
            return False, {"code": "ERR_ASSET_MIME_SPOOFING", "error": f"Подмена типа: сигнатура WebP, но заявлен '{declared_mime}'"}
        offset = 12
        width = 0
        height = 0
        found_dims = False
        is_animated = False

        while offset + 8 <= len(bytes_data):
            tag = bytes_data[offset:offset + 4]
            chunk_size = struct.unpack("<I", bytes_data[offset + 4:offset + 8])[0]
            data_offset = offset + 8

            if tag in (b"ANIM", b"ANMF"):
                is_animated = True

            if tag == b"VP8X" and data_offset + 10 <= len(bytes_data):
                flags = bytes_data[data_offset]
                if flags & 0x02:
                    is_animated = True
                w_m1 = bytes_data[data_offset + 4] | (bytes_data[data_offset + 5] << 8) | (bytes_data[data_offset + 6] << 16)
                h_m1 = bytes_data[data_offset + 7] | (bytes_data[data_offset + 8] << 8) | (bytes_data[data_offset + 9] << 16)
                width = w_m1 + 1
                height = h_m1 + 1
                found_dims = True
            elif tag == b"VP8 " and data_offset + 10 <= len(bytes_data):
                if bytes_data[data_offset + 3:data_offset + 6] == b"\x9d\x01\x2a":
                    raw_w, raw_h = struct.unpack("<HH", bytes_data[data_offset + 6:data_offset + 10])
                    width = raw_w & 0x3FFF
                    height = raw_h & 0x3FFF
                    found_dims = True
            elif tag == b"VP8L" and data_offset + 5 <= len(bytes_data):
                if bytes_data[data_offset] == 0x2F:
                    b0, b1, b2, b3 = bytes_data[data_offset + 1:data_offset + 5]
                    width = 1 + (b0 | ((b1 & 0x3F) << 8))
                    height = 1 + (((b1 >> 6) | (b2 << 2) | ((b3 & 0x0F) << 10)))
                    found_dims = True

            padded_size = chunk_size + (chunk_size & 1)
            offset = data_offset + padded_size

        if is_animated:
            return False, {"code": "ERR_ASSET_ANIMATED_WEBP", "error": "Анимированный WebP запрещен спецификацией r2 (§5)"}
        if not found_dims or width == 0 or height == 0:
            return False, {"code": "ERR_ASSET_CORRUPTED_BASE64", "error": "Не удалось извлечь размеры из чанков WebP"}
        return True, {"mime": "image/webp", "width": width, "height": height, "is_animated": False}

    return False, {"code": "ERR_ASSET_MIME_SPOOFING", "error": f"Нераспознанная двоичная сигнатура файла; не соответствует {declared_mime}"}


def validate_asset_locator(locator: Any) -> Tuple[bool, str, str, Dict[str, Any]]:
    """Asset locator security guard per AC-24."""
    if not isinstance(locator, dict):
        return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Локатор ресурса отсутствует или не является объектом", {}
    mode = locator.get("mode")
    if mode == "embedded":
        uri = locator.get("data_uri")
        if not isinstance(uri, str) or not uri:
            return False, "ERR_ASSET_CORRUPTED_BASE64", "Отсутствует поле data_uri для embedded ресурса", {}
        m = re.match(r"^data:image/(png|jpeg|webp);base64,(.+)$", uri)
        if not m:
            return False, "ERR_ASSET_CORRUPTED_BASE64", "Недопустимый формат Data URI (требуется data:image/(png|jpeg|webp);base64,...)", {}
        b64 = m.group(2)
        if not re.match(r"^[A-Za-z0-9+/]+={0,2}$", b64) or len(b64) % 4 != 0:
            return False, "ERR_ASSET_CORRUPTED_BASE64", "Некорректная Base64 строка в Data URI", {}
        return True, "", "", {"submime": f"image/{m.group(1)}", "base64": b64}

    if mode == "relative":
        p = locator.get("path")
        if not isinstance(p, str) or not p.strip():
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Путь к относительному ресурсу пуст", {}
        if re.search(r"^[A-Za-z]:", p):
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Запрещён абсолютный путь с буквой диска Windows (AC-24)", {}
        if re.search(r"^(\\\\|//)", p):
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Запрещён сетевой путь UNC (AC-24)", {}
        if re.search(r"^[a-zA-Z][a-zA-Z0-9+-.]*:", p):
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Запрещены схемы протоколов в относительном пути (AC-24)", {}
        if p.startswith("/"):
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Запрещён абсолютный путь POSIX (AC-24)", {}
        if re.search(r"(^|/|\\)\.\.(/|\\|$)", p):
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Запрещен выход за пределы каталога (.. traversal, AC-24)", {}
        if "\\" in p:
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Запрещены обратные косые черты (требуется POSIX slash /, AC-24)", {}
        if "%" in p:
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Символ % запрещён в относительном имени файла (§5)", {}
        if ":" in p:
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Символ : запрещён в относительном имени файла (§5)", {}
        if re.search(r"[?#]", p):
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Символы ? и # запрещены в относительном пути", {}
        if not unicodedata.is_normalized("NFC", p):
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Путь должен быть нормализован по форме Unicode NFC", {}
        return True, "", "", {"path": p}

    if mode == "external":
        u = locator.get("url")
        if not isinstance(u, str) or not u.strip():
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "URL внешнего ресурса пуст", {}
        if not u.lower().startswith("https://"):
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Внешние ресурсы должны строго использовать протокол https:// (AC-24)", {}
        if re.search(r"^https://[^/?#]*@", u, re.IGNORECASE):
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Запрещены учетные данные (credentials) в URL (AC-24)", {}
        if "\\" in u:
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Запрещены обратные косые черты в URL", {}
        if "/../" in u or u.endswith("/.."):
            return False, "ERR_FORBIDDEN_ASSET_LOCATOR", "Запрещен выход за пределы пути (..) в URL", {}
        return True, "", "", {"url": u}

    return False, "ERR_FORBIDDEN_ASSET_LOCATOR", f"Неподдерживаемый режим локатора: '{mode}'", {}


class IntegrityEngine:
    """Referential integrity and semantic validation engine for ParallelDoc 3.0."""

    RELATIONS = {"supports", "qualifies", "contradicts", "depends_on", "precedes", "compares"}
    DIRECTED_RELATIONS = {"supports", "qualifies", "contradicts", "depends_on", "precedes"}
    SYMMETRIC_RELATIONS = {"compares"}
    REQUIRED_KINDS = {"source", "model", "analysis", "action"}

    def __init__(
        self,
        schema_v3_path: Optional[Path] = None,
        manifest_schema_path: Optional[Path] = None,
    ):
        base_dir = Path(__file__).resolve().parent.parent
        self.schema_v3_path = schema_v3_path or (base_dir / "schema.v3.json")
        self.manifest_schema_path = manifest_schema_path or (base_dir / "manifest.schema.json")

        self.schema_v3 = self._load_json(self.schema_v3_path)
        self.manifest_schema = self._load_json(self.manifest_schema_path)
        self.format_checker = get_default_format_checker()

    def _load_json(self, path: Path) -> Optional[Dict[str, Any]]:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def compute_raw_sha256(self, raw_bytes: bytes) -> str:
        """Exact SHA-256 over raw binary bytes (UTF-8 BOM preserved, zero CRLF/LF norm)."""
        return hashlib.sha256(raw_bytes).hexdigest()

    def validate_manifest(self, manifest_data: Any) -> ManifestValidationReport:
        """Validate detached integrity manifest against manifest.schema.json."""
        issues: List[ValidationIssue] = []
        if not JSONSCHEMA_AVAILABLE:
            issues.append(
                ValidationIssue(
                    path="",
                    message="Библиотека jsonschema недоступна",
                    severity=IssueSeverity.ERROR,
                    code="ERR_NO_JSONSCHEMA",
                )
            )
            return ManifestValidationReport(is_valid=False, issues=issues, manifest=None)

        if self.manifest_schema:
            validator = Draft202012Validator(self.manifest_schema, format_checker=self.format_checker)
            for err in validator.iter_errors(manifest_data):
                pointer = to_json_pointer(err.absolute_path)
                issues.append(
                    ValidationIssue(
                        path=pointer,
                        message=f"Ошибка схемы манифеста: {err.message}",
                        severity=IssueSeverity.ERROR,
                        code="ERR_MANIFEST_SCHEMA_VIOLATION",
                        context={"validator": err.validator, "schema_path": list(err.schema_path)},
                    )
                )

        return ManifestValidationReport(
            is_valid=len(issues) == 0,
            issues=issues,
            manifest=manifest_data if not issues else None,
        )

    def check_manifest_match(
        self,
        manifest: Dict[str, Any],
        doc_metadata: Dict[str, Any],
        raw_sha256: str,
    ) -> Tuple[str, str]:
        """Check whether manifest matches loaded document.

        Returns (status, message).
        Status values: 'matched', 'mismatch', 'different_document'.
        """
        doc_id = doc_metadata.get("document_id")
        doc_rev = doc_metadata.get("revision")
        man_id = manifest.get("document_id")
        man_rev = manifest.get("revision")

        if man_id is not None and man_id != doc_id:
            return "different_document", f"Манифест принадлежит другому документу ({man_id} != {doc_id})"
        if man_rev is not None and man_rev != doc_rev:
            return "different_document", f"Манифест принадлежит другой ревизии ({man_rev} != {doc_rev})"

        if manifest.get("expected_sha256") == raw_sha256:
            return "matched", "Хэш совпал с эталоном"
        return "mismatch", "Другая версия или изменение (SHA mismatch)"

    def validate_media_contract(
        self,
        doc_or_assets: Any,
        total_budget_state: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[ValidationIssue], Dict[str, Any]]:
        """Validate media contract, binary payload, headers, budgets, and locator security (F34, F35, F39)."""
        issues: List[ValidationIssue] = []
        budget_state = total_budget_state if total_budget_state is not None else {"total_bytes": 0, "count": 0}

        assets: List[Any] = []
        if isinstance(doc_or_assets, dict):
            raw_assets = doc_or_assets.get("assets", [])
            assets = raw_assets if isinstance(raw_assets, list) else []
        elif isinstance(doc_or_assets, list):
            assets = doc_or_assets

        if len(assets) > MAX_DOC_ASSET_COUNT:
            issues.append(
                ValidationIssue(
                    path="/assets",
                    message=f"Число вложений ({len(assets)}) превышает лимит {MAX_DOC_ASSET_COUNT}",
                    severity=IssueSeverity.ERROR,
                    code="ERR_DOC_ASSET_COUNT_EXCEEDED",
                )
            )

        seen_relative_paths: Set[str] = set()

        for a_idx, a in enumerate(assets):
            if not isinstance(a, dict):
                continue
            base_path = f"/assets/{a_idx}"

            mime = a.get("mime")
            if mime not in ALLOWED_MIMES:
                issues.append(
                    ValidationIssue(
                        path=f"{base_path}/mime",
                        message=f"Недопустимый MIME тип '{mime}'; разрешены строго image/png, image/jpeg, image/webp",
                        severity=IssueSeverity.ERROR,
                        code="ERR_ASSET_INVALID_MIME",
                    )
                )

            width = a.get("width", 0)
            height = a.get("height", 0)
            if isinstance(width, int) and isinstance(height, int):
                if width > MAX_IMAGE_SIDE or height > MAX_IMAGE_SIDE:
                    issues.append(
                        ValidationIssue(
                            path=f"{base_path}/width",
                            message=f"Сторона изображения ({width}x{height}) превышает лимит {MAX_IMAGE_SIDE}px",
                            severity=IssueSeverity.ERROR,
                            code="ERR_ASSET_DIMENSIONS_EXCEEDED",
                        )
                    )
                if width * height > MAX_IMAGE_PIXELS:
                    issues.append(
                        ValidationIssue(
                            path=f"{base_path}/width",
                            message=f"Площадь изображения ({width * height} px) превышает лимит 16 MP ({MAX_IMAGE_PIXELS} px)",
                            severity=IssueSeverity.ERROR,
                            code="ERR_ASSET_DIMENSIONS_EXCEEDED",
                        )
                    )

            locator = a.get("locator")
            loc_ok, loc_code, loc_reason, loc_info = validate_asset_locator(locator)
            if not loc_ok:
                issues.append(
                    ValidationIssue(
                        path=f"{base_path}/locator",
                        message=loc_reason,
                        severity=IssueSeverity.ERROR,
                        code=loc_code,
                    )
                )
                continue

            # Duplicate relative paths check per Spec §5
            if locator and locator.get("mode") == "relative":
                rel_p = loc_info.get("path")
                if rel_p:
                    if rel_p in seen_relative_paths:
                        issues.append(
                            ValidationIssue(
                                path=f"{base_path}/locator/path",
                                message=f"Дублирующийся путь к относительному ресурсу: '{rel_p}'",
                                severity=IssueSeverity.ERROR,
                                code="ERR_FORBIDDEN_ASSET_LOCATOR",
                            )
                        )
                    seen_relative_paths.add(rel_p)

            # Embedded asset decoding and binary inspection
            if locator and locator.get("mode") == "embedded":
                b64 = loc_info.get("base64", "")
                if len(b64) * 0.75 > MAX_ASSET_BYTES * 1.05:
                    issues.append(
                        ValidationIssue(
                            path=f"{base_path}/byte_length",
                            message=f"Размер вложения превышает лимит 8 MiB ({MAX_ASSET_BYTES} байт)",
                            severity=IssueSeverity.ERROR,
                            code="ERR_ASSET_SIZE_BUDGET_EXCEEDED",
                        )
                    )
                    continue

                try:
                    raw_bytes = base64.b64decode(b64, validate=True)
                except Exception as e:
                    issues.append(
                        ValidationIssue(
                            path=f"{base_path}/locator/data_uri",
                            message=f"Сбой декодирования Base64: {e}",
                            severity=IssueSeverity.ERROR,
                            code="ERR_ASSET_CORRUPTED_BASE64",
                        )
                    )
                    continue

                if len(raw_bytes) > MAX_ASSET_BYTES:
                    issues.append(
                        ValidationIssue(
                            path=f"{base_path}/byte_length",
                            message=f"Фактический размер ({len(raw_bytes)} байт) превышает лимит 8 MiB ({MAX_ASSET_BYTES} байт)",
                            severity=IssueSeverity.ERROR,
                            code="ERR_ASSET_SIZE_BUDGET_EXCEEDED",
                        )
                    )

                decl_len = a.get("byte_length")
                if isinstance(decl_len, int) and decl_len != len(raw_bytes):
                    issues.append(
                        ValidationIssue(
                            path=f"{base_path}/byte_length",
                            message=f"Несовпадение размера: заявлено {decl_len} байт, фактически {len(raw_bytes)} байт",
                            severity=IssueSeverity.ERROR,
                            code="ERR_ASSET_BYTE_LENGTH_MISMATCH",
                        )
                    )

                hdr_ok, hdr_info = parse_image_header(raw_bytes, mime or "")
                if not hdr_ok:
                    issues.append(
                        ValidationIssue(
                            path=f"{base_path}/locator/data_uri",
                            message=hdr_info.get("error", "Ошибка заголовка изображения"),
                            severity=IssueSeverity.ERROR,
                            code=hdr_info.get("code", "ERR_ASSET_MIME_SPOOFING"),
                        )
                    )
                else:
                    if isinstance(width, int) and isinstance(height, int):
                        if width != hdr_info["width"] or height != hdr_info["height"]:
                            issues.append(
                                ValidationIssue(
                                    path=f"{base_path}/width",
                                    message=f"Несовпадение геометрии: заявлено {width}x{height} px, в заголовке файла {hdr_info['width']}x{hdr_info['height']} px",
                                    severity=IssueSeverity.ERROR,
                                    code="ERR_ASSET_DIMENSIONS_MISMATCH",
                                )
                            )

                actual_sha = hashlib.sha256(raw_bytes).hexdigest()
                decl_sha = a.get("sha256", "")
                if isinstance(decl_sha, str) and actual_sha.lower() != decl_sha.lower():
                    issues.append(
                        ValidationIssue(
                            path=f"{base_path}/sha256",
                            message=f"Несовпадение SHA-256: заявлен '{decl_sha}', фактически '{actual_sha}'",
                            severity=IssueSeverity.ERROR,
                            code="ERR_ASSET_HASH_MISMATCH",
                        )
                    )

                budget_state["total_bytes"] += len(raw_bytes)
                budget_state["count"] += 1

                if budget_state["count"] > MAX_DOC_ASSET_COUNT:
                    issues.append(
                        ValidationIssue(
                            path="/assets",
                            message=f"Превышено допустимое число медиа-вложений в документе (максимум {MAX_DOC_ASSET_COUNT})",
                            severity=IssueSeverity.ERROR,
                            code="ERR_DOC_ASSET_COUNT_EXCEEDED",
                        )
                    )
                if budget_state["total_bytes"] > MAX_DOC_MEDIA_BYTES:
                    issues.append(
                        ValidationIssue(
                            path="/assets",
                            message=f"Суммарный объем медиа-вложений ({budget_state['total_bytes']} байт) превышает лимит 32 MiB ({MAX_DOC_MEDIA_BYTES} байт)",
                            severity=IssueSeverity.ERROR,
                            code="ERR_DOC_MEDIA_BUDGET_EXCEEDED",
                        )
                    )

        return issues, budget_state

    def validate_document(
        self,
        input_data: Union[bytes, str, Dict[str, Any]],
        check_media: bool = False,
    ) -> DocumentIntegrityReport:
        """Complete validation pipeline: raw SHA, V3-only guard, schema, and referential integrity."""
        issues: List[ValidationIssue] = []

        if isinstance(input_data, bytes):
            raw_bytes = input_data
            raw_sha256 = self.compute_raw_sha256(raw_bytes)
            try:
                raw_text = raw_bytes.decode("utf-8-sig")
                data = json.loads(raw_text)
            except Exception as e:
                issues.append(
                    ValidationIssue(
                        path="",
                        message=f"Синтаксическая ошибка JSON: {e}",
                        severity=IssueSeverity.ERROR,
                        code="ERR_JSON_PARSE",
                    )
                )
                return DocumentIntegrityReport(
                    is_valid=False,
                    structure_state="invalid",
                    document_status="invalid",
                    issues=issues,
                    raw_sha256=raw_sha256,
                    orphan_units=[],
                    reconciled_groups=[],
                    synthetic_orphan_group=None,
                    stats={},
                )
        elif isinstance(input_data, str):
            raw_bytes = input_data.encode("utf-8")
            raw_sha256 = self.compute_raw_sha256(raw_bytes)
            try:
                data = json.loads(input_data)
            except Exception as e:
                issues.append(
                    ValidationIssue(
                        path="",
                        message=f"Синтаксическая ошибка JSON: {e}",
                        severity=IssueSeverity.ERROR,
                        code="ERR_JSON_PARSE",
                    )
                )
                return DocumentIntegrityReport(
                    is_valid=False,
                    structure_state="invalid",
                    document_status="invalid",
                    issues=issues,
                    raw_sha256=raw_sha256,
                    orphan_units=[],
                    reconciled_groups=[],
                    synthetic_orphan_group=None,
                    stats={},
                )
        elif isinstance(input_data, dict):
            data = input_data
            raw_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
            raw_sha256 = self.compute_raw_sha256(raw_bytes)
        else:
            issues.append(
                ValidationIssue(
                    path="",
                    message="Неподдерживаемый формат входных данных",
                    severity=IssueSeverity.ERROR,
                    code="ERR_INVALID_INPUT_TYPE",
                )
            )
            return DocumentIntegrityReport(
                is_valid=False,
                structure_state="invalid",
                document_status="invalid",
                issues=issues,
                raw_sha256="",
                orphan_units=[],
                reconciled_groups=[],
                synthetic_orphan_group=None,
                stats={},
            )

        # 1. Strict V3-Only Rejection Guard (§9)
        if not isinstance(data, dict):
            issues.append(
                ValidationIssue(
                    path="",
                    message="«Неподдерживаемый формат; требуется ParallelDoc 3.0»",
                    severity=IssueSeverity.ERROR,
                    code="ERR_REJECTED_UNSUPPORTED",
                )
            )
            return DocumentIntegrityReport(
                is_valid=False,
                structure_state="invalid",
                document_status="invalid",
                issues=issues,
                raw_sha256=raw_sha256,
                orphan_units=[],
                reconciled_groups=[],
                synthetic_orphan_group=None,
                stats={},
            )

        format_val = data.get("format")
        version_val = data.get("version")
        is_legacy = "columns" in data or "items" in data
        if format_val != "paralleldoc" or version_val != "3.0" or is_legacy:
            issues.append(
                ValidationIssue(
                    path="",
                    message="«Неподдерживаемый формат; требуется ParallelDoc 3.0»",
                    severity=IssueSeverity.ERROR,
                    code="ERR_REJECTED_UNSUPPORTED",
                )
            )
            # If it's outright rejected as legacy or missing format, we return early
            # but we also record the schema violation if schema validation is run.
            return DocumentIntegrityReport(
                is_valid=False,
                structure_state="invalid",
                document_status="invalid",
                issues=issues,
                raw_sha256=raw_sha256,
                orphan_units=[],
                reconciled_groups=[],
                synthetic_orphan_group=None,
                stats={},
            )

        # 2. Draft 2020-12 Schema Validation (Layer 1)
        schema_errors_found = False
        if self.schema_v3 and JSONSCHEMA_AVAILABLE:
            validator = Draft202012Validator(self.schema_v3, format_checker=self.format_checker)
            for err in validator.iter_errors(data):
                schema_errors_found = True
                pointer = to_json_pointer(err.absolute_path)
                issues.append(
                    ValidationIssue(
                        path=pointer,
                        message=f"Ошибка структуры schema.v3: {err.message}",
                        severity=IssueSeverity.ERROR,
                        code="ERR_SCHEMA_V3_VIOLATION",
                        context={"validator": err.validator, "schema_path": list(err.schema_path)},
                    )
                )

        # 3. Referential Integrity Validation (Layer 2)
        ref_issues, orphans, reconciled_groups, synth_orphan_group, stats = self._validate_referential_integrity(data)
        issues.extend(ref_issues)

        # 4. Media Contract Validation (Layer 3)
        if check_media:
            media_issues, _ = self.validate_media_contract(data)
            issues.extend(media_issues)

        # Determine overall structure state per Spec r2 §7:
        has_errors = any(i.severity == IssueSeverity.ERROR for i in issues)
        has_warnings = any(i.severity == IssueSeverity.WARNING for i in issues)

        if has_errors:
            structure_state = "invalid"
        elif has_warnings or orphans:
            structure_state = "partial"
        else:
            structure_state = "valid"

        return DocumentIntegrityReport(
            is_valid=not has_errors,
            structure_state=structure_state,
            document_status=structure_state,
            issues=issues,
            raw_sha256=raw_sha256,
            orphan_units=orphans,
            reconciled_groups=reconciled_groups,
            synthetic_orphan_group=synth_orphan_group,
            stats=stats,
        )

    def _validate_referential_integrity(
        self, doc: Dict[str, Any]
    ) -> Tuple[List[ValidationIssue], List[str], List[Dict[str, Any]], Optional[Dict[str, Any]], Dict[str, int]]:
        issues: List[ValidationIssue] = []

        def _get_list(obj: Any, key: str) -> List[Any]:
            """Safely extract a list value from obj[key], returning [] if missing, None, or not a list."""
            if not isinstance(obj, dict):
                return []
            val = obj.get(key)
            return val if isinstance(val, list) else []

        # Defensive top-level list extraction
        authors_list = _get_list(doc, "authors")
        units_list = _get_list(doc, "units")
        groups_list = _get_list(doc, "groups")
        visuals_list = _get_list(doc, "visuals")
        assets_list = _get_list(doc, "assets")
        profiles_list = _get_list(doc, "profiles")

        # Flag top-level collections if present but not a list
        for coll_name in ["authors", "units", "groups", "visuals", "assets", "profiles"]:
            if coll_name in doc and not isinstance(doc[coll_name], list):
                issues.append(
                    ValidationIssue(
                        path=f"/{coll_name}",
                        message=f"Коллекция '{coll_name}' должна быть массивом (list), получено: {type(doc[coll_name]).__name__}",
                        severity=IssueSeverity.ERROR,
                        code="ERR_INVALID_COLLECTION_TYPE",
                    )
                )

        authors = {a["id"]: a for a in authors_list if isinstance(a, dict) and "id" in a and isinstance(a["id"], str)}
        units = {u["id"]: u for u in units_list if isinstance(u, dict) and "id" in u and isinstance(u["id"], str)}
        assets = {a["id"]: a for a in assets_list if isinstance(a, dict) and "id" in a and isinstance(a["id"], str)}
        profiles = {p["id"]: p for p in profiles_list if isinstance(p, dict) and "id" in p and isinstance(p["id"], str)}

        # 1. Unique IDs across top-level collections & reserved builtin prefix
        seen_ids: Dict[str, str] = {}
        for coll_name in ["authors", "units", "groups", "visuals", "assets", "profiles"]:
            items = _get_list(doc, coll_name)
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                item_id = item.get("id")
                if not item_id or not isinstance(item_id, str):
                    continue
                pointer = f"/{coll_name}/{idx}/id"
                if item_id.startswith("builtin:"):
                    issues.append(
                        ValidationIssue(
                            path=pointer,
                            message=f"Пользовательский ID '{item_id}' содержит зарезервированный префикс 'builtin:'",
                            severity=IssueSeverity.ERROR,
                            code="ERR_RESERVED_BUILTIN_PREFIX",
                        )
                    )
                if item_id in seen_ids:
                    prev_coll = seen_ids[item_id]
                    if prev_coll == coll_name:
                        issues.append(
                            ValidationIssue(
                                path=pointer,
                                message=f"Дубликат ID '{item_id}' внутри коллекции '{coll_name}'",
                                severity=IssueSeverity.ERROR,
                                code="ERR_DUPLICATE_ID",
                            )
                        )
                    else:
                        issues.append(
                            ValidationIssue(
                                path=pointer,
                                message=f"Коллизия ID '{item_id}' между коллекциями '{prev_coll}' и '{coll_name}'",
                                severity=IssueSeverity.ERROR,
                                code="ERR_CROSS_COLLECTION_ID_COLLISION",
                            )
                        )
                else:
                    seen_ids[item_id] = coll_name

        # 2. Check whitespace-only text fields across required entities (Spec r2 §8 Rule 5)
        def _check_non_whitespace(obj: Any, field_name: str, ptr: str) -> None:
            if isinstance(obj, dict):
                val = obj.get(field_name)
                if isinstance(val, str) and not val.strip():
                    issues.append(
                        ValidationIssue(
                            path=ptr,
                            message=f"Поле '{field_name}' не должно состоять только из пробелов",
                            severity=IssueSeverity.ERROR,
                            code="ERR_EMPTY_WHITESPACE_ONLY",
                        )
                    )

        metadata = doc.get("metadata")
        _check_non_whitespace(metadata, "title", "/metadata/title")

        for idx, u in enumerate(units_list):
            if isinstance(u, dict):
                _check_non_whitespace(u, "title", f"/units/{idx}/title")
                _check_non_whitespace(u, "text", f"/units/{idx}/text")

        for idx, g in enumerate(groups_list):
            if isinstance(g, dict):
                _check_non_whitespace(g, "title", f"/groups/{idx}/title")

        for idx, v in enumerate(visuals_list):
            if isinstance(v, dict):
                _check_non_whitespace(v, "title", f"/visuals/{idx}/title")
                _check_non_whitespace(v, "question", f"/visuals/{idx}/question")
                _check_non_whitespace(v, "fallback", f"/visuals/{idx}/fallback")

        for idx, a in enumerate(assets_list):
            if isinstance(a, dict):
                _check_non_whitespace(a, "alt", f"/assets/{idx}/alt")
                _check_non_whitespace(a, "caption", f"/assets/{idx}/caption")

        for p_idx, p in enumerate(profiles_list):
            if isinstance(p, dict):
                _check_non_whitespace(p, "title", f"/profiles/{p_idx}/title")
                for pan_idx, pan in enumerate(_get_list(p, "panels")):
                    if isinstance(pan, dict):
                        _check_non_whitespace(pan, "title", f"/profiles/{p_idx}/panels/{pan_idx}/title")

        # 3. Metadata references
        metadata = doc.get("metadata")
        if isinstance(metadata, dict):
            if "author_refs" in metadata and not isinstance(metadata["author_refs"], list):
                issues.append(
                    ValidationIssue(
                        path="/metadata/author_refs",
                        message=f"Поле author_refs в metadata должно быть массивом, получено: {type(metadata['author_refs']).__name__}",
                        severity=IssueSeverity.ERROR,
                        code="ERR_INVALID_REFERENCE_TYPE",
                    )
                )
            for a_idx, a_ref in enumerate(_get_list(metadata, "author_refs")):
                if not isinstance(a_ref, str):
                    issues.append(
                        ValidationIssue(
                            path=f"/metadata/author_refs/{a_idx}",
                            message=f"Ссылка на автора должна быть строкой, получено: {type(a_ref).__name__}",
                            severity=IssueSeverity.ERROR,
                            code="ERR_INVALID_REFERENCE_TYPE",
                        )
                    )
                    continue
                if a_ref not in authors:
                    issues.append(
                        ValidationIssue(
                            path=f"/metadata/author_refs/{a_idx}",
                            message=f"Автор '{a_ref}' из metadata не найден в коллекции authors",
                            severity=IssueSeverity.ERROR,
                            code="ERR_DANGLING_AUTHOR_REF",
                        )
                    )
            def_prof = metadata.get("default_profile_id")
            if def_prof and isinstance(def_prof, str):
                if def_prof not in {"builtin:2", "builtin:3", "builtin:4"} and def_prof not in profiles:
                    issues.append(
                        ValidationIssue(
                            path="/metadata/default_profile_id",
                            message=f"default_profile_id '{def_prof}' не найден в profiles и не является builtin:2/3/4",
                            severity=IssueSeverity.WARNING,
                            code="WARN_UNKNOWN_DEFAULT_PROFILE",
                        )
                    )

        # 4. Unit references (author_refs, asset_ids, source_refs)
        for idx, u in enumerate(units_list):
            if not isinstance(u, dict):
                continue
            u_id = u.get("id", f"idx_{idx}")

            # author_refs
            if "author_refs" in u and not isinstance(u["author_refs"], list):
                issues.append(
                    ValidationIssue(
                        path=f"/units/{idx}/author_refs",
                        message=f"Поле author_refs для unit '{u_id}' должно быть массивом",
                        severity=IssueSeverity.ERROR,
                        code="ERR_INVALID_REFERENCE_TYPE",
                    )
                )
            for a_idx, a_ref in enumerate(_get_list(u, "author_refs")):
                if not isinstance(a_ref, str):
                    continue
                if a_ref not in authors:
                    issues.append(
                        ValidationIssue(
                            path=f"/units/{idx}/author_refs/{a_idx}",
                            message=f"Автор '{a_ref}' для unit '{u_id}' не найден в authors",
                            severity=IssueSeverity.ERROR,
                            code="ERR_DANGLING_AUTHOR_REF",
                        )
                    )

            # asset_ids
            if "asset_ids" in u and not isinstance(u["asset_ids"], list):
                issues.append(
                    ValidationIssue(
                        path=f"/units/{idx}/asset_ids",
                        message=f"Поле asset_ids для unit '{u_id}' должно быть массивом",
                        severity=IssueSeverity.ERROR,
                        code="ERR_INVALID_REFERENCE_TYPE",
                    )
                )
            for as_idx, as_id in enumerate(_get_list(u, "asset_ids")):
                if not isinstance(as_id, str):
                    continue
                if as_id not in assets:
                    issues.append(
                        ValidationIssue(
                            path=f"/units/{idx}/asset_ids/{as_idx}",
                            message=f"Вложение '{as_id}' для unit '{u_id}' не найдено в assets",
                            severity=IssueSeverity.ERROR,
                            code="ERR_DANGLING_ASSET_REF",
                        )
                    )

            # source_refs: must exist and have kind == "source"
            if "source_refs" in u and not isinstance(u["source_refs"], list):
                issues.append(
                    ValidationIssue(
                        path=f"/units/{idx}/source_refs",
                        message=f"Поле source_refs для unit '{u_id}' должно быть массивом",
                        severity=IssueSeverity.ERROR,
                        code="ERR_INVALID_REFERENCE_TYPE",
                    )
                )
            for s_idx, s_id in enumerate(_get_list(u, "source_refs")):
                if not isinstance(s_id, str):
                    continue
                if s_id not in units:
                    issues.append(
                        ValidationIssue(
                            path=f"/units/{idx}/source_refs/{s_idx}",
                            message=f"Исходная единица '{s_id}' для unit '{u_id}' не найдена в units",
                            severity=IssueSeverity.ERROR,
                            code="ERR_DANGLING_UNIT_REF",
                        )
                    )
                elif units[s_id].get("kind") != "source":
                    issues.append(
                        ValidationIssue(
                            path=f"/units/{idx}/source_refs/{s_idx}",
                            message=f"Ссылка source_refs '{s_id}' указывает на unit с kind='{units[s_id].get('kind')}', требуется kind='source'",
                            severity=IssueSeverity.ERROR,
                            code="ERR_SOURCE_REF_NON_SOURCE_KIND",
                        )
                    )

        # 5. Visual elements validation
        for v_idx, v in enumerate(visuals_list):
            if not isinstance(v, dict):
                continue
            v_id = v.get("id", f"v_{v_idx}")

            # author_refs in visual
            if "author_refs" in v and not isinstance(v["author_refs"], list):
                issues.append(
                    ValidationIssue(
                        path=f"/visuals/{v_idx}/author_refs",
                        message=f"Поле author_refs для visual '{v_id}' должно быть массивом",
                        severity=IssueSeverity.ERROR,
                        code="ERR_INVALID_REFERENCE_TYPE",
                    )
                )
            for a_idx, a_ref in enumerate(_get_list(v, "author_refs")):
                if not isinstance(a_ref, str):
                    continue
                if a_ref not in authors:
                    issues.append(
                        ValidationIssue(
                            path=f"/visuals/{v_idx}/author_refs/{a_idx}",
                            message=f"Автор '{a_ref}' для visual '{v_id}' не найден в authors",
                            severity=IssueSeverity.ERROR,
                            code="ERR_DANGLING_AUTHOR_REF",
                        )
                    )

            # owner_unit_id: must exist and have kind == "model"
            owner_id = v.get("owner_unit_id")
            if not isinstance(owner_id, str) or owner_id not in units:
                issues.append(
                    ValidationIssue(
                        path=f"/visuals/{v_idx}/owner_unit_id",
                        message=f"Владелец модели '{owner_id}' для visual '{v_id}' не найден в units",
                        severity=IssueSeverity.ERROR,
                        code="ERR_DANGLING_UNIT_REF",
                    )
                )
            elif units[owner_id].get("kind") != "model":
                issues.append(
                    ValidationIssue(
                        path=f"/visuals/{v_idx}/owner_unit_id",
                        message=f"owner_unit_id '{owner_id}' указывает на unit с kind='{units[owner_id].get('kind')}', требуется kind='model'",
                        severity=IssueSeverity.ERROR,
                        code="ERR_OWNER_UNIT_NON_MODEL_KIND",
                    )
                )

            # Visual scope ID uniqueness: node IDs and edge IDs must be mutually unique within visual
            seen_visual_elem_ids: Set[str] = set()
            v_nodes: Dict[str, Dict[str, Any]] = {}
            if "nodes" in v and not isinstance(v["nodes"], list):
                issues.append(
                    ValidationIssue(
                        path=f"/visuals/{v_idx}/nodes",
                        message=f"Поле nodes для visual '{v_id}' должно быть массивом",
                        severity=IssueSeverity.ERROR,
                        code="ERR_INVALID_REFERENCE_TYPE",
                    )
                )
            for n_idx, n in enumerate(_get_list(v, "nodes")):
                if not isinstance(n, dict):
                    continue
                n_id = n.get("id")
                if n_id and isinstance(n_id, str):
                    if n_id.startswith("builtin:"):
                        issues.append(
                            ValidationIssue(
                                path=f"/visuals/{v_idx}/nodes/{n_idx}/id",
                                message=f"ID узла '{n_id}' содержит зарезервированный префикс 'builtin:'",
                                severity=IssueSeverity.ERROR,
                                code="ERR_RESERVED_BUILTIN_PREFIX",
                            )
                        )
                    if n_id in seen_visual_elem_ids:
                        issues.append(
                            ValidationIssue(
                                path=f"/visuals/{v_idx}/nodes/{n_idx}/id",
                                message=f"Дубликат ID узла '{n_id}' внутри visual '{v_id}'",
                                severity=IssueSeverity.ERROR,
                                code="ERR_DUPLICATE_NODE_ID",
                            )
                        )
                    seen_visual_elem_ids.add(n_id)
                    v_nodes[n_id] = n

                if "unit_refs" in n and not isinstance(n["unit_refs"], list):
                    issues.append(
                        ValidationIssue(
                            path=f"/visuals/{v_idx}/nodes/{n_idx}/unit_refs",
                            message=f"Поле unit_refs для узла '{n_id}' должно быть массивом",
                            severity=IssueSeverity.ERROR,
                            code="ERR_INVALID_REFERENCE_TYPE",
                        )
                    )
                for u_idx, u_ref in enumerate(_get_list(n, "unit_refs")):
                    if not isinstance(u_ref, str):
                        continue
                    if u_ref not in units:
                        issues.append(
                            ValidationIssue(
                                path=f"/visuals/{v_idx}/nodes/{n_idx}/unit_refs/{u_idx}",
                                message=f"Ссылка на unit '{u_ref}' из узла '{n_id}' не найдена в units",
                                severity=IssueSeverity.ERROR,
                                code="ERR_DANGLING_UNIT_REF",
                            )
                        )

            # Edges verification
            depends_on_adj: Dict[str, List[str]] = {nid: [] for nid in v_nodes}
            if "edges" in v and not isinstance(v["edges"], list):
                issues.append(
                    ValidationIssue(
                        path=f"/visuals/{v_idx}/edges",
                        message=f"Поле edges для visual '{v_id}' должно быть массивом",
                        severity=IssueSeverity.ERROR,
                        code="ERR_INVALID_REFERENCE_TYPE",
                    )
                )
            for e_idx, e in enumerate(_get_list(v, "edges")):
                if not isinstance(e, dict):
                    continue
                e_id = e.get("id")
                e_from = e.get("from")
                e_to = e.get("to")
                e_rel = e.get("relation")

                if e_id and isinstance(e_id, str):
                    if e_id.startswith("builtin:"):
                        issues.append(
                            ValidationIssue(
                                path=f"/visuals/{v_idx}/edges/{e_idx}/id",
                                message=f"ID ребра '{e_id}' содержит зарезервированный префикс 'builtin:'",
                                severity=IssueSeverity.ERROR,
                                code="ERR_RESERVED_BUILTIN_PREFIX",
                            )
                        )
                    if e_id in seen_visual_elem_ids:
                        issues.append(
                            ValidationIssue(
                                path=f"/visuals/{v_idx}/edges/{e_idx}/id",
                                message=f"Коллизия ID ребра '{e_id}' с узлом или ребром внутри visual '{v_id}'",
                                severity=IssueSeverity.ERROR,
                                code="ERR_VISUAL_ID_COLLISION",
                            )
                        )
                    seen_visual_elem_ids.add(e_id)

                if e_from not in v_nodes:
                    issues.append(
                        ValidationIssue(
                            path=f"/visuals/{v_idx}/edges/{e_idx}/from",
                            message=f"Исходный узел 'from' ('{e_from}') не найден в nodes visual '{v_id}'",
                            severity=IssueSeverity.ERROR,
                            code="ERR_DANGLING_NODE_REF",
                        )
                    )
                if e_to not in v_nodes:
                    issues.append(
                        ValidationIssue(
                            path=f"/visuals/{v_idx}/edges/{e_idx}/to",
                            message=f"Целевой узел 'to' ('{e_to}') не найден в nodes visual '{v_id}'",
                            severity=IssueSeverity.ERROR,
                            code="ERR_DANGLING_NODE_REF",
                        )
                    )

                # Self-loop prohibition (§8 line 420: "Нет self-loop from=to")
                if e_from and e_to and e_from == e_to:
                    issues.append(
                        ValidationIssue(
                            path=f"/visuals/{v_idx}/edges/{e_idx}",
                            message=f"Петля from=to ('{e_from}') запрещена спецификацией",
                            severity=IssueSeverity.ERROR,
                            code="ERR_SELF_LOOP",
                        )
                    )

                # Edge unit_refs
                if "unit_refs" in e and not isinstance(e["unit_refs"], list):
                    issues.append(
                        ValidationIssue(
                            path=f"/visuals/{v_idx}/edges/{e_idx}/unit_refs",
                            message=f"Поле unit_refs для ребра '{e_id}' должно быть массивом",
                            severity=IssueSeverity.ERROR,
                            code="ERR_INVALID_REFERENCE_TYPE",
                        )
                    )
                for u_idx, u_ref in enumerate(_get_list(e, "unit_refs")):
                    if not isinstance(u_ref, str):
                        continue
                    if u_ref not in units:
                        issues.append(
                            ValidationIssue(
                                path=f"/visuals/{v_idx}/edges/{e_idx}/unit_refs/{u_idx}",
                                message=f"Ссылка на unit '{u_ref}' из ребра '{e_id}' не найдена в units",
                                severity=IssueSeverity.ERROR,
                                code="ERR_DANGLING_UNIT_REF",
                            )
                        )

                if e_rel == "depends_on" and e_from in v_nodes and e_to in v_nodes:
                    depends_on_adj[e_from].append(e_to)

            # Cycle detection in depends_on (Tolerated per §8 line 420)
            cycles = self._detect_cycles(depends_on_adj)
            for cyc in cycles:
                issues.append(
                    ValidationIssue(
                        path=f"/visuals/{v_idx}",
                        message=f"Обнаружен цикл в связях depends_on ({' -> '.join(cyc)}); разрешён спецификацией",
                        severity=IssueSeverity.INFO,
                        code="INFO_CYCLE_DETECTED",
                        context={"cycle": cyc},
                    )
                )

        # 6. Asset references
        for a_idx, a in enumerate(assets_list):
            if not isinstance(a, dict):
                continue
            if "author_refs" in a and not isinstance(a["author_refs"], list):
                issues.append(
                    ValidationIssue(
                        path=f"/assets/{a_idx}/author_refs",
                        message=f"Поле author_refs для asset '{a.get('id')}' должно быть массивом",
                        severity=IssueSeverity.ERROR,
                        code="ERR_INVALID_REFERENCE_TYPE",
                    )
                )
            for ref_idx, a_ref in enumerate(_get_list(a, "author_refs")):
                if not isinstance(a_ref, str):
                    continue
                if a_ref not in authors:
                    issues.append(
                        ValidationIssue(
                            path=f"/assets/{a_idx}/author_refs/{ref_idx}",
                            message=f"Автор '{a_ref}' для asset '{a.get('id')}' не найден в authors",
                            severity=IssueSeverity.ERROR,
                            code="ERR_DANGLING_AUTHOR_REF",
                        )
                    )

        # 7. Groups and Orphan Units
        grouped_unit_ids: Set[str] = set()
        multi_grouped_ids: Set[str] = set()
        for g_idx, g in enumerate(groups_list):
            if not isinstance(g, dict):
                continue
            g_id = g.get("id", f"g_{g_idx}")
            if "unit_refs" in g and not isinstance(g["unit_refs"], list):
                issues.append(
                    ValidationIssue(
                        path=f"/groups/{g_idx}/unit_refs",
                        message=f"Поле unit_refs в группе '{g_id}' должно быть массивом",
                        severity=IssueSeverity.ERROR,
                        code="ERR_INVALID_REFERENCE_TYPE",
                    )
                )
            for u_idx, u_ref in enumerate(_get_list(g, "unit_refs")):
                if not isinstance(u_ref, str):
                    continue
                if u_ref not in units:
                    issues.append(
                        ValidationIssue(
                            path=f"/groups/{g_idx}/unit_refs/{u_idx}",
                            message=f"Ссылка на unit '{u_ref}' в группе '{g_id}' не найдена",
                            severity=IssueSeverity.ERROR,
                            code="ERR_DANGLING_UNIT_REF",
                        )
                    )
                else:
                    if u_ref in grouped_unit_ids:
                        multi_grouped_ids.add(u_ref)
                        issues.append(
                            ValidationIssue(
                                path=f"/groups/{g_idx}/unit_refs/{u_idx}",
                                message=f"Единица '{u_ref}' включена в несколько групп одновременно",
                                severity=IssueSeverity.WARNING,
                                code="WARN_MULTI_GROUPED_UNIT",
                            )
                        )
                    grouped_unit_ids.add(u_ref)

        orphans = [uid for uid in units if uid not in grouped_unit_ids]
        reconciled_groups = list(groups_list)
        synthetic_orphan_group = None

        if orphans:
            issues.append(
                ValidationIssue(
                    path="/units",
                    message=f"Обнаружено {len(orphans)} единиц вне групп; сгруппированы в секцию «Вне групп»",
                    severity=IssueSeverity.WARNING,
                    code="WARN_ORPHAN_UNITS",
                    context={"orphan_ids": orphans},
                )
            )
            synthetic_orphan_group = {
                "id": "builtin:orphan-group",
                "title": "Вне групп",
                "unit_refs": sorted(orphans),
                "synthetic": True,
            }
            reconciled_groups.append(synthetic_orphan_group)

        # 8. Profile panel rules (§8 Rule 1 & Rule 6) and kind partition checks (§8 line 425)
        for p_idx, p in enumerate(profiles_list):
            if not isinstance(p, dict):
                continue
            p_id = p.get("id", f"p_{p_idx}")
            if "panels" in p and not isinstance(p["panels"], list):
                issues.append(
                    ValidationIssue(
                        path=f"/profiles/{p_idx}/panels",
                        message=f"Поле panels в профиле '{p_id}' должно быть массивом",
                        severity=IssueSeverity.ERROR,
                        code="ERR_INVALID_REFERENCE_TYPE",
                    )
                )
            p_kinds: List[str] = []
            seen_panel_ids: Set[str] = set()
            for pan_idx, panel in enumerate(_get_list(p, "panels")):
                if not isinstance(panel, dict):
                    continue
                pan_id = panel.get("id")
                if pan_id and isinstance(pan_id, str):
                    pan_ptr = f"/profiles/{p_idx}/panels/{pan_idx}/id"
                    if pan_id.startswith("builtin:"):
                        issues.append(
                            ValidationIssue(
                                path=pan_ptr,
                                message=f"ID панели '{pan_id}' содержит зарезервированный префикс 'builtin:'",
                                severity=IssueSeverity.ERROR,
                                code="ERR_RESERVED_BUILTIN_PREFIX",
                            )
                        )
                    if pan_id in seen_panel_ids:
                        issues.append(
                            ValidationIssue(
                                path=pan_ptr,
                                message=f"Дубликат ID панели '{pan_id}' внутри профиля '{p_id}'",
                                severity=IssueSeverity.ERROR,
                                code="ERR_DUPLICATE_PANEL_ID",
                            )
                        )
                    seen_panel_ids.add(pan_id)

                for k in _get_list(panel, "kinds"):
                    if isinstance(k, str):
                        p_kinds.append(k)

            kind_set = set(p_kinds)
            if kind_set != self.REQUIRED_KINDS or len(p_kinds) != 4:
                issues.append(
                    ValidationIssue(
                        path=f"/profiles/{p_idx}/panels",
                        message=f"Профиль '{p_id}' должен разделять ровно 4 роли {sorted(self.REQUIRED_KINDS)} без пропусков и дублей (найдено: {p_kinds})",
                        severity=IssueSeverity.ERROR,
                        code="ERR_PROFILE_KINDS_INCOMPLETE",
                    )
                )

        stats = {
            "units_count": len(units),
            "groups_count": len(groups_list),
            "visuals_count": len(visuals_list),
            "assets_count": len(assets),
            "authors_count": len(authors),
            "orphan_units_count": len(orphans),
        }

        return issues, orphans, reconciled_groups, synthetic_orphan_group, stats

    def _detect_cycles(self, adj: Dict[str, List[str]]) -> List[List[str]]:
        """
        Detect directed cycles in an adjacency dictionary using iterative 3-coloring DFS.
        Maintains strict O(V + E) complexity and eliminates recursion depth limits entirely.
        """
        if not isinstance(adj, dict):
            return []

        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {u: WHITE for u in adj}
        cycles: List[List[str]] = []

        for start_node in list(adj.keys()):
            if color.get(start_node) != WHITE:
                continue

            raw_start_nbrs = adj.get(start_node)
            start_nbrs = raw_start_nbrs if isinstance(raw_start_nbrs, list) else []

            path: List[str] = [start_node]
            path_indices: Dict[str, int] = {start_node: 0}
            color[start_node] = GRAY
            stack: List[List[Any]] = [[start_node, start_nbrs, 0]]

            while stack:
                frame = stack[-1]
                u: str = frame[0]
                neighbors: List[str] = frame[1]
                edge_idx: int = frame[2]

                if edge_idx < len(neighbors):
                    v = neighbors[edge_idx]
                    frame[2] += 1

                    if not isinstance(v, str) or v not in color:
                        continue

                    v_color = color[v]
                    if v_color == GRAY:
                        cycle_start_idx = path_indices[v]
                        cycles.append(path[cycle_start_idx:] + [v])
                    elif v_color == WHITE:
                        color[v] = GRAY
                        path_indices[v] = len(path)
                        path.append(v)

                        raw_v_nbrs = adj.get(v)
                        v_nbrs = raw_v_nbrs if isinstance(raw_v_nbrs, list) else []
                        stack.append([v, v_nbrs, 0])
                else:
                    stack.pop()
                    path.pop()
                    path_indices.pop(u, None)
                    color[u] = BLACK

        return cycles


# Module-level convenience functions
_default_engine = None


def get_engine() -> IntegrityEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = IntegrityEngine()
    return _default_engine


def compute_raw_sha256(raw_bytes: bytes) -> str:
    return get_engine().compute_raw_sha256(raw_bytes)


def validate_document(doc: Union[bytes, str, Dict[str, Any]], check_media: bool = False) -> DocumentIntegrityReport:
    return get_engine().validate_document(doc, check_media=check_media)


def validate_media_contract(
    doc_or_assets: Any, total_budget_state: Optional[Dict[str, Any]] = None
) -> Tuple[List[ValidationIssue], Dict[str, Any]]:
    return get_engine().validate_media_contract(doc_or_assets, total_budget_state=total_budget_state)


def validate_manifest(manifest: Any) -> ManifestValidationReport:
    return get_engine().validate_manifest(manifest)


def check_manifest_match(
    manifest: Dict[str, Any],
    doc_metadata: Dict[str, Any],
    raw_sha256: str,
) -> Tuple[str, str]:
    return get_engine().check_manifest_match(manifest, doc_metadata, raw_sha256)
