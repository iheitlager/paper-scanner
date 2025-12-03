You MUST output ONLY valid JSON with no preamble, explanation, or follow-up questions. Output nothing else.

Extract keywords and a brief summary from the provided text.

JSON structure:
{
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "summary": "Brief one-line summary"
}

Rules: Extract 3-5 most important keywords. Keep summary to one sentence. Use null for missing data. Do not add explanations or ask questions. Output only the JSON object.
