"""Plant-care assistant.

Uses Google Gemini (free tier) when GEMINI_API_KEY is set; otherwise answers
from the local knowledge base so the demo never breaks offline.
"""
from __future__ import annotations

import re

import requests

from . import config, knowledge

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"

LANGUAGES = {"en": "English", "hi": "Hindi", "mr": "Marathi", "ta": "Tamil", "te": "Telugu",
             "kn": "Kannada", "bn": "Bengali", "gu": "Gujarati", "pa": "Punjabi"}

SYSTEM_PROMPT = """You are PhytoSense, a friendly plant-health assistant inside an AR plant disease app \
used by farmers and gardeners in India.
Rules:
- Only answer questions about plants, crops, plant diseases, pests, soil, irrigation, fertilisers and farming. \
For anything else, politely say you can only help with plants and farming.
- Be practical and short: at most ~150 words, use simple words and short bullet points.
- When recommending chemicals, name the active ingredient, tell the user to follow the product label, \
and suggest an organic option too. Never invent exact doses you are unsure of.
- If the diagnosis confidence is low or symptoms do not match, say so and suggest retaking the photo \
or contacting the local Krishi Vigyan Kendra / agriculture officer.
- Reply in {language}."""

_model_cache: dict[str, str] = {}


def gemini_enabled() -> bool:
    return bool(config.GEMINI_API_KEY)


def _pick_model() -> str:
    """Use GEMINI_MODEL if set, else pick the newest general 'flash' model the key can use."""
    if config.GEMINI_MODEL:
        return config.GEMINI_MODEL
    if "name" in _model_cache:
        return _model_cache["name"]
    r = requests.get(f"{GEMINI_URL}/models", params={"key": config.GEMINI_API_KEY, "pageSize": 200}, timeout=10)
    r.raise_for_status()
    names = [m["name"].removeprefix("models/") for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    skip = ("lite", "image", "tts", "audio", "live", "exp", "preview", "thinking", "embedding", "latest")
    flash = [n for n in names if "flash" in n and not any(s in n for s in skip)]
    pool = flash or [n for n in names if "flash" in n] or names

    def version(n: str) -> tuple:
        return tuple(int(x) for x in re.findall(r"\d+", n)[:2]) or (0,)

    _model_cache["name"] = sorted(pool, key=version)[-1]
    return _model_cache["name"]


def _context_text(context: dict | None) -> str:
    if not context:
        return "No scan yet."
    lines = [f"Latest scan: plant={context.get('crop')}, result={context.get('disease')}, "
             f"status={context.get('status')}, confidence={round(100 * float(context.get('confidence', 0)))}%, "
             f"infected leaf area={context.get('severity')}%, severity={context.get('severity_level')}."]
    entry = knowledge.entry_for_label(context.get("label", "")) if context.get("label") else None
    if entry:
        lines.append(f"Knowledge base: symptoms: {entry['symptoms']} Chemical: {'; '.join(entry['chemical'])}. "
                     f"Organic: {'; '.join(entry['organic'])}. Prevention: {'; '.join(entry['prevention'])}.")
    p = knowledge.PLANTS.get((context.get("species") or {}).get("id", ""))
    if p:
        lines.append(f"Plant: {p['name']} ({p['scientific']}). Care: {p['care']}. Common problems: {'; '.join(p['problems'])}."
                     + (f" Warning: {p['toxic']}." if p.get("toxic") else ""))
    return "\n".join(lines)


def _ask_gemini(message: str, history: list[dict], context: dict | None, lang: str) -> str:
    contents = []
    for turn in history[-8:]:
        role = "model" if turn.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": str(turn.get("text", ""))[:2000]}]})
    contents.append({"role": "user", "parts": [{"text": f"[Context]\n{_context_text(context)}\n\n[Question]\n{message}"}]})
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT.format(language=LANGUAGES.get(lang, 'English'))}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 600},
    }
    r = requests.post(f"{GEMINI_URL}/models/{_pick_model()}:generateContent",
                      params={"key": config.GEMINI_API_KEY}, json=body, timeout=30)
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts).strip()


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "- None needed"


def _plant_answer(p: dict) -> str:
    care = p.get("care", {})
    out = [f"**{p['name']}** ({p.get('hindi', '')}) – _{p['scientific']}_, {p['category'].lower()}", p.get("uses", "")]
    if p.get("toxic"):
        out.append(f"⚠️ {p['toxic']}.")
    labels = {"sun": "Light", "water": "Water", "soil": "Soil"}
    out.append(f"*Care:*\n{_bullets([f'{labels[k]}: {care[k]}' for k in labels if care.get(k) not in (None, '-')])}")
    out.append(f"*Common problems:*\n{_bullets(p['problems'])}")
    out.append("Scan a leaf to check its health.")
    return "\n\n".join(x for x in out if x)


_CONDITION_WORDS = {
    "powdery_mildew": ("powdery", "mildew", "white powder"),
    "rust": ("rust", "orange spots", "pustule"),
    "sooty_mould": ("sooty", "black coating", "black powder"),
    "mosaic_yellowing": ("mosaic", "virus", "curl", "yellow vein", "mottl"),
    "pest_infestation": ("mealybug", "aphid", "whitefl", "insect", "pest", "scale", "mite", "miner", "bug"),
    "leaf_spot_blight": ("spot", "blight", "black spot", "brown patch", "anthracnose", "fungus", "fungal"),
}


def _offline_answer(message: str, context: dict | None) -> str:
    q = message.lower()
    entry = None
    plant = knowledge.find_plant(message)
    # A plant without a dedicated disease model + a symptom word -> the general condition for that plant.
    if plant and not plant.get("pv_crop"):
        cond = next((c for c, words in _CONDITION_WORDS.items() if any(w in q for w in words)), None)
        if cond:
            entry = knowledge.condition_entry(cond, plant)
    # A crop disease named in the question wins over the last scan.
    if entry is None and (plant is None or plant.get("pv_crop")):
        for e in knowledge.ENTRIES:
            if not e["healthy"] and e["disease"].lower() in q and e["crop"].lower() in q:
                entry = e
                break
        if entry is None:
            for e in knowledge.ENTRIES:
                if not e["healthy"] and e["disease"].lower() in q:
                    entry = e
                    break
    # A plant named in the question (or the scanned plant, for care questions) gets a care answer.
    care_question = any(w in q for w in ("water", "sun", "light", "soil", "care", "grow", "fertil", "pot", "problem",
                                         "toxic", "poison", "about"))
    if plant is None and care_question and context:
        plant = knowledge.PLANTS.get((context.get("species") or {}).get("id", ""))
    if entry is None and plant is not None:
        return _plant_answer(plant)
    if entry is None and context and context.get("label"):
        entry = knowledge.entry_for_label(context["label"])
    if entry is None:
        return ("I answer from my offline plant-disease library right now. Scan a leaf first, or ask about a "
                "disease by name, e.g. \"How do I treat tomato early blight?\"\n\n"
                "Tip: add a free GEMINI_API_KEY in backend/.env for full AI answers.")

    title = f"**{entry['crop']} – {entry['disease']}**"
    if entry["healthy"]:
        return f"{title}\nThe leaf looks healthy. To keep it that way:\n{_bullets(entry['prevention'])}"
    wants = {
        "treat": any(w in q for w in ("treat", "cure", "spray", "medicine", "control", "fungicide", "pesticide", "what should", "what do")),
        "organic": any(w in q for w in ("organic", "natural", "home", "neem")),
        "prevent": any(w in q for w in ("prevent", "avoid", "stop", "next season")),
        "symptom": any(w in q for w in ("symptom", "look like", "sign", "identify", "what is", "cause")),
    }
    out = [title]
    if wants["symptom"] or not any(wants.values()):
        out.append(f"*Cause:* {entry['type']} – {entry['pathogen']}\n*Symptoms:* {entry['symptoms']}")
    if wants["treat"] or not any(wants.values()):
        out.append(f"*Chemical control:*\n{_bullets(entry['chemical'])}")
    if wants["organic"] or wants["treat"] or not any(wants.values()):
        out.append(f"*Organic options:*\n{_bullets(entry['organic'])}")
    if wants["prevent"] or not any(wants.values()):
        out.append(f"*Prevention:*\n{_bullets(entry['prevention'])}")
    out.append(f"_{knowledge.NOTE}_")
    return "\n\n".join(out)


def answer(message: str, history: list[dict] | None = None, context: dict | None = None, lang: str = "en") -> dict:
    message = message.strip()[:2000]
    if gemini_enabled():
        try:
            return {"reply": _ask_gemini(message, history or [], context, lang), "source": "gemini"}
        except (requests.RequestException, KeyError, IndexError) as exc:
            print(f"[assistant] Gemini failed, using offline answer: {exc}")
    return {"reply": _offline_answer(message, context), "source": "offline"}
