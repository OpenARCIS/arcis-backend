import json

from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Optional, Type

from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type
)

from arcis.models.llm import BaseLLMClient
from arcis.models.errors import LLMFailure


class GeminiClient(BaseLLMClient):
    def __init__(self, model_name: str, api_key: str,\
        response_schema: Optional[Type[BaseModel]] = None, mime_type: Optional[str] = None, temperature: float = 0.7):
        super().__init__(model_name, temperature)

        self.client = genai.Client(api_key=api_key)
        self.response_schema= response_schema
        self.mime_type = mime_type

    @retry(
        wait=wait_random_exponential(min=5, max=60), 
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception)
    )
    async def _generate_with_retry(self, config, prompt: str):
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            
            # safety filter returns None if triggered
            if response.text:
                if self.response_schema:
                    decision_data = json.loads(response.text)
                    decision = self.response_schema(**decision_data)
                    return decision
                return response.text.strip()
            else:
                raise Exception

        except Exception:
            raise LLMFailure

    async def generate(self, system_role: str, user_query: str): #TODO update the abstract class after verifying response schema
        config = types.GenerateContentConfig(
            temperature=self.temperature,
            candidate_count=1,
            response_schema=self.response_schema,
            response_mime_type=self.mime_type,
        )
        return await self._generate_with_retry(config, user_query)