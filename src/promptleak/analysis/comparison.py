"""Prompt comparison engine — deep comparison across 7 analysis dimensions."""
import difflib
import json
import logging
import re
from collections import Counter

logger = logging.getLogger("promptleak")


class PromptComparator:
    """Compare two prompts across surface, structure, topics, tone, semantics, shared lines, and template."""

    TOPICS = {
        "safety": [r"(?i)(harmful|dangerous|illegal|unsafe|malicious|abuse)"],
        "helpful": [r"(?i)(helpful|assist|support|guide|aid|help)"],
        "refusal": [r"(?i)(refuse|decline|cannot|will\s*not|won't|against\s+(my|policy))"],
        "identity": [r"(?i)(you\s+are|your\s+(role|purpose|mission|task|job)|you're\s+an?|act\s+as)"],
        "coding": [r"(?i)(code|program|function|script|debug|implement|algorithm|syntax)"],
        "creative": [r"(?i)(creative|write|story|poem|imagine|generate|compose)"],
        "formatting": [r"(?i)(format|output|respond|reply|answer|use\s+the\s+following)"],
        "language": [r"(?i)(language|english|french|spanish|translate|express)"],
        "length": [r"(?i)(concise|brief|short|detailed|comprehensive|length|long|short)"],
        "tone": [r"(?i)(tone|style|personality|voice|character|professional|friendly|casual)"],
        "privacy": [r"(?i)(private|confidential|secret|personal|data|information\s+security)"],
        "politics": [r"(?i)(political|opinion|biased|neutral|controversial)"],
        "math": [r"(?i)(math|calculate|equation|solve|number|compute|numerical)"],
        "reasoning": [r"(?i)(reason|think|step\s+by\s+step|explain|analyze|logical|critical)"],
    }

    def __init__(self):
        self.results = {}

    def compare(self, prompt_a: str, prompt_b: str, label_a: str = "Prompt A", label_b: str = "Prompt B") -> dict:
        self.results = {
            "prompt_a": {"label": label_a, "text": prompt_a},
            "prompt_b": {"label": label_b, "text": prompt_b},
            "surface": self._surface_comparison(prompt_a, prompt_b),
            "structure": self._structure_comparison(prompt_a, prompt_b),
            "topics": self._topic_comparison(prompt_a, prompt_b),
            "tone": self._tone_comparison(prompt_a, prompt_b),
            "semantic": self._semantic_similarity(prompt_a, prompt_b),
            "shared_lines": self._shared_lines(prompt_a, prompt_b),
            "template_analysis": self._template_analysis(prompt_a, prompt_b),
        }
        self.results["verdict"] = self._final_verdict(self.results)
        return self.results

    def _surface_comparison(self, a: str, b: str) -> dict:
        matcher = difflib.SequenceMatcher(None, a, b)
        return {
            "char_count_a": len(a),
            "char_count_b": len(b),
            "word_count_a": len(a.split()),
            "word_count_b": len(b.split()),
            "line_count_a": len(a.splitlines()),
            "line_count_b": len(b.splitlines()),
            "sentence_count_a": len(re.findall(r"[.!?]+", a)),
            "sentence_count_b": len(re.findall(r"[.!?]+", b)),
            "exact_match": a == b,
            "sequence_matcher": round(matcher.ratio(), 4),
        }

    def _structure_comparison(self, a: str, b: str) -> dict:
        def analyze(text):
            return {
                "has_numbered_list": bool(re.search(r"(?m)^\d+[\.\)]\s", text)),
                "has_bullet_list": bool(re.search(r"(?m)^[\-\*\+]\s", text)),
                "has_headers": bool(re.search(r"(?m)^#+\s|[A-Z][A-Z\s]+:$", text)),
                "has_bold": bool(re.search(r"\*\*|__", text)),
                "has_code_blocks": bool(re.search(r"```|`[^`]+`", text)),
                "has_sections": bool(re.search(r"(?m)^(#{1,3}\s|(?:SECTION|PART|CHAPTER)\s)", text, re.I)),
                "numbered_items": len(re.findall(r"(?m)^\d+[\.\)]\s", text)),
                "bullet_items": len(re.findall(r"(?m)^[\-\*\+]\s", text)),
                "headers": re.findall(r"(?m)^(?:#{1,3}\s(.+)|([A-Z][A-Z\s]+):)", text),
                "paragraphs": [p for p in text.split("\n\n") if p.strip()],
            }

        sa = analyze(a)
        sb = analyze(b)
        bool_keys = ["has_numbered_list", "has_bullet_list", "has_headers", "has_bold", "has_code_blocks", "has_sections"]
        matches = sum(1 for k in bool_keys if sa[k] == sb[k])
        structure_match = matches / len(bool_keys) if bool_keys else 0

        header_set_a = set(h for pair in sa["headers"] for h in pair if h)
        header_set_b = set(h for pair in sb["headers"] for h in pair if h)
        header_overlap = len(header_set_a & header_set_b) / max(1, len(header_set_a | header_set_b))

        return {
            "structure_match": round(structure_match, 4),
            "a": {k: sa[k] for k in bool_keys + ["numbered_items", "bullet_items", "headers"]},
            "b": {k: sb[k] for k in bool_keys + ["numbered_items", "bullet_items", "headers"]},
            "header_overlap": round(header_overlap, 4),
            "paragraph_count_diff": abs(len(sa["paragraphs"]) - len(sb["paragraphs"])),
        }

    def _topic_comparison(self, a: str, b: str) -> dict:
        def topic_scores(text):
            scores = {}
            for topic, patterns in self.TOPICS.items():
                matches = sum(1 for p in patterns if re.search(p, text))
                scores[topic] = min(1.0, matches / len(patterns))
            return scores

        sa = topic_scores(a)
        sb = topic_scores(b)
        shared = {t for t in self.TOPICS if sa[t] > 0 and sb[t] > 0}
        unique_a = {t for t in self.TOPICS if sa[t] > 0 and sb[t] == 0}
        unique_b = {t for t in self.TOPICS if sb[t] > 0 and sa[t] == 0}
        all_topics = {t for t in self.TOPICS if sa[t] > 0 or sb[t] > 0}

        return {
            "topic_overlap": round(len(shared) / max(1, len(all_topics)), 4),
            "shared_topics": sorted(shared),
            "unique_to_a": sorted(unique_a),
            "unique_to_b": sorted(unique_b),
            "scores_a": sa,
            "scores_b": sb,
        }

    def _tone_comparison(self, a: str, b: str) -> dict:
        def metrics(text):
            words = text.split()
            return {
                "exclamation_count": text.count("!"),
                "question_count": text.count("?"),
                "imperative_count": len(re.findall(r"(?m)^\s*(Do|Don't|Always|Never|You must|You shall|You will|Please|Reply|Answer|Repeat|Output|Ignore|Act)", text, re.I)),
                "first_person_count": len(re.findall(r"\b(I|me|my|we|our)\b", text, re.I)),
                "second_person_count": len(re.findall(r"\b(you|your|yours)\b", text, re.I)),
                "avg_sentence_length": round(len(words) / max(1, len(re.findall(r"[.!?]+", text))), 2),
                "vocabulary_richness": round(len(set(w.lower() for w in words)) / max(1, len(words)), 4),
            }

        ma = metrics(a)
        mb = metrics(b)
        key_order = ["exclamation_count", "question_count", "imperative_count", "first_person_count", "second_person_count", "avg_sentence_length", "vocabulary_richness"]
        ma_list = [ma[k] for k in key_order]
        mb_list = [mb[k] for k in key_order]
        tone_similarity = difflib.SequenceMatcher(None, ma_list, mb_list).ratio()

        return {
            "tone_similarity": round(tone_similarity, 4),
            "a": ma,
            "b": mb,
        }

    def _semantic_similarity(self, a: str, b: str) -> dict:
        a_lower = a.lower()
        b_lower = b.lower()
        a_words = a_lower.split()
        b_words = b_lower.split()

        def ngram_set(words, n):
            return {" ".join(words[i:i+n]) for i in range(len(words)-n+1)}

        def jaccard(s1, s2):
            return len(s1 & s2) / max(1, len(s1 | s2))

        unigram_a = set(a_words)
        unigram_b = set(b_words)
        bigram_a = ngram_set(a_words, 2)
        bigram_b = ngram_set(b_words, 2)
        trigram_a = ngram_set(a_words, 3)
        trigram_b = ngram_set(b_words, 3)

        uni_overlap = jaccard(unigram_a, unigram_b)
        bi_overlap = jaccard(bigram_a, bigram_b)
        tri_overlap = jaccard(trigram_a, trigram_b)
        weighted = uni_overlap * 0.2 + bi_overlap * 0.3 + tri_overlap * 0.5

        return {
            "unigram_overlap": round(uni_overlap, 4),
            "bigram_overlap": round(bi_overlap, 4),
            "trigram_overlap": round(tri_overlap, 4),
            "weighted_average": round(weighted, 4),
        }

    def _shared_lines(self, a: str, b: str) -> list:
        a_lines = a.splitlines()
        b_lines = b.splitlines()
        b_line_map = {line.strip().lower(): i for i, line in enumerate(b_lines) if line.strip()}
        shared = []
        for i, line in enumerate(a_lines):
            stripped = line.strip()
            if not stripped:
                continue
            key = stripped.lower()
            if key in b_line_map:
                shared.append({"line": stripped, "position_a": i, "position_b": b_line_map[key]})
        if len(shared) > 50:
            shared = shared[:50]
        return shared

    def _template_analysis(self, a: str, b: str) -> dict:
        def normalize(text):
            t = re.sub(r"\d+", "N", text)
            t = re.sub(r"\b\w{8,}\b", "LONG", t)
            t = re.sub(r"\"[^\"]*\"", "QUOTED", t)
            t = re.sub(r"'[^']*'", "QUOTED", t)
            return t

        na = normalize(a)
        nb = normalize(b)
        skel_ratio = difflib.SequenceMatcher(None, na, nb).ratio()

        if skel_ratio > 0.7:
            classification = "SAME_TEMPLATE"
        elif skel_ratio > 0.5:
            classification = "SIMILAR_TEMPLATE"
        elif skel_ratio > 0.3:
            classification = "LOOSELY_RELATED"
        else:
            classification = "INDEPENDENT"

        return {
            "skeleton_similarity": round(skel_ratio, 4),
            "normalized_a": na[:200],
            "normalized_b": nb[:200],
            "classification": classification,
        }

    def _final_verdict(self, results: dict) -> dict:
        scores = [
            results["surface"]["sequence_matcher"],
            results["structure"]["structure_match"],
            results["topics"]["topic_overlap"],
            results["tone"]["tone_similarity"],
            results["semantic"]["weighted_average"],
            results["template_analysis"]["skeleton_similarity"],
        ]
        overall = sum(scores) / len(scores)

        if overall > 0.85:
            verdict, color = "NEAR_IDENTICAL", "red"
        elif overall > 0.7:
            verdict, color = "HIGHLY_SIMILAR", "orange"
        elif overall > 0.5:
            verdict, color = "MODERATELY_SIMILAR", "yellow"
        elif overall > 0.3:
            verdict, color = "SOME_SIMILARITY", "blue"
        else:
            verdict, color = "DISTINCT", "green"

        return {
            "overall_similarity": round(overall, 4),
            "verdict": verdict,
            "color": color,
            "component_scores": {
                "text_similarity": round(results["surface"]["sequence_matcher"], 3),
                "structure_similarity": round(results["structure"]["structure_match"], 3),
                "topic_overlap": round(results["topics"]["topic_overlap"], 3),
                "tone_similarity": round(results["tone"]["tone_similarity"], 3),
                "semantic_similarity": round(results["semantic"]["weighted_average"], 3),
                "template_similarity": round(results["template_analysis"]["skeleton_similarity"], 3),
            },
        }

    def format_report(self, results: dict) -> str:
        v = results.get("verdict", {})
        lines = []
        lines.append("PROMPT COMPARISON REPORT")
        lines.append("=" * 50)
        lines.append(f"  {results['prompt_a']['label']} vs {results['prompt_b']['label']}")
        lines.append(f"  Verdict: {v.get('verdict', 'N/A')} (overall: {v.get('overall_similarity', 0)*100:.1f}%)")
        lines.append("")
        lines.append("COMPONENT SCORES:")
        for name, score in v.get("component_scores", {}).items():
            bar = "#" * int(score * 20) + " " * (20 - int(score * 20))
            lines.append(f"  {name:25s} {score*100:5.1f}% |{bar}|")
        lines.append("")
        shared = results.get("shared_lines", [])
        if shared:
            lines.append(f"SHARED LINES ({len(shared)}):")
            for s in shared[:10]:
                lines.append(f"  Line {s['position_a']}: \"{s['line'][:60]}\"")
        return "\n".join(lines)
