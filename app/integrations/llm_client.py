from typing import Protocol, runtime_checkable

import httpx


@runtime_checkable
class BaseLLMClient(Protocol):
    """Contrato abstrato para qualquer provedor de IA."""

    async def generate(self, system_prompt: str, user_prompt: str) -> str: ...


class OpenAILLMClient:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout: float = 30.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions", headers=headers, json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()


class OllamaLLMClient:
    """Cliente local gratuito e 100% offline."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2:3b",
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 120,  # limita a resposta a ~3 frases executivas
            },
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json()["response"].strip()


class MockLLMClient:
    """Cliente para testes unitários rápidos e determinísticos."""

    def __init__(self, fixed_response: str | None = None):
        self.fixed_response = fixed_response or (
            "Seu patrimônio cresceu 8,2% nos últimos 90 dias.\n"
            "Existe concentração de 63% na Rico.\n"
            "A exposição a renda variável está abaixo de 15%."
        )
        self.last_system_prompt: str | None = None
        self.last_user_prompt: str | None = None

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return self.fixed_response
