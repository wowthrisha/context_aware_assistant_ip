"""
ML-based Intent Detection using HuggingFace Zero-Shot Classification

Replaces regex patterns with intelligent intent understanding
Uses hybrid approach: ML for complex cases, lightweight regex for obvious patterns
"""
from transformers import pipeline
import warnings
import re
warnings.filterwarnings("ignore")  # Suppress model loading warnings


class IntentDetector:
    def __init__(self):
        # Initialize zero-shot classification pipeline
        self.classifier = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=-1  # Use CPU, change to 0 for GPU if available
        )
        
        # Define all possible intents with descriptive labels for better ML understanding
        self.intents = [
            "setting a reminder or alarm for a specific time",
            "canceling or deleting an existing reminder", 
            "listing or viewing current reminders",
            "expressing a positive preference or something the user likes",
            "expressing a negative preference or something the user dislikes",
            "describing a daily routine or habit",
            "asking about personal information or memories",
            "configuring WhatsApp notifications",
            "configuring email notifications", 
            "disabling or stopping notifications",
            "checking notification settings",
            "general conversation or casual chat"
        ]
        
        # Map the descriptive labels back to original intent names
        self.intent_mapping = {
            "setting a reminder or alarm for a specific time": "set_reminder",
            "canceling or deleting an existing reminder": "cancel_reminder",
            "listing or viewing current reminders": "list_reminders", 
            "expressing a positive preference or something the user likes": "save_preference_positive",
            "expressing a negative preference or something the user dislikes": "save_preference_negative",
            "describing a daily routine or habit": "save_habit",
            "asking about personal information or memories": "recall_memory",
            "configuring WhatsApp notifications": "set_whatsapp_notification",
            "configuring email notifications": "set_email_notification",
            "disabling or stopping notifications": "disable_notification", 
            "checking notification settings": "get_notification_prefs",
            "general conversation or casual chat": "general_chat"
        }
        
        # Cache for frequently seen inputs to improve performance
        self.cache = {}
        
        # Quick regex patterns for obvious cases (bypass ML for speed and accuracy)
        self.quick_patterns = {
            "set_reminder": [
                r"\bremind me\b",
                r"\bset reminder\b",
                r"\balarm\b",
                r"\bschedule\b"
            ],
            "cancel_reminder": [
                r"\bcancel.*reminder\b",
                r"\bdelete.*reminder\b",
                r"\bremove.*reminder\b"
            ],
            "list_reminders": [
                r"\b(list|show|view).*reminders?\b",
                r"\bwhat are my reminders\b"
            ]
        }

    def _quick_regex_check(self, text: str) -> str:
        """Quick regex check for obvious patterns"""
        text_lower = text.lower()
        for intent, patterns in self.quick_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return intent
        return None

    def detect_intent(self, text: str) -> str:
        """
        Detect intent using hybrid approach: quick regex + ML zero-shot classification
        
        Args:
            text: User input text
            
        Returns:
            Detected intent as string
        """
        # Clean and normalize input
        clean_text = text.strip().lower()
        
        # Check cache first for performance
        if clean_text in self.cache:
            return self.cache[clean_text]
        
        # Quick regex check for obvious patterns
        quick_result = self._quick_regex_check(text)
        if quick_result:
            self.cache[clean_text] = quick_result
            print(f"[Regex Intent] '{text}' -> {quick_result}")
            return quick_result
        
        # Use ML for more complex cases
        try:
            result = self.classifier(
                clean_text,
                self.intents,
                multi_label=False
            )
            
            # Get the top prediction
            predicted_label = result['labels'][0]
            confidence = result['scores'][0]
            
            # Map the descriptive label back to intent name
            predicted_intent = self.intent_mapping[predicted_label]
            
            # Lower confidence threshold for better detection
            if confidence < 0.2:
                predicted_intent = "general_chat"
            
            # Cache the result
            self.cache[clean_text] = predicted_intent
            
            print(f"[ML Intent] '{text}' -> {predicted_intent} (confidence: {confidence:.2f})")
            return predicted_intent
            
        except Exception as e:
            # Fallback to general_chat if ML fails
            print(f"Intent detection error: {e}")
            return "general_chat"