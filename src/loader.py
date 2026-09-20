"""
ParallelDoc 3.0 (r2 / V3-ONLY) — Document Loader & Integrity Engine.
Strict compliance with Spec r2 §7, §8, §9, §11 (F06-F09, AC-02, AC-25, AC-26, AC-28).

Exclusive core features:
- Exact SHA-256 computed over raw loaded binary bytes (BOM preserved, zero CRLF/LF normalization).
- BOM stripped ONLY during text decoding and JSON parsing.
- V3-Only Format Guard (§9): Rejection of legacy v2.1 or non-v3 documents with exact diagnostic:
  «Неподдерживаемый формат; требуется ParallelDoc 3.0»
- Safe raw text preview with line/column pointers and visual caret snippet.
- Detached manifest verification matching manifest.schema.json (scope: "raw-bytes", SHA-256).
- Absolute prohibition of auto-migration or silent fallback to demo (F09).
- Independent trust axes: Structure, Integrity, and Epistemic/Workflow statuses.
"""

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from .validator import (
        IntegrityEngine,
        DocumentIntegrityReport,
        ManifestValidationReport,
        ValidationIssue,
        IssueSeverity,
        get_engine,
    )
except ImportError:
    from validator import (
        IntegrityEngine,
        DocumentIntegrityReport,
        ManifestValidationReport,
        ValidationIssue,
        IssueSeverity,
        get_engine,
    )


REJECTION_DIAGNOSTIC_MESSAGE = "«Неподдерживаемый формат; требуется ParallelDoc 3.0»"
UTF8_BOM = b"\xef\xbb\xbf"
MAX_PREVIEW_CHARS = 5000
MAX_PREVIEW_LINES = 500


class ErrorType(str, Enum):
    NONE = "NONE"
    EMPTY_INPUT = "EMPTY_INPUT"
    UTF8_DECODE_ERROR = "UTF8_DECODE_ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    REJECTED_UNSUPPORTED = "REJECTED_UNSUPPORTED"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    REFERENTIAL_INTEGRITY_ERROR = "REFERENTIAL_INTEGRITY_ERROR"


class StructureState(str, Enum):
    VALID = "valid"
    PARTIAL = "partial"
    INVALID = "invalid"


class IntegrityState(str, Enum):
    COMPUTED = "computed"
    MATCHED = "matched"
    MISMATCH = "mismatch"
    UNAVAILABLE = "unavailable"


class ManifestMatchStatus(str, Enum):
    NONE = "none"
    MATCHED = "matched"
    MISMATCH = "mismatch"
    DIFFERENT_DOCUMENT = "different_document"
    INVALID_MANIFEST = "invalid_manifest"


@dataclass
class RawPreviewResult:
    text: str
    total_length: int
    is_truncated: bool
    line_count: int
    error_line: Optional[int] = None
    error_column: Optional[int] = None
    snippet: Optional[str] = None


@dataclass
class ManifestVerificationResult:
    is_valid_manifest: bool
    status: ManifestMatchStatus
    message: str
    expected_sha256: Optional[str]
    actual_sha256: str
    manifest_doc_id: Optional[str] = None
    manifest_revision: Optional[str] = None
    doc_id: Optional[str] = None
    doc_revision: Optional[str] = None
    scope: Optional[str] = None
    algorithm: Optional[str] = None
    issues: List[ValidationIssue] = field(default_factory=list)


@dataclass
class DocumentLoadResult:
    success: bool
    error_type: ErrorType
    diagnostic_message: Optional[str]
    raw_sha256: str
    has_bom: bool
    byte_length: int
    structure_state: StructureState
    integrity_state: IntegrityState
    doc: Optional[Dict[str, Any]]
    issues: List[ValidationIssue]
    raw_preview: Optional[RawPreviewResult]
    manifest_result: Optional[ManifestVerificationResult]
    stats: Dict[str, int]
    raw_text: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    snippet: Optional[str] = None
    integrity_report: Optional[DocumentIntegrityReport] = None


def compute_raw_sha256(raw_bytes: bytes) -> str:
    """Computes exact SHA-256 over raw binary bytes without CRLF/LF normalization.
    Preserves UTF-8 BOM if present.
    """
    if not isinstance(raw_bytes, (bytes, bytearray)):
        raise TypeError(f"raw_bytes must be bytes or bytearray, got {type(raw_bytes).__name__}")
    return hashlib.sha256(raw_bytes).hexdigest().lower()


def compute_file_raw_sha256(filepath: Union[Path, str]) -> str:
    """Computes exact SHA-256 over raw binary file bytes on disk (BOM preserved, zero normalization)."""
    p = Path(filepath)
    return compute_raw_sha256(p.read_bytes())


def locate_error_pointer(raw_text: str, pattern: Optional[str] = None) -> Tuple[int, int]:
    """Calculate 1-indexed line and column for an error pattern in raw text."""
    if not raw_text:
        return 1, 1
    pos = 0
    if pattern:
        m = re.search(pattern, raw_text)
        if m:
            pos = m.start()
    if pos == 0 and not pattern:
        m = re.search(r"\{", raw_text)
        if m:
            pos = m.start()
    lines = raw_text[:pos].split("\n")
    line = len(lines)
    col = len(lines[-1]) + 1
    return line, col


def generate_error_snippet(
    raw_text: str, line: int, col: int, reason: str, context: int = 2
) -> str:
    """Generate formatted multi-line excerpt with visual caret pointer ^."""
    lines = raw_text.splitlines()
    if not lines:
        return ""
    start_idx = max(0, line - 1 - context)
    end_idx = min(len(lines), line + context)
    out = []
    for idx in range(start_idx, end_idx):
        ln = idx + 1
        prefix = f"{ln:4d} | "
        out.append(prefix + lines[idx])
        if ln == line:
            indent = " " * (len(prefix) + max(0, col - 1))
            out.append(f"{indent}^ [ОШИБКА: {reason}]")
    return "\n".join(out)


def generate_raw_preview(
    raw_bytes: bytes,
    error_line: Optional[int] = None,
    error_column: Optional[int] = None,
    max_chars: int = MAX_PREVIEW_CHARS,
    reason: Optional[str] = None,
) -> RawPreviewResult:
    """Safely decodes raw bytes and produces truncated preview with optional pointer snippet."""
    bytes_to_decode = raw_bytes[3:] if raw_bytes.startswith(UTF8_BOM) else raw_bytes
    text = bytes_to_decode.decode("utf-8", errors="replace")
    total_length = len(text)
    lines = text.splitlines()
    line_count = len(lines)
    is_truncated = False

    if total_length > max_chars or line_count > MAX_PREVIEW_LINES:
        is_truncated = True
        truncated_lines = lines[:MAX_PREVIEW_LINES]
        preview_text = "\n".join(truncated_lines)
        if len(preview_text) > max_chars:
            preview_text = preview_text[:max_chars]
        shown_lines = len(preview_text.splitlines())
        shown_chars = len(preview_text)
        preview_text += (
            f"\n\n... [Показаны первые {shown_lines} строк / {shown_chars} символов "
            f"из {line_count} строк / {total_length} символов. Полный файл сохранен]"
        )
    else:
        preview_text = text

    snippet = None
    if error_line is not None and error_column is not None and 1 <= error_line <= line_count:
        snippet = generate_error_snippet(
            text, error_line, error_column, reason or "Ошибка валидации"
        )

    return RawPreviewResult(
        text=preview_text,
        total_length=total_length,
        is_truncated=is_truncated,
        line_count=line_count,
        error_line=error_line,
        error_column=error_column,
        snippet=snippet,
    )


def verify_manifest(
    raw_bytes: bytes,
    manifest_input: Union[bytes, str, Dict[str, Any]],
    doc_metadata: Optional[Dict[str, Any]] = None,
    engine: Optional[IntegrityEngine] = None,
) -> ManifestVerificationResult:
    """Validate detached manifest against manifest.schema.json and evaluate hash/target binding."""
    engine = engine or get_engine()
    actual_sha256 = compute_raw_sha256(raw_bytes)

    # 1. Parse manifest data
    if isinstance(manifest_input, bytes):
        try:
            m_bytes = manifest_input[3:] if manifest_input.startswith(UTF8_BOM) else manifest_input
            m_text = m_bytes.decode("utf-8")
            manifest_obj = json.loads(m_text)
        except Exception as e:
            return ManifestVerificationResult(
                is_valid_manifest=False,
                status=ManifestMatchStatus.INVALID_MANIFEST,
                message=f"Синтаксическая ошибка JSON в манифесте: {e}",
                expected_sha256=None,
                actual_sha256=actual_sha256,
                issues=[
                    ValidationIssue(
                        path="",
                        message=f"Ошибка парсинга манифеста: {e}",
                        severity=IssueSeverity.ERROR,
                        code="ERR_MANIFEST_PARSE",
                    )
                ],
            )
    elif isinstance(manifest_input, str):
        try:
            manifest_obj = json.loads(manifest_input)
        except Exception as e:
            return ManifestVerificationResult(
                is_valid_manifest=False,
                status=ManifestMatchStatus.INVALID_MANIFEST,
                message=f"Синтаксическая ошибка JSON в манифесте: {e}",
                expected_sha256=None,
                actual_sha256=actual_sha256,
                issues=[
                    ValidationIssue(
                        path="",
                        message=f"Ошибка парсинга манифеста: {e}",
                        severity=IssueSeverity.ERROR,
                        code="ERR_MANIFEST_PARSE",
                    )
                ],
            )
    elif isinstance(manifest_input, dict):
        manifest_obj = manifest_input
    else:
        return ManifestVerificationResult(
            is_valid_manifest=False,
            status=ManifestMatchStatus.INVALID_MANIFEST,
            message=f"Недопустимый тип входных данных манифеста: {type(manifest_input).__name__}",
            expected_sha256=None,
            actual_sha256=actual_sha256,
            issues=[
                ValidationIssue(
                    path="",
                    message="Недопустимый тип входных данных манифеста",
                    severity=IssueSeverity.ERROR,
                    code="ERR_MANIFEST_INVALID_INPUT",
                )
            ],
        )

    # 2. Validate against Draft 2020-12 manifest.schema.json
    schema_report = engine.validate_manifest(manifest_obj)
    if not schema_report.is_valid:
        return ManifestVerificationResult(
            is_valid_manifest=False,
            status=ManifestMatchStatus.INVALID_MANIFEST,
            message="Манифест не соответствует manifest.schema.json",
            expected_sha256=manifest_obj.get("expected_sha256") if isinstance(manifest_obj, dict) else None,
            actual_sha256=actual_sha256,
            issues=schema_report.issues,
        )

    scope = manifest_obj.get("scope")
    algo = manifest_obj.get("algorithm")

    # Extra defense for const scope and algorithm
    if scope != "raw-bytes":
        return ManifestVerificationResult(
            is_valid_manifest=False,
            status=ManifestMatchStatus.INVALID_MANIFEST,
            message=f"Неподдерживаемый scope: {scope!r}; требуется 'raw-bytes'",
            expected_sha256=manifest_obj.get("expected_sha256"),
            actual_sha256=actual_sha256,
            scope=scope,
            algorithm=algo,
            issues=[
                ValidationIssue(
                    path="/scope",
                    message=f"scope must be 'raw-bytes', got {scope!r}",
                    severity=IssueSeverity.ERROR,
                    code="ERR_MANIFEST_SCOPE",
                )
            ],
        )

    if algo != "SHA-256":
        return ManifestVerificationResult(
            is_valid_manifest=False,
            status=ManifestMatchStatus.INVALID_MANIFEST,
            message=f"Неподдерживаемый алгоритм: {algo!r}; требуется 'SHA-256'",
            expected_sha256=manifest_obj.get("expected_sha256"),
            actual_sha256=actual_sha256,
            scope=scope,
            algorithm=algo,
            issues=[
                ValidationIssue(
                    path="/algorithm",
                    message=f"algorithm must be 'SHA-256', got {algo!r}",
                    severity=IssueSeverity.ERROR,
                    code="ERR_MANIFEST_ALGO",
                )
            ],
        )

    # 3. Document ID and Revision binding check (§8)
    doc_id = doc_metadata.get("document_id") if doc_metadata else None
    doc_rev = doc_metadata.get("revision") if doc_metadata else None
    man_doc_id = manifest_obj.get("document_id")
    man_rev = manifest_obj.get("revision")

    if man_doc_id is not None and doc_id is not None and man_doc_id != doc_id:
        return ManifestVerificationResult(
            is_valid_manifest=True,
            status=ManifestMatchStatus.DIFFERENT_DOCUMENT,
            message=f"Манифест другого документа: заявлен '{man_doc_id}', активен '{doc_id}'",
            expected_sha256=manifest_obj.get("expected_sha256"),
            actual_sha256=actual_sha256,
            manifest_doc_id=man_doc_id,
            manifest_revision=man_rev,
            doc_id=doc_id,
            doc_revision=doc_rev,
            scope=scope,
            algorithm=algo,
        )

    if man_rev is not None and doc_rev is not None and man_rev != doc_rev:
        return ManifestVerificationResult(
            is_valid_manifest=True,
            status=ManifestMatchStatus.DIFFERENT_DOCUMENT,
            message=f"Манифест другой ревизии: заявлена '{man_rev}', активна '{doc_rev}'",
            expected_sha256=manifest_obj.get("expected_sha256"),
            actual_sha256=actual_sha256,
            manifest_doc_id=man_doc_id,
            manifest_revision=man_rev,
            doc_id=doc_id,
            doc_revision=doc_rev,
            scope=scope,
            algorithm=algo,
        )

    # 4. Hash comparison
    expected_sha256 = (manifest_obj.get("expected_sha256") or "").lower()
    if expected_sha256 == actual_sha256.lower():
        return ManifestVerificationResult(
            is_valid_manifest=True,
            status=ManifestMatchStatus.MATCHED,
            message="Хэш совпадает с эталоном",
            expected_sha256=expected_sha256,
            actual_sha256=actual_sha256,
            manifest_doc_id=man_doc_id,
            manifest_revision=man_rev,
            doc_id=doc_id,
            doc_revision=doc_rev,
            scope=scope,
            algorithm=algo,
        )
    else:
        return ManifestVerificationResult(
            is_valid_manifest=True,
            status=ManifestMatchStatus.MISMATCH,
            message="SHA mismatch документа: Другая версия или изменение",
            expected_sha256=expected_sha256,
            actual_sha256=actual_sha256,
            manifest_doc_id=man_doc_id,
            manifest_revision=man_rev,
            doc_id=doc_id,
            doc_revision=doc_rev,
            scope=scope,
            algorithm=algo,
        )


def load_document(
    raw_bytes: bytes,
    manifest_input: Optional[Union[bytes, str, Dict[str, Any]]] = None,
    expected_sha256: Optional[str] = None,
    engine: Optional[IntegrityEngine] = None,
) -> DocumentLoadResult:
    """Master ingestion entry point for ParallelDoc 3.0.
    Executes raw byte digest, UTF-8 decode, JSON parse, v3 format guard, schema/referential validation,
    and detached manifest / integrity state resolution.
    """
    engine = engine or get_engine()

    if not isinstance(raw_bytes, (bytes, bytearray)):
        return DocumentLoadResult(
            success=False,
            error_type=ErrorType.REJECTED_UNSUPPORTED,
            diagnostic_message=REJECTION_DIAGNOSTIC_MESSAGE,
            raw_sha256="",
            has_bom=False,
            byte_length=0,
            structure_state=StructureState.INVALID,
            integrity_state=IntegrityState.UNAVAILABLE,
            doc=None,
            issues=[
                ValidationIssue(
                    path="",
                    message="Ожидались бинарные байты",
                    severity=IssueSeverity.ERROR,
                    code="ERR_INVALID_TYPE",
                )
            ],
            raw_preview=None,
            manifest_result=None,
            stats={},
        )

    byte_length = len(raw_bytes)
    has_bom = raw_bytes.startswith(UTF8_BOM)
    raw_sha256 = compute_raw_sha256(raw_bytes)

    # Empty file check
    if byte_length == 0:
        preview = RawPreviewResult(
            text="",
            total_length=0,
            is_truncated=False,
            line_count=0,
            error_line=1,
            error_column=1,
            snippet=None,
        )
        return DocumentLoadResult(
            success=False,
            error_type=ErrorType.EMPTY_INPUT,
            diagnostic_message=REJECTION_DIAGNOSTIC_MESSAGE,
            raw_sha256=raw_sha256,
            has_bom=False,
            byte_length=0,
            structure_state=StructureState.INVALID,
            integrity_state=IntegrityState.COMPUTED,
            doc=None,
            issues=[
                ValidationIssue(
                    path="",
                    message="Файл пуст",
                    severity=IssueSeverity.ERROR,
                    code="ERR_EMPTY_FILE",
                    line=1,
                    column=1,
                )
            ],
            raw_preview=preview,
            manifest_result=None,
            stats={},
            raw_text="",
            line=1,
            column=1,
        )

    # Stage 0: Decode UTF-8 (BOM stripped ONLY for text decoding)
    bytes_to_decode = raw_bytes[3:] if has_bom else raw_bytes
    try:
        raw_text = bytes_to_decode.decode("utf-8")
    except UnicodeDecodeError as exc:
        preview = generate_raw_preview(
            raw_bytes, 1, 1, reason=f"Ошибка UTF-8 на байте {exc.start}"
        )
        return DocumentLoadResult(
            success=False,
            error_type=ErrorType.UTF8_DECODE_ERROR,
            diagnostic_message=f"Ошибка декодирования UTF-8: {exc.reason} на байте {exc.start}",
            raw_sha256=raw_sha256,
            has_bom=has_bom,
            byte_length=byte_length,
            structure_state=StructureState.INVALID,
            integrity_state=IntegrityState.COMPUTED,
            doc=None,
            issues=[
                ValidationIssue(
                    path="",
                    message=f"Ошибка декодирования UTF-8: {exc}",
                    severity=IssueSeverity.ERROR,
                    code="ERR_UTF8_DECODE",
                    line=1,
                    column=1,
                    snippet=preview.snippet,
                )
            ],
            raw_preview=preview,
            manifest_result=None,
            stats={},
            raw_text=None,
            line=1,
            column=1,
            snippet=preview.snippet,
        )

    # Stage 1: JSON Parsing
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        preview = generate_raw_preview(
            raw_bytes, exc.lineno, exc.colno, reason=f"Синтаксическая ошибка: {exc.msg}"
        )
        return DocumentLoadResult(
            success=False,
            error_type=ErrorType.PARSE_ERROR,
            diagnostic_message=f"Синтаксическая ошибка JSON: {exc.msg} (строка {exc.lineno}, колонка {exc.colno})",
            raw_sha256=raw_sha256,
            has_bom=has_bom,
            byte_length=byte_length,
            structure_state=StructureState.INVALID,
            integrity_state=IntegrityState.COMPUTED,
            doc=None,
            issues=[
                ValidationIssue(
                    path="",
                    message=f"Синтаксическая ошибка JSON: {exc.msg}",
                    severity=IssueSeverity.ERROR,
                    code="ERR_JSON_PARSE",
                    line=exc.lineno,
                    column=exc.colno,
                    snippet=preview.snippet,
                )
            ],
            raw_preview=preview,
            manifest_result=None,
            stats={},
            raw_text=raw_text,
            line=exc.lineno,
            column=exc.colno,
            snippet=preview.snippet,
        )

    # Stage 2: Non-object root
    if not isinstance(data, dict):
        preview = generate_raw_preview(
            raw_bytes, 1, 1, reason="Корень документа должен быть JSON-объектом"
        )
        return DocumentLoadResult(
            success=False,
            error_type=ErrorType.REJECTED_UNSUPPORTED,
            diagnostic_message=REJECTION_DIAGNOSTIC_MESSAGE,
            raw_sha256=raw_sha256,
            has_bom=has_bom,
            byte_length=byte_length,
            structure_state=StructureState.INVALID,
            integrity_state=IntegrityState.COMPUTED,
            doc=None,
            issues=[
                ValidationIssue(
                    path="",
                    message=REJECTION_DIAGNOSTIC_MESSAGE,
                    severity=IssueSeverity.ERROR,
                    code="ERR_REJECTED_UNSUPPORTED",
                    line=1,
                    column=1,
                    snippet=preview.snippet,
                )
            ],
            raw_preview=preview,
            manifest_result=None,
            stats={},
            raw_text=raw_text,
            line=1,
            column=1,
            snippet=preview.snippet,
        )

    # Stage 3: Strict V3-Only Format Guard (§9)
    is_legacy = "columns" in data or "items" in data
    format_val = data.get("format")
    version_val = data.get("version")

    if is_legacy or format_val != "paralleldoc" or version_val != "3.0":
        if is_legacy:
            pattern = r'"(?:columns|items)"\s*:'
            reason = "Обнаружены устаревшие поля v2.1 (columns/items)"
        elif format_val != "paralleldoc":
            pattern = r'"format"\s*:' if "format" in data else r"\{"
            reason = f"Неверный или отсутствующий формат: {format_val!r}"
        else:
            pattern = r'"version"\s*:' if "version" in data else r"\{"
            reason = f"Неверная или отсутствующая версия: {version_val!r}"

        line, col = locate_error_pointer(raw_text, pattern)
        preview = generate_raw_preview(raw_bytes, line, col, reason=reason)
        return DocumentLoadResult(
            success=False,
            error_type=ErrorType.REJECTED_UNSUPPORTED,
            diagnostic_message=REJECTION_DIAGNOSTIC_MESSAGE,
            raw_sha256=raw_sha256,
            has_bom=has_bom,
            byte_length=byte_length,
            structure_state=StructureState.INVALID,
            integrity_state=IntegrityState.COMPUTED,
            doc=None,  # F09: Absolute prohibition of auto-migration or partial doc synthesis
            issues=[
                ValidationIssue(
                    path="",
                    message=REJECTION_DIAGNOSTIC_MESSAGE,
                    severity=IssueSeverity.ERROR,
                    code="ERR_REJECTED_UNSUPPORTED",
                    line=line,
                    column=col,
                    snippet=preview.snippet,
                )
            ],
            raw_preview=preview,
            manifest_result=None,
            stats={},
            raw_text=raw_text,
            line=line,
            column=col,
            snippet=preview.snippet,
        )

    # Stage 4: Draft 2020-12 Schema & Referential Integrity Validation
    integrity_report = engine.validate_document(data)

    # Resolve manifest and expected SHA independently
    doc_meta = data.get("metadata", {})
    manifest_res = None
    if manifest_input is not None:
        manifest_res = verify_manifest(raw_bytes, manifest_input, doc_meta, engine=engine)
        if manifest_res.status == ManifestMatchStatus.MATCHED:
            integrity_state = IntegrityState.MATCHED
        elif manifest_res.status == ManifestMatchStatus.MISMATCH:
            integrity_state = IntegrityState.MISMATCH
        else:
            integrity_state = IntegrityState.COMPUTED
    elif expected_sha256 is not None:
        if expected_sha256.lower() == raw_sha256.lower():
            integrity_state = IntegrityState.MATCHED
        else:
            integrity_state = IntegrityState.MISMATCH
    else:
        integrity_state = IntegrityState.COMPUTED

    structure_state = StructureState(integrity_report.structure_state)
    has_schema_errors = any(
        issue.code == "ERR_SCHEMA_V3_VIOLATION" for issue in integrity_report.issues
    )

    if has_schema_errors:
        error_type = ErrorType.SCHEMA_VIOLATION
        success = False
        diagnostic_message = "Ошибка валидации схемы Draft 2020-12 (schema.v3.json)"
    elif not integrity_report.is_valid:
        error_type = ErrorType.REFERENTIAL_INTEGRITY_ERROR
        success = False
        diagnostic_message = "Ошибка семантической или ссылочной целостности"
    else:
        error_type = ErrorType.NONE
        success = True
        diagnostic_message = None

    preview = generate_raw_preview(raw_bytes)

    return DocumentLoadResult(
        success=success,
        error_type=error_type,
        diagnostic_message=diagnostic_message,
        raw_sha256=raw_sha256,
        has_bom=has_bom,
        byte_length=byte_length,
        structure_state=structure_state,
        integrity_state=integrity_state,
        doc=data,
        issues=integrity_report.issues,
        raw_preview=preview,
        manifest_result=manifest_res,
        stats=integrity_report.stats,
        raw_text=raw_text,
        integrity_report=integrity_report,
    )


def load_document_from_file(
    filepath: Union[Path, str],
    manifest_path: Optional[Union[Path, str]] = None,
    expected_sha256: Optional[str] = None,
    engine: Optional[IntegrityEngine] = None,
) -> DocumentLoadResult:
    """Load document directly from filesystem path."""
    p = Path(filepath)
    raw_bytes = p.read_bytes()
    manifest_bytes = Path(manifest_path).read_bytes() if manifest_path else None
    return load_document(
        raw_bytes,
        manifest_input=manifest_bytes,
        expected_sha256=expected_sha256,
        engine=engine,
    )
