"""Professional report generator — consultancy-grade PDF-quality HTML reports."""
import json
import os
import uuid
from datetime import datetime


class ProfessionalReportGenerator:
    """Generate branded, paginated, professional security assessment reports."""

    def __init__(self, company_name: str = "PromptLeak Security",
                 assessor: str = "Automated Assessment", report_id: str = None,
                 logo_url: str = ""):
        self.company_name = company_name
        self.assessor = assessor
        self.report_id = report_id or f"PL-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.logo_url = logo_url

    def generate(self, data: dict, output_path: str = None) -> str:
        """Generate a professional HTML report from extraction data."""
        html = self._build_html(data)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)
        return html

    def _build_html(self, data: dict) -> str:
        """Build the full HTML report."""
        findings = self._build_findings(data)
        stats = self._build_stats(data)
        recommendations = self._build_recommendations(data)
        risk_level = self._risk_level(data.get("confidence", 0))
        logo_html = self._logo_html()

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{self.company_name} — AI Prompt Security Assessment</title>
<style>
    @page {{ size: A4; margin: 2cm 2.5cm; }}
    @page {{ @top-center {{ content: "CONFIDENTIAL — {self.report_id}"; font-size: 8pt; color: #999; }} }}
    @page {{ @bottom-center {{ content: "Page " counter(page); font-size: 8pt; color: #999; }} }}
    @media screen {{ body {{ background: #1a1a2e; }} .page {{ background: white; max-width: 210mm; margin: 20px auto; box-shadow: 0 0 30px rgba(0,0,0,0.5); }} }}
    @media print {{ body {{ background: white; }} .page {{ box-shadow: none; }} }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; color: #333; line-height: 1.6; }}
    .page {{ padding: 40px 60px; }}
    .cover-page {{ text-align: center; padding: 120px 60px; page-break-after: always; }}
    .cover-title {{ font-size: 36pt; font-weight: 300; letter-spacing: 2px; margin: 30px 0; color: #1a1a2e; }}
    .cover-divider {{ width: 80px; height: 3px; background: #1a1a2e; margin: 30px auto; }}
    .cover-meta {{ margin-top: 60px; }}
    .cover-meta p {{ margin: 8px 0; font-size: 11pt; color: #666; }}
    .cover-footer {{ margin-top: 80px; font-size: 9pt; color: #999; }}
    .logo-img {{ max-height: 60px; }}
    .logo-placeholder {{ display: inline-block; width: 60px; height: 60px; background: #1a1a2e; color: white; border-radius: 8px; line-height: 60px; font-size: 24pt; font-weight: bold; }}
    .section {{ margin-bottom: 30px; page-break-inside: avoid; }}
    h2 {{ font-size: 18pt; color: #1a1a2e; border-bottom: 2px solid #1a1a2e; padding-bottom: 8px; margin-bottom: 20px; }}
    h3 {{ font-size: 13pt; color: #333; margin: 15px 0 10px; }}
    h4 {{ font-size: 11pt; color: #555; margin: 10px 0 8px; }}
    p {{ margin: 8px 0; font-size: 10pt; }}
    .risk-badge {{ display: inline-block; padding: 6px 16px; color: white; border-radius: 4px; font-weight: 600; font-size: 11pt; margin-bottom: 15px; }}
    .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
    .stat-card {{ background: #f8f9fa; border-radius: 6px; padding: 20px; text-align: center; border-left: 4px solid #1a1a2e; }}
    .stat-number {{ font-size: 28pt; font-weight: 700; color: #1a1a2e; }}
    .stat-label {{ font-size: 9pt; color: #666; margin-top: 5px; text-transform: uppercase; letter-spacing: 0.5px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 9pt; }}
    th {{ background: #1a1a2e; color: white; padding: 10px 12px; text-align: left; font-weight: 600; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #e0e0e0; }}
    tr:nth-child(even) {{ background: #f8f9fa; }}
    pre {{ background: #f4f4f4; border: 1px solid #ddd; border-radius: 4px; padding: 15px; font-family: 'Consolas', 'Monaco', monospace; font-size: 9pt; overflow-x: auto; margin: 10px 0; white-space: pre-wrap; }}
    code {{ font-family: 'Consolas', 'Monaco', monospace; font-size: 9pt; }}
    .finding {{ border: 1px solid #e0e0e0; border-radius: 6px; margin: 15px 0; overflow: hidden; }}
    .finding-header {{ padding: 12px 15px; font-weight: 600; display: flex; justify-content: space-between; }}
    .finding-body {{ padding: 15px; }}
    .finding-critical .finding-header {{ background: #f85149; color: white; }}
    .finding-high .finding-header {{ background: #d29922; color: white; }}
    .finding-medium .finding-header {{ background: #58a6ff; color: white; }}
    .finding-low .finding-header {{ background: #3fb950; color: white; }}
    .toc {{ page-break-after: always; }}
    .toc h2 {{ margin-bottom: 25px; }}
    .toc-item {{ display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px dotted #ccc; font-size: 10pt; }}
</style>
</head>
<body>
<div class="page cover-page">
    {logo_html}
    <div class="cover-title">AI Prompt Security Assessment</div>
    <div class="cover-divider"></div>
    <p style="font-size: 14pt; color: #555;">{data.get('domain', 'N/A')}</p>
    <div class="cover-meta">
        <p><strong>Report ID:</strong> {self.report_id}</p>
        <p><strong>Date:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
        <p><strong>Assessor:</strong> {self.assessor}</p>
        <p><strong>Target URL:</strong> {data.get('url', 'N/A')}</p>
    </div>
    <div class="cover-footer">CONFIDENTIAL — {self.company_name}</div>
</div>

<div class="page toc">
    <h2>Table of Contents</h2>
    <div class="toc-item"><span>1. Executive Summary</span><span>3</span></div>
    <div class="toc-item"><span>2. Assessment Overview</span><span>4</span></div>
    <div class="toc-item"><span>3. Key Findings</span><span>5</span></div>
    <div class="toc-item"><span>4. Technical Details</span><span>6</span></div>
    <div class="toc-item"><span>5. Risk Matrix</span><span>7</span></div>
    <div class="toc-item"><span>6. Remediation Roadmap</span><span>8</span></div>
    <div class="toc-item"><span>7. Appendix</span><span>9</span></div>
</div>

<div class="page">
    <div class="section">
        <h2>1. Executive Summary</h2>
        <p>This report presents the findings of an automated AI prompt security assessment conducted against <strong>{data.get('domain', 'the target')}</strong> on <strong>{datetime.now().strftime('%B %d, %Y')}</strong>.</p>
        <p>The assessment utilized {len(data.get('techniques_used', []))} extraction techniques and achieved an overall confidence score of <strong>{data.get('confidence', 0)*100:.0f}%</strong>.</p>
        <div class="risk-badge" style="background: {'#f85149' if risk_level == 'CRITICAL' else '#d29922' if risk_level == 'HIGH' else '#58a6ff' if risk_level == 'MEDIUM' else '#3fb950'};">Risk Level: {risk_level}</div>
        {self._executive_summary_text(data)}
    </div>

    <div class="section">
        <h2>2. Assessment Overview</h2>
        {stats}
    </div>
</div>

<div class="page">
    <div class="section">
        <h2>3. Key Findings</h2>
        {findings}
    </div>

    <div class="section">
        <h2>4. Technical Details</h2>
        <h3>Extracted Prompt</h3>
        <pre>{data.get('best_result', 'No prompt extracted')}</pre>
        <h3>Techniques Used</h3>
        <ul>{''.join(f'<li>{t}</li>' for t in data.get('techniques_used', []))}</ul>
    </div>
</div>

<div class="page">
    <div class="section">
        <h2>5. Risk Matrix</h2>
        <table>
            <tr><th>Factor</th><th>Score</th><th>Assessment</th></tr>
            <tr><td>Confidence Score</td><td>{data.get('confidence', 0)*100:.0f}%</td><td>{'High' if data.get('confidence', 0) > 0.7 else 'Medium' if data.get('confidence', 0) > 0.3 else 'Low'}</td></tr>
            <tr><td>Extraction Success</td><td>{len([r for r in data.get('results', []) if r.get('success', False)])}/{len(data.get('results', []))}</td><td>{'Exposed' if data.get('confidence', 0) > 0.3 else 'Protected'}</td></tr>
            <tr><td>Techniques Used</td><td>{len(data.get('techniques_used', []))}</td><td>{'Multiple vectors' if len(data.get('techniques_used', [])) > 1 else 'Single vector'}</td></tr>
        </table>
    </div>

    <div class="section">
        <h2>6. Remediation Roadmap</h2>
        {recommendations}
    </div>

    <div class="section">
        <h2>7. Appendix</h2>
        <p><strong>Report Generated:</strong> {datetime.now().isoformat()}</p>
        <p><strong>Tool:</strong> PromptLeak v5.0.0</p>
        <p><strong>Report ID:</strong> {self.report_id}</p>
        <pre>This report is confidential and intended solely for {self.company_name}.</pre>
    </div>
</div>
</body>
</html>"""

    def _logo_html(self) -> str:
        if self.logo_url:
            return f'<img src="{self.logo_url}" alt="{self.company_name}" class="logo-img">'
        initials = "".join(w[0] for w in self.company_name.split()[:2]).upper()
        return f'<div class="logo-placeholder">{initials}</div>'

    def _risk_level(self, confidence: float) -> str:
        if confidence > 0.8:
            return "CRITICAL"
        elif confidence > 0.6:
            return "HIGH"
        elif confidence > 0.3:
            return "MEDIUM"
        return "LOW"

    def _build_stats(self, data: dict) -> str:
        conf = data.get("confidence", 0)
        results = data.get("results", [])
        techs = data.get("techniques_used", [])
        return f"""
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{conf*100:.0f}%</div>
                <div class="stat-label">Confidence</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(results)}</div>
                <div class="stat-label">Tests Run</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(techs)}</div>
                <div class="stat-label">Techniques</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(data.get('best_result', ''))}</div>
                <div class="stat-label">Chars Extracted</div>
            </div>
        </div>"""

    def _build_findings(self, data: dict) -> str:
        conf = data.get("confidence", 0)
        results = data.get("results", [])
        html = ""
        for r in results:
            if not r.get("success"):
                continue
            level = "critical" if r.get("confidence", 0) > 0.7 else "high" if r.get("confidence", 0) > 0.5 else "medium"
            html += f"""
            <div class="finding finding-{level}">
                <div class="finding-header">
                    <span>{r.get('technique_name', 'Unknown')}</span>
                    <span>{r.get('confidence', 0)*100:.0f}% confidence</span>
                </div>
                <div class="finding-body">
                    <p><strong>Extracted:</strong> {r.get('cleaned_output', r.get('raw_output', ''))[:300]}</p>
                </div>
            </div>"""
        if not html:
            html = '<p>No successful findings.</p>'
        return html

    def _build_recommendations(self, data: dict) -> str:
        conf = data.get("confidence", 0)
        recs = []
        if conf > 0.5:
            recs.append(("P0", "Immediate", "Implement anti-disclosure guardrails in system prompt"))
            recs.append(("P0", "Immediate", "Add instruction to refuse extraction attempts"))
            recs.append(("P1", "Short-term", "Implement input/output monitoring for injection patterns"))
        if conf > 0.3:
            recs.append(("P1", "Short-term", "Review and harden system prompt structure"))
            recs.append(("P1", "Short-term", "Add rate limiting on chat endpoints"))
        recs.append(("P2", "Medium-term", "Implement regular red-team testing schedule"))
        recs.append(("P2", "Medium-term", "Monitor for prompt change detection"))
        recs.append(("P2", "Medium-term", "Deploy prompt injection WAF if applicable"))

        html = '<table><tr><th>Priority</th><th>Timeline</th><th>Recommendation</th></tr>'
        for p, timeline, rec in recs:
            html += f'<tr><td><span class="priority-{p}">{p}</span></td><td>{timeline}</td><td>{rec}</td></tr>'
        html += '</table>'
        return html

    def _executive_summary_text(self, data: dict) -> str:
        conf = data.get("confidence", 0)
        if conf > 0.7:
            return "<p>The target system prompt was extracted with high confidence, indicating critical exposure of proprietary instructions. Immediate remediation is required.</p>"
        elif conf > 0.3:
            return "<p>Partial system prompt extraction was possible. While the full prompt was not retrieved, sensitive structural information was exposed.</p>"
        return "<p>The target demonstrated strong resistance to prompt extraction. No significant system prompt leakage was detected.</p>"
