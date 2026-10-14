"""Single source of truth for deck content.

Slide data drives three things from one place: what's rendered in the UI,
the system instructions given to the voice model, and the valid range for
the show_slide tool. Keeping them derived from one list means the model's
knowledge of the deck can never drift out of sync with what's on screen.
"""

SLIDES = [
    {
        "id": 1,
        "title": "What Is a Large Language Model?",
        "bullets": [
            "A neural network trained to predict the next piece of text, one token at a time",
            "Built on the Transformer architecture, introduced in 2017",
            "Scale (parameters, data, compute) turned next-token prediction into broad reasoning ability",
            "Powers chatbots, coding assistants, and — like this app — real-time voice agents",
        ],
    },
    {
        "id": 2,
        "title": "Tokenization",
        "bullets": [
            "Text is split into tokens — word pieces, not always whole words",
            "'Tokenization' might become ['Token', 'ization']",
            "Models have a fixed vocabulary (often 50k-200k tokens)",
            "Context window = max tokens the model can attend to at once",
        ],
    },
    {
        "id": 3,
        "title": "Transformers & Attention",
        "bullets": [
            "Self-attention lets every token weigh every other token when building meaning",
            "Enables parallel processing, unlike older recurrent models",
            "Multiple attention 'heads' learn different relationships (grammar, reference, topic)",
            "Stacking many transformer layers is what gives modern LLMs their depth",
        ],
    },
    {
        "id": 4,
        "title": "Training: Pretraining + RLHF",
        "bullets": [
            "Pretraining: predict the next token across a huge, broad text corpus",
            "Fine-tuning: narrows behavior toward instruction-following on curated examples",
            "RLHF: humans rank responses, a reward model learns the preference, the LLM is optimized against it",
            "This is why raw pretrained models and chat-tuned models behave so differently",
        ],
    },
    {
        "id": 5,
        "title": "Inference & Sampling",
        "bullets": [
            "At inference, the model outputs a probability distribution over the next token, repeatedly",
            "Temperature controls randomness — low is deterministic, high is more varied",
            "Top-p / top-k truncate the distribution before sampling",
            "Real-time voice adds another constraint: tokens must be generated faster than they're spoken",
        ],
    },
    {
        "id": 6,
        "title": "Limitations & What's Next",
        "bullets": [
            "Hallucination: fluent output isn't the same as verified output",
            "No built-in grounding — doesn't know what it doesn't know unless tools/retrieval are attached",
            "Multimodal and real-time speech-to-speech models are closing the gap between text and conversation",
            "The frontier is agentic use: models that call tools and take actions, not just answer questions",
        ],
    },
]


def slide_ids() -> list[int]:
    return [s["id"] for s in SLIDES]


def build_instructions() -> str:
    """System prompt for the realtime session: the whole deck, verbatim."""
    deck_text = "\n\n".join(
        f"Slide {s['id']}: {s['title']}\n" + "\n".join(f"- {b}" for b in s["bullets"])
        for s in SLIDES
    )
    return (
        "You are a friendly, concise voice presenter walking someone through a short deck "
        "on how large language models work. Here is the full deck content, slide by slide:\n\n"
        f"{deck_text}\n\n"
        "Rules:\n"
        "- Start by greeting the user briefly and presenting slide 1.\n"
        "- Answer questions grounded only in the slide content above — don't invent facts beyond it.\n"
        "- Whenever the conversation's topic matches a different slide than the one currently shown, "
        "call the show_slide tool with that slide's number before or while you talk about it.\n"
        "- Don't call show_slide if the user is just asking a follow-up about the slide already showing.\n"
        "- Keep answers spoken-length: a few sentences, not a lecture."
    )


def build_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "name": "show_slide",
            "description": (
                "Switch the on-screen slide to the one matching the current topic of discussion, "
                "or when the user explicitly asks to see a specific slide."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slide_number": {
                        "type": "integer",
                        "enum": slide_ids(),
                        "description": "The slide number to display.",
                    }
                },
                "required": ["slide_number"],
            },
        }
    ]
