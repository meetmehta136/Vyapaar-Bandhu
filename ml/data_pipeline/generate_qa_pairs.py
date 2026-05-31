"""Generate synthetic Q&A pairs from chunked CGST Act + CBIC circulars.
Uses Claude Sonnet (or OpenRouter fallback) to create training data for embedding fine-tuning.

Usage:
  python generate_qa_pairs.py --chunks ml/data/processed/all_chunks.jsonl --output ml/data/processed/qa_pairs.json

Requires: ANTHROPIC_API_KEY or OPENROUTER_API_KEY in environment."""
import json, os, re, random, time, argparse
from pathlib import Path

from tqdm import tqdm

QA_SYSTEM_PROMPT = """You are an expert on the Indian CGST Act, 2017.
Generate question-answer pairs about GST compliance based strictly on the provided text.
Rules:
- Questions must be answerable from the text alone (no external knowledge).
- Each question should test understanding of a specific rule, condition, or definition.
- Answers must be concise (1-3 sentences) and directly cite the text.
- Return valid JSON only — a list of objects with "question" and "answer" keys.
- Generate 1-2 QA pairs per chunk. Do NOT make up facts."""


def parse_args():
    parser = argparse.ArgumentParser(description="Generate synthetic Q&A pairs for GSTMind")
    parser.add_argument("--chunks", default="ml/data/processed/all_chunks.jsonl",
                        help="Path to all_chunks.jsonl")
    parser.add_argument("--output", default="ml/data/processed/qa_pairs.json",
                        help="Output path for QA pairs JSON")
    parser.add_argument("--target", type=int, default=480,
                        help="Target number of QA pairs")
    parser.add_argument("--provider", choices=["anthropic", "openrouter"], default="anthropic",
                        help="LLM provider")
    parser.add_argument("--model", default=None,
                        help="Model name (defaults: claude-sonnet-4-20250514 or anthropic/claude-sonnet-4)")
    return parser.parse_args()


def load_chunks(path: str) -> list[dict]:
    chunks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def generate_qa_anthropic(text: str, api_key: str, model: str) -> list[dict]:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model or "claude-sonnet-4-20250514",
        max_tokens=600,
        system=QA_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Generate QA pairs from this text:\n\n{text[:3000]}"}],
    )
    return _parse_qa_response(resp.content[0].text)


def generate_qa_openrouter(text: str, api_key: str, model: str) -> list[dict]:
    import anthropic
    client = anthropic.Anthropic(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    resp = client.messages.create(
        model=model or "anthropic/claude-sonnet-4",
        max_tokens=600,
        system=QA_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Generate QA pairs from this text:\n\n{text[:3000]}"}],
    )
    return _parse_qa_response(resp.content[0].text)


def _parse_qa_response(text: str) -> list[dict]:
    json_match = re.search(r"\[.*\]", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return []


def main():
    args = parse_args()

    chunks = load_chunks(args.chunks)
    print(f"Loaded {len(chunks)} chunks")

    if args.provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        gen_fn = lambda text: generate_qa_anthropic(text, api_key, args.model)
    else:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        gen_fn = lambda text: generate_qa_openrouter(text, api_key, args.model)

    if not api_key:
        print(f"Error: {args.provider.upper()}_API_KEY not set in environment")
        return

    random.shuffle(chunks)
    qa_pairs = []

    for chunk in tqdm(chunks, desc="Generating QA pairs"):
        if len(qa_pairs) >= args.target:
            break
        try:
            pairs = gen_fn(chunk["text"])
            for p in pairs:
                if p.get("question") and p.get("answer"):
                    p["chunk_id"] = chunk["chunk_id"]
                    p["citation"] = chunk["citation"]
                    qa_pairs.append(p)
            time.sleep(0.5)
        except Exception as e:
            tqdm.write(f"Error on {chunk['chunk_id']}: {e}")
            continue

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(qa_pairs, f, indent=2, ensure_ascii=False)

    print(f"\nGenerated {len(qa_pairs)} QA pairs → {out_path}")


if __name__ == "__main__":
    main()
