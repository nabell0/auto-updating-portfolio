#!/usr/bin/env python3
"""리추얼 기록을 집계한다.

같은 CSV를 넣으면 수치와 문단 후보가 항상 같다.
외부 모델을 호출하지 않으므로 실행마다 문장이 바뀌지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import sys
from datetime import date
from pathlib import Path

ABILITIES = ("자기조절력", "대인관계력", "자기동기력")
HEAVY_MARKS = ("컨디션", "조퇴", "아프", "아팠", "몸 상태", "몸이")
CLASSIFY_RULES = (
    ("자기조절력", ("조퇴", "컨디션", "아프", "멈추", "닫", "연타", "거절")),
    ("대인관계력", ("동료", "같이", "함께", "친절", "팀")),
    ("자기동기력", ("재제출", "아침", "일찍", "루틴", "떠올리", "통과")),
)
STATS_START = "<!-- PORTFOLIO_STATS_START -->"
STATS_END = "<!-- PORTFOLIO_STATS_END -->"


def external_api_key():
    """키가 환경에 있을 때만 읽는다. 집계와 문단에는 넣지 않는다."""
    return os.environ.get("API_KEY")


def classify(evidence: str, ability: str) -> str:
    chosen = (ability or "").strip()
    if chosen in ABILITIES:
        return chosen
    if chosen:
        raise ValueError(f"알 수 없는 능력: {chosen}")
    text = evidence or ""
    for name, keys in CLASSIFY_RULES:
        if any(key in text for key in keys):
            return name
    return "미분류"


def parse_date(value: str) -> date:
    raw = (value or "").strip()
    parts = raw.split("-")
    if len(parts) != 3:
        raise ValueError(f"날짜 형식은 YYYY-MM-DD입니다: {raw}")
    year, month, day = (int(part) for part in parts)
    return date(year, month, day)


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        missing = [name for name in ("date", "evidence") if name not in fields]
        if missing:
            raise ValueError("CSV에 필요한 열이 없습니다: " + ", ".join(missing))
        rows = []
        for index, raw in enumerate(reader, start=2):
            if raw is None:
                continue
            if not any((value or "").strip() for value in raw.values()):
                continue
            try:
                when = parse_date(raw.get("date", ""))
                evidence = (raw.get("evidence") or "").strip()
                if not evidence:
                    raise ValueError("evidence가 비어 있습니다")
                kind = (raw.get("kind") or "ritual").strip() or "ritual"
                if kind not in ("ritual", "submission"):
                    raise ValueError(f"kind는 ritual 또는 submission입니다: {kind}")
                ability = classify(evidence, raw.get("ability") or "")
                source = (raw.get("source") or "").strip() or "기록"
            except ValueError as error:
                raise ValueError(f"{path.name} {index}행: {error}") from error
            rows.append(
                {
                    "date": when.isoformat(),
                    "kind": kind,
                    "ability": ability,
                    "evidence": evidence,
                    "source": source,
                    "heavy": kind == "ritual" and any(mark in evidence for mark in HEAVY_MARKS),
                }
            )
    rows.sort(key=lambda row: (row["date"], row["kind"], row["ability"], row["evidence"], row["source"]))
    return rows


def submission_span(rows: list[dict]) -> dict | None:
    rejects = [row["date"] for row in rows if row["kind"] == "submission" and "반려" in row["evidence"]]
    passes = [row["date"] for row in rows if row["kind"] == "submission" and "통과" in row["evidence"]]
    if not rejects or not passes:
        return None
    start = min(rejects)
    end = max(passes)
    if end < start:
        return None
    span = (date.fromisoformat(end) - date.fromisoformat(start)).days
    return {"from": start, "to": end, "days": span}


def aggregate(rows: list[dict], source_name: str) -> dict:
    ritual_dates = sorted({row["date"] for row in rows if row["kind"] == "ritual"})
    heavy_dates = sorted({row["date"] for row in rows if row["heavy"]})
    by_ability = {name: 0 for name in (*ABILITIES, "미분류")}
    for row in rows:
        by_ability[row["ability"]] = by_ability.get(row["ability"], 0) + 1
    by_ability = {name: count for name, count in sorted(by_ability.items()) if count}
    dates = [row["date"] for row in rows]
    return {
        "by_ability": by_ability,
        "heavy_days": len(heavy_dates),
        "heavy_dates": heavy_dates,
        "input": source_name,
        "records": len(rows),
        "ritual_days": len(ritual_dates),
        "ritual_dates": ritual_dates,
        "span": submission_span(rows),
        "through": dates[-1] if dates else None,
        "from": dates[0] if dates else None,
    }


def paragraph_for(row: dict) -> str:
    year, month, day = (int(part) for part in row["date"].split("-"))
    evidence = row["evidence"].strip()
    if not evidence.endswith((".", "。")):
        evidence += "."
    return (
        f"{year}년 {month}월 {day}일, {evidence} "
        f"이 기록은 {row['ability']}의 근거다. 출처는 {row['source']}이다."
    )


def render_candidates(rows: list[dict], stats: dict) -> str:
    lines = ["# 능력별 문단 후보", ""]
    span = stats["span"]
    if span is None:
        lines.append("제출 구간: 반려와 통과가 함께 있는 기록이 0건이다.")
    else:
        lines.append(
            f"제출 구간: {span['from']} 반려부터 {span['to']} 통과까지 {span['days']}일."
        )
    lines.append(f"리추얼을 남긴 날: {stats['ritual_days']}일.")
    lines.append(f"몸이 무거워도 자리를 지킨 날: {stats['heavy_days']}일.")
    lines.append("")
    for ability in (*ABILITIES, "미분류"):
        chosen = [row for row in rows if row["ability"] == ability]
        if not chosen:
            continue
        lines.append(f"## {ability}")
        lines.append("")
        lines.append(f"건수: {len(chosen)}")
        lines.append("")
        for row in chosen:
            lines.append(f"- 날짜: {row['date']}")
            lines.append(f"  근거: {row['evidence']}")
            lines.append(f"  출처: {row['source']}")
            lines.append(f"  문단: {paragraph_for(row)}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_stats_html(stats: dict) -> str:
    span = stats["span"]
    if span is None:
        span_label = "0일"
        span_note = "출처: 제출 현황. 반려와 통과가 함께 있는 기록이 없다."
        bridge = "제출 현황에서 반려와 통과를 함께 집계하지 못했다."
    else:
        span_label = f"{span['days']}일"
        span_note = f"출처: 제출 현황. {span['from']} 반려부터 {span['to']} 통과까지."
        bridge = (
            f"{span['days']}일은 {span['from']} 반려부터 {span['to']} 통과까지다. "
            f"같은 파일의 리추얼은 {stats['ritual_days']}일이고, "
            f"몸이 무거워도 자리를 지킨 날은 {stats['heavy_days']}일이다."
        )
    heavy_note = "출처: 리추얼 기록. " + (
        ", ".join(stats["heavy_dates"]) if stats["heavy_dates"] else "해당 날짜 0일."
    )
    ritual_note = "출처: 리추얼 기록. " + (
        f"{stats['ritual_dates'][0]}부터 {stats['ritual_dates'][-1]}까지."
        if stats["ritual_dates"]
        else "해당 날짜 0일."
    )
    cards = (
        ("span", span_label, "반려에서 통과까지", span_note),
        ("ritual", f"{stats['ritual_days']}일", "리추얼을 남긴 날", ritual_note),
        ("heavy", f"{stats['heavy_days']}일", "몸이 무거워도 자리를 지킨 날", heavy_note),
    )
    articles = []
    for _key, strong, title, note in cards:
        articles.append(
            "\n".join(
                [
                    "          <article class=\"metric\">",
                    f"            <strong>{html.escape(strong)}</strong>",
                    f"            <span>{html.escape(title)}</span>",
                    f"            <small>{html.escape(note)}</small>",
                    "          </article>",
                ]
            )
        )
    body = "\n".join(articles)
    return (
        "          <div class=\"metrics\">\n"
        f"{body}\n"
        "          </div>\n"
        f"          <p class=\"bridge\">{html.escape(bridge)}</p>\n"
    )


def update_html(html_path: Path, stats: dict) -> None:
    text = html_path.read_text(encoding="utf-8")
    if STATS_START not in text or STATS_END not in text:
        raise ValueError(f"{html_path}에 {STATS_START} 표시가 없습니다.")
    start = text.index(STATS_START) + len(STATS_START)
    end = text.index(STATS_END)
    if end < start:
        raise ValueError(f"{html_path}의 수치 표시 순서가 잘못되었습니다.")
    updated = text[:start] + "\n" + render_stats_html(stats) + "          " + text[end:]
    html_path.write_text(updated, encoding="utf-8", newline="\n")


def canonical_bytes(rows: list[dict]) -> bytes:
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return payload.encode("utf-8")


def write_outputs(out_dir: Path, rows: list[dict], stats: dict) -> tuple[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stats_path = out_dir / "portfolio_update.json"
    text_path = out_dir / "ability_candidates.md"
    stats_bytes = (
        json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    text_bytes = render_candidates(rows, stats).encode("utf-8")
    stats_path.write_bytes(stats_bytes)
    text_path.write_bytes(text_bytes)
    return (
        hashlib.sha256(stats_bytes).hexdigest(),
        hashlib.sha256(text_bytes).hexdigest(),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="리추얼 CSV로 포트폴리오 수치와 능력별 문단 후보를 만듭니다.")
    parser.add_argument("csv_path", type=Path, help="새 리추얼 기록 CSV. 예: new_records.csv")
    parser.add_argument("--out", type=Path, default=Path("."), help="출력 폴더. 기본값은 현재 폴더.")
    parser.add_argument("--html", type=Path, default=None, help="수치 표시가 있는 index.html. 지정한 경우에만 고친다.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # 환경변수를 읽기만 하고 출력에는 넣지 않는다. 키가 있든 없든 집계는 같다.
    external_api_key()
    if not args.csv_path.is_file():
        print(f"입력 파일이 없습니다: {args.csv_path}", file=sys.stderr)
        return 1
    try:
        rows = load_rows(args.csv_path)
        stats = aggregate(rows, args.csv_path.name)
        stats["rows_sha256"] = hashlib.sha256(canonical_bytes(rows)).hexdigest()
        stats_hash, text_hash = write_outputs(args.out, rows, stats)
        if args.html is not None:
            update_html(args.html, stats)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"portfolio_update.json sha256={stats_hash}")
    print(f"ability_candidates.md sha256={text_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
