"""
Prompt management utility for PMO MCP Server.

This module handles loading and accessing prompts from YAML configuration files.
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from config.settings import get_settings
from core.exceptions import PromptError


logger = logging.getLogger(__name__)


class PromptManager:
    """
    Manages prompts loading and access from YAML configuration.
    """

    def __init__(self):
        """Initialize prompt manager with settings."""
        self.settings = get_settings()
        self._cache: Dict[str, Any] = {}
        self._cache_enabled = True
        self._prompts_data: Optional[Dict[str, Any]] = None

    def _load_prompts_file(self) -> Dict[str, Any]:
        """
        Load prompts from YAML file.

        Returns:
            Prompts dictionary

        Raises:
            PromptError: If unable to load prompts
        """
        if self._prompts_data is not None and self._cache_enabled:
            return self._prompts_data

        prompts_file = self.settings.get_prompts_file()

        if not prompts_file.exists():
            error_msg = f"Prompts configuration file not found at {prompts_file}"
            logger.error(error_msg)
            raise PromptError("prompts.yaml", error_msg)

        try:
            with open(prompts_file, 'r', encoding='utf-8') as f:
                self._prompts_data = yaml.safe_load(f) or {}

            logger.info("Successfully loaded prompts configuration")
            return self._prompts_data

        except yaml.YAMLError as e:
            error_msg = f"Invalid YAML in prompts file: {str(e)}"
            logger.error(error_msg)
            raise PromptError("prompts.yaml", error_msg)

        except Exception as e:
            error_msg = f"Error loading prompts: {str(e)}"
            logger.error(error_msg)
            raise PromptError("prompts.yaml", error_msg)

    def get_tool_selection_guide(self) -> str:
        """
        Get the tool selection guide prompt.

        Returns:
            Tool selection guide text
        """
        try:
            prompts_data = self._load_prompts_file()
            guide_data = prompts_data.get("tool_selection_guide", {})
            return guide_data.get("content", "")
        except PromptError as e:
            logger.error(f"Error loading tool selection guide: {e}")
            return "Tool selection guide not available"

    def get_prompt(self, prompt_name: str) -> str:
        """
        Get a specific prompt by name.

        Args:
            prompt_name: Name of the prompt

        Returns:
            Prompt content text

        Raises:
            PromptError: If prompt not found
        """
        try:
            prompts_data = self._load_prompts_file()
            prompts_section = prompts_data.get("prompts", {})

            if prompt_name not in prompts_section:
                raise PromptError(prompt_name, f"Prompt '{prompt_name}' not found")

            prompt_data = prompts_section[prompt_name]
            return prompt_data.get("content", "")

        except KeyError:
            raise PromptError(prompt_name, f"Prompt '{prompt_name}' not found")

    def get_prompt_with_metadata(self, prompt_name: str) -> Dict[str, str]:
        """
        Get prompt with its metadata (title, description, content).

        Args:
            prompt_name: Name of the prompt

        Returns:
            Dictionary with prompt metadata

        Raises:
            PromptError: If prompt not found
        """
        try:
            prompts_data = self._load_prompts_file()
            prompts_section = prompts_data.get("prompts", {})

            if prompt_name not in prompts_section:
                raise PromptError(prompt_name, f"Prompt '{prompt_name}' not found")

            return prompts_section[prompt_name]

        except KeyError:
            raise PromptError(prompt_name, f"Prompt '{prompt_name}' not found")

    def get_all_prompts(self) -> Dict[str, Dict[str, str]]:
        """
        Get all available prompts.

        Returns:
            Dictionary of all prompts with their metadata
        """
        try:
            prompts_data = self._load_prompts_file()
            return prompts_data.get("prompts", {})
        except PromptError:
            return {}

    def get_error_message(self, error_key: str, **kwargs) -> str:
        """
        Get error message template and format it with provided values.

        Args:
            error_key: Key for the error message
            **kwargs: Values to format into the message

        Returns:
            Formatted error message
        """
        try:
            prompts_data = self._load_prompts_file()
            error_messages = prompts_data.get("error_messages", {})

            if error_key not in error_messages:
                return f"Error: {error_key}"

            message_template = error_messages[error_key]
            return message_template.format(**kwargs)

        except (PromptError, KeyError):
            return f"Error: {error_key}"

    def get_success_message(self, success_key: str, **kwargs) -> str:
        """
        Get success message template and format it with provided values.

        Args:
            success_key: Key for the success message
            **kwargs: Values to format into the message

        Returns:
            Formatted success message
        """
        try:
            prompts_data = self._load_prompts_file()
            success_messages = prompts_data.get("success_messages", {})

            if success_key not in success_messages:
                return f"Success: {success_key}"

            message_template = success_messages[success_key]
            return message_template.format(**kwargs)

        except (PromptError, KeyError):
            return f"Success: {success_key}"

    def get_help_text(self, help_key: str) -> str:
        """
        Get help text by key.

        Args:
            help_key: Key for the help text

        Returns:
            Help text
        """
        try:
            prompts_data = self._load_prompts_file()
            help_text = prompts_data.get("help_text", {})
            return help_text.get(help_key, "")
        except PromptError:
            return ""

    def reload_prompts(self):
        """Reload prompts from file."""
        self._prompts_data = None
        self._cache.clear()
        self._load_prompts_file()
        logger.info("Reloaded prompts configuration")

    def list_available_prompts(self) -> list:
        """
        Get list of all available prompt names.

        Returns:
            List of prompt names
        """
        try:
            prompts_data = self._load_prompts_file()
            prompts_section = prompts_data.get("prompts", {})
            return list(prompts_section.keys())
        except PromptError:
            return []


# Global prompt manager instance
_prompt_manager = None


def get_prompt_manager() -> PromptManager:
    """
    Get the global prompt manager instance.

    Returns:
        PromptManager instance
    """
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
