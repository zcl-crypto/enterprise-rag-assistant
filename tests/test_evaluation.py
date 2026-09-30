from scripts.evaluate_dense import load_cases, percentile
from scripts.evaluate_hybrid import score_separation


def test_evaluation_labels_and_percentiles() -> None:
    cases = load_cases()
    assert len(cases) == 110
    assert sum(case.category == "single_document" for case in cases) == 75
    assert sum(case.category == "cross_document" for case in cases) == 5
    assert sum(case.category == "no_answer" for case in cases) == 25
    assert sum(case.category == "unauthorized" for case in cases) == 5
    assert all(case.answer for case in cases if case.category != "unauthorized")
    assert len({case.question for case in cases}) == len(cases)
    assert percentile([10, 20, 30], 0.5) == 20
    assert percentile([10, 20, 30], 0.95) == 29


def test_score_separation_detects_overlapping_answerability_scores() -> None:
    rows = [
        {"category": "single_document", "hybrid_rerank": {"retrieved_scores": [0.5]}},
        {"category": "no_answer", "hybrid_rerank": {"retrieved_scores": [0.9]}},
    ]
    assert score_separation(rows, "hybrid_rerank") == {
        "positive_top1_min": 0.5,
        "no_answer_top1_max": 0.9,
        "single_threshold_separates_all": False,
    }
