"""Realmweave quests: cross-domain opportunities agents may take or ignore."""
from .quest import Quest, QUEST_TEMPLATES
from .board import QuestBoard, INTEREST_THRESHOLD

__all__ = ["Quest", "QUEST_TEMPLATES", "QuestBoard", "INTEREST_THRESHOLD"]
