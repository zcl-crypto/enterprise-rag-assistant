import json
from pathlib import Path

from rag_app.documents import parse_file
from scripts.generate_corpus import ROOT, generate_corpus, load_manifest


def test_fictional_corpus_covers_all_formats_and_evaluation_categories(tmp_path: Path) -> None:
    records = load_manifest()
    extras = json.loads((ROOT / "data" / "corpus" / "eval_extras.json").read_text(encoding="utf-8"))
    assert len(records) == 25
    assert {record["format"] for record in records} == {"pdf", "docx", "md", "txt", "html"}
    assert sum(len(record["qa"]) for record in records) == 75
    assert sum(len(cases) for cases in extras.values()) == 35

    paths = generate_corpus(tmp_path)
    assert len(paths) == len(records)
    for record, path in zip(records, paths, strict=True):
        parsed = parse_file(path)
        text = "".join(block.text for block in parsed.blocks).replace("\n", "")
        assert record["sections"][0][1][:6] in text
        assert parsed.source_format == record["format"]
