from __future__ import annotations

import html

def build_report_html(summary: dict, dpi: int) -> str:
    rows: list[str] = []
    detail_sections: list[str] = []
    for result in summary["page_results"]:
        page = result["page"]
        diff_link = f'<a href="{html.escape(result["diff_image_name"])}">visual diff</a>' if result.get("diff_image_name") else "—"
        overall = (
            result["exists_left"] and result["exists_right"] and result["character_exact"] and result["visually_identical"]
        )
        rows.append(
            "<tr>"
            f"<td>{page}</td><td>{'Same' if overall else 'Changed'}</td>"
            f"<td>{'Yes' if result['text_exact'] else 'No'}</td>"
            f"<td>{'Yes' if result['word_sequence_exact'] else 'No'}</td>"
            f"<td>{'Yes' if result['character_exact'] else 'No'}</td>"
            f"<td>{result['word_similarity']:.2%}</td>"
            f"<td>{result['character_similarity']:.2%}</td>"
            f"<td>{result['pixel_difference']:.3%}</td><td>{diff_link}</td>"
            "</tr>"
        )
        word_preview = "".join(
            f"<li><b>{html.escape(change['type'])}</b> — left: <code>{html.escape(change['left'])}</code> → right: <code>{html.escape(change['right'])}</code></li>"
            for change in result.get("word_changes_preview", [])[:8]
        ) or "<li>No word-sequence changes.</li>"
        char_preview = "".join(
            f"<li><b>{html.escape(change['type'])}</b> at L{change['left_index']}/R{change['right_index']} — left: <code>{html.escape(change['left'])}</code> → right: <code>{html.escape(change['right'])}</code></li>"
            for change in result.get("character_changes_preview", [])[:8]
        ) or "<li>No character changes.</li>"
        detail_sections.append(
            f"<details><summary>Page {page} exact-content details</summary>"
            f"<p>Characters: {result['left_characters']} vs {result['right_characters']} | inserted {result['chars_inserted']}, deleted {result['chars_deleted']}, replaced {result['chars_replaced']}</p>"
            f"<p>Words: {result['left_words']} vs {result['right_words']} | inserted {result['words_inserted']}, deleted {result['words_deleted']}, replaced {result['words_replaced']}</p>"
            f"<h4>Word changes</h4><ul>{word_preview}</ul><h4>Character changes</h4><ul>{char_preview}</ul></details>"
        )
    return f"""<!doctype html><html><head><meta charset='utf-8'>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:36px;color:#1f2937;line-height:1.45}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border:1px solid #d1d5db;padding:8px;text-align:left}}th{{background:#f3f4f6;position:sticky;top:0}}code{{word-break:break-all;background:#f8fafc;padding:1px 3px}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0}}.card{{border:1px solid #e5e7eb;border-radius:10px;padding:12px}}details{{margin:12px 0;padding:10px;border:1px solid #e5e7eb;border-radius:8px}}summary{{cursor:pointer;font-weight:600}}
</style></head><body>
<h1>PDF Comparison Report</h1>
<p><strong>Byte identical:</strong> {'Yes' if summary['byte_identical'] else 'No'}</p>
<p><strong>Left SHA-256:</strong> <code>{summary['sha256_left']}</code><br><strong>Right SHA-256:</strong> <code>{summary['sha256_right']}</code></p>
<div class='cards'><div class='card'><b>Pages</b><br>{summary['left_pages']} vs {summary['right_pages']}</div><div class='card'><b>Changed pages</b><br>{summary['different_pages']}</div><div class='card'><b>Exact character pages</b><br>{summary['exact_character_pages']}/{summary['total_compared_pages']}</div><div class='card'><b>Visual-identical pages</b><br>{summary['visually_identical_pages']}/{summary['total_compared_pages']}</div></div>
<table><thead><tr><th>Page</th><th>Status</th><th>Text exact</th><th>Words exact</th><th>Characters exact</th><th>Word similarity</th><th>Char similarity</th><th>Pixel diff</th><th>Visual diff</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Exact content details</h2>{''.join(detail_sections)}
<p>{html.escape(summary['comparison_note'])}</p><p>Visual comparison rendered locally at {dpi} DPI.</p>
</body></html>"""
