"""
Language detection utility for automatically detecting programming languages in projects
"""

from pathlib import Path
from typing import Optional, Callable
from collections import Counter

from config.settings import LANGUAGE_EXTENSIONS
from config.commands import LANGUAGE_ALIASES


class LanguageDetector:
    """Utility class for detecting programming languages in project directories"""

    def __init__(self):
        self.language_extensions = LANGUAGE_EXTENSIONS
        self.language_aliases = LANGUAGE_ALIASES

    def detect_language(
        self,
        project_path: Path,
        output_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Detect the programming language based on file extensions in the project directory

        Args:
            project_path: Path to the project directory
            output_callback: Optional callback for detailed output messages

        Returns:
            Detected language name (e.g., 'python', 'javascript', etc.)
        """
        language_counts = Counter()

        # Count files for each language
        for language, extensions in self.language_extensions.items():
            count = sum(len(list(project_path.rglob(f"*{ext}"))) for ext in extensions)
            language_counts[language] = count

            if output_callback and count > 0:
                output_callback(f"   📁 Found {count} {language} files\n")

        # Find the language with the most files
        if language_counts:
            detected_language = language_counts.most_common(1)[0][0]
            total_files = language_counts[detected_language]

            if output_callback:
                output_callback(
                    f"   🎯 Language with most files: {detected_language} ({total_files} files)\n"
                )

            return detected_language
        else:
            if output_callback:
                output_callback(
                    "   ⚠️  No recognized files found, defaulting to python\n"
                )

            return "python"

    def detect_language_sync(self, project_path: Path) -> str:
        """
        Synchronous version of detect_language without output callback

        Args:
            project_path: Path to the project directory

        Returns:
            Detected language name
        """
        return self.detect_language(project_path)

    def normalize_language_name(self, language: str) -> str:
        """
        Normalize language name using aliases

        Args:
            language: Language name (potentially an alias)

        Returns:
            Normalized language name
        """
        return self.language_aliases.get(language.lower(), language.lower())

    def is_supported_language(self, language: str) -> bool:
        """
        Check if a language is supported

        Args:
            language: Language name to check

        Returns:
            True if the language is supported, False otherwise
        """
        normalized = self.normalize_language_name(language)
        return normalized in self.language_extensions

    def get_supported_languages(self) -> list:
        """
        Get a list of all supported languages

        Returns:
            List of supported language names
        """
        return list(self.language_extensions.keys())

    def get_language_extensions(self, language: str) -> list:
        """
        Get file extensions for a specific language

        Args:
            language: Language name

        Returns:
            List of file extensions for the language
        """
        normalized = self.normalize_language_name(language)
        return self.language_extensions.get(normalized, [])


# Global instance for easy access
language_detector = LanguageDetector()


def detect_project_language(
    project_path: Path, output_callback: Optional[Callable[[str], None]] = None
) -> str:
    """
    Convenience function to detect project language

    Args:
        project_path: Path to the project directory
        output_callback: Optional callback for detailed output messages

    Returns:
        Detected language name
    """
    return language_detector.detect_language(project_path, output_callback)


def detect_project_language_sync(project_path: Path) -> str:
    """
    Convenience function to detect project language synchronously

    Args:
        project_path: Path to the project directory

    Returns:
        Detected language name
    """
    return language_detector.detect_language_sync(project_path)
