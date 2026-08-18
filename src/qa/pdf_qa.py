"""Input / PDF QA — page integrity, DPI, blur, skew, crop anomalies.

Reads the ORIGINAL PDF and the rendered PNG pages produced for OMR.
Never modifies inputs; only reports. Re-rendering (SAFE_REPAIR) is
applied by the fixer stage when DPI deviates from the target.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from qa.qa_model import QACategory, QAIssue, QAStageResult, QAStatus

try:
    import numpy as np
    from PIL import Image
    from pypdf import PdfReader

    _DEPS_OK = True
except ImportError:  # pragma: no cover
    _DEPS_OK = False


@dataclass
class PDFQAConfig:
    target_dpi: float = 400.0
    dpi_tolerance: float = 2.0  # +- DPI
    blur_threshold: float = 50.0  # Laplacian variance, lower = blurrier
    skew_warn_deg: float = 0.3
    skew_fail_deg: float = 1.5
    edge_margin_px: int = 4  # content this close to page edge = crop anomaly


@dataclass
class PageMetrics:
    page: int
    width_px: int = 0
    height_px: int = 0
    dpi: float = 0.0
    blur_score: float = 0.0
    skew_deg: float = 0.0
    content_bbox: tuple[int, int, int, int] = (0, 0, 0, 0)

    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "dpi": round(self.dpi, 1),
            "blur_score": round(self.blur_score, 1),
            "skew_deg": round(self.skew_deg, 3),
            "content_bbox": list(self.content_bbox),
        }


def _skew_degrees(gray: np.ndarray) -> float:
    """Estimate page skew from the dominant near-horizontal edge angle.

    Staff lines dominate horizontal edges; their mean angle approximates
    the page rotation. Small-image noise is filtered by magnitude threshold.
    """
    if hasattr(gray, "convert"):  # PIL Image
        gray = np.asarray(gray.convert("L"))
    else:
        gray = np.asarray(gray)
    if gray.ndim == 3:
        gray = gray[..., 0]
    gx = np.gradient(gray.astype(np.float32), axis=1)
    gy = np.gradient(gray.astype(np.float32), axis=0)
    mag = np.hypot(gx, gy)
    mask = mag > np.percentile(mag, 92)
    if mask.sum() < 100:
        return 0.0
    angles = np.degrees(np.arctan2(gy[mask], gx[mask]))
    # Keep edges that are near horizontal (staff lines): |angle| < 25 deg
    horiz = angles[np.abs(angles) < 25.0]
    if horiz.size < 50:
        return 0.0
    return float(np.mean(horiz))


def _blur_score(gray: np.ndarray) -> float:
    """Variance of Laplacian — standard sharpness metric."""
    if hasattr(gray, "convert"):  # PIL Image
        gray = np.asarray(gray.convert("L"))
    else:
        gray = np.asarray(gray)
    if gray.ndim == 3:
        gray = gray[..., 0]
    lap = np.abs(
        np.diff(gray.astype(np.float32), 2, axis=0)[:, 1:-1]
        + np.diff(gray.astype(np.float32), 2, axis=1)[1:-1, :]
    )
    return float(lap.var())


def _content_bbox(gray: np.ndarray) -> tuple[int, int, int, int]:
    if hasattr(gray, "convert"):  # PIL Image
        gray = np.asarray(gray.convert("L"))
    else:
        gray = np.asarray(gray)
    if gray.ndim == 3:
        gray = gray[..., 0]
    dark = gray < 200
    rows = np.any(dark, axis=1)
    cols = np.any(dark, axis=0)
    if not rows.any():
        return (0, 0, 0, 0)
    ys = np.where(rows)[0]
    xs = np.where(cols)[0]
    return (int(xs[0]), int(ys[0]), int(xs[-1]), int(ys[-1]))


class PDFInputQA:
    """Check page integrity, DPI, blur, skew and cropping of the input."""

    def __init__(self, config: PDFQAConfig | None = None) -> None:
        self.config = config or PDFQAConfig()
        self.metrics: list[PageMetrics] = []

    def run(
        self,
        pdf_path: str | Path,
        rendered_dir: str | Path,
        expected_pages: int | None = None,
    ) -> QAStageResult:
        stage = QAStageResult(stage=QACategory.INPUT_PDF)
        if not _DEPS_OK:
            stage.status = "FAIL"
            stage.issues.append(
                QAIssue(
                    issue_id="INPUT-PDF-DEPS",
                    category=QACategory.INPUT_PDF,
                    check="dependencies",
                    status=QAStatus.HUMAN_REVIEW,
                    severity="high",
                    description="Pillow/numpy/pypdf not installed",
                )
            )
            return stage

        if pdf_path is None:
            stage.status = "FAIL"
            stage.issues.append(
                QAIssue(
                    issue_id="INPUT-PDF-MISSING",
                    category=QACategory.INPUT_PDF,
                    check="pdf_exists",
                    status=QAStatus.HUMAN_REVIEW,
                    severity="high",
                    description="No source PDF provided for input QA",
                )
            )
            return stage

        pdf_path = Path(pdf_path)
        rendered_dir = Path(rendered_dir)

        if not pdf_path.exists():
            stage.status = "FAIL"
            stage.issues.append(
                QAIssue(
                    issue_id="INPUT-PDF-MISSING",
                    category=QACategory.INPUT_PDF,
                    check="pdf_exists",
                    status=QAStatus.HUMAN_REVIEW,
                    severity="high",
                    description=f"Source PDF not found: {pdf_path}",
                )
            )
            return stage

        reader = PdfReader(str(pdf_path))
        pdf_pages = len(reader.pages)
        stage.checks_run += 1

        # --- 1. Page completeness -------------------------------------------
        pngs = sorted(rendered_dir.glob("page-*.png")) if rendered_dir.exists() else []
        stage.checks_run += 1
        if len(pngs) != pdf_pages:
            stage.status = "FAIL"
            stage.issues.append(
                QAIssue(
                    issue_id="INPUT-PDF-PAGES",
                    category=QACategory.INPUT_PDF,
                    check="page_completeness",
                    status=QAStatus.SAFE_REPAIR,
                    severity="high",
                    description=(
                        f"Rendered {len(pngs)} pages but PDF has {pdf_pages} pages"
                    ),
                    evidence={
                        "pdf_pages": pdf_pages,
                        "rendered_pages": len(pngs),
                        "expected_pages": expected_pages,
                    },
                    fix={"action": "re-render", "tool": "pdftoppm", "args": ["-r", str(int(self.config.target_dpi)), "-png"]},
                )
            )
        if expected_pages is not None and pdf_pages != expected_pages:
            stage.issues.append(
                QAIssue(
                    issue_id="INPUT-PDF-PAGE-COUNT",
                    category=QACategory.INPUT_PDF,
                    check="page_count_vs_omr",
                    status=QAStatus.AI_REVIEW,
                    severity="medium",
                    description=f"PDF has {pdf_pages} pages but OMR expected {expected_pages}",
                    evidence={"pdf_pages": pdf_pages, "expected_pages": expected_pages},
                )
            )

        # --- 2-5. Per-page DPI / blur / skew / crop --------------------------
        blur_values: list[float] = []
        skew_values: list[float] = []
        for png in pngs:
            stage.checks_run += 1
            page_no = int(png.stem.split("-")[-1])
            img = Image.open(png)
            metric = PageMetrics(page=page_no, width_px=img.width, height_px=img.height)

            # DPI from PDF mediabox
            if page_no <= pdf_pages:
                mb = reader.pages[page_no - 1].mediabox
                pt_width = float(mb.width)
                metric.dpi = img.width / (pt_width / 72.0)
                if abs(metric.dpi - self.config.target_dpi) > self.config.dpi_tolerance:
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"INPUT-PDF-DPI-{page_no:02d}",
                            category=QACategory.INPUT_PDF,
                            check="dpi",
                            status=QAStatus.SAFE_REPAIR,
                            severity="medium",
                            part_id="",
                            measure_number="",
                            description=(
                                f"Page {page_no} rendered at {metric.dpi:.1f} DPI "
                                f"(target {self.config.target_dpi:.0f} ± {self.config.dpi_tolerance})"
                            ),
                            evidence={"dpi": round(metric.dpi, 1), "target": self.config.target_dpi},
                            fix={"action": "re-render", "tool": "pdftoppm", "args": ["-r", str(int(self.config.target_dpi)), "-png"]},
                        )
                    )

            gray = img.convert("L")
            metric.blur_score = _blur_score(gray)
            blur_values.append(metric.blur_score)
            if metric.blur_score < self.config.blur_threshold:
                stage.issues.append(
                    QAIssue(
                        issue_id=f"INPUT-PDF-BLUR-{page_no:02d}",
                        category=QACategory.INPUT_PDF,
                        check="blur",
                        status=QAStatus.AI_REVIEW,
                        severity="medium",
                        description=(
                            f"Page {page_no} may be blurred "
                            f"(Laplacian variance {metric.blur_score:.1f} < {self.config.blur_threshold})"
                        ),
                        evidence={"blur_score": round(metric.blur_score, 1)},
                        confidence="medium",
                    )
                )

            metric.skew_deg = _skew_degrees(gray)
            skew_values.append(abs(metric.skew_deg))
            if abs(metric.skew_deg) > self.config.skew_fail_deg:
                stage.issues.append(
                    QAIssue(
                        issue_id=f"INPUT-PDF-SKEW-{page_no:02d}",
                        category=QACategory.INPUT_PDF,
                        check="skew",
                        status=QAStatus.AI_REVIEW,
                        severity="medium",
                        description=(
                            f"Page {page_no} skew {metric.skew_deg:+.2f}° "
                            f"exceeds {self.config.skew_fail_deg}° — deskew before OMR"
                        ),
                        evidence={"skew_deg": round(metric.skew_deg, 3)},
                        confidence="medium",
                    )
                )
            elif abs(metric.skew_deg) > self.config.skew_warn_deg:
                stage.issues.append(
                    QAIssue(
                        issue_id=f"INPUT-PDF-SKEW-{page_no:02d}",
                        category=QACategory.INPUT_PDF,
                        check="skew",
                        status=QAStatus.PASS,
                        severity="info",
                        description=(
                            f"Page {page_no} skew {metric.skew_deg:+.2f}° within tolerance "
                            f"but above warning level {self.config.skew_warn_deg}°"
                        ),
                        evidence={"skew_deg": round(metric.skew_deg, 3)},
                    )
                )

            bbox = _content_bbox(gray)
            metric.content_bbox = bbox
            if bbox != (0, 0, 0, 0):
                touches_edge = (
                    bbox[0] <= self.config.edge_margin_px
                    or bbox[1] <= self.config.edge_margin_px
                    or img.width - bbox[2] <= self.config.edge_margin_px
                    or img.height - bbox[3] <= self.config.edge_margin_px
                )
                if touches_edge:
                    stage.issues.append(
                        QAIssue(
                            issue_id=f"INPUT-PDF-CROP-{page_no:02d}",
                            category=QACategory.INPUT_PDF,
                            check="crop_anomaly",
                            status=QAStatus.AI_REVIEW,
                            severity="medium",
                            description=(
                                f"Page {page_no} content touches the page edge — "
                                f"possible crop anomaly (bbox {bbox})"
                            ),
                            evidence={"bbox": list(bbox), "page_size": [img.width, img.height]},
                            confidence="medium",
                        )
                    )

            self.metrics.append(metric)

        if blur_values:
            stage.checks_run += 1
            stage.issues.append(
                QAIssue(
                    issue_id="INPUT-PDF-BLUR-SUMMARY",
                    category=QACategory.INPUT_PDF,
                    check="blur_summary",
                    status=QAStatus.PASS,
                    severity="info",
                    description=(
                        f"Sharpness summary: min {min(blur_values):.1f}, "
                        f"mean {sum(blur_values) / len(blur_values):.1f}, "
                        f"max {max(blur_values):.1f} (threshold {self.config.blur_threshold})"
                    ),
                    evidence={
                        "min": round(min(blur_values), 1),
                        "mean": round(sum(blur_values) / len(blur_values), 1),
                        "max": round(max(blur_values), 1),
                    },
                )
            )
        if skew_values:
            stage.checks_run += 1
            stage.issues.append(
                QAIssue(
                    issue_id="INPUT-PDF-SKEW-SUMMARY",
                    category=QACategory.INPUT_PDF,
                    check="skew_summary",
                    status=QAStatus.PASS,
                    severity="info",
                    description=f"Skew summary: max |{max(skew_values):.2f}|° across {len(skew_values)} pages",
                    evidence={"max_abs_deg": round(max(skew_values), 3)},
                )
            )

        # Stage status
        if stage.status == "FAIL":
            pass
        elif any(i.status == QAStatus.AI_REVIEW for i in stage.issues):
            stage.status = "WARN"
        else:
            stage.status = "PASS"
        return stage
