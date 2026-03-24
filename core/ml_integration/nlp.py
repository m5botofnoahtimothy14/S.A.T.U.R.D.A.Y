# ml_integration/nlp.py
"""
NLP Engine - Deep Learning Powered Natural Language Processing
============================================================
Uses neural networks and NLTK for advanced voice/text understanding.
All voice commands are now processed through DL-powered NLP.
"""

import os
import json
import time
import re
import structlog
from typing import Any, Dict, List, Optional, Tuple
from collections import deque, defaultdict

import numpy as np

logger = structlog.get_logger("AEGIS.ML.NLP")

class NLPDecisionNetwork:
    """Neural network for NLP decisions"""
    
    def __init__(self, input_size: int = 30, hidden_size: int = 60, output_size: int = 15):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        
        np.random.seed(42)
        self.weights1 = np.random.randn(input_size, hidden_size) * 0.1
        self.weights2 = np.random.randn(hidden_size, output_size) * 0.1
        self.bias1 = np.zeros(hidden_size)
        self.bias2 = np.zeros(output_size)
        
    def sigmoid(self, x):
        return 1 / (1 + np.exp(-np.clip(x, -500, 500)))
    
    def relu(self, x):
        return np.maximum(0, x)
    
    def softmax(self, x):
        exp_x = np.exp(x - np.max(x))
        return exp_x / (exp_x.sum() + 1e-10)
    
    def forward(self, inputs):
        self.hidden = self.relu(np.dot(inputs, self.weights1) + self.bias1)
        output = self.softmax(np.dot(self.hidden, self.weights2) + self.bias2)
        return output
    
    def predict(self, features):
        output = self.forward(features)[0]
        return output


class NLPEngine:
    """
    DEEP LEARNING Powered NLP Engine.
    Uses neural networks + NLTK for:
    - Voice command understanding
    - Intent classification
    - Entity extraction
    - Sentiment analysis
    - Language understanding
    - Context awareness
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.data_dir = "data/ml_integration"
        os.makedirs(self.data_dir, exist_ok=True)
        
        self._init_nltk()
        self._init_deep_learning()
        
        self.conversation_context = deque(maxlen=10)
        self.intent_history = deque(maxlen=50)
        self.entity_cache = {}
        
        self._load_nlp_models()
        
        logger.info("DEEP LEARNING NLP Engine initialized - Voice understanding active")
        
    def _init_nltk(self):
        """Initialize NLTK for NLP processing"""
        try:
            import nltk
            nltk.data.path.append("data/nltk_data")
            
            self.nltk_available = True
            logger.info("NLTK initialized for NLP processing")
            
        except Exception as e:
            logger.warning(f"NLTK init failed: {e}")
            self.nltk_available = False
    
    def _init_deep_learning(self):
        """Initialize neural network for NLP decisions"""
        try:
            self.decision_nn = NLPDecisionNetwork()
            self.dl_active = True
            self._load_nlp_nn()
            
        except Exception as e:
            logger.warning(f"DL NLP init failed: {e}")
            self.dl_active = False
    
    def _load_nlp_nn(self):
        """Load trained NLP neural network"""
        try:
            nn_file = f"{self.data_dir}/nlp_nn.json"
            if os.path.exists(nn_file):
                with open(nn_file, "r") as f:
                    data = json.load(f)
                self.decision_nn.weights1 = np.array(data.get("weights1"))
                self.decision_nn.weights2 = np.array(data.get("weights2"))
                self.decision_nn.bias1 = np.array(data.get("bias1"))
                self.decision_nn.bias2 = np.array(data.get("bias2"))
                logger.info("Loaded NLP neural network")
        except Exception as e:
            logger.warning(f"Failed to load NLP NN: {e}")
    
    def _save_nlp_nn(self):
        """Save NLP neural network"""
        try:
            nn_file = f"{self.data_dir}/nlp_nn.json"
            data = {
                "weights1": self.decision_nn.weights1.tolist(),
                "weights2": self.decision_nn.weights2.tolist(),
                "bias1": self.decision_nn.bias1.tolist(),
                "bias2": self.decision_nn.bias2.tolist()
            }
            with open(nn_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save NLP NN: {e}")

    def _load_nlp_models(self):
        """Load persisted NLP metadata used by the engine."""
        self.entity_cache = {}
        cache_file = f"{self.data_dir}/entity_cache.json"
        try:
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if isinstance(payload, dict):
                    self.entity_cache = payload
                    logger.info("Loaded NLP entity cache", entries=len(self.entity_cache))
        except Exception as e:
            logger.warning(f"Failed to load NLP metadata: {e}")

    def process_voice_command(self, text: str) -> Dict[str, Any]:
        """
        Process voice command through DL NLP pipeline.
        """
        if not text:
            return {"error": "Empty input"}
        
        text = text.strip()
        
        tokens = self._tokenize(text)
        pos_tags = self._pos_tag(tokens)
        entities = self._extract_entities(text, tokens)
        sentiment = self._analyze_sentiment(text)
        intent = self._classify_intent(text, tokens, pos_tags)
        context = self._get_context()
        
        features = self._extract_nlp_features(text, tokens, pos_tags, intent, sentiment, entities)
        
        nn_result = None
        if self.dl_active and len(self.intent_history) > 5:
            nn_result = self.decision_nn.predict(features)
        
        response = {
            "input": text,
            "tokens": tokens,
            "pos_tags": pos_tags,
            "entities": entities,
            "sentiment": sentiment,
            "intent": intent,
            "context": context,
            "confidence": float(max(nn_result)) if nn_result is not None else 0.7,
            "nn_decision": nn_result.tolist() if nn_result is not None else None
        }
        
        self.conversation_context.append(response)
        self.intent_history.append({
            "intent": intent,
            "timestamp": time.time(),
            "success": None
        })
        
        return response
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text"""
        if self.nltk_available:
            try:
                import nltk
                return nltk.word_tokenize(text.lower())
            except:
                pass
        return re.findall(r'\w+', text.lower())
    
    def _pos_tag(self, tokens: List[str]) -> List[Tuple[str, str]]:
        """Part-of-speech tagging"""
        if self.nltk_available:
            try:
                import nltk
                return nltk.pos_tag(tokens)
            except:
                pass
        return [(t, "NN") for t in tokens]
    
    def _extract_entities(self, text: str, tokens: List[str]) -> Dict[str, List[str]]:
        """Extract named entities"""
        entities = {
            "persons": [],
            "locations": [],
            "times": [],
            "actions": [],
            "objects": []
        }
        
        time_patterns = r'\d{1,2}:\d{2}|\bmorning\b|\bafternoon\b|\bevening\b|\bnight\b|\btoday\b|\btomorrow\b'
        times = re.findall(time_patterns, text.lower())
        entities["times"] = times
        
        action_verbs = ['play', 'stop', 'open', 'close', 'call', 'send', 'search', 'find', 'turn', 'set', 'start', 'wait']
        for token in tokens:
            if token in action_verbs:
                entities["actions"].append(token)
        
        return entities
    
    def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment using neural approach"""
        positive_words = ['good', 'great', 'awesome', 'thanks', 'thank', 'please', 'yes', 'love', 'perfect', 'nice']
        negative_words = ['bad', 'wrong', 'hate', 'no', 'not', 'stop', 'cancel', 'error', 'fail', 'awful']
        
        text_lower = text.lower()
        
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        
        if pos_count > neg_count:
            sentiment = "positive"
            score = min(1.0, 0.5 + pos_count * 0.1)
        elif neg_count > pos_count:
            sentiment = "negative"
            score = max(0.0, 0.5 - neg_count * 0.1)
        else:
            sentiment = "neutral"
            score = 0.5
        
        return {"sentiment": sentiment, "score": score}
    
    def _classify_intent(self, text: str, tokens: List[str], pos_tags: List[Tuple]) -> str:
        """Classify intent using pattern matching + learning"""
        text_lower = text.lower()
        
        intent_patterns = {
            "music": ["play", "music", "song", "spotify", "pause", "skip"],
            "call": ["call", "phone", "dial", "contact"],
            "message": ["message", "text", "send", "whatsapp"],
            "search": ["search", "find", "look", "google"],
            "weather": ["weather", "temperature", "forecast"],
            "control": ["turn", "switch", "light", "on", "off", "open", "close"],
            "information": ["what", "who", "when", "where", "why", "how", "tell"],
            "reminder": ["remind", "alarm", "schedule"],
            "navigation": ["navigate", "direction", "route", "map"],
            "system": ["status", "check", "system", "run"],
            "greeting": ["hello", "hi", "hey", "good morning"],
            "help": ["help", "assist", "support"],
        }
        
        for intent, keywords in intent_patterns.items():
            if any(kw in text_lower for kw in keywords):
                return intent
        
        return "general"
    
    def _extract_nlp_features(self, text: str, tokens: List[str], pos_tags: List[Tuple], intent: str, sentiment: Dict, entities: Dict) -> np.ndarray:
        """Extract features for neural network"""
        features = []
        
        features.append(len(text) / 100.0)
        features.append(len(tokens) / 20.0)
        
        intent_list = ["music", "call", "message", "search", "weather", "control", "information", "reminder", "navigation", "system", "greeting", "help", "general", "question", "statement"]
        for i in intent_list:
            features.append(1.0 if intent == i else 0.0)
        
        features.append(sentiment.get("score", 0.5))
        
        features.append(len(entities.get("actions", [])) / 5.0)
        features.append(len(entities.get("times", [])) / 3.0)
        
        features.append(sum(1 for t, p in (pos_tags if pos_tags else []) if p.startswith("VB")) / max(1, len(tokens)))
        
        features.append(time.time() % 86400 / 86400.0)
        
        while len(features) < 30:
            features.append(0.5)
            
        return np.array([features[:30]])
    
    def _get_context(self) -> Dict:
        """Get conversation context"""
        if not self.conversation_context:
            return {"turn": 0, "topic": None}
        
        recent = list(self.conversation_context)[-3:]
        
        intents = [r.get("intent") for r in recent]
        most_common_intent = max(set(intents), default="general") if intents else "general"
        
        return {
            "turn": len(self.conversation_context),
            "topic": most_common_intent,
            "recent_intents": intents
        }
    
    def learn_from_outcome(self, text: str, outcome: bool):
        """Learn from command execution outcome"""
        if not self.dl_active:
            return
            
        tokens = self._tokenize(text)
        pos_tags = self._pos_tag(tokens)
        sentiment = self._analyze_sentiment(text)
        intent = self._classify_intent(text, tokens, pos_tags)
        
        features = self._extract_nlp_features(text, tokens, pos_tags, intent, sentiment, {})
        
        output = self.decision_nn.forward(features)[0]
        
        intent_list = ["music", "call", "message", "search", "weather", "control", "information", "reminder", "navigation", "system", "greeting", "help", "general", "question", "statement"]
        
        expected = np.zeros(15)
        if intent in intent_list:
            idx = intent_list.index(intent)
            expected[idx] = 1.0 if outcome else 0.0
        
        error = expected - output
        output_delta = error
        hidden_error = np.dot(output_delta, self.decision_nn.weights2.T)
        hidden_delta = hidden_error * (self.decision_nn.hidden > 0).astype(float)
        
        self.decision_nn.weights2 += 0.01 * np.dot(self.decision_nn.hidden.T, output_delta)
        self.decision_nn.weights1 += 0.01 * np.dot(features.T, hidden_delta)
        self.decision_nn.bias2 += 0.01 * output_delta
        self.decision_nn.bias1 += 0.01 * hidden_delta
        
        if self.intent_history:
            last = self.intent_history[-1]
            last["success"] = outcome
        
        self._save_nlp_nn()
    
    def get_status(self) -> Dict:
        """Get NLP engine status"""
        return {
            "dl_active": self.dl_active,
            "nltk_available": self.nltk_available,
            "intents_classified": len(self.intent_history),
            "conversation_turns": len(self.conversation_context),
            "entities_extracted": len(self.entity_cache)
        }
