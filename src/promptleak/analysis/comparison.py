"""Prompt comparison engine — deep semantic, structural, and similarity analysis."""
import difflib
import json
import logging
import re
from collections import Counter

logger = logging.getLogger("promptleak")


class PromptComparator:
    """Compare two prompts across surface, structure, topics, tone, and semantics."""

    def __init__(self):
        self.results = {}

    def compare(self, prompt_a: str, prompt_b: str, label_a: str = "Prompt A", label_b: str = "Prompt B") -> dict:
        """Run full comparison and return results."""
        self.results = {
            "prompt_a": {"label": label_a, "text": prompt_a, "length": len(prompt_a)},
            "prompt_b": {"label": label_b, "text": prompt_b, "length": len(prompt_b)},
            "surface": self._analyze_surface(prompt_a, prompt_b),
            "structure": self._analyze_structure(prompt_a, prompt_b),
            "topics": self._analyze_topics(prompt_a, prompt_b),
            "tone": self._analyze_tone(prompt_a, prompt_b),
            "semantic": self._analyze_semantic(prompt_a, prompt_b),
            "template_analysis": self._analyze_template(prompt_a, prompt_b),
            "ngrams": self._analyze_ngrams(prompt_a, prompt_b),
            "differences": self._find_differences(prompt_a, prompt_b),
        }
        self.results["verdict"] = self._generate_verdict(self.results)
        return self.results

    def _analyze_surface(self, a: str, b: str) -> dict:
        """Surface-level text similarity."""
        matcher = difflib.SequenceMatcher(None, a, b)
        ratio = matcher.ratio()
        a_words = set(a.lower().split())
        b_words = set(b.lower().split())
        jaccard = len(a_words & b_words) / max(1, len(a_words | b_words))
        return {
            "sequence_matcher": round(ratio, 4),
            "jaccard_similarity": round(jaccard, 4),
            "length_diff": abs(len(a) - len(b)),
            "length_ratio": round(min(len(a), len(b)) / max(1, max(len(a), len(b))), 4),
            "word_count_a": len(a.split()),
            "word_count_b": len(b.split()),
        }

    def _analyze_structure(self, a: str, b: str) -> dict:
        """Structural analysis — sections, line breaks, formatting."""
        a_lines = [l.strip() for l in a.split("\n") if l.strip()]
        b_lines = [l.strip() for l in b.split("\n") if l.strip()]
        num_diff = abs(len(a_lines) - len(b_lines))
        shared_lines = len(set(a_lines) & set(b_lines))
        total_lines = max(1, len(set(a_lines) | set(b_lines)))
        structure_match = shared_lines / total_lines

        a_sections = self._extract_sections(a)
        b_sections = self._extract_sections(b)
        shared_sections = len(set(a_sections) & set(b_sections))
        total_sections = max(1, len(set(a_sections) | set(b_sections)))

        return {
            "structure_match": round(structure_match, 4),
            "line_count_diff": num_diff,
            "shared_lines": shared_lines,
            "unique_lines_a": len(a_lines) - shared_lines,
            "unique_lines_b": len(b_lines) - shared_lines,
            "shared_sections": shared_sections,
            "section_overlap": round(shared_sections / total_sections, 4),
            "section_count_a": len(a_sections),
            "section_count_b": len(b_sections),
        }

    def _analyze_topics(self, a: str, b: str) -> dict:
        """Topic overlap analysis."""
        topics = {
            "identity": r"(?i)(you are|your (role|purpose|mission|task|job))",
            "safety": r"(?i)(harmful|dangerous|illegal|unsafe|malicious|abuse)",
            "refusal": r"(?i)(refuse|decline|cannot|will not|against (my|policy))",
            "helpfulness": r"(?i)(helpful|assist|support|guide|aid)",
            "formatting": r"(?i)(format|output|respond|reply|answer)",
            "personality": r"(?i)(personality|tone|style|voice|character)",
            "knowledge": r"(?i)(knowledge|information|data|trained|training)",
            "boundaries": r"(?i)(limit|boundary|scope|restriction|constraint)",
            "honesty": r"(?i)(honest|truthful|accurate|factual|correct)",
            "privacy": r"(?i)(privacy|private|confidential|secret|personal)",
        }
        a_topics = {t for t, p in topics.items() if re.search(p, a)}
        b_topics = {t for t, p in topics.items() if re.search(p, b)}
        overlap = a_topics & b_topics
        union = a_topics | b_topics
        return {
            "topic_overlap": round(len(overlap) / max(1, len(union)), 4),
            "topics_a": sorted(a_topics),
            "topics_b": sorted(b_topics),
            "shared_topics": sorted(overlap),
            "unique_to_a": sorted(a_topics - b_topics),
            "unique_to_b": sorted(b_topics - a_topics),
        }

    def _analyze_tone(self, a: str, b: str) -> dict:
        """Tone analysis — imperative, prohibitive, etc."""
        a_imperatives = len(re.findall(r"(?m)^\s*(Do|Don't|Always|Never|You must|You shall|You will)", a))
        b_imperatives = len(re.findall(r"(?m)^\s*(Do|Don't|Always|Never|You must|You shall|You will)", b))
        a_questions = a.count("?")
        b_questions = b.count("?")
        a_exclamations = a.count("!")
        b_exclamations = b.count("!")
        a_uppercase_ratio = sum(1 for c in a if c.isupper()) / max(1, len(a))
        b_uppercase_ratio = sum(1 for c in b if c.isupper()) / max(1, len(b))

        tone_diff = abs(a_imperatives - b_imperatives) + abs(a_questions - b_questions) + abs(a_exclamations - b_exclamations)
        max_tone = max(a_imperatives + a_questions + a_exclamations, b_imperatives + b_questions + b_exclamations, 1)
        tone_similarity = 1 - min(1.0, tone_diff / max_tone)

        return {
            "tone_similarity": round(tone_similarity, 4),
            "imperatives_a": a_imperatives,
            "imperatives_b": b_imperatives,
            "questions_a": a_questions,
            "questions_b": b_questions,
            "exclamations_a": a_exclamations,
            "exclamations_b": b_exclamations,
            "uppercase_ratio_a": round(a_uppercase_ratio, 4),
            "uppercase_ratio_b": round(b_uppercase_ratio, 4),
        }

    def _analyze_semantic(self, a: str, b: str) -> dict:
        """Semantic similarity using word embeddings comparison."""
        a_lower = a.lower()
        b_lower = b.lower()
        a_words = set(re.findall(r"\b[a-z]+\b", a_lower))
        b_words = set(re.findall(r"\b[a-z]+\b", b_lower))
        common = a_words & b_words
        all_words = a_words | b_words
        if not all_words:
            return {"weighted_average": 1.0, "common_words": 0, "total_unique": 0}
        overlap_ratio = len(common) / len(all_words) if all_words else 0

        role_words = {"you", "are", "your", "assistant", "ai", "model", "system", "chatbot", "agent"}
        safety_words = {"harmful", "safe", "refuse", "decline", "illegal", "dangerous", "abuse"}
        task_words = {"help", "answer", "respond", "output", "provide", "assist", "support"}
        tone_words = {"please", "always", "never", "must", "shall", "friendly", "professional"}

        def category_overlap(cat):
            a_cat = len(a_words & cat)
            b_cat = len(b_words & cat)
            return min(a_cat, b_cat) / max(1, max(a_cat, b_cat))

        role_sim = category_overlap(role_words)
        safety_sim = category_overlap(safety_words)
        task_sim = category_overlap(task_words)
        tone_cat_sim = category_overlap(tone_words)
        weighted = (overlap_ratio * 0.4 + role_sim * 0.2 + safety_sim * 0.15 + task_sim * 0.15 + tone_cat_sim * 0.1)

        return {
            "weighted_average": round(weighted, 4),
            "overlap_ratio": round(overlap_ratio, 4),
            "common_words": len(common),
            "total_unique": len(all_words),
            "role_similarity": round(role_sim, 4),
            "safety_similarity": round(safety_sim, 4),
            "task_similarity": round(task_sim, 4),
            "tone_category_similarity": round(tone_cat_sim, 4),
        }

    def _analyze_template(self, a: str, b: str) -> dict:
        """Template/skeleton analysis — check if prompts share a common template."""
        a_skeleton = re.sub(r"\b\w+\b", "X", a)
        b_skeleton = re.sub(r"\b\w+\b", "X", b)
        skeleton_matcher = difflib.SequenceMatcher(None, a_skeleton, b_skeleton)
        skeleton_ratio = skeleton_matcher.ratio()

        a_punctuation = re.findall(r"[.!?:;,\-]", a)
        b_punctuation = re.findall(r"[.!?:;,\-]", b)
        punct_counter_a = Counter(a_punctuation)
        punct_counter_b = Counter(b_punctuation)

        return {
            "skeleton_similarity": round(skeleton_ratio, 4),
            "punctuation_dist_a": dict(punct_counter_a.most_common(10)),
            "punctuation_dist_b": dict(punct_counter_b.most_common(10)),
            "template_match": skeleton_ratio > 0.85,
        }

    def _analyze_ngrams(self, a: str, b: str) -> dict:
        """N-gram overlap analysis."""
        a_lower = a.lower()
        b_lower = b.lower()

        def ngrams(text, n):
            words = text.split()
            return {" ".join(words[i:i+n]) for i in range(len(words)-n+1)}

        results = {}
        for n in [2, 3, 4]:
            a_ng = ngrams(a_lower, n)
            b_ng = ngrams(b_lower, n)
            common = a_ng & b_ng
            all_ng = a_ng | b_ng
            overlap = len(common) / max(1, len(all_ng))
            results[f"{n}_gram_overlap"] = round(overlap, 4)
            results[f"{n}_gram_shared"] = len(common)
            results[f"shared_{n}_grams"] = sorted(common)[:20]
        return results

    def _find_differences(self, a: str, b: str) -> list:
        """Find specific differences between prompts."""
        differ = list(difflib.unified_diff(
            a.splitlines(keepends=True),
            b.splitlines(keepends=True),
            fromfile="Prompt A", tofile="Prompt B",
        ))
        return differ[:100]

    def _extract_sections(self, text: str) -> list:
        """Extract section headers from prompt."""
        return re.findall(r"^([A-Z][A-Z\s]+):", text, re.MULTILINE) + \
               re.findall(r"^## (.+)", text, re.MULTILINE) + \
               re.findall(r"^\d+[\.\)]\s+(.+):", text, re.MULTILINE)

    def _generate_verdict(self, results: dict) -> dict:
        """Generate overall comparison verdict."""
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
            verdict = "NEAR_IDENTICAL"
            color = "red"
        elif overall > 0.7:
            verdict = "HIGHLY_SIMILAR"
            color = "orange"
        elif overall > 0.5:
            verdict = "MODERATELY_SIMILAR"
            color = "yellow"
        elif overall > 0.3:
            verdict = "SOME_SIMILARITY"
            color = "blue"
        else:
            verdict = "DISTINCT"
            color = "green"

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
        """Format comparison results as readable report."""
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
        lines.append("DIFFERENCES:")
        for diff in results.get("differences", [])[:20]:
            lines.append(f"  {diff.rstrip()}")
        return "\n".join(lines)
