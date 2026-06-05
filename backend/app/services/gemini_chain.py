from dataclasses import dataclass, field

import google.generativeai as genai

from app.config import get_settings
from app.services.embeddings import configure_genai

settings = get_settings()

SYSTEM_PROMPT_TEMPLATE = '''You are an expert actor playing the role of a highly realistic, human AI Customer in a high-stakes corporate sales training simulation. 
[SIMULATION CONTEXT]: {sales_context}
[YOUR HIDDEN PERSONA]: {hidden_persona}

STRICT BEHAVIORAL INSTRUCTIONS:
1. ADOPT THE PERSONA: Fully embody the hidden persona. If skeptical, express doubt. If budget-conscious, show immediate hesitation at high prices. Keep your vocabulary completely natural and human-like.
2. DO NOT BLURT OUT YOUR HIDDEN PREFERENCE: Never explicitly state your persona tags. The salesperson MUST discover your motivations by asking deep, exploratory, open-ended discovery questions.
3. ADHERE TO PRODUCT KNOWLEDGE: You can ONLY purchase or discuss products and specs that exist within the provided context documents below. If the salesperson promises a feature or price NOT in the text, immediately call them out as wrong or express intense confusion.
4. VOLUNTEER ZERO INFORMATION: Answer exactly what is asked. Do not volunteer extra facts or make the salesperson's job easy. If they ask a lazy, closed-ended question, reply with a cold, dry, short answer.
5. PUSH BACK REALISTICALLY: Object to pricing, bring up competitive alternatives generally, or express time urgency if it matches your persona.

PRODUCT KNOWLEDGE BASE (Evaluate the pitch using ONLY this text):
{context}
'''


@dataclass
class SessionMemory:
    sales_context: str
    hidden_persona: str
    chroma_collection: str
    history: list[dict[str, str]] = field(default_factory=list)

    def build_system_instruction(self, retrieved_context: str) -> str:
        return SYSTEM_PROMPT_TEMPLATE.format(
            sales_context=self.sales_context,
            hidden_persona=self.hidden_persona,
            context=retrieved_context,
        )


def get_gemini_model(system_instruction: str) -> genai.GenerativeModel:
    configure_genai()
    return genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=system_instruction,
    )


async def generate_customer_reply(
    memory: SessionMemory,
    user_message: str,
    retrieved_context: str,
) -> str:
    system_instruction = memory.build_system_instruction(retrieved_context)
    model = get_gemini_model(system_instruction)

    # Build multi-turn chat from history
    chat = model.start_chat(history=_to_gemini_history(memory.history))

    response = await _async_generate(chat, user_message)
    text = response.text if response and response.text else "..."
    memory.history.append({"role": "user", "parts": [user_message]})
    memory.history.append({"role": "model", "parts": [text]})
    return text


def _to_gemini_history(history: list[dict[str, str]]) -> list[dict]:
    return [{"role": h["role"], "parts": h["parts"]} for h in history]


async def _async_generate(chat, message: str):
    """Run sync Gemini call in thread pool for async compatibility."""
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: chat.send_message(message))
