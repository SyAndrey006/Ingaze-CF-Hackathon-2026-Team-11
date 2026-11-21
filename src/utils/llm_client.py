"""Provider-agnostic, deterministic structured LLM client."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal, Optional, Type, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

TModel = TypeVar("TModel", bound=BaseModel)
Provider = Literal["openai", "openrouter", "gemini"]


class LLMConfig(BaseModel):
    """Configuration for deterministic structured LLM invocations."""

    provider: Provider = Field(default="openai")
    model: str = Field(default="gpt-4o-mini")
    # Retained for compatibility with existing callers. Requests always use 0.0.
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    max_retries: int = Field(default=2, ge=0, le=5)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    api_key_env_var: Optional[str] = Field(default=None)


class StructuredLLMClient:
    """OpenAI-compatible structured-output client with Pydantic validation."""

    _KEY_ENV_VARS = (
        "LLM_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "GEMINI_API_KEY",
    )
    _DEFAULT_BASE_URLS = {
        "openrouter": "https://openrouter.ai/api/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    }
    _DEFAULT_MODELS = {
        "openai": "gpt-4o-mini",
        "openrouter": "openai/gpt-4o-mini",
        "gemini": "gemini-2.5-flash",
    }

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or LLMConfig()

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[TModel],
    ) -> TModel:
        """Call an LLM at temperature zero and validate its response as ``response_model``.

        The client first asks the SDK for a Pydantic-parsed response. Providers or
        models that do not support that feature fall back to JSON mode and local
        Pydantic validation.
        """
        api_key, provider, configured_base_url, configured_model = self._resolve_credentials()

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency is installed in the app
            raise RuntimeError(
                "The structured LLM client requires the 'openai' Python package. "
                "Install it with `pip install openai`."
            ) from exc

        base_url = configured_base_url or self._DEFAULT_BASE_URLS.get(provider)
        client_kwargs = {
            "api_key": api_key,
            "timeout": self.config.timeout_seconds,
        }
        if base_url:
            client_kwargs["base_url"] = base_url
        client = OpenAI(**client_kwargs)

        structured_error: Optional[Exception] = None
        try:
            parsed = self._request_pydantic(
                client,
                configured_model,
                system_prompt,
                user_prompt,
                response_model,
            )
            if parsed is not None:
                return parsed
        except Exception as exc:
            # Unsupported schema/response_format is common on compatible APIs.
            # The JSON-mode request below is the clean compatibility path.
            status_code = getattr(exc, "status_code", None)
            if status_code not in (400, 404, 422) and not isinstance(
                exc, (TypeError, AttributeError, NotImplementedError)
            ):
                raise RuntimeError(f"Structured LLM request failed: {exc}") from exc
            structured_error = exc

        schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        json_system_prompt = (
            f"{system_prompt}\n\n"
            "Return exactly one JSON object and no markdown. The object must conform "
            f"to this JSON Schema:\n{schema}"
        )
        last_error: Optional[Exception] = structured_error
        retry_prompt = user_prompt

        for attempt in range(self.config.max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=configured_model,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": json_system_prompt},
                        {"role": "user", "content": retry_prompt},
                    ],
                )
                content = self._message_content(response)
                return response_model.model_validate_json(content)
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    break
                retry_prompt = (
                    f"{user_prompt}\n\nThe previous response did not validate. "
                    "Return a corrected JSON object matching the provided schema."
                )
            except Exception as exc:
                last_error = exc
                status_code = getattr(exc, "status_code", None)
                if status_code not in (400, 404, 422) or attempt >= self.config.max_retries:
                    break

        raise RuntimeError(
            f"Could not obtain valid structured output for {response_model.__name__}. "
            f"The structured-output attempt failed with {structured_error!r}; "
            f"JSON-mode validation failed with {last_error!r}."
        ) from last_error

    def _resolve_credentials(self) -> tuple[str, Provider, Optional[str], str]:
        """Load .env values and resolve credentials/provider/model settings."""
        project_root = Path(__file__).resolve().parents[2]
        load_dotenv(project_root / ".env", override=False)

        base_url = os.environ.get("LLM_BASE_URL") or None
        model_from_env = os.environ.get("LLM_MODEL")
        configured_model = model_from_env or self.config.model

        if self.config.api_key_env_var:
            key_name = self.config.api_key_env_var
            api_key = os.environ.get(key_name)
            provider = self.config.provider
        elif os.environ.get("LLM_API_KEY"):
            key_name = "LLM_API_KEY"
            api_key = os.environ[key_name]
            provider = self._provider_for_base_url(base_url) or self.config.provider
        else:
            preferred_key = {
                "openai": "OPENAI_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
                "gemini": "GEMINI_API_KEY",
            }[self.config.provider]
            key_name = preferred_key
            api_key = os.environ.get(preferred_key)
            provider = self.config.provider
            if not api_key:
                for candidate, candidate_provider in (
                    ("OPENAI_API_KEY", "openai"),
                    ("OPENROUTER_API_KEY", "openrouter"),
                    ("GEMINI_API_KEY", "gemini"),
                ):
                    if os.environ.get(candidate):
                        key_name = candidate
                        api_key = os.environ[candidate]
                        provider = candidate_provider
                        break

        if not api_key:
            raise RuntimeError(
                "No LLM API key is configured. Add one of these to the project .env "
                "file or your environment: LLM_API_KEY, OPENAI_API_KEY, "
                "OPENROUTER_API_KEY, or GEMINI_API_KEY. Optionally set LLM_BASE_URL "
                "and LLM_MODEL for an OpenAI-compatible endpoint."
            )

        provider = self._provider_for_base_url(base_url) or provider
        if model_from_env:
            configured_model = model_from_env
        elif self.config.model == LLMConfig.model_fields["model"].default:
            configured_model = self._DEFAULT_MODELS[provider]
        return api_key, provider, base_url, configured_model

    @staticmethod
    def _provider_for_base_url(base_url: Optional[str]) -> Optional[Provider]:
        if not base_url:
            return None
        lowered = base_url.lower()
        if "openrouter" in lowered:
            return "openrouter"
        if "generativelanguage.googleapis.com" in lowered or "gemini" in lowered:
            return "gemini"
        return "openai"

    @staticmethod
    def _request_pydantic(
        client: object,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[TModel],
    ) -> Optional[TModel]:
        """Use SDK-native Pydantic parsing when the configured endpoint supports it."""
        beta = getattr(client, "beta", None)
        chat = getattr(beta, "chat", None)
        completions = getattr(chat, "completions", None)
        parse = getattr(completions, "parse", None)
        if parse is None:
            return None

        response = parse(
            model=model,
            temperature=0.0,
            response_format=response_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise RuntimeError(f"The LLM refused the structured request: {message.refusal}")
        parsed = getattr(message, "parsed", None)
        if isinstance(parsed, response_model):
            return parsed
        if parsed is not None:
            return response_model.model_validate(parsed)
        content = StructuredLLMClient._message_content(response)
        return response_model.model_validate_json(content)

    @staticmethod
    def _message_content(response: object) -> str:
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise ValueError("The LLM response did not contain a message body.") from exc
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [
                part.get("text", "") if isinstance(part, dict) else getattr(part, "text", "")
                for part in content
            ]
            joined = "".join(text_parts)
            if joined:
                return joined
        raise ValueError("The LLM response body was empty or was not text.")
