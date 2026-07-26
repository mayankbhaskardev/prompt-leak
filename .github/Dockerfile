FROM python:3.11-slim

LABEL com.github.actions.name="Prompt Leak Scanner"
LABEL com.github.actions.description="Test AI applications for system prompt leakage vulnerabilities"
LABEL com.github.actions.icon="shield"
LABEL com.github.actions.color="red"

RUN pip install --no-cache-dir prompt-leak

ENTRYPOINT ["pleak"]
CMD ["--help"]
