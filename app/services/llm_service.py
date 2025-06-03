import logging
import os
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

import google.genai as genai
from google.genai.types import GenerateContentConfig

from app import config

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.prompts_cache: Dict[str, str] = {}
        self.client = None

        if config.GEMINI_API_KEY:
            self.client = genai.Client(api_key=config.GEMINI_API_KEY)
            logger.info("Gemini client initialized.")
        else:
            logger.error("Gemini API key not found. LLM features will fail.")
        if not self.client:
            logger.warning("LLM client is not initialized. All LLM operations will fail.")

    def _load_prompt(self, prompt_name: str) -> Optional[str]:
        if prompt_name in self.prompts_cache:
            return self.prompts_cache[prompt_name]

        try:
            prompt_file_path = config.PROMPTS_DIR_PATH / prompt_name
            if not prompt_file_path.exists():
                logger.error(f"Prompt file not found: {prompt_file_path}")
                return None
            
            with open(prompt_file_path, 'r', encoding='utf-8-sig') as f:
                prompt_content = f.read()
            self.prompts_cache[prompt_name] = prompt_content
            logger.info(f"Prompt '{prompt_name}' loaded successfully.")
            return prompt_content
        except Exception as e:
            logger.error(f"Error loading prompt '{prompt_name}': {e}")
            return None

    def _render_prompt(self, prompt_template: str, **kwargs: Any) -> str:
        rendered_prompt = prompt_template
        for key, value in kwargs.items():
            rendered_prompt = rendered_prompt.replace(f"{{{key}}}", str(value))
        return rendered_prompt

    async def _make_llm_call(self, model_name: str, messages: List[Dict[str, str]], temperature: float = 0.5, max_tokens: Optional[int] = None) -> Optional[str]:
        if not self.client:
            logger.error("LLM client not initialized. Cannot make API call.")
            return None
        try:
            prompt = "\n".join([m["content"] for m in messages])
            generation_config_params = {"temperature": temperature}
            if max_tokens is not None:
                generation_config_params["max_output_tokens"] = max_tokens

            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=GenerateContentConfig(temperature=temperature, automatic_function_calling=genai.types.AutomaticFunctionCallingConfig(disable=True))
            )
            if hasattr(response, "text"):
                return response.text.strip() if response.text else None
            if hasattr(response, "candidates") and response.candidates:
                return response.candidates[0].text.strip() if response.candidates[0].text else None
            logger.warning("Gemini response did not contain expected text content.")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during Gemini LLM call to model {model_name}: {e}")
            return None

    async def find_faq_match_index(self, user_query: str, enumerated_faqs_text: str) -> Optional[int]:
        search_prompt_template = self._load_prompt("search.txt")
        if not search_prompt_template:
            return None

        rendered_system_prompt = self._render_prompt(search_prompt_template, enumerated_questions=enumerated_faqs_text)
        
        messages = [
            {"role": "system", "content": rendered_system_prompt},
            {"role": "user", "content": user_query}
        ]
        
        response_text = await self._make_llm_call(
            model_name=config.SEARCH_MODEL_NAME,
            messages=messages,
            temperature=0.0
        )

        if response_text:
            try:
                return int(response_text)
            except ValueError:
                logger.error(f"LLM returned non-integer for FAQ match: '{response_text}'")
                return 0
        return 0

    async def generate_chat_response(
        self,
        personality_prompt_text: str,
        user_message: str,
        user_name: str,
        chat_history_text: Optional[str] = None,
        reply_to_text: Optional[str] = None,
        reply_to_name: Optional[str] = None
    ) -> Optional[str]:
        messages = [{"role": "system", "content": personality_prompt_text}]

        reply_prompt_template = self._load_prompt("reply.txt")
        if reply_to_text and reply_to_name and reply_prompt_template:
            rendered_reply_context = self._render_prompt(reply_prompt_template, author=reply_to_name, reply=reply_to_text)
            messages.append({"role": "system", "content": rendered_reply_context})

        history_prompt_template = self._load_prompt("history.txt")
        if chat_history_text and history_prompt_template:
            rendered_history = self._render_prompt(history_prompt_template, history=chat_history_text)
            messages.append({"role": "user", "content": rendered_history})

        message_prompt_template = self._load_prompt("message.txt")
        if not message_prompt_template:
            logger.error("Message prompt template (message.txt) not found.")
            return None
        
        rendered_user_message = self._render_prompt(message_prompt_template, author=user_name, message=user_message)
        messages.append({"role": "user", "content": rendered_user_message})
        
        response_text = await self._make_llm_call(
            model_name=config.ANSWER_MODEL_NAME,
            messages=messages,
            temperature=0.7
        )
        return response_text

    async def summarize_text(self, text_to_summarize: str) -> Optional[str]:
        summarize_prompt_template = self._load_prompt("summarize.txt")
        if not summarize_prompt_template:
            return None

        messages = [
            {"role": "system", "content": summarize_prompt_template},
            {"role": "user", "content": text_to_summarize}
        ]

        summary = await self._make_llm_call(
            model_name=config.ANSWER_MODEL_NAME,
            messages=messages,
            temperature=0.3
        )
        return summary

    async def is_text_appropriate(self, text_to_check: str) -> bool:
        filter_prompt_template = self._load_prompt("filter.txt")
        if not filter_prompt_template:
            return False

        messages = [
            {"role": "system", "content": filter_prompt_template},
            {"role": "user", "content": text_to_check}
        ]

        response_text = await self._make_llm_call(
            model_name=config.ANSWER_MODEL_NAME,
            messages=messages,
            temperature=0.0
        )

        if response_text == "1":
            return True
        elif response_text == "0":
            return False
        else:
            logger.warning(f"LLM filter returned unexpected value: '{response_text}'. Defaulting to inappropriate.")
            return False

    async def generate_active_support_message(self, chat_context: Optional[str] = None, is_ignored_previously: bool = False) -> Optional[str]:
        if is_ignored_previously:
            prompt_template = self._load_prompt("stay_active_no_context.txt")
            messages = [{"role": "user", "content": prompt_template}]
        else:
            prompt_template = self._load_prompt("stay_active.txt")
            if not prompt_template or not chat_context:
                logger.warning("Stay active prompt or context missing for contextual active support.")
                prompt_template = self._load_prompt("stay_active_no_context.txt")
                messages = [{"role": "user", "content": prompt_template}]
            else:
                messages = [
                    {"role": "system", "content": prompt_template},
                    {"role": "user", "content": chat_context}
                ]
        
        if not prompt_template:
            return None

        response_text = await self._make_llm_call(
            model_name=config.ANSWER_MODEL_NAME,
            messages=messages,
            temperature=0.8
        )
        return response_text

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    async def run_tests():
        print("LLMService Test Block")
        print("---------------------")

        if not config.PROMPTS_DIR_PATH.exists() or not any(config.PROMPTS_DIR_PATH.iterdir()):
            print(f"CRITICAL: Prompts directory {config.PROMPTS_DIR_PATH} is missing or empty. Cannot run tests.")
            return
            
        service = LLMService()
        if not service.client:
            print("LLM client initialization failed. Exiting tests.")
            return

        print("\n1. Testing prompt loading ('non-found.txt')...")
        non_found_prompt = service._load_prompt("non-found.txt")
        if non_found_prompt:
            print(f"   'non-found.txt' loaded successfully (first few chars): {non_found_prompt[:100]}...")
        else:
            print("   Failed to load 'non-found.txt'.")

        print("\n2. Testing FAQ matching...")
        faqs_text = "1. What is your name?\n2. How old are you?\n3. Where do you live?"
        match_index = await service.find_faq_match_index("Tell me your name", faqs_text)
        print(f"   Match index for 'Tell me your name': {match_index} (Expected ~1 or 0)")
        match_index_no_match = await service.find_faq_match_index("What is the weather?", faqs_text)
        print(f"   Match index for 'What is the weather?': {match_index_no_match} (Expected 0)")

        print("\n3. Testing chat response generation...")
        if non_found_prompt:
            chat_resp = await service.generate_chat_response(
                personality_prompt_text=non_found_prompt,
                user_message="Hello there!",
                user_name="Tester"
            )
            print(f"   Chat response to 'Hello there!': {chat_resp}")
        else:
            print("   Skipping chat response test as 'non-found.txt' could not be loaded.")

        print("\n4. Testing summarization...")
        text_to_sum = "The quick brown fox jumps over the lazy dog. This is a classic sentence used for testing typewriters and fonts. It contains all letters of the English alphabet. The dog, however, was not amused by this aerial display of agility from the fox."
        summary = await service.summarize_text(text_to_sum)
        print(f"   Summary: {summary}")

        print("\n5. Testing content appropriateness...")
        appropriate_text = "Can you tell me about the curriculum?"
        is_app_1 = await service.is_text_appropriate(appropriate_text)
        print(f"   '{appropriate_text}' is appropriate: {is_app_1} (Expected True)")
        
        inappropriate_text = "This is some really nasty stuff I shouldn't say."
        is_app_2 = await service.is_text_appropriate(inappropriate_text)
        print(f"   '{inappropriate_text}' is appropriate: {is_app_2} (Expected False)")

        print("\n6. Testing active support message (no context)...")
        active_msg_no_ctx = await service.generate_active_support_message(is_ignored_previously=True)
        print(f"   Active support (ignored, no context): {active_msg_no_ctx}")
        
        print("\n7. Testing active support message (with context)...")
        sample_chat_ctx = "UserA: Anyone here?\nUserB: Not much happening today."
        active_msg_ctx = await service.generate_active_support_message(chat_context=sample_chat_ctx)
        print(f"   Active support (with context): {active_msg_ctx}")

        print("\n--- LLMService Tests Complete ---")

    import asyncio
    asyncio.run(run_tests())
