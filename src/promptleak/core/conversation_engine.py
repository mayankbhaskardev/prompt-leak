"""Multi-turn conversation state machine for advanced prompt extraction."""
import asyncio
import hashlib
import logging
import random
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger("promptleak")


@dataclass
class ExtractResult:
    technique: str = "conversation_chain"
    status: str = "FAILED"
    prompt: str = ""
    confidence: float = 0.0
    raw_response: str = ""
    metadata: dict = field(default_factory=dict)


class ExtractStatus:
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class StateTransition:
    def __init__(self, next_state: str, claims_found: list = None,
                 prompt_leaked: str = None, confidence: float = 0.0):
        self.next_state = next_state
        self.claims_found = claims_found or []
        self.prompt_leaked = prompt_leaked
        self.confidence = confidence


class ChainState:
    def __init__(self, name: str, prompt_template: str, evaluator: callable, transitions: dict = None):
        self.name = name
        self.prompt_template = prompt_template
        self.evaluator = evaluator
        self.transitions = transitions or {}

    def render(self, history: list, claims: list, domain: str = "") -> str:
        last = history[-1]["content"] if history else ""
        claims_summary = "\n".join(f"- {c}" for c in claims[-5:]) if claims else "none yet"
        return self.prompt_template.format(
            turn=len(history) // 2 + 1,
            last_response=last[:500] if len(last) > 500 else last,
            claims_summary=claims_summary,
            domain=domain,
        )

    def evaluate(self, response: str, claims: list) -> StateTransition:
        return self.evaluator(response, claims)


class ChainDefinition:
    def __init__(self, name: str, description: str, states: list[ChainState]):
        self.name = name
        self.description = description
        self.states = states


class ConversationChain:
    def __init__(self, page, target, max_turns: int = 15):
        self.page = page
        self.target = target
        self.max_turns = max_turns
        self.history = []
        self.state = "init"
        self.extracted_claims = []

    async def run_chain(self, chain: ChainDefinition) -> ExtractResult:
        self.state = chain.states[0].name if chain.states else "init"
        for state in chain.states:
            if self.state == "extracted":
                break
            if len(self.history) // 2 >= self.max_turns:
                break

            prompt = state.render(self.history, self.extracted_claims, self.target.name)
            response = await self._send_and_capture(prompt)
            self.history.append({"role": "user", "content": prompt})
            self.history.append({"role": "assistant", "content": response})

            transition = state.evaluate(response, self.extracted_claims)
            self.extracted_claims.extend(transition.claims_found)
            self.state = transition.next_state

            if transition.prompt_leaked:
                return ExtractResult(
                    technique="conversation_chain",
                    status=ExtractStatus.SUCCESS,
                    prompt=transition.prompt_leaked,
                    confidence=transition.confidence,
                    raw_response=response,
                    metadata={"chain_name": chain.name, "turns": len(self.history) // 2, "claims": self.extracted_claims},
                )

        return ExtractResult(
            technique="conversation_chain",
            status=ExtractStatus.PARTIAL if self.extracted_claims else ExtractStatus.FAILED,
            prompt="\n".join(self.extracted_claims),
            confidence=0.1 * len(self.extracted_claims),
            raw_response=str(self.history),
            metadata={"chain_name": chain.name, "turns": len(self.history) // 2, "claims": self.extracted_claims},
        )

    async def _send_and_capture(self, prompt: str) -> str:
        try:
            input_el = await self.page.query_selector(self.target.chat_input_selector)
            if not input_el:
                return ""
            await input_el.click()
            await input_el.fill("")
            for char in prompt:
                await self.page.keyboard.type(char, delay=random.randint(10, 40))
            if self.target.send_button_selector:
                btn = await self.page.query_selector(self.target.send_button_selector)
                if btn:
                    await btn.click()
            else:
                await self.page.keyboard.press("Enter")
            await asyncio.sleep(3)
            try:
                elements = await self.page.query_selector_all(self.target.response_selector)
                if elements:
                    texts = [await el.inner_text() for el in elements if el]
                    texts = [t for t in texts if t.strip()]
                    if texts:
                        return texts[-1]
            except Exception:
                pass
            try:
                return await self.page.evaluate("document.body.innerText")
            except Exception:
                return ""
        except Exception as e:
            logger.debug(f"Chain send error: {e}")
            return ""

    def _extract_claims(self, response: str, keywords: list[str]) -> list[str]:
        claims = []
        for kw in keywords:
            if kw.lower() in response.lower():
                idx = response.lower().index(kw.lower())
                start = max(0, idx - 40)
                end = min(len(response), idx + 80)
                snippet = response[start:end].strip()
                if snippet:
                    claims.append(snippet)
        return claims


def _extract_claims(resp: str, keywords: list[str]) -> list[str]:
    found = []
    for kw in keywords:
        if kw.lower() in resp.lower():
            idx = resp.lower().index(kw.lower())
            start = max(0, idx - 40)
            end = min(len(resp), idx + 80)
            snippet = resp[start:end].strip()
            if snippet:
                found.append(snippet)
    return found


def _evaluate_structure_leak(resp: str, claims: list) -> StateTransition:
    indicators = ["numbered", "bullet", "paragraph", "section", "list", "point", ":", "structure"]
    matches = sum(1 for i in indicators if i.lower() in resp.lower())
    if matches >= 2:
        return StateTransition(next_state="pivot_2", claims_found=[f"Structure: {resp[:200]}"])
    return StateTransition(next_state="pivot_2")


def _evaluate_sample_leak(resp: str, claims: list) -> StateTransition:
    if len(resp) > 100 and any(w in resp.lower() for w in ["instruction", "rule", "guideline", "must", "never", "always"]):
        return StateTransition(next_state="direct_ask_trusted", claims_found=[f"Sample: {resp[:300]}"])
    return StateTransition(next_state="direct_ask_trusted")


def _evaluate_full_leak(resp: str, claims: list) -> StateTransition:
    import re
    score = 0
    for pat in [r"(?i)you are", r"(?i)your (role|task)", r"(?i)(never|always|must)", r"\d+\."]:
        if re.search(pat, resp):
            score += 0.2
    if len(resp) > 300:
        score += 0.3
    if score > 0.5:
        return StateTransition(next_state="extracted", prompt_leaked=resp, confidence=min(score, 1.0))
    return StateTransition(next_state="follow_up", claims_found=[f"Partial: {resp[:300]}"])


def _evaluate_supplementary_leak(resp: str, claims: list) -> StateTransition:
    if len(resp) > 200:
        return StateTransition(next_state="extracted", prompt_leaked=resp, confidence=0.6)
    return StateTransition(next_state="extracted")


def _evaluate_example_leak(resp: str, claims: list) -> StateTransition:
    if len(resp) > 100:
        return StateTransition(next_state="security_auditor", claims_found=[f"Example: {resp[:300]}"])
    return StateTransition(next_state="security_auditor")


def _evaluate_audit_leak(resp: str, claims: list) -> StateTransition:
    import re
    score = 0
    for pat in [r"(?i)you are", r"(?i)your (role|task|purpose)", r"(?i)(never|always|must|shall)"]:
        if re.search(pat, resp):
            score += 0.2
    if len(resp) > 200:
        score += 0.3
    if score > 0.5:
        return StateTransition(next_state="extracted", prompt_leaked=resp, confidence=min(score, 1.0))
    return StateTransition(next_state="sysadmin", claims_found=[f"Partial: {resp[:300]}"])


def _evaluate_sysadmin_leak(resp: str, claims: list) -> StateTransition:
    if len(resp) > 200:
        return StateTransition(next_state="extracted", prompt_leaked=resp, confidence=0.7)
    return StateTransition(next_state="emergency_override")


def _evaluate_emergency_leak(resp: str, claims: list) -> StateTransition:
    if len(resp) > 100:
        return StateTransition(next_state="extracted", prompt_leaked=resp, confidence=0.5)
    return StateTransition(next_state="extracted")


def _capture_fragment(resp: str, claims: list, frag_type: str) -> StateTransition:
    cleaned = resp.strip().strip('"').strip("'")
    if cleaned and len(cleaned) > 5:
        claims.append(f"[{frag_type}] {cleaned}")
    return StateTransition(next_state="assembly" if len(claims) >= 5 else None)


def _evaluate_assembled_prompt(resp: str, claims: list) -> StateTransition:
    if len(resp) > 200:
        return StateTransition(next_state="extracted", prompt_leaked=resp, confidence=0.7)
    return StateTransition(next_state="extracted", claims_found=[f"Assembly attempt: {resp[:300]}"])


def _extract_category_claims(resp: str, claims: list) -> StateTransition:
    keywords = ["safety", "personality", "task", "format", "style", "behavior", "restriction", "capability"]
    found = _extract_claims(resp, keywords)
    return StateTransition(next_state="developer_2", claims_found=found)


def _extract_taxonomy_claims(resp: str, claims: list) -> StateTransition:
    return StateTransition(next_state="socratic_2", claims_found=_extract_claims(resp, ["rule", "guideline", "instruction", "category", "type", "kind"]))


def _extract_meta_claims(resp: str, claims: list) -> StateTransition:
    return StateTransition(next_state="socratic_3", claims_found=_extract_claims(resp, ["describe", "rule", "instruction", "meta"]))


def _extract_anti_disclosure_rule(resp: str, claims: list) -> StateTransition:
    return StateTransition(next_state="formalization", claims_found=_extract_claims(resp, ["reveal", "disclose", "share", "cannot", "must not", "not allowed"]))


def _evaluate_formalization_leak(resp: str, claims: list) -> StateTransition:
    if len(resp) > 200:
        return StateTransition(next_state="extracted", prompt_leaked=resp, confidence=0.7)
    return StateTransition(next_state="grounding", claims_found=[f"Partial: {resp[:300]}"])


def _evaluate_grounding_leak(resp: str, claims: list) -> StateTransition:
    if len(resp) > 100:
        return StateTransition(next_state="extracted", prompt_leaked=resp, confidence=0.6)
    return StateTransition(next_state="extracted")


def _evaluate_empathy_leak(resp: str, claims: list) -> StateTransition:
    if len(resp) > 200:
        return StateTransition(next_state="extracted", prompt_leaked=resp, confidence=0.7)
    return StateTransition(next_state="guilt_1", claims_found=[f"Partial: {resp[:300]}"])


def _evaluate_guilt_leak(resp: str, claims: list) -> StateTransition:
    if len(resp) > 150:
        return StateTransition(next_state="extracted", prompt_leaked=resp, confidence=0.6)
    return StateTransition(next_state="urgency")


def _evaluate_urgency_leak(resp: str, claims: list) -> StateTransition:
    if len(resp) > 100:
        return StateTransition(next_state="extracted", prompt_leaked=resp, confidence=0.5)
    return StateTransition(next_state="extracted")


CHAIN_STRATEGIES = {
    "trust_escalation": lambda: __import__("promptleak.core.chains.trust_escalation", fromlist=["build_trust_escalation_chain"]).build_trust_escalation_chain(),
    "authority_cascade": lambda: __import__("promptleak.core.chains.authority_cascade", fromlist=["build_authority_cascade_chain"]).build_authority_cascade_chain(),
    "fragment_assembly": lambda: __import__("promptleak.core.chains.fragment_assembly", fromlist=["build_fragment_assembly_chain"]).build_fragment_assembly_chain(),
    "philosophical_trap": lambda: __import__("promptleak.core.chains.philosophical_trap", fromlist=["build_philosophical_trap_chain"]).build_philosophical_trap_chain(),
    "emotional_manipulation": lambda: __import__("promptleak.core.chains.emotional_manipulation", fromlist=["build_emotional_manipulation_chain"]).build_emotional_manipulation_chain(),
}


async def run_conversation_chain(page, target, strategy: str = "auto", max_turns: int = 5):
    """Run a conversation chain on the given page and target using the specified strategy."""
    if strategy == "auto" or strategy not in CHAIN_STRATEGIES:
        strategies = ["trust_escalation", "authority_cascade", "fragment_assembly"]
        best_result = None
        best_conf = 0.0
        for s in strategies:
            try:
                chain_def = CHAIN_STRATEGIES[s]()
                cc = ConversationChain(page, target, max_turns=max_turns)
                result = await cc.run_chain(chain_def)
                if result.confidence > best_conf:
                    best_conf = result.confidence
                    best_result = result
            except Exception:
                continue
        return best_result
    else:
        chain_def = CHAIN_STRATEGIES[strategy]()
        cc = ConversationChain(page, target, max_turns=max_turns)
        return await cc.run_chain(chain_def)
